from __future__ import annotations

import argparse
import json
import mimetypes
import threading
from dataclasses import asdict, dataclass, field, is_dataclass, replace
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from time import time
from typing import Callable, Literal
from urllib import parse
from uuid import uuid4

from sqlalchemy import select

from .auth import (
    SESSION_COOKIE,
    AuthStore,
    WeChatComponentConfig,
    WeChatComponentProvider,
    WeChatLoginConfig,
    WeChatOAuthProvider,
    parse_wechat_component_event,
)
from .collectors.baidu_search import collect_baidu_search_candidates
from .config import AgentConfig
from .cover_generation import generate_cover_image
from .database import (
    ContentAssetRow,
    ContentJobRow,
    JobEventRow,
    PublishAttemptRow,
    build_engine,
    init_schema,
    session_factory,
)
from .formatters.wechat_gzh import format_wechat_markdown, theme_label, write_gzh_outputs
from .generation import generate_llm_drafts
from .keyword_seed import build_keyword_seed_candidates
from .models import TopicBrief, TopicScore, WorkflowResult
from .prompts import COVER_STYLE_GUIDANCE, apply_cover_style
from .wechat_publish import publish_wechat_draft
from .workflow import run_keyword_workflow


CollectorName = Literal["baidu_search"]
ChannelName = Literal["wechat", "xiaohongshu"]
JobStatus = Literal["queued", "running", "completed", "preview_ready", "publishing", "published_draft", "failed", "archived"]
StepName = Literal["materials", "content", "format", "cover", "submit", "all"]


@dataclass(frozen=True)
class WebRunOptions:
    keyword: str
    channel: ChannelName = "wechat"
    collector: CollectorName = "baidu_search"
    use_llm: bool = False
    format_gzh: bool = True
    generate_cover: bool = False
    submit_wechat_draft: bool = False
    wechat_content_html: str = ""
    wechat_cover_image: str = ""
    format_theme: str = "moyu-green"
    cover_style: str = "business-tech"
    output_dir: Path = Path("output")


@dataclass
class WebJob:
    id: str
    options: WebRunOptions
    status: JobStatus = "queued"
    events: list[str] = field(default_factory=list)
    result: dict | None = None
    error: str = ""
    publish_attempts: list[dict] = field(default_factory=list)
    created_at: float = field(default_factory=time)
    updated_at: float = field(default_factory=time)
    user_id: int | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "status": self.status,
            "events": list(self.events),
            "result": self.result,
            "error": self.error,
            "options": _options_to_json(self.options),
            "publish_attempts": list(self.publish_attempts),
            "user_id": self.user_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class JobStore:
    def __init__(self, database_url: str | None = None, auto_start: bool = True):
        self._jobs: dict[str, WebJob] = {}
        self._lock = threading.Lock()
        self._auto_start = auto_start
        self._engine = build_engine(database_url)
        init_schema(self._engine)
        self._session_factory = session_factory(self._engine)
        self.auth = AuthStore(self._session_factory)

    def create(self, options: WebRunOptions, user_id: int | None = None, step: StepName = "all") -> WebJob:
        job = WebJob(id=uuid4().hex[:12], options=options, user_id=user_id)
        with self._lock:
            self._jobs[job.id] = job
        self._persist_job(job)
        if self._auto_start:
            thread = threading.Thread(target=self._run_job, args=(job.id, step), daemon=True)
            thread.start()
        return job

    def start_step(self, job_id: str, step: StepName, options: WebRunOptions | None = None) -> WebJob:
        job = self.get(job_id)
        if job is None:
            raise KeyError(job_id)
        if options is not None:
            self._update(job_id, options=options)
        validate_step_prerequisites(step, job.result)
        if self._auto_start:
            thread = threading.Thread(target=self._run_job, args=(job_id, step), daemon=True)
            thread.start()
        else:
            self._run_job(job_id, step)
        refreshed = self.get(job_id)
        if refreshed is None:
            raise KeyError(job_id)
        return refreshed

    def get(self, job_id: str) -> WebJob | None:
        with self._lock:
            job = self._jobs.get(job_id)
        if job:
            return job
        with self._session_factory() as session:
            row = session.get(ContentJobRow, job_id)
            if row is None:
                return None
            return _job_from_row(row)

    def list(self, limit: int = 50, user_id: int | None = None) -> list[WebJob]:
        with self._session_factory() as session:
            statement = select(ContentJobRow).order_by(ContentJobRow.created_at.desc()).limit(limit)
            if user_id is not None:
                statement = statement.where(ContentJobRow.user_id == user_id)
            rows = session.scalars(statement).all()
            return [_job_from_row(row) for row in rows]

    def user_owns_asset_path(self, user_id: int, path: Path) -> bool:
        normalized = str(path)
        with self._session_factory() as session:
            row = session.scalar(
                select(ContentAssetRow)
                .join(ContentJobRow)
                .where(ContentJobRow.user_id == user_id, ContentAssetRow.path == normalized)
            )
            return row is not None

    def _run_job(self, job_id: str, step: StepName = "all") -> None:
        job = self.get(job_id)
        if job is None:
            return
        self._update(job_id, status="running", event=_step_started_message(step))
        try:
            if step == "all":
                result = run_agent_workflow(job.options, progress=lambda message: self._update(job_id, event=message))
            else:
                result = run_agent_step(
                    job.options,
                    step=step,
                    current_result=job.result,
                    progress=lambda message: self._update(job_id, event=message),
                )
            self._update(job_id, status=_status_for_result(result), result=result, event=_step_finished_message(step))
        except Exception as exc:
            self._update(job_id, status="failed", error=str(exc), event=f"步骤失败：{exc}")

    def _update(
        self,
        job_id: str,
        status: JobStatus | None = None,
        event: str | None = None,
        result: dict | None = None,
        error: str | None = None,
        options: WebRunOptions | None = None,
    ) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
        if job is None:
            job = self.get(job_id)
            if job is None:
                raise KeyError(job_id)
            with self._lock:
                self._jobs[job_id] = job
        with self._lock:
            if status:
                job.status = status
            if options is not None:
                job.options = options
            if event:
                job.events.append(event)
            if result is not None:
                job.result = result
            if error is not None:
                job.error = error
            job.updated_at = time()
        self._persist_job(job, event=event)

    def record_publish_attempt(
        self,
        job_id: str,
        platform: str,
        status: JobStatus,
        response: dict | None = None,
        error: str = "",
    ) -> None:
        now = time()
        attempt = {
            "platform": platform,
            "status": status,
            "response": response or {},
            "error": error,
            "created_at": now,
            "updated_at": now,
        }
        with self._lock:
            job = self._jobs.get(job_id)
        if job is None:
            job = self.get(job_id)
            if job is None:
                raise KeyError(job_id)
        with self._lock:
            job.status = status
            job.error = error
            job.publish_attempts.append(attempt)
            job.updated_at = now
            self._jobs[job_id] = job
        with self._session_factory() as session:
            row = session.get(ContentJobRow, job_id)
            if row is None:
                raise KeyError(job_id)
            row.status = status
            row.error = error
            row.updated_at = now
            row.publish_attempts.append(
                PublishAttemptRow(
                    job_id=job_id,
                    platform=platform,
                    status=status,
                    response_json=response or {},
                    error=error,
                    created_at=now,
                    updated_at=now,
                )
            )
            session.commit()

    def _persist_job(self, job: WebJob, event: str | None = None) -> None:
        with self._session_factory() as session:
            row = session.get(ContentJobRow, job.id)
            if row is None:
                row = ContentJobRow(
                    id=job.id,
                    user_id=job.user_id,
                    keyword=job.options.keyword,
                    channel=job.options.channel,
                    collector=job.options.collector,
                    created_at=job.created_at,
                    updated_at=job.updated_at,
                )
                session.add(row)
            row.keyword = job.options.keyword
            row.user_id = job.user_id
            row.channel = job.options.channel
            row.collector = job.options.collector
            row.status = job.status
            row.options_json = _options_to_json(job.options)
            row.result_json = job.result
            row.error = job.error
            row.updated_at = job.updated_at
            if event:
                row.events.append(JobEventRow(job_id=job.id, message=event, created_at=job.updated_at))
            if job.result is not None:
                row.assets.clear()
                row.assets.extend(_asset_rows_from_result(job.id, job.result, created_at=job.updated_at))
            session.commit()


def _options_to_json(options: WebRunOptions) -> dict:
    return {
        "keyword": options.keyword,
        "channel": options.channel,
        "collector": options.collector,
        "use_llm": options.use_llm,
        "format_gzh": options.format_gzh,
        "generate_cover": options.generate_cover,
        "submit_wechat_draft": options.submit_wechat_draft,
        "wechat_content_html": options.wechat_content_html,
        "wechat_cover_image": options.wechat_cover_image,
        "format_theme": options.format_theme,
        "cover_style": options.cover_style,
        "output_dir": str(options.output_dir),
    }


def _options_from_json(payload: dict | None) -> WebRunOptions:
    payload = payload or {}
    return WebRunOptions(
        keyword=str(payload.get("keyword", "")),
        channel=payload.get("channel", "wechat"),
        collector=payload.get("collector", "baidu_search"),
        use_llm=bool(payload.get("use_llm", False)),
        format_gzh=bool(payload.get("format_gzh", True)),
        generate_cover=bool(payload.get("generate_cover", False)),
        submit_wechat_draft=bool(payload.get("submit_wechat_draft", False)),
        wechat_content_html=str(payload.get("wechat_content_html", "")),
        wechat_cover_image=str(payload.get("wechat_cover_image", "")),
        format_theme=str(payload.get("format_theme", "moyu-green")),
        cover_style=str(payload.get("cover_style", "business-tech")),
        output_dir=Path(str(payload.get("output_dir", "output"))),
    )


def _job_from_row(row: ContentJobRow) -> WebJob:
    return WebJob(
        id=row.id,
        options=_options_from_json(row.options_json),
        status=row.status,
        events=[event.message for event in row.events],
        result=row.result_json,
        error=row.error,
        publish_attempts=[
            {
                "platform": attempt.platform,
                "status": attempt.status,
                "response": attempt.response_json,
                "error": attempt.error,
                "created_at": attempt.created_at,
                "updated_at": attempt.updated_at,
            }
            for attempt in row.publish_attempts
        ],
        created_at=row.created_at,
        updated_at=row.updated_at,
        user_id=row.user_id,
    )


