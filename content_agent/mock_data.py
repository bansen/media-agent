from __future__ import annotations

from .models import CandidateContent, ContentChannel


AI_SIDE_HUSTLE_CANDIDATES = [
    CandidateContent(
        title="普通人用 AI 做副业，最容易踩的 5 个坑",
        source="mock",
        url="https://mock.local/ai-side-hustle-avoid-pitfalls",
        heat=80,
        interaction=76,
        hook=90,
        pain=88,
        reuse=82,
        material=70,
    ),
    CandidateContent(
        title="下班后做副业前，先学会这 3 个 AI 工具",
        source="mock",
        url="https://mock.local/ai-tools-after-work",
        heat=74,
        interaction=69,
        hook=82,
        pain=80,
        reuse=84,
        material=78,
    ),
    CandidateContent(
        title="待业 30 天，我用 AI 重建学习和接单流程",
        source="mock",
        url="https://mock.local/ai-learning-freelance-flow",
        heat=71,
        interaction=73,
        hook=86,
        pain=84,
        reuse=76,
        material=74,
    ),
    CandidateContent(
        title="AI学习不是报课，普通人先跑通这 4 个场景",
        source="mock",
        url="https://mock.local/ai-learning-scenarios",
        heat=68,
        interaction=64,
        hook=78,
        pain=79,
        reuse=86,
        material=82,
    ),
]

HEALTH_CANDIDATES = [
    CandidateContent(
        title="职场女性的 5 个低成本养生习惯",
        source="mock",
        url="https://mock.local/working-women-health-habits",
        heat=78,
        interaction=80,
        hook=84,
        pain=88,
        reuse=90,
        material=72,
    ),
    CandidateContent(
        title="宝妈也能坚持的 10 分钟睡前放松清单",
        source="mock",
        url="https://mock.local/mom-night-routine",
        heat=76,
        interaction=82,
        hook=83,
        pain=86,
        reuse=88,
        material=75,
    ),
    CandidateContent(
        title="办公室久坐人群，一天 4 个时间点这样调整",
        source="mock",
        url="https://mock.local/office-health-routine",
        heat=73,
        interaction=78,
        hook=80,
        pain=87,
        reuse=85,
        material=77,
    ),
    CandidateContent(
        title="气色变好的不是贵补品，是这些日常小习惯",
        source="mock",
        url="https://mock.local/daily-health-habits",
        heat=72,
        interaction=74,
        hook=86,
        pain=82,
        reuse=89,
        material=70,
    ),
]


def get_mock_candidates(keyword: str, channel: ContentChannel = "wechat") -> list[CandidateContent]:
    normalized = keyword.strip().lower()
    if not normalized:
        raise ValueError("keyword cannot be empty")

    if channel == "xiaohongshu" or any(word in normalized for word in ["养生", "健康", "女性", "宝妈"]):
        return list(HEALTH_CANDIDATES)
    if any(word in normalized for word in ["ai", "副业", "赚钱", "学习", "deepseek"]):
        return list(AI_SIDE_HUSTLE_CANDIDATES)
    return list(AI_SIDE_HUSTLE_CANDIDATES if channel == "wechat" else HEALTH_CANDIDATES)
