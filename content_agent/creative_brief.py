from __future__ import annotations

from dataclasses import dataclass
import re

from .models import ContentChannel


@dataclass(frozen=True)
class CreativeBrief:
    raw_prompt: str
    topic: str
    audience: str
    angles: list[str]
    tone: list[str]
    channel: ContentChannel
    search_queries: list[str]


def build_creative_brief(prompt: str, channel: ContentChannel = "wechat") -> CreativeBrief:
    raw_prompt = _normalize_space(prompt)
    topic = _extract_topic(raw_prompt)
    audience = _extract_audience(raw_prompt)
    angles = _extract_angles(raw_prompt)
    tone = _extract_tone(raw_prompt)
    search_queries = _build_queries(topic, audience, angles, channel)
    return CreativeBrief(
        raw_prompt=raw_prompt,
        topic=topic,
        audience=audience,
        angles=angles,
        tone=tone,
        channel=channel,
        search_queries=search_queries,
    )


def is_creative_prompt(prompt: str) -> bool:
    return any(
        term in prompt
        for term in [
            "我想写",
            "帮我写",
            "写一篇",
            "生成一篇",
            "主题是",
            "目标读者",
            "目标用户",
            "面向",
            "内容要",
            "要求",
            "风格",
        ]
    )


def _extract_topic(prompt: str) -> str:
    topic = _extract_labeled_value(prompt, ["主题是", "主题为", "主题:", "主题："])
    if topic:
        return _clean_topic(topic)
    clean = re.sub(r"^(?:帮我|请|我想|想)?(?:写|生成|做)(?:一篇)?(?:公众号|小红书|百家号)?(?:文章|笔记|内容)?[，,：:\s]*", "", prompt)
    first_clause = re.split(r"[，,。；;]", clean, maxsplit=1)[0].strip()
    return _clean_topic(first_clause or prompt)


def _extract_audience(prompt: str) -> str:
    return _extract_labeled_value(prompt, ["目标读者是", "目标读者为", "目标用户是", "面向", "写给", "读者是"])


def _extract_labeled_value(prompt: str, labels: list[str]) -> str:
    for label in labels:
        index = prompt.find(label)
        if index < 0:
            continue
        value = prompt[index + len(label) :]
        stop_match = re.search(
            r"[，,。；;]|目标读者|目标用户|面向|写给|内容要|要求|风格|语气|最好|希望|不要",
            value,
        )
        if stop_match:
            value = value[: stop_match.start()]
        return _normalize_space(value).strip("：: ")
    return ""


def _extract_angles(prompt: str) -> list[str]:
    angles: list[str] = []
    checks = [
        ("避坑", ["避坑", "坑", "风险", "误区"]),
        ("行动步骤", ["行动步骤", "步骤", "清单", "怎么做", "实操"]),
        ("真实案例", ["真实案例", "案例", "经验"]),
        ("核心能力", ["核心能力", "能力"]),
        ("视频能力", ["视频"]),
        ("工具接入", ["接入", "配置", "API", "api"]),
    ]
    for label, terms in checks:
        if any(term in prompt for term in terms):
            angles.append(label)
    return _dedupe(angles)


def _extract_tone(prompt: str) -> list[str]:
    tone: list[str] = []
    checks = ["真实", "不鸡血", "生活化", "实用", "克制", "犀利", "温和", "专业"]
    for label in checks:
        if label in prompt:
            tone.append(label)
    return tone


def _build_queries(topic: str, audience: str, angles: list[str], channel: ContentChannel) -> list[str]:
    base = topic.strip()
    queries: list[str] = []
    if not base:
        return []
    if "避坑" in angles:
        queries.append(f"{base} 避坑")
    if "真实案例" in angles:
        queries.append(f"{base} 真实案例")
    if "行动步骤" in angles:
        queries.append(f"{base} 方法 步骤")
    if "核心能力" in angles:
        queries.append(f"{base} 核心能力")
    if "视频能力" in angles:
        queries.append(f"{base} 视频能力")
    if "工具接入" in angles:
        queries.append(f"{base} API 接入")
    if audience:
        queries.append(f"{base} {audience}")
    if channel == "xiaohongshu":
        queries.append(f"{base} 小红书")
    else:
        queries.append(f"{base} 公众号")
    queries.extend([base, f"{base} 最新", f"{base} 案例"])
    return _dedupe([_normalize_space(query) for query in queries if query.strip()])


def _clean_topic(topic: str) -> str:
    clean = re.sub(r"[（(].*?[）)]", "", topic)
    clean = re.sub(r"^(?:关于|围绕|写)?", "", clean).strip()
    return _normalize_space(clean).strip("，,。；; ")


def _normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


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
