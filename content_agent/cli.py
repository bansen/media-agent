from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, is_dataclass
from pathlib import Path

from .collectors.baidu_search import collect_baidu_search_candidates
from .collectors.source_urls import collect_source_url_candidates, resolve_source_urls
from .config import AgentConfig
from .cover_generation import generate_cover_image
from .cover_copy import build_image_prompt, prepare_cover_copy
from .formatters.wechat_gzh import format_wechat_markdown, write_gzh_outputs
from .generation import generate_llm_drafts
from .fact_review import FactReviewError
from .publication_review import ensure_article_review, retain_rejected_draft
from .keyword_seed import build_keyword_seed_candidates
from .llm_content_planner import apply_llm_content_plan, generate_llm_content_plan
from .wechat_publish import publish_wechat_draft
from .workflow import run_keyword_workflow


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the content-agent MVP workflow.")
    parser.add_argument("--keyword", required=True, help="Seed keyword, such as AI副业 or 养生.")
    parser.add_argument(
        "--channel",
        default="wechat",
        choices=["wechat", "xiaohongshu"],
        help="Primary channel profile for keyword expansion and cover prompt.",
    )
    parser.add_argument(
        "--collector",
        default="baidu_search",
        choices=["baidu_search"],
        help="Topic source collector. baidu_search uses Baidu Qianfan web search.",
    )
    parser.add_argument("--check-config", action="store_true", help="Print redacted configuration status.")
    parser.add_argument("--use-llm", action="store_true", help="Generate channel drafts with the configured LLM.")
    parser.add_argument("--format-gzh", action="store_true", help="Format the WeChat draft with gzh-design skill assets.")
    parser.add_argument("--generate-cover", action="store_true", help="Generate a cover image with the configured image provider.")
    parser.add_argument("--submit-wechat-draft", action="store_true", help="Submit the formatted WeChat article to draft box.")
    parser.add_argument("--wechat-content-html", help="Existing formatted WeChat HTML file to submit.")
    parser.add_argument("--wechat-cover-image", help="Local cover image path used as WeChat thumb material.")
    parser.add_argument(
        "--source-url",
        action="append",
        default=[],
        dest="source_urls",
        help="Source page URL to fetch directly (repeatable). Skips Baidu when provided.",
    )
    parser.add_argument(
        "--use-prompt-as-title",
        action="store_true",
        help="Briefing mode: keep creative prompt as the article title; requires --source-url or URLs in --keyword.",
    )
    parser.add_argument("--output-dir", default="output", help="Directory for generated files.")
    args = parser.parse_args(argv)

    if args.check_config:
        config = AgentConfig.from_env_file()
        print(json.dumps(config.redacted_status(), ensure_ascii=False, indent=2))
        return 0
    if args.generate_cover and not args.use_llm and not (args.channel == "wechat" and args.wechat_content_html):
        print("生成封面需要最终正文，请使用 --use-llm 或提供 --wechat-content-html。", file=sys.stderr)
        return 2
    if args.submit_wechat_draft and not args.wechat_cover_image and not args.generate_cover:
        print("--wechat-cover-image is required when --submit-wechat-draft is used without --generate-cover", file=sys.stderr)
        return 2

    candidates = _collect_candidates(
        args.keyword,
        args.channel,
        args.collector,
        source_urls=args.source_urls,
        use_prompt_as_title=args.use_prompt_as_title,
    )
    if not candidates and args.collector == "baidu_search" and not (
        args.use_prompt_as_title or resolve_source_urls(args.source_urls, args.keyword)
    ):
        _progress("Baidu search returned no candidates; using keyword seed topics")
        candidates = build_keyword_seed_candidates(args.keyword, args.channel)
    result = run_keyword_workflow(
        args.keyword,
        candidates=candidates,
        primary_channel=args.channel,
    )
    llm = None
    if args.use_llm:
        config = AgentConfig.from_env_file()
        _progress("Loaded config")
        llm = config.build_llm_provider()
        _progress("Generating content plan and Chinese titles with LLM")
        content_plan = generate_llm_content_plan(llm, result, channel=args.channel)
        result = apply_llm_content_plan(
            result,
            content_plan,
            channel=args.channel,
            use_prompt_as_title=args.use_prompt_as_title,
        )
        _progress("Finished LLM content planning")
    payload = _to_jsonable(result)
    if args.use_llm:
        _progress("Starting LLM draft generation")
        try:
            payload["llm_drafts"] = generate_llm_drafts(result, llm, progress=_progress)
        except FactReviewError as exc:
            retain_rejected_draft(payload, exc)
            payload["error"] = str(exc)
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 1
        _progress("Finished LLM draft generation")
    formatted_html = None
    if args.wechat_content_html:
        content_path = Path(args.wechat_content_html)
        _progress(f"Loading existing WeChat HTML: {content_path}")
        formatted_html = content_path.read_text(encoding="utf-8")
        payload["wechat_content_html"] = str(content_path)
    elif args.format_gzh or args.submit_wechat_draft:
        _progress("Formatting WeChat article with gzh-design")
        markdown = payload.get("llm_drafts", {}).get("wechat_article") or _wechat_outline_to_markdown(result.wechat_outline)
        formatted_html = format_wechat_markdown(markdown)
        paths = write_gzh_outputs(formatted_html, Path(args.output_dir), _safe_basename(args.keyword))
        payload["gzh_formatting"] = {
            "theme": "摸鱼绿(moyu-green)",
            "clean_html": str(paths.clean_html),
            "preview_html": str(paths.preview_html),
        }
        _progress("Finished gzh-design formatting")
    cover_image_path = args.wechat_cover_image
    if args.generate_cover:
        config = AgentConfig.from_env_file()
        if args.channel == "wechat":
            try:
                ensure_article_review(result, payload, config.build_llm_provider())
            except FactReviewError as exc:
                payload["error"] = str(exc)
                print(json.dumps(payload, ensure_ascii=False, indent=2))
                return 1
        _progress("正在根据最终正文提炼封面文案和画面")
        cover_copy = prepare_cover_copy(payload, args.channel, config.build_llm_provider())
        payload["cover_copy"] = _to_jsonable(cover_copy)
        payload["cover_prompt"] = build_image_prompt(cover_copy, args.channel, "business-tech")
        _progress(f"Generating cover image with {config.image_provider}")
        generated_cover = generate_cover_image(
            prompt=payload["cover_prompt"],
            output_dir=Path(args.output_dir),
            basename=_safe_basename(args.keyword),
            model=config.image_model,
            api_token=config.image_api_key,
            provider=config.image_provider,
            aspect_ratio="3:4" if args.channel == "xiaohongshu" else "16:9",
        )
        cover_image_path = str(generated_cover.path)
        payload["cover_image"] = {
            "path": str(generated_cover.path),
            "url": generated_cover.url,
            "model": generated_cover.model,
            "prompt": generated_cover.prompt,
            "headline": cover_copy.headline if args.channel == "wechat" else "",
        }
        _progress("Finished cover generation")
    if args.submit_wechat_draft:
        _progress("Submitting WeChat draft")
        config = AgentConfig.from_env_file()
        try:
            ensure_article_review(result, payload, config.build_llm_provider(), formatted_html or "")
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
            _progress("Finished WeChat draft submission")
        except Exception as exc:
            payload["wechat_draft_error"] = str(exc)
            _progress(f"WeChat draft submission failed: {exc}")
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 1
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0

