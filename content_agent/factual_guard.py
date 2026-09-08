from __future__ import annotations

FALL_TERMS = ("蒸发", "暴跌", "大跌", "跌停", "腰斩", "缩水")
RISE_TERMS = ("大涨", "暴涨", "飙涨", "涨停", "市值增加")
MARKET_SUBJECTS = ("市值", "股价")


def factual_conflicts(source: str, generated: str) -> list[str]:
    """Return factual conflicts when generated text invents or inverts source facts."""
    source_text = source or ""
    generated_text = generated or ""
    if not generated_text.strip():
        return []

    issues: list[str] = []
    source_fall = _present(source_text, FALL_TERMS)
    source_rise = _present(source_text, RISE_TERMS)
    generated_fall = _present(generated_text, FALL_TERMS)
    generated_rise = _present(generated_text, RISE_TERMS)

    unsupported_fall = [term for term in generated_fall if term not in source_text]
    if unsupported_fall and not source_fall:
        issues.append("素材没有下跌事实，不得写成" + "、".join(unsupported_fall))
    elif unsupported_fall and source_rise and not source_fall:
        issues.append("素材是上涨，不得写成" + "、".join(unsupported_fall))

    unsupported_rise = [term for term in generated_rise if term not in source_text]
    if unsupported_rise and source_fall and not source_rise:
        issues.append("素材是下跌，不得写成" + "、".join(unsupported_rise))
    elif unsupported_rise and not source_rise and _mentions_market(generated_text):
        issues.append("素材没有上涨事实，不得断言市值或股价" + "、".join(unsupported_rise))

    if _compresses_multi_day_move_into_one_day(source_text, generated_text):
        issues.append("素材不是一天内的市值变化，不得写成一天蒸发或一天大涨")

    return issues


def source_facts(*parts: str) -> str:
    return "\n".join(part.strip() for part in parts if part and part.strip())


def _present(text: str, terms: tuple[str, ...]) -> list[str]:
    return [term for term in terms if term in text]


def _mentions_market(text: str) -> bool:
    return any(term in text for term in MARKET_SUBJECTS)


def _compresses_multi_day_move_into_one_day(source: str, generated: str) -> bool:
    if "一天" not in generated or not _mentions_market(generated):
        return False
    if "一天" in source or "单日" in generated and "单日" in source:
        return False
    return any(marker in source for marker in ("个交易日", "近5", "五个交易日", "5个交易日"))
