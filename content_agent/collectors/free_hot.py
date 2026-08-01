from __future__ import annotations

import html
import json
import math
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Protocol
from urllib import parse, request

from ..models import CandidateContent


class FreeHotRunner(Protocol):
    def get_json(self, url: str, headers: dict[str, str]) -> dict:
        ...

    def get_text(self, url: str, headers: dict[str, str]) -> str:
        ...


@dataclass(frozen=True)
class UrlLibFreeHotRunner:
    def get_json(self, url: str, headers: dict[str, str]) -> dict:
        http_request = request.Request(url, headers=headers, method="GET")
        with request.urlopen(http_request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))

    def get_text(self, url: str, headers: dict[str, str]) -> str:
        http_request = request.Request(url, headers=headers, method="GET")
        with request.urlopen(http_request, timeout=60) as response:
            return response.read().decode("utf-8")


@dataclass(frozen=True)
class FreeHotConfig:
    sources: list[str] = field(default_factory=lambda: ["google_news_rss", "hn", "github"])
    google_news_runner: FreeHotRunner | None = None
    hn_runner: FreeHotRunner | None = None
    github_runner: FreeHotRunner | None = None


@dataclass(frozen=True)
class GoogleNewsRssCollector:
    runner: FreeHotRunner | None = None

    def collect(self, keyword: str, limit: int = 10) -> list[CandidateContent]:
        _require_keyword(keyword)
        params = parse.urlencode({"q": keyword, "hl": "zh-CN", "gl": "CN", "ceid": "CN:zh-Hans"})
        xml_text = (self.runner or UrlLibFreeHotRunner()).get_text(
            f"https://news.google.com/rss/search?{params}",
            {"User-Agent": _user_agent()},
        )
        items = _parse_rss_items(xml_text)
        return [
            _candidate(
                title=item["title"],
                source="google_news_rss",
                url=item["url"],
                snippet=item["summary"],
                rank=index,
                keyword=keyword,
                heat_hint=0,
                interaction_hint=0,
            )
            for index, item in enumerate(items[:limit])
        ]


@dataclass(frozen=True)
class HNAlgoliaCollector:
    runner: FreeHotRunner | None = None

    def collect(self, keyword: str, limit: int = 10) -> list[CandidateContent]:
        _require_keyword(keyword)
        params = parse.urlencode({"query": keyword, "tags": "story", "hitsPerPage": limit})
        data = (self.runner or UrlLibFreeHotRunner()).get_json(
            f"https://hn.algolia.com/api/v1/search?{params}",
            {"User-Agent": _user_agent()},
        )
        candidates = []
        for index, item in enumerate(data.get("hits", [])[:limit]):
            title = item.get("title") or item.get("story_title") or ""
            if not title:
                continue
            points = _number(item.get("points"))
            comments = _number(item.get("num_comments"))
            candidates.append(
                _candidate(
                    title=title,
                    source="hn_algolia",
                    url=item.get("url") or item.get("story_url"),
                    snippet=item.get("comment_text") or "",
                    rank=index,
                    keyword=keyword,
                    heat_hint=_log_hint(points),
                    interaction_hint=_log_hint(comments),
                )
            )
        return candidates


@dataclass(frozen=True)
class GitHubSearchCollector:
    runner: FreeHotRunner | None = None

    def collect(self, keyword: str, limit: int = 10) -> list[CandidateContent]:
        _require_keyword(keyword)
        params = parse.urlencode({"q": keyword, "sort": "stars", "order": "desc", "per_page": limit})
        data = (self.runner or UrlLibFreeHotRunner()).get_json(
            f"https://api.github.com/search/repositories?{params}",
            {"Accept": "application/vnd.github+json", "User-Agent": _user_agent()},
        )
        candidates = []
        for index, item in enumerate(data.get("items", [])[:limit]):
            title = item.get("full_name") or item.get("name") or ""
            description = item.get("description") or ""
            if not title:
                continue
            if _is_noisy_github_repository(title, description):
                continue
            stars = _number(item.get("stargazers_count"))
            forks = _number(item.get("forks_count"))
            candidates.append(
                _candidate(
                    title=f"GitHub 项目：{title}",
                    source="github",
                    url=item.get("html_url"),
                    snippet=description,
                    rank=index,
                    keyword=keyword,
                    heat_hint=_log_hint(stars),
                    interaction_hint=_log_hint(forks),
                )
            )
        return candidates


def collect_free_hot_candidates(keyword: str, config: FreeHotConfig, limit: int = 10) -> list[CandidateContent]:
    source_candidates = [collector.collect(keyword, limit=limit) for collector in _build_collectors(config)]
    return _round_robin_dedupe(source_candidates, limit=limit)


