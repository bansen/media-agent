from __future__ import annotations

import argparse
import json
import mimetypes
import threading
from dataclasses import asdict, dataclass, field, is_dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from time import time
from typing import Callable, Literal
from urllib import parse
from uuid import uuid4

from .collectors.free_hot import collect_free_hot_candidates
from .config import AgentConfig
from .cover_generation import generate_cover_image
from .formatters.wechat_gzh import format_wechat_markdown, write_gzh_outputs
from .generation import generate_llm_drafts
from .mock_data import get_mock_candidates
from .models import TopicBrief, TopicScore, WorkflowResult
from .wechat_publish import publish_wechat_draft
from .workflow import run_keyword_workflow


CollectorName = Literal["mock", "free_hot"]
ChannelName = Literal["wechat", "xiaohongshu"]
JobStatus = Literal["queued", "running", "completed", "failed"]


@dataclass(frozen=True)
class WebRunOptions:
    keyword: str
    channel: ChannelName = "wechat"
    collector: CollectorName = "free_hot"
    use_llm: bool = False
    format_gzh: bool = True
    generate_cover: bool = False
    submit_wechat_draft: bool = False
    wechat_content_html: str = ""
    wechat_cover_image: str = ""
    output_dir: Path = Path("output")


@dataclass
class WebJob:
    id: str
    options: WebRunOptions
    status: JobStatus = "queued"
    events: list[str] = field(default_factory=list)
    result: dict | None = None
    error: str = ""
    created_at: float = field(default_factory=time)
    updated_at: float = field(default_factory=time)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "status": self.status,
            "events": list(self.events),
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class JobStore:
    def __init__(self):
        self._jobs: dict[str, WebJob] = {}
        self._lock = threading.Lock()

    def create(self, options: WebRunOptions) -> WebJob:
        job = WebJob(id=uuid4().hex[:12], options=options)
        with self._lock:
            self._jobs[job.id] = job
        thread = threading.Thread(target=self._run_job, args=(job.id,), daemon=True)
        thread.start()
        return job

    def get(self, job_id: str) -> WebJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def _run_job(self, job_id: str) -> None:
        job = self.get(job_id)
        if job is None:
            return
        self._update(job_id, status="running", event="Job started")
        try:
            result = run_agent_workflow(job.options, progress=lambda message: self._update(job_id, event=message))
            self._update(job_id, status="completed", result=result, event="Job completed")
        except Exception as exc:
            self._update(job_id, status="failed", error=str(exc), event=f"Job failed: {exc}")

    def _update(
        self,
        job_id: str,
        status: JobStatus | None = None,
        event: str | None = None,
        result: dict | None = None,
        error: str | None = None,
    ) -> None:
        with self._lock:
            job = self._jobs[job_id]
            if status:
                job.status = status
            if event:
                job.events.append(event)
            if result is not None:
                job.result = result
            if error is not None:
                job.error = error
            job.updated_at = time()


def run_agent_workflow(options: WebRunOptions, progress: Callable[[str], None] | None = None) -> dict:
    _validate_options(options)
    emit = progress or (lambda message: None)

    emit(f"Collecting candidates with {options.collector}")
    candidates = _collect_candidates(options)
    emit(f"Collected {len(candidates)} candidates")
    emit("Scoring and building channel outputs")
    result = run_keyword_workflow(options.keyword, candidates=candidates, primary_channel=options.channel)
    payload = _to_jsonable(result)

    formatted_html = None
    if options.use_llm:
        emit("Loading config")
        config = AgentConfig.from_env_file()
        emit("Starting LLM draft generation")
        payload["llm_drafts"] = generate_llm_drafts(result, config.build_llm_provider(), progress=emit)
        emit("Finished LLM draft generation")

    if options.wechat_content_html:
        content_path = Path(options.wechat_content_html)
        emit(f"Loading existing WeChat HTML: {content_path}")
        formatted_html = content_path.read_text(encoding="utf-8")
        payload["wechat_content_html"] = str(content_path)
    elif options.format_gzh or options.submit_wechat_draft:
        emit("Formatting WeChat article")
        markdown = payload.get("llm_drafts", {}).get("wechat_article") or _wechat_outline_to_markdown(result.wechat_outline)
        formatted_html = format_wechat_markdown(markdown)
        paths = write_gzh_outputs(formatted_html, options.output_dir, _safe_basename(options.keyword))
        payload["gzh_formatting"] = {
            "theme": "摸鱼绿(moyu-green)",
            "clean_html": str(paths.clean_html),
            "preview_html": str(paths.preview_html),
        }
        emit("Finished WeChat formatting")

    cover_image_path = options.wechat_cover_image
    if cover_image_path:
        payload["cover_image"] = {
            "path": cover_image_path,
            "url": "",
            "model": "manual",
            "prompt": result.cover_prompt,
        }
    if options.generate_cover:
        emit("Generating cover image with Replicate")
        config = AgentConfig.from_env_file()
        generated_cover = generate_cover_image(
            prompt=result.cover_prompt,
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
        }
        emit("Finished cover generation")

    if options.submit_wechat_draft:
        emit("Submitting WeChat draft")
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
        emit("Finished WeChat draft submission")

    return payload


