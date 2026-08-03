from __future__ import annotations

from collections.abc import Callable
import re
from typing import Protocol

from .models import WorkflowResult


class TextGenerationProvider(Protocol):
    def generate(self, prompt: str) -> str:
        ...


def generate_llm_drafts(
    result: WorkflowResult,
    llm: TextGenerationProvider,
    progress: Callable[[str], None] | None = None,
) -> dict[str, str]:
    topic = result.topics[0]
    prompts = {
        "wechat_article": _wechat_prompt(result),
        "xhs_note": _xhs_prompt(result),
    }
    drafts = {}
    for name, prompt in prompts.items():
        if progress:
            progress(f"Generating {name} with LLM")
        generated = llm.generate(prompt)
        if name == "wechat_article":
            generated = _force_markdown_title(generated, topic.optimized_title)
        drafts[name] = generated
    drafts["selected_topic"] = topic.optimized_title
    drafts["source_topic"] = topic.title
    return drafts


def _wechat_prompt(result: WorkflowResult) -> str:
    topic = result.topics[0]
    return "\n\n".join(
        [
            "你是公众号内容编辑，请生成一篇可进入草稿箱的中文长文。",
            result.wechat_outline,
            (
                "主题约束：必须围绕用户关键词、选中素材和推荐选题写；"
                f"文章一级标题必须严格使用《{topic.optimized_title}》；"
                f"正文需要解释素材《{topic.title}》与读者的关系；"
                "禁止泛化成 AI 学习、副业赚钱等无关主题。"
            ),
            "要求：标题克制但有点击欲；正文 1200-1800 字；使用小标题；禁止承诺收益；不要承诺日更或固定更新频率。",
        ]
    )


def _xhs_prompt(result: WorkflowResult) -> str:
    return "\n\n".join(
        [
            "你是小红书图文笔记编辑，请生成适合手动发布的小红书内容。",
            result.xhs_package,
            "要求：标题 20 字内；正文生活化；包含标签；健康内容禁止诊断和治疗承诺。",
        ]
    )


def _force_markdown_title(markdown: str, title: str) -> str:
    clean_title = title.strip()
    if not clean_title:
        return markdown
    forced_heading = f"# {clean_title}"
    stripped = markdown.lstrip()
    if re.match(r"^#\s+", stripped):
        return re.sub(r"^#\s+.*(?:\n|$)", forced_heading + "\n", stripped, count=1)
    return f"{forced_heading}\n\n{stripped}"
