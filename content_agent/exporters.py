from __future__ import annotations

from html import escape

from .models import WorkflowResult


def build_wechat_draft_payload(result: WorkflowResult, thumb_media_id: str, content_html: str | None = None) -> dict:
    if not thumb_media_id.strip():
        raise ValueError("thumb_media_id cannot be empty")

    topic = result.topics[0]
    html = content_html or _outline_to_html(result.wechat_outline)
    return {
        "articles": [
            {
                "title": topic.optimized_title,
                "thumb_media_id": thumb_media_id,
                "author": "",
                "digest": f"{result.keyword} 爆款选题草稿",
                "show_cover_pic": 1,
                "content": html,
                "content_source_url": topic.url or "",
                "need_open_comment": 1,
                "only_fans_can_comment": 0,
            }
        ]
    }


def export_xhs_markdown(result: WorkflowResult) -> str:
    topic = result.topics[0]
    return "\n".join(
        [
            "# 小红书发布包",
            "",
            f"关键词：{result.keyword}",
            f"推荐选题：{topic.optimized_title}",
            f"来源标题：{topic.title}",
            f"爆款评分：{topic.score.total} / {topic.score.level}",
            "",
            "## 正文",
            result.xhs_package,
            "",
            "## 封面",
            result.cover_prompt,
            "",
            "## 风险检查",
            *[f"- {note}" for note in topic.risk_notes],
        ]
    )


def _outline_to_html(outline: str) -> str:
    paragraphs = [line.strip() for line in outline.splitlines() if line.strip()]
    return "".join(f"<p>{escape(paragraph)}</p>" for paragraph in paragraphs)
