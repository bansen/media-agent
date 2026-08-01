from __future__ import annotations

from .models import CandidateContent, ContentChannel


def build_keyword_seed_candidates(keyword: str, channel: ContentChannel) -> list[CandidateContent]:
    clean_keyword = keyword.strip()
    if not clean_keyword:
        raise ValueError("keyword cannot be empty")
    if channel == "xiaohongshu":
        titles = [
            f"{clean_keyword}，20-45岁女性最容易忽略的 5 个细节",
            f"把{clean_keyword}做成日常习惯，先从这 3 步开始",
            f"{clean_keyword}避坑清单：别再被复杂方法劝退",
        ]
        return [
            CandidateContent(
                title=title,
                source="keyword_seed",
                url=None,
                heat=68 - index * 3,
                interaction=70 - index * 2,
                hook=82 - index * 2,
                pain=84 - index * 2,
                reuse=86 - index,
                material=62 - index * 2,
            )
            for index, title in enumerate(titles)
        ]
    titles = [
        f"{clean_keyword}，普通人最该先跑通的 3 个步骤",
        f"用{clean_keyword}做出第一个结果，别先陷进这 5 个坑",
        f"{clean_keyword}从想法到上线：一份适合新手的执行清单",
    ]
    return [
        CandidateContent(
            title=title,
            source="keyword_seed",
            url=None,
            heat=70 - index * 3,
            interaction=68 - index * 2,
            hook=84 - index * 2,
            pain=82 - index * 2,
            reuse=86 - index,
            material=64 - index * 2,
        )
        for index, title in enumerate(titles)
    ]