def submit_previewed_wechat_draft(job: WebJob, progress: Callable[[str], None] | None = None) -> dict:
    if job.status != "completed" or not job.result:
        raise ValueError("completed preview is required before submitting")

    result_payload = dict(job.result)
    html_path = _preview_clean_html_path(result_payload)
    cover_path = _preview_cover_path(result_payload)
    if not html_path:
        raise ValueError("formatted WeChat preview is required before submitting")
    if not cover_path:
        raise ValueError("cover image is required before submitting")

    emit = progress or (lambda message: None)
    emit("Submitting WeChat draft from preview")
    content_html = Path(html_path).read_text(encoding="utf-8")
    config = AgentConfig.from_env_file()
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


def render_index_html() -> str:
    return INDEX_HTML


class ContentAgentHandler(BaseHTTPRequestHandler):
    store = JobStore()

    def do_GET(self) -> None:
        parsed = parse.urlparse(self.path)
        if parsed.path == "/":
            self._send_html(render_index_html())
            return
        if parsed.path == "/api/config":
            self._send_json(
                {
                    "config": AgentConfig.from_env_file().redacted_status(),
                    "collectors": ["mock", "free_hot"],
                    "channels": ["wechat", "xiaohongshu"],
                }
            )
            return
        if parsed.path.startswith("/api/jobs/"):
            job_id = parsed.path.rsplit("/", 1)[-1]
            job = self.store.get(job_id)
            if job is None:
                self._send_json({"error": "job not found"}, status=HTTPStatus.NOT_FOUND)
                return
            self._send_json(job.to_dict())
            return
        if parsed.path == "/file":
            self._send_file(parsed.query)
            return
        self._send_json({"error": "not found"}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        parsed = parse.urlparse(self.path)
        if parsed.path.startswith("/api/jobs/") and parsed.path.endswith("/submit"):
            job_id = parsed.path.split("/")[-2]
            job = self.store.get(job_id)
            if job is None:
                self._send_json({"error": "job not found"}, status=HTTPStatus.NOT_FOUND)
                return
            try:
                result = submit_previewed_wechat_draft(
                    job,
                    progress=lambda message: self.store._update(job_id, event=message),
                )
                self.store._update(job_id, status="completed", result=result, event="WeChat draft submission completed")
                self._send_json(self.store.get(job_id).to_dict())
            except Exception as exc:
                self.store._update(job_id, status="failed", error=str(exc), event=f"WeChat draft submission failed: {exc}")
                self._send_json({"error": str(exc), "job": self.store.get(job_id).to_dict()}, status=HTTPStatus.BAD_REQUEST)
            return
        if parsed.path != "/api/jobs":
            self._send_json({"error": "not found"}, status=HTTPStatus.NOT_FOUND)
            return
        try:
            options = _options_from_payload(self._read_json())
            job = self.store.create(options)
            self._send_json(job.to_dict(), status=HTTPStatus.ACCEPTED)
        except Exception as exc:
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)

    def log_message(self, format: str, *args) -> None:
        return

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw or "{}")

    def _send_html(self, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(HTTPStatus.OK)
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

    def _send_file(self, query: str) -> None:
        params = parse.parse_qs(query)
        raw_path = params.get("path", [""])[0]
        path = Path(raw_path)
        if not _is_safe_served_file(path):
            self._send_json({"error": "file is not allowed"}, status=HTTPStatus.BAD_REQUEST)
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
        collector=payload.get("collector", "free_hot"),
        use_llm=bool(payload.get("use_llm", False)),
        format_gzh=bool(payload.get("format_gzh", True)),
        generate_cover=bool(payload.get("generate_cover", False)),
        submit_wechat_draft=bool(payload.get("submit_wechat_draft", False)),
        wechat_content_html=str(payload.get("wechat_content_html", "")).strip(),
        wechat_cover_image=str(payload.get("wechat_cover_image", "")).strip(),
        output_dir=Path(str(payload.get("output_dir", "output")).strip() or "output"),
    )


