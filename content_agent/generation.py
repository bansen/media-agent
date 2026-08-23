from __future__ import annotations

from collections.abc import Callable
import re
from typing import Protocol

from .content_planner import ContentPlan, build_content_plan
from .models import WorkflowResult
from .skill_loader import load_content_skill


class TextGenerationProvider(Protocol):
    def generate(self, prompt: str) -> str:
        ...


def generate_llm_drafts(
    result: WorkflowResult,
    llm: TextGenerationProvider,
    progress: Callable[[str], None] | None = None,
) -> dict[str, str]:
    topic = result.topics[0]
    plan = build_content_plan(topic, result.keyword)
    channel = _result_channel(result)
    prompts = {}
    if channel == "xiaohongshu":
        prompts["xhs_note"] = _xhs_prompt(result)
    else:
        prompts["wechat_article"] = _wechat_prompt(result)
    drafts = {}
    for name, prompt in prompts.items():
        if progress:
            progress(f"Generating {name} with LLM")
        generated = llm.generate(prompt)
        if name == "wechat_article":
            issues = _wechat_alignment_issues(generated, plan)
            if issues:
                if progress:
                    progress("Rewriting off-topic WeChat draft")
                correction_prompt = "\n\n".join(
                    [
                        prompt,
                        "上一次正文偏离项目主题，必须整篇重写，不能只补一段。",
                        "偏题原因：" + "；".join(issues),
                        "重写要求：严格按照内容运营蓝图逐节展开，只输出完整 Markdown 正文。",
                    ]
                )
                generated = llm.generate(correction_prompt)
                remaining_issues = _wechat_alignment_issues(generated, plan)
                if remaining_issues:
                    raise RuntimeError("公众号正文主题校验失败：" + "；".join(remaining_issues))
            generated = _force_markdown_title(generated, topic.optimized_title)
        drafts[name] = generated
    drafts["selected_topic"] = topic.optimized_title
    drafts["source_topic"] = topic.title
    return drafts


def _wechat_alignment_issues(markdown: str, plan: ContentPlan) -> list[str]:
    if plan.project_kind != "creator_video_tool":
        return []
    video_terms = ["短视频", "视频脚本", "素材", "配音", "字幕", "背景音乐", "成片", "横竖屏", "批量"]
    agent_drift_terms = ["Agent 跑偏", "遗忘上下文", "长期记忆", "上下文管理", "任务控制"]
    video_hits = sum(term in markdown for term in video_terms)
    drift_hits = sum(term in markdown for term in agent_drift_terms)
    issues = []
    if video_hits < 3:
        issues.append("没有覆盖从视频脚本、素材、配音字幕到高清成片的短视频链路")
    if drift_hits >= 2:
        issues.append("错误写成了 Agent 记忆或上下文管理文章")
    return issues


def _result_channel(result: WorkflowResult) -> str:
    brief = result.creative_brief
    if isinstance(brief, dict):
        return str(brief.get("channel") or "wechat")
    return str(getattr(brief, "channel", "wechat") or "wechat")


def _wechat_prompt(result: WorkflowResult) -> str:
    topic = result.topics[0]
    plan = build_content_plan(topic, result.keyword)
    opening_rule = []
    if "工具接入教程" in result.wechat_outline:
        opening_rule.append("开头必须直接进入工具接入场景，第一段说明要接入什么、验证什么、读者能得到什么。")
        opening_rule.append("不要写“学 AI 做作品”、副业、面试、HR、读者投稿等泛用故事。")
    if plan.content_type == "github_project_share":
        if plan.project_kind == "creator_video_tool":
            opening_rule.append("开头必须写短视频创作者在脚本、素材、配音、字幕和剪辑之间切换的真实痛点。")
            opening_rule.append("正文必须完整解释视频脚本、匹配素材、配音字幕、背景音乐到高清成片的链路。")
            opening_rule.append("不要改写成 Agent 跑偏、记忆或上下文管理，也不要虚构无人值守收益。")
        elif plan.project_kind == "agent_framework":
            opening_rule.append("开头必须先写 Agent 使用痛点，不要用“今天分享一个 GitHub 链接/项目”开场。")
        else:
            opening_rule.append("开头必须从 README 对应的真实使用场景切入，不要套用 Agent 或副业故事。")
        opening_rule.append("正文可以提项目名，但不要在正文中反复展示 URL；项目地址只放在文末一次。")
    if plan.content_type == "knowledge_workflow":
        opening_rule.append("正文主线必须依次覆盖资料进入、Codex 整理、Obsidian 链接沉淀和检索复用。")
        opening_rule.append("Codex、Obsidian、个人知识库缺一不可；不要改写成泛泛的 AI 工具介绍或 Codex 入门。")
    material_summary = []
    if topic.source_summary.strip():
        material_summary.append("素材摘要：")
        material_summary.append(topic.source_summary.strip())
    return "\n\n".join(
        [
            "你是公众号内容编辑，请生成一篇可进入草稿箱的中文长文。",
            result.wechat_outline,
            *material_summary,
            (
                "主题约束：必须围绕用户关键词、选中素材和推荐选题写；"
                f"文章一级标题必须严格使用《{topic.optimized_title}》；"
                f"正文需要解释素材《{topic.title}》与读者的关系；"
                "禁止泛化成 AI 学习、副业赚钱等无关主题。"
            ),
            (
                "内容质量红线：不要把用户提示词、搜索链接、来源标题当正文复制；"
                "不要连续两个小节重复同一观点；每个小标题下面必须提供新的信息、判断或行动；"
                "如果写卡片、清单或关键问题，数量必须和正文展开的点数一致。"
            ),
            (
                "输出格式：只输出 Markdown 正文，第一行必须是 # 标题；"
                "不要输出任何解释、确认语、分隔线、标题：、正文：、可复制到草稿箱等说明文字。"
            ),
            *opening_rule,
            "要求：标题克制但有点击欲；正文 1200-1800 字；使用小标题；禁止承诺收益；不要承诺日更或固定更新频率。",
        ]
    )


def _xhs_prompt(result: WorkflowResult) -> str:
    topic = result.topics[0]
    material = [f"选中素材：{topic.title}"]
    if topic.source_summary.strip():
        material.extend(["素材摘要：", topic.source_summary.strip()])
    return "\n\n".join(
        [
            "你是小红书图文笔记编辑，请生成适合手动发布的小红书内容。",
            "以下是必须遵循的小红书内容生成 Skill：",
            load_content_skill("xiaohongshu_content"),
            "以下是后续图文排版必须遵循的 Skill，请让正文编号结构可被逐点排版：",
            load_content_skill("xiaohongshu_layout"),
            *material,
            result.xhs_package,
            "要求：标题 20 字内；正文生活化；包含标签；健康内容禁止诊断和治疗承诺；输出只包含标题、正文、标签，不要输出封面图组或排版说明；正文主要方法使用连续编号。",
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
