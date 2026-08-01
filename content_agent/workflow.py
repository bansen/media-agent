from __future__ import annotations

from .keyword_expander import expand_keywords
from .models import CandidateContent, ContentChannel, TopicBrief, WorkflowResult
from .prompts import (
    build_cover_prompt,
    build_wechat_outline,
    build_xhs_package,
)
from .scoring import score_candidate
from .title_optimizer import optimize_title


def run_keyword_workflow(
    keyword: str,
    candidates: list[CandidateContent],
    primary_channel: ContentChannel = "wechat",
    limit: int = 10,
) -> WorkflowResult:
    if not candidates:
        raise ValueError("candidates cannot be empty")

    expanded_keywords = expand_keywords(keyword, channel=primary_channel)
    topics = sorted(
        (_brief_for(candidate, keyword=keyword, primary_channel=primary_channel) for candidate in candidates),
        key=lambda item: item.score.total + _keyword_relevance_boost(keyword, item.title),
        reverse=True,
    )
    selected = topics[0]

    return WorkflowResult(
        keyword=keyword,
        expanded_keywords=expanded_keywords,
        topics=topics[:limit],
        wechat_outline=build_wechat_outline(selected),
        xhs_package=build_xhs_package(selected),
        cover_prompt=build_cover_prompt(selected, channel=primary_channel),
    )


def _brief_for(candidate: CandidateContent, keyword: str, primary_channel: ContentChannel = "wechat") -> TopicBrief:
    score = score_candidate(candidate)
    is_health = _is_health_topic(candidate.title, primary_channel)
    optimized_title = optimize_title(candidate.title, primary_channel, keyword=keyword)
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
        angle=_angle_for(optimized_title, is_health),
        material_needs=_material_needs_for(is_health),
        risk_notes=_risk_notes_for(is_health),
    )


def _angle_for(title: str, is_health: bool) -> str:
    if is_health:
        return f"把《{title}》改成职场女性和宝妈都能立刻收藏的生活习惯清单。"
    return f"把《{title}》改成普通人能执行的副业/AI学习方法拆解。"


def _material_needs_for(is_health: bool) -> list[str]:
    if is_health:
        return ["生活场景案例", "通用健康常识来源", "可执行习惯清单"]
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
    cleaned_keyword = keyword.strip().lower()
    cleaned_title = title.strip().lower()
    if not cleaned_keyword:
        return 0
    if cleaned_keyword in cleaned_title:
        return 35

    terms = [term for term in _keyword_terms(cleaned_keyword) if term in cleaned_title]
    return min(24, len(terms) * 8)


def _keyword_terms(keyword: str) -> list[str]:
    parts = [part for part in keyword.replace("/", " ").replace("-", " ").split() if len(part) >= 2]
    if parts:
        return parts
    if len(keyword) <= 2:
        return [keyword]
    return [keyword[index : index + 2] for index in range(0, len(keyword) - 1)]