def _validate_options(options: WebRunOptions) -> None:
    if not options.keyword:
        raise ValueError("keyword cannot be empty")
    if options.channel not in {"wechat", "xiaohongshu"}:
        raise ValueError("channel must be wechat or xiaohongshu")
    if options.collector not in {"mock", "free_hot"}:
        raise ValueError("collector must be mock or free_hot")
    if options.submit_wechat_draft and not options.wechat_cover_image and not options.generate_cover:
        raise ValueError("wechat_cover_image is required when submitting without generating a cover")


def _collect_candidates(options: WebRunOptions):
    if options.collector == "mock":
        return get_mock_candidates(options.keyword, channel=options.channel)
    config = AgentConfig.from_env_file()
    if options.collector == "free_hot":
        return collect_free_hot_candidates(options.keyword, config=config.build_free_hot_config())
    raise ValueError("collector must be mock or free_hot")


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
    .check {
      display: flex;
      align-items: center;
      gap: 10px;
      margin: 12px 0;
      color: var(--ink);
      font-size: 14px;
    }
    .check input { width: 18px; height: 18px; }
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
          <option value="free_hot" selected>free_hot 关键词免费源</option>
          <option value="mock">mock 本地样例</option>
        </select>

        <label class="check"><input id="useLlm" type="checkbox">生成内容</label>
        <label class="check"><input id="formatGzh" type="checkbox" checked>公众号排版</label>
        <label class="check"><input id="generateCover" type="checkbox">生成封面</label>

        <label for="wechatContentHtml">已有公众号 HTML</label>
        <input id="wechatContentHtml" placeholder="output/AI副业_排版_摸鱼绿(moyu-green).html">

        <label for="wechatCoverImage">已有封面图</label>
        <input id="wechatCoverImage" placeholder="output/AI副业_cover_wechat_thumb.jpg">

        <button id="runButton" type="submit">运行 Agent</button>
      </form>
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
    let currentJobId = "";

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      runButton.disabled = true;
      submitDraftButton.disabled = true;
      submitHint.textContent = "先生成预览，确认无误后再提交。";
      currentJobId = "";
      statusEl.textContent = "starting";
      eventsEl.innerHTML = "";
      topicsEl.innerHTML = '<p class="empty">正在收集和评分。</p>';
      previewEl.innerHTML = '<p class="empty">等待排版结果。</p>';
      assetsEl.innerHTML = '<p class="empty">等待封面或提交结果。</p>';

      const payload = {
        keyword: document.getElementById("keyword").value,
        channel: document.getElementById("channel").value,
        collector: document.getElementById("collector").value,
        use_llm: document.getElementById("useLlm").checked,
        format_gzh: document.getElementById("formatGzh").checked,
        generate_cover: document.getElementById("generateCover").checked,
        submit_wechat_draft: false,
        wechat_content_html: document.getElementById("wechatContentHtml").value,
        wechat_cover_image: document.getElementById("wechatCoverImage").value,
        output_dir: "output"
      };

      try {
        const response = await fetch("/api/jobs", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify(payload)
        });
        const job = await response.json();
        if (!response.ok) throw new Error(job.error || "启动失败");
        currentJobId = job.id;
        pollJob(job.id);
      } catch (error) {
        statusEl.textContent = "failed";
        eventsEl.innerHTML = `<p class="error">${escapeHtml(error.message)}</p>`;
        runButton.disabled = false;
      }
    });

    submitDraftButton.addEventListener("click", async () => {
      if (!currentJobId) return;
      submitDraftButton.disabled = true;
      submitHint.textContent = "正在提交到公众号草稿箱。";
      try {
        const response = await fetch(`/api/jobs/${currentJobId}/submit`, {method: "POST"});
        const payload = await response.json();
        const job = payload.job || payload;
        renderJob(job);
        if (!response.ok) throw new Error(payload.error || "提交失败");
      } catch (error) {
        submitHint.textContent = error.message;
      }
    });

    async function pollJob(jobId) {
      const response = await fetch(`/api/jobs/${jobId}`);
      const job = await response.json();
      renderJob(job);
      if (job.status === "queued" || job.status === "running") {
        setTimeout(() => pollJob(jobId), 1200);
      } else {
        runButton.disabled = false;
      }
    }

    function renderJob(job) {
      statusEl.textContent = job.status;
      eventsEl.innerHTML = (job.events || []).map(item => `<div class="event">${escapeHtml(item)}</div>`).join("");
      if (job.error) {
        eventsEl.innerHTML += `<p class="error">${escapeHtml(job.error)}</p>`;
      }
      if (job.result) renderResult(job.result);
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
  </script>
</body>
</html>"""


if __name__ == "__main__":
    raise SystemExit(main())
