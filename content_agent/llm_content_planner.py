from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import json
import re
from typing import Protocol

from .models import ContentChannel, TopicBrief, WorkflowResult
from .prompts import build_cover_prompt_from_strategy, build_cover_strategy, build_wechat_outline, build_xhs_package
from .factual_guard import factual_conflicts, source_facts


FORBIDDEN_TITLE_TERMS = [
    "README",
    "github.com",
    "项目分享",
    "项目资料",
    "值不值得试",
    "值不值得看",
    "核心场景",
    "使用门槛",
    "实际价值在这里",
    "先看定位",
]


class TextGenerationProvider(Protocol):
    def generate(self, prompt: str) -> str:
        ...


@dataclass(frozen=True)
class LLMEditorialPlan:
    core_topic: str
    target_audience: str
    pain_point: str
    core_value: str
    key_points: list[str]
    article_structure: list[str]
    cover_concept: str
    titles: list[str]
    selected_title: str


def generate_llm_content_plan(
    llm: TextGenerationProvider,
    result: WorkflowResult,
    channel: ContentChannel,
) -> LLMEditorialPlan:
    if not result.topics:
        raise ValueError("生成内容策划前必须先选中素材")
    prompt = _planning_prompt(result, channel)
    response = llm.generate(prompt)
    try:
        plan = parse_llm_content_plan(response, channel)
        _reject_invented_facts(result, plan)
        return plan
    except ValueError as exc:
        correction_prompt = "\n\n".join(
            [
                prompt,
                f"上一次内容策划不合格：{exc}",
                "请修正所有字段和标题，重新输出完整 JSON。不要解释，不要只返回修改过的字段。",
                "用户提示词只是选题角度，不能当作事实；涨跌、金额、时间和主体必须与素材一致，素材没写的不要补。",
            ]
        )
        plan = parse_llm_content_plan(llm.generate(correction_prompt), channel)
        _reject_invented_facts(result, plan)
        return plan


def parse_llm_content_plan(response: str, channel: ContentChannel) -> LLMEditorialPlan:
    payload = _parse_json_object(response)
    required_strings = ["core_topic", "target_audience", "pain_point", "core_value", "cover_concept", "selected_title"]
    for field_name in required_strings:
        if not str(payload.get(field_name) or "").strip():
            raise ValueError(f"DeepSeek 内容策划缺少字段：{field_name}")
    key_points = _string_list(payload.get("key_points"), "key_points", minimum=3)
    article_structure = _string_list(payload.get("article_structure"), "article_structure", minimum=4)
    raw_titles = _string_list(payload.get("titles"), "titles", minimum=5)
    selected_title = str(payload["selected_title"]).strip()
    if selected_title not in raw_titles:
        raise ValueError("DeepSeek 最佳标题必须存在于候选标题中")
    titles = []
    for title in raw_titles:
        if _title_is_overlong(title, channel):
            continue
        _validate_title(title, channel)
        titles.append(title)
    if not titles:
        title_limit = _title_limit(channel)
        raise ValueError(f"DeepSeek 返回的所有标题都超过 {title_limit} 个字符")
    if selected_title not in titles:
        selected_title = titles[0]
    plan = LLMEditorialPlan(
        core_topic=str(payload["core_topic"]).strip(),
        target_audience=str(payload["target_audience"]).strip(),
        pain_point=str(payload["pain_point"]).strip(),
        core_value=str(payload["core_value"]).strip(),
        key_points=key_points,
        article_structure=article_structure,
        cover_concept=str(payload["cover_concept"]).strip(),
        titles=titles,
        selected_title=selected_title,
    )
    return plan



def original_prompt_title(result: WorkflowResult) -> str:
    """Use the user's creative prompt / topic line as the published article title."""
    lines = [line.strip() for line in (result.keyword or "").splitlines() if line.strip()]
    for line in lines:
        if line.startswith(("http://", "https://")):
            continue
        return line
    return lines[0] if lines else ""


def apply_llm_content_plan(
    result: WorkflowResult,
    plan: LLMEditorialPlan,
    channel: ContentChannel,
    *,
    use_prompt_as_title: bool = False,
) -> WorkflowResult:
    if not result.topics:
        raise ValueError("应用内容策划前必须先选中素材")
    current = result.topics[0]
    # Only briefing topics should lock the published H1 to the prompt text.
    # Manual keyword / creative prompts keep DeepSeek's selected_title.
    if use_prompt_as_title:
        article_title = original_prompt_title(result) or plan.selected_title
        title_candidates = [
            {"title": article_title, "score": 1000.0, "reason": "简报选题：沿用创作提示词原标题"}
        ]
        title_candidates.extend(
            {
                "title": title,
                "score": float(100 - index * 3),
                "reason": "DeepSeek 基于素材核心内容生成（仅备选）",
            }
            for index, title in enumerate(plan.titles)
            if title != article_title
        )
    else:
        article_title = plan.selected_title
        title_candidates = [
            {"title": title, "score": float(100 - index * 3), "reason": "DeepSeek 基于素材核心内容生成"}
            for index, title in enumerate(plan.titles)
        ]
    selected = replace(
        current,
        optimized_title=article_title,
        angle=f"围绕“{plan.core_topic}”展开，突出“{plan.core_value}”，写给{plan.target_audience}。",
        title_candidates=title_candidates,
    )
    topics: list[TopicBrief] = [selected, *result.topics[1:]]
    strategy = build_cover_strategy(selected, result.creative_brief, channel=channel)
    strategy.update(
        {
            "core_message": plan.core_value,
            "audience": plan.target_audience,
            "scene": plan.cover_concept,
            "subject": plan.cover_concept,
        }
    )
    return replace(
        result,
        topics=topics,
        wechat_outline=build_wechat_outline(selected, keyword=result.keyword),
        xhs_package=build_xhs_package(selected),
        cover_strategy=strategy,
        cover_prompt=build_cover_prompt_from_strategy(selected, strategy, channel=channel),
        content_plan=asdict(plan),
    )



