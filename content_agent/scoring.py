from __future__ import annotations

from .models import CandidateContent, TopicScore


WEIGHTS = {
    "heat": 0.30,
    "interaction": 0.20,
    "hook": 0.15,
    "pain": 0.15,
    "reuse": 0.10,
    "material": 0.10,
}

METRIC_LABELS = {
    "heat": "热度",
    "interaction": "互动",
    "hook": "标题钩子",
    "pain": "人群痛点",
    "reuse": "可复用度",
    "material": "素材可得性",
}


def score_candidate(candidate: CandidateContent) -> TopicScore:
    metrics = {
        "heat": candidate.heat,
        "interaction": candidate.interaction,
        "hook": candidate.hook,
        "pain": candidate.pain,
        "reuse": candidate.reuse,
        "material": candidate.material,
    }
    for name, value in metrics.items():
        if value < 0 or value > 100:
            raise ValueError(f"{name} must be between 0 and 100")

    total = round(sum(metrics[name] * weight for name, weight in WEIGHTS.items()), 2)
    reasons = [
        f"{METRIC_LABELS[name]} {metrics[name]:.0f} x {weight:.2f}"
        for name, weight in WEIGHTS.items()
        if metrics[name] >= 70
    ]
    if not reasons:
        reasons.append("暂无强爆款信号，建议仅记录观察")

    return TopicScore(total=total, level=_level_for(total), reasons=reasons)


def _level_for(total: float) -> str:
    if total >= 78:
        return "A"
    if total >= 65:
        return "B"
    if total >= 50:
        return "C"
    return "D"