def _round_robin_dedupe(source_candidates: list[list[CandidateContent]], limit: int) -> list[CandidateContent]:
    merged: list[CandidateContent] = []
    seen: set[str] = set()
    max_length = max((len(candidates) for candidates in source_candidates), default=0)
    for index in range(max_length):
        for candidates in source_candidates:
            if index >= len(candidates):
                continue
            candidate = candidates[index]
            key = candidate.url or f"{candidate.source}:{candidate.title}"
            if key in seen:
                continue
            seen.add(key)
            merged.append(candidate)
            if len(merged) >= limit:
                return merged
    return merged


def _build_collectors(config: FreeHotConfig):
    collectors = []
    for source in config.sources:
        normalized = source.strip()
        if not normalized:
            continue
        if normalized == "google_news_rss":
            collectors.append(GoogleNewsRssCollector(runner=config.google_news_runner))
        elif normalized == "hn":
            collectors.append(HNAlgoliaCollector(runner=config.hn_runner))
        elif normalized == "github":
            collectors.append(GitHubSearchCollector(runner=config.github_runner))
        elif normalized == "rsshub_weibo":
            raise ValueError("FREE_HOT_SOURCES source rsshub_weibo does not support keyword search")
        elif normalized == "dailyhot":
            raise ValueError("FREE_HOT_SOURCES source dailyhot does not support keyword search")
        else:
            raise ValueError(f"Unsupported free_hot source: {source}")
    if not collectors:
        raise ValueError("FREE_HOT_SOURCES cannot be empty")
    return collectors


def _candidate(
    title: str,
    source: str,
    url: str | None,
    snippet: str,
    rank: int,
    keyword: str,
    heat_hint: float,
    interaction_hint: float,
) -> CandidateContent:
    clean_title = _clean_text(title)
    clean_snippet = _clean_snippet(snippet)
    text = f"{clean_title} {clean_snippet}"
    rank_boost = max(0, 20 - rank * 3)
    match_boost = 16 if keyword.lower() in text.lower() else 0
    hook = min(95, 58 + _signal(clean_title, ["普通人", "新手", "避坑", "最", "如何", "为什么", "清单", "步骤", "案例"]) + (8 if any(char.isdigit() for char in clean_title) else 0))
    return CandidateContent(
        title=clean_title,
        source=source,
        url=url,
        heat=min(96, 54 + rank_boost + match_boost + heat_hint),
        interaction=min(92, 48 + rank_boost + interaction_hint),
        hook=hook,
        pain=min(92, 56 + _signal(text, ["副业", "赚钱", "学习", "职场", "宝妈", "健康", "久坐", "焦虑", "低成本"])),
        reuse=min(90, 58 + _signal(text, ["工具", "方法", "清单", "路线", "步骤", "案例", "教程", "项目"])),
        material=min(88, 56 + _signal(text, ["新闻", "数据", "报告", "项目", "工具", "开源", "研究", "热搜"])),
    )


def _parse_rss_items(xml_text: str) -> list[dict[str, str]]:
    root = ET.fromstring(xml_text)
    items = []
    for item in root.findall(".//item"):
        title = item.findtext("title") or ""
        link = item.findtext("link") or ""
        summary = item.findtext("description") or ""
        if title:
            items.append({"title": title, "url": link, "summary": summary})
    return items


def _clean_text(value: str) -> str:
    no_tags = re.sub(r"<[^>]+>", "", value or "")
    return _clip_text(html.unescape(no_tags).strip(), limit=120)


def _clean_snippet(value: str) -> str:
    no_tags = re.sub(r"<[^>]+>", "", value or "")
    return _clip_text(html.unescape(no_tags).strip(), limit=300)


def _clip_text(value: str, limit: int) -> str:
    normalized = re.sub(r"\s+", " ", value).strip()
    if len(normalized) <= limit:
        return normalized
    return normalized[:limit].rstrip() + "..."


def _signal(text: str, terms: list[str]) -> int:
    return sum(7 for term in terms if term in text)


def _is_noisy_github_repository(title: str, description: str) -> bool:
    text = f"{title} {description}"
    noisy_terms = ["PDF下载", "百度云", "电子书下载", "网盘", "资源合集"]
    return any(term in text for term in noisy_terms)


def _number(value) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0


def _log_hint(value: float) -> float:
    if value <= 0:
        return 0
    return min(22, math.log10(value + 1) * 7)


def _require_keyword(keyword: str) -> None:
    if not keyword.strip():
        raise ValueError("keyword cannot be empty")


def _user_agent() -> str:
    return "content-agent/0.1"
