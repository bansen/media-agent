from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from typing import Literal


ContentChannel = Literal["wechat", "xiaohongshu"]


@dataclass(frozen=True)
class CandidateContent:
    title: str
    source: str
    url: str | None
    heat: float
    interaction: float
    hook: float
    pain: float
    reuse: float
    material: float
    summary: str = ""


@dataclass(frozen=True)
class TopicScore:
    total: float
    level: str
    reasons: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class TopicBrief:
    title: str
    optimized_title: str
    score: TopicScore
    source: str
    url: str | None
    platform_fit: list[ContentChannel]
    angle: str
    material_needs: list[str]
    risk_notes: list[str]
    source_summary: str = ""
    title_candidates: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class WorkflowResult:
    keyword: str
    expanded_keywords: list[str]
    topics: list[TopicBrief]
    wechat_outline: str
    xhs_package: str
    cover_prompt: str
    creative_brief: Any | None = None
    cover_strategy: dict[str, str] = field(default_factory=dict)
    content_plan: dict[str, Any] = field(default_factory=dict)