def _reject_invented_facts(result: WorkflowResult, plan: LLMEditorialPlan) -> None:
    topic = result.topics[0]
    generated = "\n".join(
        [
            plan.core_topic,
            plan.pain_point,
            plan.core_value,
            plan.selected_title,
            *plan.key_points,
            *plan.titles,
            *plan.article_structure,
        ]
    )
    issues = factual_conflicts(source_facts(topic.title, topic.source_summary), generated)
    if issues:
        raise ValueError("内容策划与素材事实冲突：" + "；".join(issues))


def _planning_prompt(result: WorkflowResult, channel: ContentChannel) -> str:
    topic = result.topics[0]
    title_limit = 20 if channel == "xiaohongshu" else 34
    return "\n".join(
        [
            "你是资深中文自媒体总编。请先做内容策划，不要写正文。",
            "只根据素材标题和素材正文摘要提炼事实，不得臆造项目功能、数据、用户评价或收益。",
            "用户提示词只是选题角度，不是事实来源。素材写大涨就不得写成蒸发、暴跌或大跌；素材写下跌就不得写成大涨。",
            "金额、时间范围和主体必须与素材一致。素材没写的数字、一天内涨跌、因果不要补。",
            f"发布渠道：{channel}",
            f"用户提示词：{result.keyword}",
            f"来源标题：{topic.title}",
            f"来源链接：{topic.url or '无'}",
            "素材正文摘要：",
            topic.source_summary.strip() or "未提供摘要。只能使用来源标题中的事实，用户提示词不能当作事实。",
            "",
            "请输出 5 个差异明显、体现具体痛点/能力/结果的候选标题，并选择最佳标题。",
            "所有标题必须使用中文表达；可以保留必要的产品名、AI、PPT、Agent 等专有名词。",
            f"每个标题不超过 {title_limit} 个字符。",
            "标题不得包含链接、README、仓库路径、项目分享、项目资料、值不值得试、核心场景、使用门槛等来源或模板话术。",
            "不要为了制造钩子虚构数字、效果、对比或用户行为。",
            "文章结构必须根据素材本身设计，不能固定套用项目定位、核心场景、使用门槛三段式。",
            "cover_concept 必须描述与核心内容直接相关的具体主体和场景，禁止默认办公桌、电脑或抽象 Agent 节点图。",
            "",
            "只输出 JSON，不要 Markdown、解释或前后缀。字段必须完整：",
            '{"core_topic":"","target_audience":"","pain_point":"","core_value":"","key_points":["","",""],"article_structure":["","","",""],"cover_concept":"","titles":["","","","",""],"selected_title":""}',
        ]
    )


def _parse_json_object(response: str) -> dict:
    clean = response.strip()
    clean = re.sub(r"^```(?:json)?\s*", "", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\s*```$", "", clean)
    start = clean.find("{")
    end = clean.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("DeepSeek 内容策划没有返回有效 JSON")
    try:
        parsed = json.loads(clean[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ValueError(f"DeepSeek 内容策划 JSON 解析失败：{exc.msg}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("DeepSeek 内容策划必须返回 JSON 对象")
    return parsed


def _string_list(value: object, field_name: str, minimum: int) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"DeepSeek 内容策划字段 {field_name} 必须是数组")
    items = [str(item).strip() for item in value if str(item).strip()]
    if len(items) < minimum:
        raise ValueError(f"DeepSeek 内容策划字段 {field_name} 至少需要 {minimum} 项")
    return items


def _validate_title(title: str, channel: ContentChannel) -> None:
    if not re.search(r"[\u4e00-\u9fff]", title):
        raise ValueError(f"DeepSeek 标题必须包含中文：{title}")
    forbidden = next((term for term in FORBIDDEN_TITLE_TERMS if term.lower() in title.lower()), "")
    if forbidden:
        raise ValueError(f"DeepSeek 标题包含模板化禁用词“{forbidden}”：{title}")
    title_limit = _title_limit(channel)
    if len(title) > title_limit:
        raise ValueError(f"DeepSeek 标题超过 {title_limit} 个字符：{title}")


def _title_is_overlong(title: str, channel: ContentChannel) -> bool:
    return len(title) > _title_limit(channel)


def _title_limit(channel: ContentChannel) -> int:
    return 20 if channel == "xiaohongshu" else 34
