from __future__ import annotations

from dataclasses import dataclass
import re

from .creative_brief import build_creative_brief, is_creative_prompt


@dataclass(frozen=True)
class KeywordIntent:
    raw_keyword: str
    topic: str
    entities: list[str]
    modifiers: list[str]
    task_kind: str


def parse_keyword_intent(keyword: str) -> KeywordIntent:
    raw = keyword.strip()
    entities = extract_keyword_entities(raw)
    modifiers = extract_keyword_modifiers(raw)
    topic = clean_search_keyword(raw)
    task_kind = _task_kind(raw, entities, modifiers)
    return KeywordIntent(raw_keyword=raw, topic=topic, entities=entities, modifiers=modifiers, task_kind=task_kind)


def clean_search_keyword(keyword: str) -> str:
    brief = build_creative_brief(keyword)
    if is_creative_prompt(keyword) and brief.topic:
        return brief.topic
    entities = extract_keyword_entities(keyword)
    entity = " ".join(entities) if entities else extract_keyword_entity(keyword)
    modifiers = extract_keyword_modifiers(keyword)
    parts = [entity, *[modifier for modifier in modifiers if modifier not in entity]]
    return " ".join(part for part in parts if part).strip() or keyword.strip()


def extract_keyword_entity(keyword: str) -> str:
    clean = _normalize_space(keyword)
    if not clean:
        return ""
    entities = extract_keyword_entities(clean)
    if entities:
        return entities[0]
    first_clause = re.split(r"[，,；;。]|\b(?:要|希望|突出|关注|侧重|重点)\b", clean, maxsplit=1)[0].strip()
    first_clause = re.sub(r"[（(].*?[）)]", "", first_clause).strip()
    first_clause = re.sub(r"(介绍|入门|教程|怎么用|如何用|是什么)$", "", first_clause, flags=re.IGNORECASE).strip()
    return _normalize_known_entity(first_clause)


def extract_keyword_entities(keyword: str) -> list[str]:
    clean = _normalize_space(keyword)
    entities: list[str] = []
    patterns = [
        (r"(?i)\bdeepseek[-\s]*v4[-\s]*flash\b", "DeepSeek V4 Flash"),
        (r"(?i)\bdeepseek\b", "DeepSeek"),
        (r"(?i)\bcodex\b", "Codex"),
        (r"(?i)\bobsidian\b", "Obsidian"),
        (r"(?i)\bminimax\s*h\s*3\b", "MiniMax H3"),
        (r"(?i)\bchatgpt\b", "ChatGPT"),
        (r"(?i)\bclaude\b", "Claude"),
    ]
    for pattern, label in patterns:
        if re.search(pattern, clean):
            entities.append(label)
    if "DeepSeek V4 Flash" in entities:
        entities = [entity for entity in entities if entity != "DeepSeek"]
    return _dedupe(entities)


def extract_keyword_modifiers(keyword: str) -> list[str]:
    clean = _normalize_space(keyword)
    modifiers: list[str] = []
    if "接入" in clean or "直连" in clean or "配置" in clean:
        modifiers.append("接入")
    if "识图" in clean or "图片识别" in clean or "视觉" in clean:
        modifiers.append("识图")
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
    if "搭建" in clean or "配合" in clean or "结合" in clean:
        modifiers.append("搭建")
    if "知识库" in clean or "第二大脑" in clean or "知识工作流" in clean:
        modifiers.append("知识库")
    if "避坑" in clean or "坑" in clean:
        modifiers.append("避坑")
    return _dedupe(modifiers)


def build_search_queries(keyword: str) -> list[str]:
    brief = build_creative_brief(keyword)
    if is_creative_prompt(keyword) and brief.search_queries:
        return brief.search_queries
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


def _task_kind(keyword: str, entities: list[str], modifiers: list[str]) -> str:
    if "知识库" in modifiers and any(entity in entities for entity in ["Codex", "Obsidian"]):
        return "knowledge_workflow"
    if len(entities) >= 2 and any(term in modifiers for term in ["接入", "识图", "API"]):
        return "tool_integration"
    if any(term in modifiers for term in ["接入", "识图", "API"]) and entities:
        return "tool_integration"
    if entities:
        return "model_analysis"
    if any(term in keyword for term in ["副业", "赚钱", "变现", "接单"]):
        return "side_hustle"
    return "general"


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
