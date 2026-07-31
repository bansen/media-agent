from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal, Protocol
from urllib import parse, request

from ..models import CandidateContent


PublicSearchProvider = Literal["bing", "newsapi", "all"]


class PublicSearchError(RuntimeError):
    pass


class JsonRunner(Protocol):
    def get_json(self, url: str, headers: dict[str, str]) -> dict:
        ...


@dataclass(frozen=True)
class UrlLibJsonRunner:
    def get_json(self, url: str, headers: dict[str, str]) -> dict:
        http_request = request.Request(url, headers=headers, method="GET")
        with request.urlopen(http_request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))


@dataclass(frozen=True)
class PublicSearchConfig:
    provider: PublicSearchProvider = "bing"
    bing_api_key: str = ""
    newsapi_api_key: str = ""
    bing_runner: JsonRunner | None = None
    newsapi_runner: JsonRunner | None = None


@dataclass(frozen=True)
class BingSearchCollector:
    api_key: str
    runner: JsonRunner | None = None

    def collect(self, keyword: str, limit: int = 10) -> list[CandidateContent]:
        _require_keyword(keyword)
        _require_key(self.api_key, "BING_SEARCH_API_KEY")
        params = parse.urlencode(
            {
                "q": keyword,
                "count": limit,
                "mkt": "zh-CN",
                "setLang": "zh-Hans",
                "textFormat": "Raw",
                "safeSearch": "Moderate",
            }
        )
        data = (self.runner or UrlLibJsonRunner()).get_json(
            f"https://api.bing.microsoft.com/v7.0/search?{params}",
            {"Ocp-Apim-Subscription-Key": self.api_key},
        )
        items = data.get("webPages", {}).get("value", [])
        return [
            _candidate_from_search_item(
                title=item.get("name", ""),
                source="bing",
                url=item.get("url"),
                snippet=item.get("snippet", ""),
                rank=index,
                keyword=keyword,
            )
            for index, item in enumerate(items[:limit])
            if item.get("name")
        ]


@dataclass(frozen=True)
class NewsAPISearchCollector:
    api_key: str
    runner: JsonRunner | None = None

    def collect(self, keyword: str, limit: int = 10) -> list[CandidateContent]:
        _require_keyword(keyword)
        _require_key(self.api_key, "NEWSAPI_API_KEY")
        params = parse.urlencode(
            {
                "q": keyword,
                "language": "zh",
                "pageSize": limit,
                "sortBy": "popularity",
            }
        )
        data = (self.runner or UrlLibJsonRunner()).get_json(
            f"https://newsapi.org/v2/everything?{params}",
            {"X-Api-Key": self.api_key},
        )
        if data.get("status") not in (None, "ok"):
            raise PublicSearchError(f"NewsAPI search failed: {data}")
        return [
            _candidate_from_search_item(
                title=item.get("title", ""),
                source=f"newsapi:{item.get('source', {}).get('name') or 'unknown'}",
                url=item.get("url"),
                snippet=item.get("description", ""),
                rank=index,
                keyword=keyword,
            )
            for index, item in enumerate(data.get("articles", [])[:limit])
            if item.get("title") and item.get("url")
        ]


def collect_public_search_candidates(
    keyword: str,
    config: PublicSearchConfig,
    limit: int = 10,
) -> list[CandidateContent]:
    collectors = _build_collectors(config)
    candidates: list[CandidateContent] = []
    seen_urls: set[str] = set()
    per_provider_limit = max(limit, 1)
    for collector in collectors:
        for candidate in collector.collect(keyword, limit=per_provider_limit):
            dedupe_key = candidate.url or f"{candidate.source}:{candidate.title}"
            if dedupe_key in seen_urls:
                continue
            seen_urls.add(dedupe_key)
            candidates.append(candidate)
            if len(candidates) >= limit:
                return candidates
    return candidates


def _build_collectors(config: PublicSearchConfig):
    collectors = []
    if config.provider in {"bing", "all"}:
        if not config.bing_api_key and config.provider == "bing":
            raise PublicSearchError("BING_SEARCH_API_KEY is required when PUBLIC_SEARCH_PROVIDER=bing")
        if config.bing_api_key:
            collectors.append(BingSearchCollector(api_key=config.bing_api_key, runner=config.bing_runner))
    if config.provider in {"newsapi", "all"}:
        if not config.newsapi_api_key and config.provider == "newsapi":
            raise PublicSearchError("NEWSAPI_API_KEY is required when PUBLIC_SEARCH_PROVIDER=newsapi")
        if config.newsapi_api_key:
            collectors.append(NewsAPISearchCollector(api_key=config.newsapi_api_key, runner=config.newsapi_runner))
    if not collectors:
        raise PublicSearchError("No public search provider is configured. Set BING_SEARCH_API_KEY or NEWSAPI_API_KEY.")
    return collectors


def _candidate_from_search_item(
    title: str,
    source: str,
    url: str | None,
    snippet: str,
    rank: int,
    keyword: str,
) -> CandidateContent:
    text = f"{title} {snippet}"
    rank_boost = max(0, 22 - rank * 4)
    match_boost = 14 if keyword.lower() in text.lower() else 0
    hook = _hook_score(title)
    pain = _pain_score(text)
    return CandidateContent(
        title=title.strip(),
        source=source,
        url=url,
        heat=min(95, 55 + rank_boost + match_boost),
        interaction=min(90, 50 + rank_boost),
        hook=hook,
        pain=pain,
        reuse=min(90, 58 + _keyword_signal(text, ["方法", "清单", "步骤", "案例", "路线", "工具", "习惯"])),
        material=min(88, 56 + _keyword_signal(text, ["截图", "数据", "案例", "报告", "工具", "新闻", "研究"])),
    )


def _hook_score(title: str) -> float:
    score = 58
    score += _keyword_signal(title, ["普通人", "新手", "避坑", "不要", "最", "如何", "为什么", "清单", "步骤", "案例"])
    if any(char.isdigit() for char in title):
        score += 8
    return min(95, score)


def _pain_score(text: str) -> float:
    return min(92, 56 + _keyword_signal(text, ["焦虑", "副业", "赚钱", "学习", "职场", "宝妈", "健康", "久坐", "低成本", "踩坑"]))


def _keyword_signal(text: str, terms: list[str]) -> int:
    return sum(7 for term in terms if term in text)


def _require_keyword(keyword: str) -> None:
    if not keyword.strip():
        raise ValueError("keyword cannot be empty")


def _require_key(api_key: str, env_name: str) -> None:
    if not api_key.strip():
        raise PublicSearchError(f"{env_name} is required")
