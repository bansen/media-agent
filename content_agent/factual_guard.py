from __future__ import annotations

import re

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

    issues.extend(_score_margin_conflicts(source_text, generated_text))
    if "不明原因肺炎" in source_text and "鼠疫" in source_text:
        if _plague_exclusion_claims(generated_text) and not _plague_exclusion_claims(source_text):
            issues.append("原文仅诊断不明原因肺炎，未发现相关微生物不能升级为非鼠疫感染、排除鼠疫或辟谣鼠疫死亡；保留病因未明及消息归属")
    return issues


def _plague_exclusion_claims(text: str) -> bool:
    pattern = r"排除(?:了)?鼠疫|(?:并非|而非|不是|非)鼠疫(?:感染)?|(?:否认|未)感染鼠疫|否认鼠疫感染|辟谣鼠疫(?:感染|死亡)?|鼠疫(?:感染|死亡)?(?:已被|已)?辟谣"
    for match in re.finditer(pattern, text):
        prefix = re.split(r"[，。；\n]", text[max(0, match.start()-24):match.start()])[-1]
        if not re.search(r"(?:未|没有|不)$|(?:不能|不可|尚未|并未|无法|不代表|不等于|未能|没有证据)[^，。；\n]{0,10}$", prefix):
            return True
    return False


def _score_margin_conflicts(source: str, generated: str) -> list[str]:
    """Check explicit largest-margin claims only when a score list is available."""
    if "比分" not in source:
        return []
    score = re.compile(r"(?<!\d)(\d{1,2})\s*(?:比|[-–:：])\s*(\d{1,2})(?!\d)")
    # Require a delimited list; avoid combining unrelated scores from page chrome.
    lists = re.findall(r"\d{1,2}\s*(?:比|[-–:：])\s*\d{1,2}(?:\s*[、，,]\s*\d{1,2}\s*(?:比|[-–:：])\s*\d{1,2}){2,}", source)
    if len(lists) != 1:
        return []
    pairs = [(int(a), int(b)) for a, b in score.findall(lists[0])]
    largest = max(abs(a - b) for a, b in pairs)
    sentences = re.split(r"[。！？\n]", generated)
    for index, sentence in enumerate(sentences):
        if not re.search(r"分差最大|最大分差", sentence) or re.search(r"不|并非|未必|是否|吗", sentence):
            continue
        matches = score.findall(sentence)
        if not matches and index and re.search(r"这|决胜局|末局", sentence):
            matches = score.findall(sentences[index - 1])
        if not matches:
            continue
        a, b = map(int, matches[-1])
        if (a, b) in pairs and abs(a - b) < largest:
            return [f"比分计算错误：{a}比{b}的分差是{abs(a-b)}，原文比分最大分差为{largest}，不能称为最大分差"]
    return []


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
