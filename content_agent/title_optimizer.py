from __future__ import annotations

import re

from .models import ContentChannel


FORBIDDEN_TITLE_TERMS = [
    "暴富",
    "稳赚",
    "月入",
    "躺赚",
    "保证",
    "根治",
    "治愈",
    "治疗",
    "诊断",
]


def optimize_title(title: str, channel: ContentChannel, keyword: str = "") -> str:
    clean_title = clean_source_title(title)
    if channel == "xiaohongshu" or _looks_like_health(clean_title):
        return _sanitize_title(_optimize_health_title(clean_title))
    if keyword.strip() and not _looks_like_ai_focus(keyword):
        return _sanitize_title(_optimize_keyword_title(clean_title, keyword.strip()))
    return _sanitize_title(_optimize_ai_side_hustle_title(clean_title))


def clean_source_title(title: str) -> str:
    clean = re.sub(r"\s+", " ", title).strip()
    clean = re.split(r"\s+[—-]\s+|[丨｜]", clean, maxsplit=1)[0].strip()
    clean = re.sub(r"\s+", " ", clean)
    return clean.strip(" -_｜丨")


def _optimize_ai_side_hustle_title(title: str) -> str:
    if _contains_any(title, ["坑", "骗局", "卖课", "割韭菜", "造假", "避坑"]):
        return "AI 副业可以做，但这 5 个坑先别踩"
    if _contains_any(title, ["轻创业", "副业", "声音变现", "AI服务", "交易", "爆发", "接单", "赚钱"]):
        if _contains_any(title, ["交易", "服务", "AI服务", "爆发", "增长"]):
            return "AI 服务需求变多了，普通人怎么找到第一单？"
        if _contains_any(title, ["接单", "赚钱"]):
            return "想用 AI 接单，先从这 3 类小服务切入"
        return "AI 副业不是玄学，普通人先抓住这 3 个切入口"
    if _contains_any(title, ["工具", "学习", "路线", "教程", "提示词"]):
        if _contains_any(title, ["提示词", "教程"]):
            return "别只收藏提示词，先跑通这 3 个 AI 交付场景"
        return "学 AI 工具别贪多，先搭一条可交付路线"
    if 10 <= len(title) <= 28 and not _contains_any(title, FORBIDDEN_TITLE_TERMS):
        return title
    return "普通人学 AI，先把一个真实任务做成作品"


def _optimize_keyword_title(title: str, keyword: str) -> str:
    model_entity = _model_entity_from_source_title(title)
    if model_entity and _contains_any(title, ["发布", "上线", "更新", "模型"]):
        return f"{model_entity}有新变化，普通人先看懂这 3 点"
    if keyword in title and 10 <= len(title) <= 30 and not _contains_any(title, FORBIDDEN_TITLE_TERMS):
        return title
    if _contains_any(title, ["架构", "系统", "平台", "工程", "数据", "项目", "技术"]):
        return f"{keyword}入门：先看懂这 3 个核心问题"
    if _contains_any(title, ["发布", "更新", "趋势", "报告", "方案"]):
        return f"{keyword}有新变化，普通人先看懂这 3 点"
    return f"{keyword}怎么入门？先从这 3 个真实场景开始"


def _optimize_health_title(title: str) -> str:
    if _contains_any(title, ["久坐", "办公室", "肩颈", "腰背"]):
        return "久坐职场女性可收藏的 4 个低成本习惯"
    if _contains_any(title, ["睡前", "放松", "睡眠", "熬夜"]):
        return "宝妈睡前 10 分钟，试试这份放松清单"
    if _contains_any(title, ["气色", "养生", "健康", "习惯"]):
        return "职场女性可收藏的 5 个低成本养生习惯"
    return "职场女性可收藏的低成本习惯清单"


def _sanitize_title(title: str) -> str:
    safe_title = title
    replacements = {
        "暴富": "增长",
        "稳赚": "更稳",
        "月入": "收入",
        "躺赚": "轻量尝试",
        "保证": "更容易",
        "根治": "改善",
        "治愈": "调整",
        "治疗": "调理",
        "诊断": "观察",
    }
    for unsafe, safe in replacements.items():
        safe_title = safe_title.replace(unsafe, safe)
    return safe_title.strip()


def _looks_like_health(title: str) -> bool:
    return _contains_any(title, ["养生", "女性", "宝妈", "健康", "久坐", "气色", "睡前", "办公室"])


def _looks_like_ai_focus(text: str) -> bool:
    return _contains_any(
        text,
        [
            "AI",
            "ai",
            "DeepSeek",
            "deepseek",
            "大模型",
            "副业",
            "赚钱",
            "变现",
            "轻创业",
            "接单",
        ],
    )


def _contains_any(text: str, terms: list[str]) -> bool:
    return any(term in text for term in terms)


def _model_entity_from_source_title(title: str) -> str:
    match = re.match(r"([A-Za-z][A-Za-z0-9]*(?:\s+[A-Za-z0-9]+){0,3})", title.strip())
    if not match:
        return ""
    entity = re.sub(r"\s+", " ", match.group(1)).strip()
    if len(entity) < 3 or not re.search(r"\d|[A-Z]", entity):
        return ""
    return entity
