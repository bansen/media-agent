from __future__ import annotations

from collections.abc import Callable
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
        drafts[name] = llm.generate(prompt)
    drafts["selected_topic"] = topic.optimized_title
    drafts["source_topic"] = topic.title
    return drafts


def _wechat_prompt(result: WorkflowResult) -> str:
    return "\n\n".join(
        [
            "你是公众号内容编辑，请生成一篇可进入草稿箱的中文长文。",
            result.wechat_outline,
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
