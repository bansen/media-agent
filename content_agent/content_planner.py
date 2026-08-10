from __future__ import annotations

from dataclasses import dataclass
import re

from .models import TopicBrief


@dataclass(frozen=True)
class ContentPlan:
    content_type: str
    project_name: str = ""
    reader_hook: str = ""
    article_promise: str = ""
    title_angles: list[str] = None
    structure: str = ""
    cover_scene: str = ""


def build_content_plan(topic: TopicBrief, prompt: str = "") -> ContentPlan:
    text = f"{topic.title} {topic.source_summary} {prompt}"
    if _is_github_project(text, topic.url):
        project_name = _github_project_name(text, topic.url) or "这个开源项目"
        agent_focus = "Agent" if re.search(r"\bagent\b|智能体|Codex|Claude", text, flags=re.IGNORECASE) else "开源项目"
        return ContentPlan(
            content_type="github_project_share",
            project_name=project_name,
            reader_hook=f"{agent_focus} 总是跑偏、断上下文、做不成长任务",
            article_promise="帮读者看懂这个项目解决的真实问题、适合谁用，以及值不值得收藏。",
            title_angles=[
                f"{agent_focus} 总是跑偏？这个开源项目给了一套工作系统",
                f"别只会写 Prompt，{agent_focus} 真正缺的是这套工作流",
                f"让 {agent_focus} 连续工作，这个开源项目的思路值得看",
                f"做 {agent_focus} 的人，应该看看这个开源项目",
                f"{agent_focus} 走向数字员工，差的可能不是模型",
            ],
            structure="结构：痛点开场 -> 项目一句话定位 -> 它解决的 3 个关键问题 -> 适合谁用 -> 怎么开始看 -> 项目地址与判断建议。",
            cover_scene=(
                "open-source agent system, abstract workflow nodes, automation timeline, "
                "connected task graph, clean technical interface, abstract product visualization"
            ),
        )
    return ContentPlan(content_type="general")


def strip_urls(text: str) -> str:
    clean = re.sub(r"https?://[^\s，。；、）)】\]\"'<>]+", "", text)
    clean = re.sub(r"^(?:写一篇|帮我写|分享|介绍|生成一篇)\s*", "", clean)
    clean = re.sub(r"(?:的)?(?:文章|内容|公众号文章)\s*$", "", clean)
    clean = re.sub(r"\s+", " ", clean)
    return clean.strip(" ，,。；;：:")


def _is_github_project(text: str, url: str | None) -> bool:
    return "github.com" in f"{text} {url or ''}".lower() or "GitHub 开源项目" in text


def _github_project_name(text: str, url: str | None) -> str:
    source = f"{url or ''} {text}"
    match = re.search(r"github\.com/([^/\s]+)/([^/\s?#]+)", source, flags=re.IGNORECASE)
    if match:
        return f"{match.group(1)}/{match.group(2).removesuffix('.git')}"
    match = re.search(r"GitHub 开源项目[:：]\s*([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)", text)
    return match.group(1) if match else ""
