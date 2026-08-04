from __future__ import annotations

import re


def clean_search_keyword(keyword: str) -> str:
    entity = extract_keyword_entity(keyword)
    modifiers = extract_keyword_modifiers(keyword)
    parts = [entity, *[modifier for modifier in modifiers if modifier not in entity]]
    return " ".join(part for part in parts if part).strip() or keyword.strip()


def extract_keyword_entity(keyword: str) -> str:
    clean = _normalize_space(keyword)
    if not clean:
        return ""
    first_clause = re.split(r"[，,；;。]|\b(?:要|希望|突出|关注|侧重|重点)\b", clean, maxsplit=1)[0].strip()
    first_clause = re.sub(r"[（(].*?[）)]", "", first_clause).strip()
    first_clause = re.sub(r"(介绍|入门|教程|怎么用|如何用|是什么)$", "", first_clause, flags=re.IGNORECASE).strip()
    return _normalize_known_entity(first_clause)


def extract_keyword_modifiers(keyword: str) -> list[str]:
    clean = _normalize_space(keyword)
    modifiers: list[str] = []
    if "核心能力" in clean:
        modifiers.append("核心能力")
    if "视频" in clean:
        modifiers.append("视频")
    if "参数" in clean:
        modifiers.append("参数")
    if "API" in clean or "api" in clean:
        modifiers.append("API")
    if "开源" in clean:
        modifiers.append("开源")
    if "避坑" in clean or "坑" in clean:
        modifiers.append("避坑")
    return _dedupe(modifiers)


def build_search_queries(keyword: str) -> list[str]:
    primary = clean_search_keyword(keyword)
    entity = extract_keyword_entity(keyword) or primary
    modifiers = extract_keyword_modifiers(keyword)
    queries = [primary]

    if "视频" in modifiers:
        queries.append(f"{entity} 视频能力")
    if "核心能力" in modifiers:
        queries.append(f"{entity} 核心能力")
    if "参数" in modifiers or "API" in modifiers:
        queries.append(f"{entity} 参数 API")

    queries.extend(
        [
            f"{entity} 能力 参数",
            f"{entity} 使用场景",
            f"{entity} API 接入",
            f"{entity} 最新发布",
        ]
    )
    return _dedupe([query for query in queries if query.strip()])


def _normalize_space(value: str) -> str:
    clean = re.sub(r"\s+", " ", value).strip()
    clean = clean.replace("：", ":")
    return clean


def _normalize_known_entity(value: str) -> str:
    clean = value.strip()
    clean = re.sub(r"(?i)\bminimax\s*h\s*3\b", "MiniMax H3", clean)
    clean = re.sub(r"(?i)\bdeepseek\b", "DeepSeek", clean)
    clean = re.sub(r"(?i)\bchatgpt\b", "ChatGPT", clean)
    return clean


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result
