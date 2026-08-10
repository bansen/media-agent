from __future__ import annotations

from .creative_brief import build_creative_brief, is_creative_prompt
from .keyword_expander import expand_keywords
from .keyword_intent import clean_search_keyword, parse_keyword_intent
from .models import CandidateContent, ContentChannel, TopicBrief, WorkflowResult
from .prompts import (
    build_cover_prompt_from_strategy,
    build_cover_strategy,
    build_wechat_outline,
    build_xhs_package,
)
from .scoring import score_candidate
from .title_optimizer import build_title_candidates, optimize_title


def run_keyword_workflow(
    keyword: str,
    candidates: list[CandidateContent],
    primary_channel: ContentChannel = "wechat",
    limit: int = 10,
) -> WorkflowResult:
    if not candidates:
        raise ValueError("candidates cannot be empty")

    intent = parse_keyword_intent(keyword)
    creative_brief = build_creative_brief(keyword, channel=primary_channel)
    expanded_keywords = expand_keywords(intent.topic or keyword, channel=primary_channel)
    ranked_topics = sorted(
        (_brief_for(candidate, keyword=keyword, primary_channel=primary_channel) for candidate in candidates),
        key=lambda item: item.score.total + _keyword_relevance_boost(keyword, item.title),
        reverse=True,
    )
    topics = _dedupe_topics_by_optimized_title(ranked_topics)
    selected = topics[0]
    cover_strategy = build_cover_strategy(selected, creative_brief, channel=primary_channel)

    return WorkflowResult(
        keyword=keyword,
        expanded_keywords=creative_brief.search_queries if is_creative_prompt(keyword) else expanded_keywords,
        topics=topics[:limit],
        wechat_outline=build_wechat_outline(selected, keyword=keyword),
        xhs_package=build_xhs_package(selected),
        cover_prompt=build_cover_prompt_from_strategy(selected, cover_strategy, channel=primary_channel),
        creative_brief=creative_brief,
        cover_strategy=cover_strategy,
    )


def _brief_for(candidate: CandidateContent, keyword: str, primary_channel: ContentChannel = "wechat") -> TopicBrief:
    score = score_candidate(candidate)
    intent = parse_keyword_intent(keyword)
    is_health = _is_health_topic(candidate.title, primary_channel)
    optimized_title = optimize_title(candidate.title, primary_channel, keyword=keyword)
    title_candidates = build_title_candidates(candidate.title, primary_channel, keyword=keyword)
    platform_fit: list[ContentChannel] = ["xiaohongshu"] if is_health else ["wechat"]
    if not is_health and score.total >= 75:
        platform_fit.append("xiaohongshu")

    return TopicBrief(
        title=candidate.title,
        optimized_title=optimized_title,
        score=score,
        source=candidate.source,
        url=candidate.url,
        platform_fit=platform_fit,
        angle=_angle_for(optimized_title, is_health, keyword),
        material_needs=_material_needs_for(is_health, intent.task_kind),
        risk_notes=_risk_notes_for(is_health),
        title_candidates=title_candidates,
    )


def _dedupe_topics_by_optimized_title(topics: list[TopicBrief]) -> list[TopicBrief]:
    unique: list[TopicBrief] = []
    seen: set[str] = set()
    for topic in topics:
        key = _normalize_match_text(topic.optimized_title)
        if key in seen:
            continue
        seen.add(key)
        unique.append(topic)
    return unique


def _angle_for(title: str, is_health: bool, keyword: str = "") -> str:
    if is_health:
        return f"把《{title}》改成职场女性和宝妈都能立刻收藏的生活习惯清单。"
    intent = parse_keyword_intent(keyword)
    if intent.task_kind == "tool_integration":
        focus = "、".join([*intent.entities, *intent.modifiers])
        return f"把《{title}》写成工具接入教程，围绕 {focus} 做清晰步骤、验证结果和避坑提醒。"
    return f"把《{title}》改成普通人能执行的副业/AI学习方法拆解。"


def _material_needs_for(is_health: bool, task_kind: str = "general") -> list[str]:
    if is_health:
        return ["生活场景案例", "通用健康常识来源", "可执行习惯清单"]
    if task_kind == "tool_integration":
        return ["官方文档或 API 说明", "配置步骤截图", "识图验证样例", "常见报错和解决方法"]
    return ["真实工具截图", "普通人案例", "步骤清单", "失败避坑"]


def _risk_notes_for(is_health: bool) -> list[str]:
    if is_health:
        return ["避免医疗诊断", "避免治疗承诺", "建议保留人工审核"]
    return ["避免承诺收益", "避免夸大变现", "建议补充真实案例来源"]


def _is_health_topic(title: str, primary_channel: ContentChannel) -> bool:
    if primary_channel == "xiaohongshu":
        return True
    health_terms = [
        "养生",
        "女性",
        "宝妈",
        "健康",
        "久坐",
        "气色",
        "睡前",
        "放松",
        "办公室",
        "习惯",
    ]
    return any(term in title for term in health_terms)


def _keyword_relevance_boost(keyword: str, title: str) -> float:
    intent = parse_keyword_intent(keyword)
    cleaned_keyword = clean_search_keyword(keyword).strip().lower()
    cleaned_title = title.strip().lower()
    if not cleaned_keyword:
        return 0
    intent_boost = _intent_coverage_boost(intent.entities, intent.modifiers, cleaned_title)
    if cleaned_keyword in cleaned_title:
        return 35 + intent_boost

    terms = [term for term in _keyword_terms(cleaned_keyword) if term in cleaned_title]
    return min(24, len(terms) * 8) + intent_boost


def _intent_coverage_boost(entities: list[str], modifiers: list[str], title: str) -> float:
    if not entities and not modifiers:
        return 0
    normalized_title = _normalize_match_text(title)
    entity_hits = sum(1 for entity in entities if _normalize_match_text(entity) in normalized_title)
    modifier_hits = sum(1 for modifier in modifiers if _normalize_match_text(modifier) in normalized_title)
    boost = entity_hits * 12 + modifier_hits * 6
    if entities and entity_hits == len(entities):
        boost += 16
    return boost


def _keyword_terms(keyword: str) -> list[str]:
    parts = [part for part in keyword.replace("/", " ").replace("-", " ").split() if len(part) >= 2]
    if parts:
        return parts
    if len(keyword) <= 2:
        return [keyword]
    return [keyword[index : index + 2] for index in range(0, len(keyword) - 1)]


def _normalize_match_text(text: str) -> str:
    return text.lower().replace("-", "").replace("_", "").replace(" ", "")