def _asset_rows_from_result(job_id: str, result: dict, created_at: float) -> list[ContentAssetRow]:
    rows: list[ContentAssetRow] = []
    formatting = result.get("gzh_formatting") or {}
    if formatting.get("clean_html"):
        rows.append(
            ContentAssetRow(
                job_id=job_id,
                kind="wechat_clean_html",
                path=str(formatting["clean_html"]),
                mime_type="text/html",
                metadata_json={"theme": formatting.get("theme", "")},
                created_at=created_at,
            )
        )
    if formatting.get("preview_html"):
        rows.append(
            ContentAssetRow(
                job_id=job_id,
                kind="wechat_preview_html",
                path=str(formatting["preview_html"]),
                mime_type="text/html",
                metadata_json={"theme": formatting.get("theme", "")},
                created_at=created_at,
            )
        )
    cover = result.get("cover_image") or {}
    if cover.get("path"):
        rows.append(
            ContentAssetRow(
                job_id=job_id,
                kind="cover_image",
                path=str(cover["path"]),
                url=str(cover.get("url", "")),
                mime_type="image/jpeg",
                metadata_json={"model": cover.get("model", ""), "prompt": cover.get("prompt", ""), "style": cover.get("style", "")},
                created_at=created_at,
            )
        )
    if result.get("wechat_content_html"):
        rows.append(
            ContentAssetRow(
                job_id=job_id,
                kind="wechat_content_html",
                path=str(result["wechat_content_html"]),
                mime_type="text/html",
                metadata_json={},
                created_at=created_at,
            )
        )
    return rows


def _status_for_result(result: dict) -> JobStatus:
    if result.get("wechat_draft"):
        return "published_draft"
    if result.get("gzh_formatting") or result.get("cover_image"):
        return "preview_ready"
    return "completed"


def run_agent_workflow(options: WebRunOptions, progress: Callable[[str], None] | None = None) -> dict:
    _validate_options(options)
    emit = progress or (lambda message: None)

    emit("正在用百度搜索收集候选素材")
    candidates = _collect_candidates(options)
    emit(f"已收集 {len(candidates)} 条候选素材")
    if not candidates and options.collector == "baidu_search":
        emit("百度搜索暂无结果，已改用关键词种子选题")
        candidates = build_keyword_seed_candidates(options.keyword, options.channel)
    emit("正在评分并生成选题")
    result = run_keyword_workflow(options.keyword, candidates=candidates, primary_channel=options.channel)
    payload = _to_jsonable(result)
    payload["cover_prompt"] = _cover_prompt_for_style(str(payload.get("cover_prompt", "")), options.cover_style)

    formatted_html = None
    if options.use_llm:
        emit("正在读取模型配置")
        config = AgentConfig.from_env_file()
        emit("正在生成正文内容")
        payload["llm_drafts"] = generate_llm_drafts(result, config.build_llm_provider(), progress=_localized_generation_progress(emit))
        emit("正文内容生成完成")

    if options.wechat_content_html:
        content_path = Path(options.wechat_content_html)
        emit(f"正在读取已有公众号 HTML：{content_path}")
        formatted_html = content_path.read_text(encoding="utf-8")
        payload["wechat_content_html"] = str(content_path)
    elif options.format_gzh or options.submit_wechat_draft:
        emit("正在进行公众号排版")
        markdown = payload.get("llm_drafts", {}).get("wechat_article") or _wechat_outline_to_markdown(result.wechat_outline)
        formatted_html = format_wechat_markdown(markdown, theme=options.format_theme)
        paths = write_gzh_outputs(formatted_html, options.output_dir, _safe_basename(options.keyword), theme=options.format_theme)
        payload["gzh_formatting"] = {
            "theme": theme_label(options.format_theme),
            "clean_html": str(paths.clean_html),
            "preview_html": str(paths.preview_html),
        }
        emit("公众号排版完成")

    cover_image_path = options.wechat_cover_image
    if cover_image_path:
        payload["cover_image"] = {
            "path": cover_image_path,
            "url": "",
            "model": "manual",
            "prompt": payload["cover_prompt"],
            "style": options.cover_style,
        }
    if options.generate_cover:
        emit("正在用 Replicate 生成清晰封面")
        config = AgentConfig.from_env_file()
        generated_cover = generate_cover_image(
            prompt=str(payload["cover_prompt"]),
            output_dir=options.output_dir,
            basename=_safe_basename(options.keyword),
            model=config.replicate_cover_model,
            api_token=config.replicate_api_token,
        )
        cover_image_path = str(generated_cover.path)
        payload["cover_image"] = {
            "path": str(generated_cover.path),
            "url": generated_cover.url,
            "model": generated_cover.model,
            "prompt": generated_cover.prompt,
            "style": options.cover_style,
        }
        emit("封面生成完成")

    if options.submit_wechat_draft:
        emit("正在提交公众号草稿箱")
        config = AgentConfig.from_env_file()
        published = publish_wechat_draft(
            result=result,
            content_html=formatted_html or "",
            cover_image_path=cover_image_path or "",
            config=config,
        )
        payload["wechat_draft"] = {
            "thumb_media_id": published.thumb_media_id,
            "response": published.response,
        }
        emit("公众号草稿箱提交完成")

    return payload


def run_agent_step(
    options: WebRunOptions,
    step: StepName,
    current_result: dict | None = None,
    progress: Callable[[str], None] | None = None,
) -> dict:
    validate_step_prerequisites(step, current_result)
    emit = progress or (lambda message: None)

    if step == "materials":
        _validate_options(options)
        emit("正在用百度搜索收集候选素材")
        candidates = _collect_candidates(options)
        emit(f"已收集 {len(candidates)} 条候选素材")
        if not candidates:
            emit("百度搜索暂无结果，已改用关键词种子选题")
            candidates = build_keyword_seed_candidates(options.keyword, options.channel)
        emit("正在评分并生成选题")
        result = run_keyword_workflow(options.keyword, candidates=candidates, primary_channel=options.channel)
        payload = _to_jsonable(result)
        payload["cover_prompt"] = _cover_prompt_for_style(str(payload.get("cover_prompt", "")), options.cover_style)
        return payload

    payload = dict(current_result or {})
    if step == "content":
        emit("正在读取模型配置")
        config = AgentConfig.from_env_file()
        emit("正在生成正文内容")
        payload["llm_drafts"] = generate_llm_drafts(
            _workflow_result_from_payload(payload),
            config.build_llm_provider(),
            progress=_localized_generation_progress(emit),
        )
        emit("正文内容生成完成")
        return payload

    if step == "format":
        emit("正在进行公众号排版")
        markdown = str((payload.get("llm_drafts") or {}).get("wechat_article") or "")
        formatted_html = format_wechat_markdown(markdown, theme=options.format_theme)
        paths = write_gzh_outputs(formatted_html, options.output_dir, _safe_basename(options.keyword), theme=options.format_theme)
        payload["gzh_formatting"] = {
            "theme": theme_label(options.format_theme),
            "clean_html": str(paths.clean_html),
            "preview_html": str(paths.preview_html),
        }
        emit("公众号排版完成")
        return payload

    if step == "cover":
        emit("正在用 Replicate 生成清晰封面")
        config = AgentConfig.from_env_file()
        prompt = _cover_prompt_for_style(str(payload.get("cover_prompt", "")), options.cover_style)
        generated_cover = generate_cover_image(
            prompt=prompt,
            output_dir=options.output_dir,
            basename=_safe_basename(options.keyword),
            model=config.replicate_cover_model,
            api_token=config.replicate_api_token,
        )
        payload["cover_prompt"] = prompt
        payload["cover_image"] = {
            "path": str(generated_cover.path),
            "url": generated_cover.url,
            "model": generated_cover.model,
            "prompt": generated_cover.prompt,
            "style": options.cover_style,
        }
        emit("封面生成完成")
        return payload

    raise ValueError(f"unsupported step: {step}")


def submit_previewed_wechat_draft(
    job: WebJob,
    progress: Callable[[str], None] | None = None,
    config: AgentConfig | None = None,
) -> dict:
    if job.status in {"queued", "running", "publishing"} or not job.result:
        raise ValueError("completed preview is required before submitting")

    result_payload = dict(job.result)
    html_path = _preview_clean_html_path(result_payload)
    cover_path = _preview_cover_path(result_payload)
    if not html_path:
        raise ValueError("formatted WeChat preview is required before submitting")
    if not cover_path:
        raise ValueError("cover image is required before submitting")

    emit = progress or (lambda message: None)
    emit("正在从预览提交公众号草稿箱")
    content_html = Path(html_path).read_text(encoding="utf-8")
    config = config or AgentConfig.from_env_file()
    published = publish_wechat_draft(
        result=_workflow_result_from_payload(result_payload),
        content_html=content_html,
        cover_image_path=cover_path,
        config=config,
    )
    result_payload["wechat_draft"] = {
        "thumb_media_id": published.thumb_media_id,
        "response": published.response,
    }
    return result_payload


def submit_stored_previewed_wechat_draft(
    store: JobStore,
    job_id: str,
    config: AgentConfig,
) -> WebJob:
    job = store.get(job_id)
    if job is None:
        raise KeyError(job_id)
    preview_job = replace(
        job,
        events=list(job.events),
        result=dict(job.result) if job.result else None,
        publish_attempts=list(job.publish_attempts),
    )
    try:
        validate_step_prerequisites("submit", preview_job.result)
        store._update(job_id, status="publishing", event="开始提交草稿箱")
        result = submit_previewed_wechat_draft(
            preview_job,
            progress=lambda message: store._update(job_id, event=message),
            config=config,
        )
        store._update(job_id, status="published_draft", result=result, event="草稿箱提交完成")
        store.record_publish_attempt(
            job_id,
            platform="wechat",
            status="published_draft",
            response=result.get("wechat_draft", {}).get("response", {}),
            error="",
        )
        submitted = store.get(job_id)
        if submitted is None:
            raise KeyError(job_id)
        return submitted
    except Exception as exc:
        store._update(job_id, status="failed", error=str(exc), event=f"草稿箱提交失败：{exc}")
        store.record_publish_attempt(
            job_id,
            platform="wechat",
            status="failed",
            response={},
            error=str(exc),
        )
        raise


