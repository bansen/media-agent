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
            (
                "输出格式：只输出 Markdown 正文，第一行必须是 # 标题；"
                "不要输出任何解释、确认语、分隔线、标题：、正文：、可复制到草稿箱等说明文字。"
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
    stripped = _strip_wechat_article_noise(markdown)
    if re.match(r"^#\s+", stripped):
        return re.sub(r"^#\s+.*(?:\n|$)", forced_heading + "\n", stripped, count=1)
    return f"{forced_heading}\n\n{stripped}"


def _strip_wechat_article_noise(markdown: str) -> str:
    stripped = markdown.strip()
    stripped = re.sub(r"^```(?:markdown)?\s*", "", stripped, flags=re.IGNORECASE)
    stripped = re.sub(r"\s*```$", "", stripped)

    body_lines: list[str] = []
    skipping_prefix = True
    for line in stripped.splitlines():
        clean_line = line.strip()
        if skipping_prefix:
            if not clean_line or clean_line in {"---", "----", "——"}:
                continue
            if _is_assistant_preamble(clean_line):
                continue
            if re.match(r"^(?:标题|文章标题|公众号标题|正文)\s*[:：]", clean_line):
                continue
            if re.match(r"^#\s+", clean_line):
                continue
            skipping_prefix = False
        body_lines.append(line)

    return "\n".join(body_lines).strip()


def _is_assistant_preamble(line: str) -> bool:
    return bool(
        re.match(r"^(好的|当然|可以|以下是|这是|下面是)", line)
        and any(term in line for term in ["公众号文章", "准备", "按照要求", "草稿箱", "复制"])
    )
