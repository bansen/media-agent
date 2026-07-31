from __future__ import annotations

from .models import ContentChannel


COMMON_SUFFIXES = ["教程", "避坑", "案例", "清单", "新手入门"]

CHANNEL_EXPANSIONS: dict[str, list[str]] = {
    "wechat": [
        "AI赚钱",
        "AI工具变现",
        "普通人副业",
        "打工人副业",
        "副业避坑",
        "AI学习路线",
    ],
    "xiaohongshu": [
        "职场女性养生",
        "宝妈养生",
        "办公室养生",
        "低成本养生",
        "女性健康习惯",
        "养生清单",
    ],
}


def expand_keywords(keyword: str, channel: ContentChannel = "wechat") -> list[str]:
    cleaned = keyword.strip()
    if not cleaned:
        raise ValueError("keyword cannot be empty")

    expansions = [cleaned]
    expansions.extend(CHANNEL_EXPANSIONS.get(channel, []))
    expansions.extend(f"{cleaned}{suffix}" for suffix in COMMON_SUFFIXES)

    seen: set[str] = set()
    unique: list[str] = []
    for item in expansions:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return unique