def render_index_html() -> str:
    return INDEX_HTML


def render_landing_html() -> str:
    return LANDING_HTML


def render_trial_html() -> str:
    return TRIAL_HTML


class ContentAgentHandler(BaseHTTPRequestHandler):
    store = JobStore()

    def do_GET(self) -> None:
        parsed = parse.urlparse(self.path)
        if parsed.path == "/":
            self._send_html(render_landing_html())
            return
        if parsed.path == "/app":
            user = self._require_user()
            if user is None:
                return
            self._send_html(render_index_html())
            return
        if parsed.path == "/trial":
            self._send_html(render_trial_html())
            return
        if parsed.path == "/auth/wechat/start":
            self._start_wechat_auth(parsed.query)
            return
        if parsed.path == "/auth/wechat/callback":
            self._finish_wechat_auth(parsed.query)
            return
        if parsed.path == "/auth/wechat-official/start":
            self._start_wechat_official_auth()
            return
        if parsed.path == "/auth/wechat-official/callback":
            self._finish_wechat_official_auth(parsed.query)
            return
        if parsed.path == "/wechat/component/notify":
            self._verify_wechat_component_notify(parsed.query)
            return
        if parsed.path == "/auth/manual":
            self._send_html(render_manual_auth_html())
            return
        if parsed.path == "/auth/logout":
            self._logout()
            return
        if parsed.path == "/settings/wechat":
            user = self._require_user()
            if user is None:
                return
            account = self.store.auth.manual_wechat_account_for_user(user["id"]) or {}
            self._send_html(render_wechat_settings_html(account=account))
            return
        if parsed.path == "/api/config":
            if self._require_user(json_response=True) is None:
                return
            self._send_json(
                {
                    "config": AgentConfig.from_env_file().redacted_status(),
                    "collectors": ["baidu_search"],
                    "channels": ["wechat", "xiaohongshu"],
                }
            )
            return
        if parsed.path == "/api/jobs":
            user = self._require_user(json_response=True)
            if user is None:
                return
            self._send_json({"jobs": [job.to_dict() for job in self.store.list(user_id=user["id"])]})
            return
        if parsed.path.startswith("/api/jobs/"):
            user = self._require_user(json_response=True)
            if user is None:
                return
            job_id = parsed.path.rsplit("/", 1)[-1]
            job = self.store.get(job_id)
            if job is None or job.user_id != user["id"]:
                self._send_json({"error": "job not found"}, status=HTTPStatus.NOT_FOUND)
                return
            self._send_json(job.to_dict())
            return
        if parsed.path == "/file":
            user = self._require_user(json_response=True)
            if user is None:
                return
            self._send_file(parsed.query, user_id=user["id"])
            return
        self._send_json({"error": "not found"}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        parsed = parse.urlparse(self.path)
        if parsed.path == "/wechat/component/notify":
            self._handle_wechat_component_notify(parsed.query)
            return
        if parsed.path == "/auth/manual":
            self._finish_manual_auth()
            return
        if parsed.path == "/settings/wechat":
            self._save_wechat_settings()
            return
        if parsed.path.startswith("/api/jobs/") and "/steps/" in parsed.path:
            user = self._require_user(json_response=True)
            if user is None:
                return
            parts = parsed.path.strip("/").split("/")
            if len(parts) != 5:
                self._send_json({"error": "not found"}, status=HTTPStatus.NOT_FOUND)
                return
            job_id = parts[2]
            step = parts[4]
            job = self.store.get(job_id)
            if job is None or job.user_id != user["id"]:
                self._send_json({"error": "job not found"}, status=HTTPStatus.NOT_FOUND)
                return
            if step == "submit":
                try:
                    submitted = submit_stored_previewed_wechat_draft(
                        self.store,
                        job_id,
                        config=self._wechat_publish_config_for_user(user["id"]),
                    )
                    self._send_json(submitted.to_dict())
                except Exception as exc:
                    latest = self.store.get(job_id)
                    self._send_json(
                        {"error": str(exc), "job": latest.to_dict() if latest else None},
                        status=HTTPStatus.BAD_REQUEST,
                    )
                return
            try:
                options = _merge_options_payload(job.options, self._read_json())
                updated = self.store.start_step(job_id, _parse_step(step), options=options)
                self._send_json(updated.to_dict(), status=HTTPStatus.ACCEPTED)
            except Exception as exc:
                latest = self.store.get(job_id)
                self._send_json(
                    {"error": str(exc), "job": latest.to_dict() if latest else None},
                    status=HTTPStatus.BAD_REQUEST,
                )
            return
        if parsed.path.startswith("/api/jobs/") and parsed.path.endswith("/submit"):
            user = self._require_user(json_response=True)
            if user is None:
                return
            job_id = parsed.path.split("/")[-2]
            job = self.store.get(job_id)
            if job is None or job.user_id != user["id"]:
                self._send_json({"error": "job not found"}, status=HTTPStatus.NOT_FOUND)
                return
            try:
                submitted = submit_stored_previewed_wechat_draft(
                    self.store,
                    job_id,
                    config=self._wechat_publish_config_for_user(user["id"]),
                )
                self._send_json(submitted.to_dict())
            except Exception as exc:
                self._send_json({"error": str(exc), "job": self.store.get(job_id).to_dict()}, status=HTTPStatus.BAD_REQUEST)
            return
        if parsed.path != "/api/jobs":
            self._send_json({"error": "not found"}, status=HTTPStatus.NOT_FOUND)
            return
        user = self._require_user(json_response=True)
        if user is None:
            return
        try:
            payload = self._read_json()
            options = _options_from_payload(payload)
            job = self.store.create(options, user_id=user["id"], step=_parse_step(str(payload.get("step", "all"))))
            self._send_json(job.to_dict(), status=HTTPStatus.ACCEPTED)
        except Exception as exc:
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)

    def log_message(self, format: str, *args) -> None:
        return

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw or "{}")

    def _read_form_body(self) -> str:
        length = int(self.headers.get("Content-Length", "0"))
        return self.rfile.read(length).decode("utf-8")

    def _read_text_body(self) -> str:
        length = int(self.headers.get("Content-Length", "0"))
        return self.rfile.read(length).decode("utf-8")

    def _send_html(self, html: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_text(self, text: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _redirect(self, location: str, cookies: list[str] | None = None) -> None:
        self.send_response(HTTPStatus.FOUND)
        self.send_header("Location", location)
        for cookie in cookies or []:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()

    def _session_token(self) -> str:
        cookie = SimpleCookie(self.headers.get("Cookie", ""))
        morsel = cookie.get(SESSION_COOKIE)
        return morsel.value if morsel else ""

    def _current_user(self) -> dict | None:
        return self.store.auth.user_for_session(self._session_token())

    def _require_user(self, json_response: bool = False) -> dict | None:
        user = self._current_user()
        if user is not None:
            return user
        if json_response:
            self._send_json({"error": "authentication required"}, status=HTTPStatus.UNAUTHORIZED)
        else:
            self._redirect("/auth/wechat/start?next=/app")
        return None

    def _start_wechat_auth(self, query: str) -> None:
        params = parse.parse_qs(query)
        next_path = params.get("next", ["/app"])[0]
        config = WeChatLoginConfig.from_env()
        if not config.is_configured():
            self._send_html(render_auth_setup_html())
            return
        state = self.store.auth.create_oauth_state(provider="wechat", next_path=next_path)
        self._redirect(WeChatOAuthProvider(config).authorization_url(state=state))

    def _finish_wechat_auth(self, query: str) -> None:
        params = parse.parse_qs(query)
        code = params.get("code", [""])[0]
        state = params.get("state", [""])[0]
        next_path = self.store.auth.consume_oauth_state(state, provider="wechat")
        if not code or next_path is None:
            self._send_json({"error": "invalid wechat login state"}, status=HTTPStatus.BAD_REQUEST)
            return
        provider = WeChatOAuthProvider(WeChatLoginConfig.from_env())
        token_payload = provider.fetch_access_token(code)
        if token_payload.get("errcode"):
            self._send_json({"error": token_payload}, status=HTTPStatus.BAD_REQUEST)
            return
        profile = provider.fetch_userinfo(token_payload["access_token"], token_payload["openid"])
        if profile.get("errcode"):
            self._send_json({"error": profile}, status=HTTPStatus.BAD_REQUEST)
            return
        user = self.store.auth.upsert_external_user(
            provider="wechat",
            provider_user_id=profile.get("openid") or token_payload["openid"],
            union_id=profile.get("unionid") or token_payload.get("unionid", ""),
            display_name=profile.get("nickname") or "微信用户",
            profile=profile,
        )
        session_token = self.store.auth.create_session(user.id)
        self._redirect(next_path, cookies=[_session_cookie(session_token)])

    def _start_wechat_official_auth(self) -> None:
        if self._current_user() is None:
            self._redirect("/auth/wechat/start?next=/auth/wechat-official/start")
            return
        config = self._wechat_component_config()
        if not config.is_configured_for_auth() or not config.can_fetch_component_token():
            self._send_html(render_wechat_component_setup_html())
            return
        provider = WeChatComponentProvider(config)
        state = self.store.auth.create_oauth_state(provider="wechat_official", next_path="/settings/wechat")
        try:
            component_access_token = provider.fetch_component_access_token()
            pre_auth_code = provider.fetch_pre_auth_code(component_access_token)
            self._redirect(provider.authorization_url(pre_auth_code=pre_auth_code, state=state))
        except Exception as exc:
            self._send_html(render_wechat_component_setup_html(error=str(exc)), status=HTTPStatus.BAD_REQUEST)

    def _finish_wechat_official_auth(self, query: str) -> None:
        user = self._require_user()
        if user is None:
            return
        params = parse.parse_qs(query)
        state = params.get("state", [""])[0]
        auth_code = params.get("auth_code", params.get("authorization_code", [""]))[0]
        next_path = self.store.auth.consume_oauth_state(state, provider="wechat_official")
        if not auth_code or next_path is None:
            self._send_json({"error": "invalid wechat official authorization state"}, status=HTTPStatus.BAD_REQUEST)
            return
        provider = WeChatComponentProvider(self._wechat_component_config())
        try:
            component_access_token = provider.fetch_component_access_token()
            auth_info = provider.query_auth(auth_code, component_access_token)
            authorizer_appid = str(auth_info.get("authorizer_appid", ""))
            profile = provider.fetch_authorizer_info(authorizer_appid, component_access_token)
            display_name = str(profile.get("nick_name") or profile.get("principal_name") or authorizer_appid)
            self.store.auth.upsert_component_wechat_account(
                user_id=user["id"],
                authorizer_appid=authorizer_appid,
                display_name=display_name,
                authorizer_refresh_token=str(auth_info.get("authorizer_refresh_token", "")),
                authorizer_access_token=str(auth_info.get("authorizer_access_token", "")),
                expires_in=int(auth_info.get("expires_in") or 7200),
                profile=profile,
            )
            self._redirect(next_path)
        except Exception as exc:
            self._send_html(render_wechat_component_setup_html(error=str(exc)), status=HTTPStatus.BAD_REQUEST)

    def _verify_wechat_component_notify(self, query: str) -> None:
        params = parse.parse_qs(query)
        echo = params.get("echostr", [""])[0]
        self._send_text(echo or "success")

    def _handle_wechat_component_notify(self, query: str) -> None:
        params = parse.parse_qs(query)
        try:
            event = parse_wechat_component_event(
                self._read_text_body(),
                config=self._wechat_component_config(),
                query_params=params,
            )
            if event.get("InfoType") == "component_verify_ticket":
                self.store.auth.save_wechat_component_verify_ticket(event.get("ComponentVerifyTicket", ""))
            self._send_text("success")
        except Exception as exc:
            self._send_text(str(exc), status=HTTPStatus.BAD_REQUEST)

    def _logout(self) -> None:
        self.store.auth.delete_session(self._session_token())
        self._redirect("/", cookies=[_expired_session_cookie()])

    def _finish_manual_auth(self) -> None:
        params = parse.parse_qs(self._read_form_body())
        try:
            user = self.store.auth.create_manual_wechat_user(
                display_name=params.get("display_name", [""])[0],
                app_id=params.get("app_id", [""])[0],
                app_secret=params.get("app_secret", [""])[0],
                access_token=params.get("access_token", [""])[0],
            )
            session_token = self.store.auth.create_session(user.id)
            self._redirect("/app", cookies=[_session_cookie(session_token)])
        except Exception as exc:
            self._send_html(render_manual_auth_html(error=str(exc)), status=HTTPStatus.BAD_REQUEST)

    def _save_wechat_settings(self) -> None:
        user = self._require_user()
        if user is None:
            return
        params = parse.parse_qs(self._read_form_body())
        try:
            self.store.auth.update_manual_wechat_account(
                user_id=user["id"],
                display_name=params.get("display_name", [""])[0],
                app_id=params.get("app_id", [""])[0],
                app_secret=params.get("app_secret", [""])[0],
                access_token=params.get("access_token", [""])[0],
            )
            account = self.store.auth.manual_wechat_account_for_user(user["id"]) or {}
            self._send_html(render_wechat_settings_html(account=account, message="已保存公众号参数。"))
        except Exception as exc:
            account = {
                "display_name": params.get("display_name", [""])[0],
                "app_id": params.get("app_id", [""])[0],
                "access_token": params.get("access_token", [""])[0],
            }
            self._send_html(render_wechat_settings_html(account=account, error=str(exc)), status=HTTPStatus.BAD_REQUEST)

    def _wechat_publish_config_for_user(self, user_id: int) -> AgentConfig:
        config = AgentConfig.from_env_file()
        component_account = self.store.auth.component_wechat_account_for_user(user_id)
        if component_account:
            authorizer_access_token = self._component_authorizer_access_token(user_id, component_account)
            if authorizer_access_token:
                return replace(
                    config,
                    wechat_app_id=component_account.get("authorizer_appid", "") or config.wechat_app_id,
                    wechat_app_secret="",
                    wechat_access_token=authorizer_access_token,
                )
        account = self.store.auth.manual_wechat_account_for_user(user_id)
        if not account:
            return config
        return replace(
            config,
            wechat_app_id=account.get("app_id", "") or config.wechat_app_id,
            wechat_app_secret=account.get("app_secret", "") or config.wechat_app_secret,
            wechat_access_token=account.get("access_token", "") or config.wechat_access_token,
        )

    def _component_authorizer_access_token(self, user_id: int, account: dict) -> str:
        access_token = str(account.get("authorizer_access_token", ""))
        expires_at = float(account.get("authorizer_access_token_expires_at") or 0)
        if access_token and expires_at > time() + 60:
            return access_token
        refresh_token = str(account.get("authorizer_refresh_token", ""))
        authorizer_appid = str(account.get("authorizer_appid", ""))
        if not refresh_token or not authorizer_appid:
            return access_token
        refreshed = WeChatComponentProvider(self._wechat_component_config()).refresh_authorizer_access_token(
            authorizer_appid=authorizer_appid,
            authorizer_refresh_token=refresh_token,
        )
        stored = self.store.auth.update_component_wechat_token(
            user_id=user_id,
            authorizer_appid=authorizer_appid,
            authorizer_access_token=str(refreshed.get("authorizer_access_token", "")),
            expires_in=int(refreshed.get("expires_in") or 7200),
            authorizer_refresh_token=str(refreshed.get("authorizer_refresh_token", "")),
        )
        return str(stored.get("authorizer_access_token", ""))

    def _wechat_component_config(self) -> WeChatComponentConfig:
        config = WeChatComponentConfig.from_env()
        if config.verify_ticket:
            return config
        stored_ticket = self.store.auth.wechat_component_verify_ticket()
        if not stored_ticket:
            return config
        return replace(config, verify_ticket=stored_ticket)

    def _send_file(self, query: str, user_id: int) -> None:
        params = parse.parse_qs(query)
        raw_path = params.get("path", [""])[0]
        path = Path(raw_path)
        if not _is_safe_served_file(path):
            self._send_json({"error": "file is not allowed"}, status=HTTPStatus.BAD_REQUEST)
            return
        if not self.store.user_owns_asset_path(user_id, path):
            self._send_json({"error": "file not found"}, status=HTTPStatus.NOT_FOUND)
            return
        if not path.exists() or not path.is_file():
            self._send_json({"error": "file not found"}, status=HTTPStatus.NOT_FOUND)
            return
        body = path.read_bytes()
        content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the content-agent local web workbench.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)

    server = ThreadingHTTPServer((args.host, args.port), ContentAgentHandler)
    print(f"[content-agent] Web workbench running at http://{args.host}:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


def _options_from_payload(payload: dict) -> WebRunOptions:
    return WebRunOptions(
        keyword=str(payload.get("keyword", "")).strip(),
        channel=payload.get("channel", "wechat"),
        collector=payload.get("collector", "baidu_search"),
        use_llm=bool(payload.get("use_llm", False)),
        format_gzh=bool(payload.get("format_gzh", True)),
        generate_cover=bool(payload.get("generate_cover", False)),
        submit_wechat_draft=bool(payload.get("submit_wechat_draft", False)),
        wechat_content_html=str(payload.get("wechat_content_html", "")).strip(),
        wechat_cover_image=str(payload.get("wechat_cover_image", "")).strip(),
        format_theme=str(payload.get("format_theme", "moyu-green")).strip() or "moyu-green",
        cover_style=str(payload.get("cover_style", "business-tech")).strip() or "business-tech",
        output_dir=Path(str(payload.get("output_dir", "output")).strip() or "output"),
    )


def _merge_options_payload(options: WebRunOptions, payload: dict | None) -> WebRunOptions:
    merged = _options_to_json(options)
    merged.update(payload or {})
    return _options_from_payload(merged)


def _parse_step(step: str) -> StepName:
    if step in {"materials", "content", "format", "cover", "submit", "all"}:
        return step  # type: ignore[return-value]
    raise ValueError("未知步骤")


def validate_step_prerequisites(step: StepName, result: dict | None) -> None:
    if step in {"materials", "all"}:
        return
    if not result or not result.get("topics"):
        raise ValueError("请先搜素材，再执行后续步骤")
    if step == "content":
        return
    if step == "format" and not (result.get("llm_drafts") or {}).get("wechat_article"):
        raise ValueError("请先生成内容，再进行公众号排版")
    if step == "cover" and not result.get("cover_prompt"):
        raise ValueError("请先搜素材，再生成封面")
    if step == "submit":
        if not _preview_clean_html_path(result):
            raise ValueError("请先完成公众号排版预览，再提交草稿箱")
        if not _preview_cover_path(result):
            raise ValueError("请先生成封面，再提交草稿箱")


def _validate_options(options: WebRunOptions) -> None:
    if not options.keyword:
        raise ValueError("keyword cannot be empty")
    if options.channel not in {"wechat", "xiaohongshu"}:
        raise ValueError("channel must be wechat or xiaohongshu")
    if options.collector != "baidu_search":
        raise ValueError("collector must be baidu_search")
    if options.submit_wechat_draft and not options.wechat_cover_image and not options.generate_cover:
        raise ValueError("wechat_cover_image is required when submitting without generating a cover")
    theme_label(options.format_theme)
    _cover_prompt_for_style("workspace cover", options.cover_style)


def _cover_prompt_for_style(prompt: str, cover_style: str) -> str:
    prefix = "Replicate image prompt: "
    text = str(prompt or "").strip()
    if text.startswith(prefix):
        text = text[len(prefix) :]
    style_part, marker, rest = text.partition(". Main idea:")
    for guidance in COVER_STYLE_GUIDANCE.values():
        if style_part.startswith(guidance + ", "):
            style_part = style_part[len(guidance) + 2 :]
            break
    styled = apply_cover_style(style_part or "full-bleed editorial cover", cover_style)
    return f"{prefix}{styled}{marker}{rest}" if marker else f"{prefix}{styled}"


def _localized_generation_progress(emit: Callable[[str], None]) -> Callable[[str], None]:
    labels = {
        "Generating wechat_article with LLM": "正在生成公众号正文",
        "Generating xhs_note with LLM": "正在生成小红书笔记",
    }

    def _emit(message: str) -> None:
        emit(labels.get(message, message))

    return _emit


def _step_started_message(step: StepName) -> str:
    return {
        "materials": "开始搜素材",
        "content": "开始生成内容",
        "format": "开始排版预览",
        "cover": "开始生成封面",
        "submit": "开始提交草稿箱",
        "all": "任务开始",
    }.get(step, "任务开始")


def _step_finished_message(step: StepName) -> str:
    return {
        "materials": "素材步骤完成",
        "content": "内容步骤完成",
        "format": "排版步骤完成",
        "cover": "封面步骤完成",
        "submit": "草稿箱提交完成",
        "all": "任务完成",
    }.get(step, "任务完成")


def _collect_candidates(options: WebRunOptions):
    config = AgentConfig.from_env_file()
    if options.collector == "baidu_search":
        return collect_baidu_search_candidates(options.keyword, api_key=config.baidu_search_api_key)
    raise ValueError("collector must be baidu_search")


def _to_jsonable(value):
    if is_dataclass(value):
        return _to_jsonable(asdict(value))
    if isinstance(value, list):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: _to_jsonable(item) for key, item in value.items()}
    return value


def _preview_clean_html_path(payload: dict) -> str:
    formatting = payload.get("gzh_formatting") or {}
    return str(formatting.get("clean_html") or payload.get("wechat_content_html") or "").strip()


def _preview_cover_path(payload: dict) -> str:
    cover = payload.get("cover_image") or {}
    return str(cover.get("path") or "").strip()


def _workflow_result_from_payload(payload: dict) -> WorkflowResult:
    return WorkflowResult(
        keyword=str(payload["keyword"]),
        expanded_keywords=list(payload.get("expanded_keywords", [])),
        topics=[_topic_brief_from_payload(topic) for topic in payload.get("topics", [])],
        wechat_outline=str(payload.get("wechat_outline", "")),
        xhs_package=str(payload.get("xhs_package", "")),
        cover_prompt=str(payload.get("cover_prompt", "")),
    )


def _topic_brief_from_payload(payload: dict) -> TopicBrief:
    score = payload.get("score") or {}
    return TopicBrief(
        title=str(payload.get("title", "")),
        optimized_title=str(payload.get("optimized_title") or payload.get("title", "")),
        score=TopicScore(
            total=float(score.get("total", 0)),
            level=str(score.get("level", "")),
            reasons=list(score.get("reasons", [])),
        ),
        source=str(payload.get("source", "")),
        url=payload.get("url"),
        platform_fit=list(payload.get("platform_fit", [])),
        angle=str(payload.get("angle", "")),
        material_needs=list(payload.get("material_needs", [])),
        risk_notes=list(payload.get("risk_notes", [])),
    )


def _wechat_outline_to_markdown(outline: str) -> str:
    lines = [line.strip() for line in outline.splitlines() if line.strip()]
    title = lines[0].replace("公众号文章：", "").strip("《》") if lines else "公众号文章"
    body = ["# " + title]
    for line in lines[1:]:
        if line.startswith("结构："):
            body.append("\n## 内容结构")
            body.append(line.removeprefix("结构："))
        elif line.startswith("合规："):
            body.append("\n## 写在最后")
            body.append(line.removeprefix("合规："))
        else:
            body.append("\n## " + line.split("：", 1)[0])
            body.append(line.split("：", 1)[-1])
    return "\n\n".join(body)


def _safe_basename(keyword: str) -> str:
    safe = "".join(char for char in keyword if char.isalnum() or char in {"-", "_"})
    return safe or "article"


def _is_safe_served_file(path: Path) -> bool:
    if not str(path):
        return False
    resolved = path.resolve()
    output_root = Path("output").resolve()
    return resolved == output_root or output_root in resolved.parents


def _session_cookie(token: str) -> str:
    return f"{SESSION_COOKIE}={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age={60 * 60 * 24 * 30}"


def _expired_session_cookie() -> str:
    return f"{SESSION_COOKIE}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0"


def render_auth_setup_html() -> str:
    return AUTH_SETUP_HTML


def render_manual_auth_html(error: str = "") -> str:
    error_html = f'<p class="error">{html_escape(error)}</p>' if error else ""
    return MANUAL_AUTH_HTML.replace("{{ERROR}}", error_html)


def render_wechat_settings_html(account: dict, message: str = "", error: str = "") -> str:
    message_html = f'<p class="success">{html_escape(message)}</p>' if message else ""
    error_html = f'<p class="error">{html_escape(error)}</p>' if error else ""
    html = WECHAT_SETTINGS_HTML.replace("{{MESSAGE}}", message_html).replace("{{ERROR}}", error_html)
    return (
        html.replace("{{DISPLAY_NAME}}", html_escape(account.get("display_name", "")))
        .replace("{{APP_ID}}", html_escape(account.get("app_id", "")))
        .replace("{{ACCESS_TOKEN}}", html_escape(account.get("access_token", "")))
    )


def render_wechat_component_setup_html(error: str = "") -> str:
    error_html = f'<p class="error">{html_escape(error)}</p>' if error else ""
    return WECHAT_COMPONENT_SETUP_HTML.replace("{{ERROR}}", error_html)


def html_escape(value: str) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#039;")
    )