def _to_jsonable(value):
    if is_dataclass(value):
        return _to_jsonable(asdict(value))
    if isinstance(value, list):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: _to_jsonable(item) for key, item in value.items()}
    return value


def _progress(message: str) -> None:
    print(f"[content-agent] {message}", file=sys.stderr, flush=True)


def _collect_candidates(
    keyword: str,
    channel: str,
    collector: str,
    source_urls: list[str] | None = None,
    use_prompt_as_title: bool = False,
):
    urls = resolve_source_urls(source_urls or [], keyword)
    if use_prompt_as_title or urls:
        if not urls:
            raise ValueError("简报选题已勾选但未提供原链接，请粘贴来源 URL")
        _progress(f"Fetching {len(urls)} source URL(s) directly")
        candidates = collect_source_url_candidates(urls, limit=10)
        _progress(f"Collected {len(candidates)} source URL candidates")
        return candidates
    config = AgentConfig.from_env_file()
    if collector == "baidu_search":
        _progress("Collecting Baidu search candidates")
        candidates = collect_baidu_search_candidates(keyword, api_key=config.baidu_search_api_key)
        _progress(f"Collected {len(candidates)} Baidu search candidates")
        return candidates
    raise ValueError("collector must be baidu_search")


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


if __name__ == "__main__":
    raise SystemExit(main())