LANDING_HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Media Agent - 内容增长工作台</title>
  <style>
    :root {
      --bg: #f6f7f2;
      --ink: #14211d;
      --muted: #60706a;
      --line: #dce3dc;
      --green: #0f8a5f;
      --dark: #12261f;
      --gold: #b9892d;
      --panel: #ffffff;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      color: var(--ink);
      background: var(--bg);
      font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif;
      letter-spacing: 0;
    }
    header, main { width: min(1120px, calc(100% - 36px)); margin: 0 auto; }
    header { height: 72px; display: flex; align-items: center; justify-content: space-between; }
    .brand { font-weight: 900; font-size: 18px; }
    nav { display: flex; gap: 16px; align-items: center; }
    .login { color: var(--green); text-decoration: none; font-weight: 800; }
    .hero { min-height: calc(100vh - 72px); display: grid; grid-template-columns: minmax(0, 1.04fr) minmax(340px, .96fr); gap: 36px; align-items: center; padding-bottom: 40px; }
    h1 { margin: 0; font-size: clamp(40px, 6vw, 76px); line-height: 1.02; max-width: 820px; }
    .lead { margin-top: 22px; color: var(--muted); font-size: 18px; line-height: 1.8; max-width: 640px; }
    .actions { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 30px; }
    .primary, .secondary {
      display: inline-flex; align-items: center; justify-content: center;
      min-height: 48px; padding: 0 20px; border-radius: 8px; text-decoration: none; font-weight: 900;
    }
    .primary { background: var(--green); color: #fff; }
    .secondary { border: 1px solid var(--line); color: var(--dark); background: #fff; }
    .board { background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 18px; box-shadow: 0 24px 70px rgba(20, 33, 29, .10); }
    .row { display: grid; grid-template-columns: 90px 1fr 72px; gap: 12px; align-items: center; padding: 12px 0; border-bottom: 1px solid var(--line); }
    .row:last-child { border-bottom: 0; }
    .tag { color: var(--green); font-weight: 900; font-size: 12px; }
    .topic { font-weight: 850; line-height: 1.45; }
    .score { color: var(--gold); font-weight: 900; text-align: right; }
    .features { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; margin: 0 auto 42px; }
    .feature { background: #fff; border: 1px solid var(--line); border-radius: 8px; padding: 18px; min-height: 130px; }
    .feature h2 { font-size: 16px; margin: 0 0 10px; }
    .feature p { margin: 0; color: var(--muted); line-height: 1.7; font-size: 14px; }
    @media (max-width: 880px) {
      .hero { grid-template-columns: 1fr; padding-top: 24px; }
      .features { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <header>
    <div class="brand">Media Agent</div>
    <nav>
      <a class="login" href="/trial">开始试用</a>
    </nav>
  </header>
  <main>
    <section class="hero">
      <div>
        <h1>把自媒体创作从想法推进到可发布</h1>
        <p class="lead">很多人想做公众号、小红书、百家号等自媒体，却被选题、素材、内容、封面、排版和发布流程反复卡住。Media Agent 把这些环节放进一个可追踪的工作台，让每次创作都有进度、有预览、有记录。</p>
        <div class="actions">
          <a class="primary" href="/trial">开始试用</a>
          <a class="secondary" href="#features">查看能力</a>
        </div>
      </div>
      <div class="board" aria-label="内容生产示例">
        <div class="row"><span class="tag">关键词</span><span class="topic">AI副业</span><span class="score">输入</span></div>
        <div class="row"><span class="tag">数据</span><span class="topic">自动筛选爆款数据</span><span class="score">发现</span></div>
        <div class="row"><span class="tag">内容</span><span class="topic">生成可编辑内容、封面与预览</span><span class="score">成稿</span></div>
        <div class="row"><span class="tag">推进</span><span class="topic">保存每次状态，随时回来继续</span><span class="score">可追踪</span></div>
      </div>
    </section>
    <section id="features" class="features">
      <article class="feature"><h2>爆款数据筛选</h2><p>输入关键词后，自动筛选爆款数据，减少从空白页开始找方向的时间。</p></article>
      <article class="feature"><h2>创作流程推进</h2><p>把素材、内容、封面、排版和预览串起来，让卡住的环节一个个往前走。</p></article>
      <article class="feature"><h2>内容资产库</h2><p>每次生成都会保存状态、预览、封面和提交记录，随时回来继续处理。</p></article>
    </section>
  </main>
</body>
</html>"""


TRIAL_HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>选择试用平台 - Media Agent</title>
  <style>
    :root {
      --bg: #f6f7f2;
      --ink: #14211d;
      --muted: #60706a;
      --line: #dce3dc;
      --green: #0f8a5f;
      --panel: #ffffff;
      --disabled: #a5ada8;
    }
    * { box-sizing: border-box; }
    body { margin: 0; background: var(--bg); color: var(--ink); font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif; letter-spacing: 0; }
    main { width: min(980px, calc(100% - 36px)); margin: 48px auto; }
    a { color: var(--green); font-weight: 800; text-decoration: none; }
    h1 { margin: 18px 0 10px; font-size: clamp(32px, 5vw, 56px); line-height: 1.05; }
    .lead { color: var(--muted); line-height: 1.8; font-size: 16px; max-width: 680px; }
    .platforms { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; margin-top: 30px; }
    .platform { background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 18px; min-height: 210px; box-shadow: 0 20px 60px rgba(20, 33, 29, .08); display: flex; flex-direction: column; }
    .platform.disabled { color: var(--disabled); background: #f9faf7; }
    .status { display: inline-flex; width: fit-content; min-height: 26px; align-items: center; padding: 0 10px; border-radius: 999px; background: #e9f3ed; color: #0a6547; font-size: 12px; font-weight: 900; }
    .disabled .status { background: #eef0ed; color: #7e8782; }
    h2 { margin: 14px 0 8px; font-size: 20px; }
    p { margin: 0; color: var(--muted); line-height: 1.7; font-size: 14px; }
    .platform.disabled p { color: #8d9691; }
    .actions { display: grid; gap: 10px; margin-top: auto; padding-top: 18px; }
    .button { min-height: 42px; display: inline-flex; align-items: center; justify-content: center; border-radius: 8px; font-weight: 900; }
    .primary { background: var(--green); color: white; }
    .secondary { border: 1px solid var(--line); background: #fff; color: var(--ink); }
    .soon { min-height: 42px; display: inline-flex; align-items: center; justify-content: center; border-radius: 8px; border: 1px solid var(--line); color: #7e8782; font-weight: 900; background: #fff; }
    @media (max-width: 820px) { .platforms { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
  <main>
    <a href="/">返回首页</a>
    <h1>选择要试用的平台</h1>
    <p class="lead">不同平台会逐步开放。已开放的平台可以继续登录或填写参数；未开放的平台暂不可选。</p>
    <section class="platforms">
      <article class="platform">
        <span class="status">已开放</span>
        <h2>微信公众号</h2>
        <p>适合先跑通选题、内容、排版、封面和草稿箱提交流程。</p>
        <div class="actions">
          <a class="button primary" href="/auth/wechat/start?next=/app">登录工作台</a>
          <a class="button secondary" href="/auth/wechat-official/start">授权公众号</a>
          <a class="button secondary" href="/auth/manual">手动填写参数</a>
        </div>
      </article>
      <article class="platform disabled" aria-disabled="true">
        <span class="status">敬请期待</span>
        <h2>百家号</h2>
        <p>后续开放内容生成、预览和发布流程。</p>
        <div class="actions"><span class="soon">暂不可选</span></div>
      </article>
      <article class="platform disabled" aria-disabled="true">
        <span class="status">敬请期待</span>
        <h2>小红书</h2>
        <p>后续开放笔记生成、封面和半自动发布包。</p>
        <div class="actions"><span class="soon">暂不可选</span></div>
      </article>
    </section>
  </main>
</body>
</html>"""


MANUAL_AUTH_HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>手动填写公众号参数 - Media Agent</title>
  <style>
    body { margin: 0; min-height: 100vh; background: #f6f7f2; color: #14211d; font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif; letter-spacing: 0; }
    main { width: min(720px, calc(100% - 36px)); margin: 42px auto; background: #fff; border: 1px solid #dce3dc; border-radius: 8px; padding: 28px; box-shadow: 0 24px 70px rgba(20, 33, 29, .10); }
    h1 { margin: 0 0 10px; font-size: 26px; }
    p { color: #60706a; line-height: 1.7; }
    label { display: block; margin: 16px 0 6px; color: #60706a; font-size: 12px; font-weight: 800; }
    input { width: 100%; height: 42px; border: 1px solid #dce3dc; border-radius: 8px; padding: 0 12px; font-size: 14px; }
    input:focus { border-color: #0f8a5f; outline: none; box-shadow: 0 0 0 3px rgba(15, 138, 95, .12); }
    button { width: 100%; height: 46px; margin-top: 22px; border: 0; border-radius: 8px; background: #0f8a5f; color: #fff; font-size: 15px; font-weight: 900; cursor: pointer; }
    .hint { background: #f3f6f1; border-radius: 8px; padding: 12px; }
    .error { color: #b23b3b; font-weight: 800; }
    a { color: #0f8a5f; font-weight: 800; }
  </style>
</head>
<body>
  <main>
    <h1>手动填写公众号参数</h1>
    <p class="hint">你可以在微信公众平台查看开发者参数。适合暂时不接微信开放平台授权、先自己使用或小团队试用的场景。后续可在工作台里继续编辑修改。</p>
    {{ERROR}}
    <form method="post" action="/auth/manual">
      <label for="display_name">账号名称</label>
      <input id="display_name" name="display_name" placeholder="例如：班森的公众号">

      <label for="app_id">WECHAT_APP_ID</label>
      <input id="app_id" name="app_id" required placeholder="公众号 AppID">

      <label for="app_secret">WECHAT_APP_SECRET</label>
      <input id="app_secret" name="app_secret" type="password" required placeholder="公众号 AppSecret">

      <label for="access_token">WECHAT_ACCESS_TOKEN 可选</label>
      <input id="access_token" name="access_token" placeholder="已有 access_token 时可填写">

      <button type="submit">保存并进入工作台</button>
    </form>
    <p><a href="/">返回首页</a></p>
  </main>
</body>
</html>"""


WECHAT_SETTINGS_HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>公众号参数 - Media Agent</title>
  <style>
    body { margin: 0; min-height: 100vh; background: #f6f7f2; color: #14211d; font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif; letter-spacing: 0; }
    main { width: min(720px, calc(100% - 36px)); margin: 42px auto; background: #fff; border: 1px solid #dce3dc; border-radius: 8px; padding: 28px; box-shadow: 0 24px 70px rgba(20, 33, 29, .10); }
    h1 { margin: 0 0 10px; font-size: 26px; }
    p { color: #60706a; line-height: 1.7; }
    label { display: block; margin: 16px 0 6px; color: #60706a; font-size: 12px; font-weight: 800; }
    input { width: 100%; height: 42px; border: 1px solid #dce3dc; border-radius: 8px; padding: 0 12px; font-size: 14px; }
    input:focus { border-color: #0f8a5f; outline: none; box-shadow: 0 0 0 3px rgba(15, 138, 95, .12); }
    button { width: 100%; height: 46px; margin-top: 22px; border: 0; border-radius: 8px; background: #0f8a5f; color: #fff; font-size: 15px; font-weight: 900; cursor: pointer; }
    .hint { background: #f3f6f1; border-radius: 8px; padding: 12px; }
    .error { color: #b23b3b; font-weight: 800; }
    .success { color: #0f8a5f; font-weight: 800; }
    a { color: #0f8a5f; font-weight: 800; }
  </style>
</head>
<body>
  <main>
    <h1>公众号参数</h1>
    <p class="hint">参数可在微信公众平台查看。AppSecret 留空时会保留原值；填写新值会覆盖。</p>
    {{MESSAGE}}
    {{ERROR}}
    <form method="post" action="/settings/wechat">
      <label for="display_name">账号名称</label>
      <input id="display_name" name="display_name" value="{{DISPLAY_NAME}}">

      <label for="app_id">WECHAT_APP_ID</label>
      <input id="app_id" name="app_id" value="{{APP_ID}}" required>

      <label for="app_secret">WECHAT_APP_SECRET</label>
      <input id="app_secret" name="app_secret" type="password" placeholder="留空则保留原 AppSecret">

      <label for="access_token">WECHAT_ACCESS_TOKEN 可选</label>
      <input id="access_token" name="access_token" value="{{ACCESS_TOKEN}}">

      <button type="submit">保存修改</button>
    </form>
    <p><a href="/app">返回工作台</a></p>
  </main>
</body>
</html>"""


AUTH_SETUP_HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>配置微信登录 - Media Agent</title>
  <style>
    body { margin: 0; min-height: 100vh; display: grid; place-items: center; background: #f6f7f2; color: #14211d; font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif; }
    main { width: min(640px, calc(100% - 36px)); background: #fff; border: 1px solid #dce3dc; border-radius: 8px; padding: 28px; box-shadow: 0 24px 70px rgba(20, 33, 29, .10); }
    h1 { margin: 0 0 12px; font-size: 24px; }
    p { color: #60706a; line-height: 1.7; }
    code { display: block; padding: 12px; margin: 10px 0; background: #f3f6f1; border-radius: 8px; color: #0f6044; overflow-wrap: anywhere; }
    a { color: #0f8a5f; font-weight: 800; }
  </style>
</head>
<body>
  <main>
    <h1>需要先配置微信授权登录</h1>
    <p>请在服务器的 <code>.env.production</code> 中配置微信开放平台网站应用参数：</p>
    <code>WECHAT_LOGIN_APP_ID=</code>
    <code>WECHAT_LOGIN_APP_SECRET=</code>
    <code>WECHAT_LOGIN_REDIRECT_URI=https://media-agent.createbeauty.top/auth/wechat/callback</code>
    <p>配置完成并重新部署后，点击试用会跳转微信扫码授权登录。</p>
    <p><a href="/">返回首页</a></p>
  </main>
</body>
</html>"""


WECHAT_COMPONENT_SETUP_HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>配置公众号授权 - Media Agent</title>
  <style>
    body { margin: 0; min-height: 100vh; display: grid; place-items: center; background: #f6f7f2; color: #14211d; font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif; }
    main { width: min(720px, calc(100% - 36px)); background: #fff; border: 1px solid #dce3dc; border-radius: 8px; padding: 28px; box-shadow: 0 24px 70px rgba(20, 33, 29, .10); }
    h1 { margin: 0 0 12px; font-size: 24px; }
    p { color: #60706a; line-height: 1.7; }
    code { display: block; padding: 12px; margin: 10px 0; background: #f3f6f1; border-radius: 8px; color: #0f6044; overflow-wrap: anywhere; }
    .error { color: #b23b3b; font-weight: 800; }
    a { color: #0f8a5f; font-weight: 800; }
  </style>
</head>
<body>
  <main>
    <h1>需要先配置微信开放平台公众号授权</h1>
    <p>这是多人 SaaS 的公众号授权方式：用户授权自己的公众号给平台，平台用授权后的 authorizer token 提交草稿，不需要每个用户填写 AppSecret。</p>
    {{ERROR}}
    <code>WECHAT_COMPONENT_APP_ID=</code>
    <code>WECHAT_COMPONENT_APP_SECRET=</code>
    <code>WECHAT_COMPONENT_TOKEN=</code>
    <code>WECHAT_COMPONENT_AES_KEY=</code>
    <code>WECHAT_COMPONENT_AUTH_REDIRECT_URI=https://media-agent.createbeauty.top/auth/wechat-official/callback</code>
    <code>WECHAT_COMPONENT_VERIFY_TICKET=</code>
    <p>如果已经有可用的 component_access_token，也可以临时配置 <code>WECHAT_COMPONENT_ACCESS_TOKEN=</code> 跑通授权链路。</p>
    <p><a href="/app">返回工作台</a></p>
  </main>
</body>
</html>"""


INDEX_HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Content Agent 内容工作台</title>
  <style>
    :root {
      --bg: #f7f8f3;
      --ink: #17201d;
      --muted: #69716d;
      --line: #dfe5dc;
      --panel: #ffffff;
      --green: #0f8a5f;
      --green-dark: #0a6547;
      --amber: #c7831c;
      --red: #b23b3b;
      --blue: #2f6d91;
      --shadow: 0 18px 50px rgba(23, 32, 29, 0.08);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif;
      letter-spacing: 0;
    }
    .shell {
      display: grid;
      grid-template-columns: 360px minmax(0, 1fr);
      min-height: 100vh;
    }
    aside {
      border-right: 1px solid var(--line);
      padding: 24px;
      background: #fbfcf8;
    }
    main { padding: 24px; }
    h1 { margin: 0 0 6px; font-size: 24px; line-height: 1.2; overflow-wrap: anywhere; }
    h2 { margin: 0 0 14px; font-size: 16px; }
    p { margin: 0; }
    .sub { color: var(--muted); font-size: 13px; line-height: 1.6; margin-bottom: 24px; }
    .account-links { display: flex; flex-wrap: wrap; gap: 10px; margin: -12px 0 22px; }
    .account-links a { color: var(--green-dark); font-size: 13px; font-weight: 800; text-decoration: none; }
    label { display: block; color: var(--muted); font-size: 12px; font-weight: 700; margin: 14px 0 6px; }
    input, select {
      width: 100%;
      height: 40px;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 0 12px;
      background: #fff;
      color: var(--ink);
      font-size: 14px;
      outline: none;
    }
    input:focus, select:focus { border-color: var(--green); box-shadow: 0 0 0 3px rgba(15, 138, 95, 0.12); }
    button {
      width: 100%;
      height: 44px;
      margin-top: 18px;
      border: 0;
      border-radius: 8px;
      background: var(--green);
      color: white;
      font-weight: 800;
      font-size: 14px;
      cursor: pointer;
    }
    button:disabled { opacity: 0.6; cursor: wait; }
    .step-buttons { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 18px; }
    .step-buttons button { margin: 0; }
    .step-buttons .secondary-step { background: #e9f3ed; color: var(--green-dark); }
    .step-buttons .disabled-step { background: #eef0ed; color: #7e8782; }
    .grid { display: grid; grid-template-columns: minmax(0, 1.1fr) minmax(320px, 0.9fr); gap: 18px; }
    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
      padding: 18px;
      min-width: 0;
    }
    .status {
      display: inline-flex;
      align-items: center;
      min-height: 26px;
      padding: 0 10px;
      border-radius: 999px;
      background: #edf5ef;
      color: var(--green-dark);
      font-size: 12px;
      font-weight: 800;
      margin-bottom: 14px;
    }
    .events { display: grid; gap: 8px; }
    .event {
      border-left: 3px solid var(--green);
      padding: 8px 10px;
      background: #f7fbf8;
      color: #29322f;
      font-size: 13px;
      line-height: 1.5;
      border-radius: 0 6px 6px 0;
    }
    .topics { display: grid; gap: 10px; }
    .topic {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      background: #fff;
    }
    .topic-title { font-size: 14px; font-weight: 800; line-height: 1.45; overflow-wrap: anywhere; word-break: break-word; }
    .source-title { width: 100%; overflow-wrap: anywhere; word-break: break-word; }
    .meta { margin-top: 8px; color: var(--muted); font-size: 12px; display: flex; gap: 10px; flex-wrap: wrap; }
    iframe {
      width: 100%;
      height: 540px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
    }
    .cover {
      width: 100%;
      max-height: 260px;
      object-fit: contain;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #f0f2ed;
    }
    .empty { color: var(--muted); font-size: 13px; line-height: 1.6; }
    .error { color: var(--red); font-weight: 700; }
    .path { word-break: break-all; color: var(--blue); font-size: 12px; margin-top: 8px; }
    .history-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin: 24px 0 10px;
    }
    .history-head h2 { margin: 0; }
    .mini-button {
      width: auto;
      height: 30px;
      margin: 0;
      padding: 0 10px;
      background: #e9f3ed;
      color: var(--green-dark);
      font-size: 12px;
    }
    .history-list { display: grid; gap: 8px; }
    .history-item {
      width: 100%;
      height: auto;
      margin: 0;
      padding: 10px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      color: var(--ink);
      text-align: left;
      cursor: pointer;
    }
    .history-item.active { border-color: var(--green); box-shadow: 0 0 0 3px rgba(15, 138, 95, 0.10); }
    .history-title { font-size: 13px; font-weight: 800; line-height: 1.35; overflow-wrap: anywhere; }
    .history-meta { margin-top: 6px; color: var(--muted); font-size: 11px; line-height: 1.5; display: flex; flex-wrap: wrap; gap: 8px; }
    .publish-tag { color: var(--green-dark); font-weight: 900; }
    @media (max-width: 980px) {
      .shell { grid-template-columns: 1fr; }
      aside { border-right: 0; border-bottom: 1px solid var(--line); }
      .grid { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <div class="shell">
    <aside>
      <h1>Content Agent 内容工作台</h1>
      <p class="sub">关键词到选题、内容、排版、封面和草稿箱的本地工作台。</p>
      <div class="account-links">
        <a href="/auth/wechat-official/start">授权公众号</a>
        <a href="/settings/wechat">公众号参数</a>
        <a href="/auth/logout">退出登录</a>
      </div>
      <form id="runForm">
        <label for="keyword">关键词</label>
        <input id="keyword" name="keyword" value="AI副业" autocomplete="off">

        <label for="channel">渠道</label>
        <select id="channel" name="channel">
          <option value="wechat">公众号</option>
          <option value="xiaohongshu">小红书</option>
        </select>

        <label for="collector">数据源</label>
        <select id="collector" name="collector">
          <option value="baidu_search" selected>百度搜索 前10篇非广告</option>
        </select>

        <label for="formatTheme">公众号排版样式</label>
        <select id="formatTheme" name="format_theme">
          <option value="moyu-green" selected>摸鱼绿</option>
          <option value="tech-blue">科技蓝</option>
          <option value="minimal-mono">极简黑白</option>
          <option value="warm-card">暖色知识卡</option>
        </select>

        <label for="coverStyle">素材图片风格</label>
        <select id="coverStyle" name="cover_style">
          <option value="business-tech" selected>商务科技</option>
          <option value="real-photo">真实摄影</option>
          <option value="minimal-illustration">极简插画</option>
          <option value="knowledge-card">知识封面</option>
        </select>

        <div class="step-buttons">
          <button id="runButton" type="submit" data-step="materials">搜素材</button>
          <button class="secondary-step" type="button" data-step="content">生成内容</button>
          <button class="secondary-step" type="button" data-step="format">排版预览</button>
          <button class="secondary-step" type="button" data-step="cover">生成封面</button>
        </div>
      </form>
      <div class="history-head">
        <h2>历史记录</h2>
        <button id="refreshHistoryButton" class="mini-button" type="button">刷新</button>
      </div>
      <div id="historyList" class="history-list"><p class="empty">暂无历史记录。</p></div>
    </aside>
    <main>
      <div class="grid">
        <section class="panel">
          <h2>进度</h2>
          <div id="status" class="status">idle</div>
          <div id="events" class="events"><p class="empty">等待运行。</p></div>
        </section>
        <section class="panel">
          <h2>选题评分</h2>
          <div id="topics" class="topics"><p class="empty">运行后展示候选选题。</p></div>
        </section>
      </div>
      <div class="grid" style="margin-top:18px;">
        <section class="panel">
          <h2>公众号预览</h2>
          <div id="preview"><p class="empty">勾选公众号排版后展示预览。</p></div>
        </section>
        <section class="panel">
          <h2>封面与提交</h2>
          <div id="assets"><p class="empty">生成封面或提交草稿后展示结果。</p></div>
          <button id="submitDraftButton" type="button" disabled>提交公众号草稿箱</button>
          <p id="submitHint" class="empty" style="margin-top:10px;">生成公众号预览和封面后可提交。</p>
        </section>
      </div>
    </main>
  </div>
  <script>
    const form = document.getElementById("runForm");
    const runButton = document.getElementById("runButton");
    const statusEl = document.getElementById("status");
    const eventsEl = document.getElementById("events");
    const topicsEl = document.getElementById("topics");
    const previewEl = document.getElementById("preview");
    const assetsEl = document.getElementById("assets");
    const submitDraftButton = document.getElementById("submitDraftButton");
    const submitHint = document.getElementById("submitHint");
    const historyList = document.getElementById("historyList");
    const refreshHistoryButton = document.getElementById("refreshHistoryButton");
    const stepButtons = Array.from(document.querySelectorAll("[data-step]"));
    const statusLabels = {
      queued: "排队中",
      running: "执行中",
      completed: "已完成",
      preview_ready: "预览完成",
      publishing: "发布中",
      published_draft: "已发布",
      failed: "失败",
      archived: "已归档"
    };
    let currentJobId = "";

    loadHistory();
    refreshHistoryButton.addEventListener("click", loadHistory);
    stepButtons.forEach(button => {
      if (button.id === "runButton") return;
      button.addEventListener("click", () => runStep(button.dataset.step));
    });

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      startMaterialsJob();
    });

    async function startMaterialsJob() {
      setBusy(true);
      submitDraftButton.disabled = true;
      submitHint.textContent = "先生成预览，确认无误后再提交。";
      currentJobId = "";
      statusEl.textContent = "启动中";
      eventsEl.innerHTML = "";
      topicsEl.innerHTML = '<p class="empty">正在收集和评分。</p>';
      previewEl.innerHTML = '<p class="empty">等待排版结果。</p>';
      assetsEl.innerHTML = '<p class="empty">等待封面或提交结果。</p>';

      const payload = collectOptions();
      payload.step = "materials";
      payload.use_llm = false;
      payload.format_gzh = false;
      payload.generate_cover = false;

      try {
        const response = await fetch("/api/jobs", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify(payload)
        });
        const job = await response.json();
        if (!response.ok) throw new Error(job.error || "启动失败");
        currentJobId = job.id;
        loadHistory();
        pollJob(job.id);
      } catch (error) {
        statusEl.textContent = "失败";
        eventsEl.innerHTML = `<p class="error">${escapeHtml(error.message)}</p>`;
        setBusy(false);
      }
    }

    async function runStep(step) {
      if (!currentJobId) {
        eventsEl.innerHTML = '<p class="error">请先搜素材，或从历史记录选择一篇内容。</p>';
        return;
      }
      setBusy(true);
      const stepText = {content: "正在生成内容。", format: "正在排版预览。", cover: "正在生成封面。"}[step] || "正在执行。";
      submitHint.textContent = stepText;
      try {
        const response = await fetch(`/api/jobs/${currentJobId}/steps/${step}`, {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify(collectOptions())
        });
        const payload = await response.json();
        const job = payload.job || payload;
        renderJob(job);
        if (!response.ok) throw new Error(payload.error || "步骤执行失败");
        pollJob(job.id);
      } catch (error) {
        eventsEl.innerHTML += `<p class="error">${escapeHtml(error.message)}</p>`;
        setBusy(false);
      }
    }

    submitDraftButton.addEventListener("click", async () => {
      if (!currentJobId) return;
      submitDraftButton.disabled = true;
      submitHint.textContent = "正在提交到公众号草稿箱。";
      try {
        const response = await fetch(`/api/jobs/${currentJobId}/steps/submit`, {method: "POST"});
        const payload = await response.json();
        const job = payload.job || payload;
        renderJob(job);
        loadHistory();
        if (!response.ok) throw new Error(payload.error || "提交失败");
      } catch (error) {
        submitHint.textContent = error.message;
      }
    });

    async function pollJob(jobId) {
      const response = await fetch(`/api/jobs/${jobId}`);
      const job = await response.json();
      renderJob(job);
      if (job.status === "queued" || job.status === "running" || job.status === "publishing") {
        setTimeout(() => pollJob(jobId), 1200);
      } else {
        setBusy(false);
        loadHistory();
      }
    }

    function renderJob(job) {
      currentJobId = job.id || currentJobId;
      statusEl.textContent = statusLabel(job.status);
      eventsEl.innerHTML = (job.events || []).map(item => `<div class="event">${escapeHtml(item)}</div>`).join("");
      if (job.error) {
        eventsEl.innerHTML += `<p class="error">${escapeHtml(job.error)}</p>`;
      }
      if (job.result) renderResult(job.result);
    }

    async function loadHistory() {
      try {
        const response = await fetch("/api/jobs");
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.error || "加载历史失败");
        renderHistory(payload.jobs || []);
      } catch (error) {
        historyList.innerHTML = `<p class="error">${escapeHtml(error.message)}</p>`;
      }
    }

    function renderHistory(jobs) {
      if (!jobs.length) {
        historyList.innerHTML = '<p class="empty">暂无历史记录。</p>';
        return;
      }
      historyList.innerHTML = jobs.map(job => {
        const options = job.options || {};
        const active = job.id === currentJobId ? " active" : "";
        return `
          <button class="history-item${active}" type="button" data-job-id="${escapeHtml(job.id)}">
            <div class="history-title">${escapeHtml(options.keyword || job.result?.keyword || "未命名内容")}</div>
            <div class="history-meta">
              <span>${escapeHtml(options.channel || "")}</span>
              <span>${escapeHtml(statusLabel(job.status))}</span>
              <span class="publish-tag">${escapeHtml(publishLabel(job))}</span>
              <span>${formatTime(job.updated_at)}</span>
            </div>
          </button>
        `;
      }).join("");
      historyList.querySelectorAll(".history-item").forEach(button => {
        button.addEventListener("click", () => loadJob(button.dataset.jobId));
      });
    }

    async function loadJob(jobId) {
      const response = await fetch(`/api/jobs/${jobId}`);
      const job = await response.json();
      if (!response.ok) {
        historyList.innerHTML = `<p class="error">${escapeHtml(job.error || "记录不存在")}</p>`;
        return;
      }
      currentJobId = job.id;
      applyOptions(job.options || {});
      renderJob(job);
      loadHistory();
    }

    function collectOptions() {
      return {
        keyword: document.getElementById("keyword").value,
        channel: document.getElementById("channel").value,
        collector: document.getElementById("collector").value,
        use_llm: false,
        format_gzh: false,
        generate_cover: false,
        submit_wechat_draft: false,
        wechat_content_html: "",
        wechat_cover_image: "",
        format_theme: document.getElementById("formatTheme").value,
        cover_style: document.getElementById("coverStyle").value,
        output_dir: "output"
      };
    }

    function applyOptions(options) {
      if (options.keyword) document.getElementById("keyword").value = options.keyword;
      if (options.channel) document.getElementById("channel").value = options.channel;
      if (options.collector) document.getElementById("collector").value = options.collector;
      if (options.format_theme) document.getElementById("formatTheme").value = options.format_theme;
      if (options.cover_style) document.getElementById("coverStyle").value = options.cover_style;
    }

    function renderResult(result) {
      topicsEl.innerHTML = (result.topics || []).map(topic => `
        <div class="topic">
          <div class="topic-title" title="${escapeHtml(topic.optimized_title || topic.title)}">${escapeHtml(topic.optimized_title || topic.title)}</div>
          <div class="meta">
            <span>${escapeHtml(topic.source)}</span>
            <span>${escapeHtml(topic.score.level)} · ${topic.score.total}</span>
            ${topic.optimized_title ? `<span class="source-title" title="${escapeHtml(topic.title)}">来源：${escapeHtml(topic.title)}</span>` : ""}
          </div>
        </div>
      `).join("") || '<p class="empty">暂无选题。</p>';

      const previewPath = result.gzh_formatting && result.gzh_formatting.preview_html;
      previewEl.innerHTML = previewPath
        ? `<iframe src="/file?path=${encodeURIComponent(previewPath)}"></iframe><p class="path">${escapeHtml(previewPath)}</p>`
        : '<p class="empty">没有生成公众号预览。</p>';

      const coverPath = result.cover_image && result.cover_image.path;
      const draft = result.wechat_draft ? JSON.stringify(result.wechat_draft.response, null, 2) : "";
      assetsEl.innerHTML = [
        coverPath ? `<img class="cover" src="/file?path=${encodeURIComponent(coverPath)}"><p class="path">${escapeHtml(coverPath)}</p>` : "",
        draft ? `<pre>${escapeHtml(draft)}</pre>` : "",
        result.wechat_draft_error ? `<p class="error">${escapeHtml(result.wechat_draft_error)}</p>` : ""
      ].filter(Boolean).join("") || '<p class="empty">没有封面或草稿结果。</p>';
      renderSubmitGate(result);
    }

    function setBusy(isBusy) {
      stepButtons.forEach(button => button.disabled = isBusy);
      if (isBusy) {
        submitDraftButton.disabled = true;
      }
    }

    function statusLabel(status) {
      return statusLabels[status] || status || "";
    }

    function publishLabel(job) {
      if (job.status === "published_draft" || job.result?.wechat_draft) return "已发布";
      const attempts = job.publish_attempts || [];
      if (attempts.some(attempt => attempt.status === "failed")) return "发布失败";
      return "未发布";
    }

    function renderSubmitGate(result) {
      const hasPreview = Boolean(result.gzh_formatting && result.gzh_formatting.clean_html);
      const hasCover = Boolean(result.cover_image && result.cover_image.path);
      const submitted = Boolean(result.wechat_draft);
      submitDraftButton.disabled = submitted || !hasPreview || !hasCover || !currentJobId;
      if (submitted) {
        submitHint.textContent = "已提交到公众号草稿箱。";
      } else if (!hasPreview && !hasCover) {
        submitHint.textContent = "请先生成公众号预览和封面。";
      } else if (!hasPreview) {
        submitHint.textContent = "缺少公众号排版预览，请勾选公众号排版后重新运行。";
      } else if (!hasCover) {
        submitHint.textContent = "缺少封面图，请勾选生成封面后重新运行。";
      } else {
        submitHint.textContent = "预览确认无误后，再提交到公众号草稿箱。";
      }
    }

    function escapeHtml(value) {
      return String(value).replace(/[&<>"']/g, char => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#039;"
      }[char]));
    }

    function formatTime(value) {
      if (!value) return "";
      return new Date(value * 1000).toLocaleString("zh-CN", {hour12: false});
    }
  </script>
</body>
</html>"""


if __name__ == "__main__":
    raise SystemExit(main())
