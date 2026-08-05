from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Protocol
from urllib import request

from ..keyword_intent import build_search_queries
from ..models import CandidateContent


BAIDU_WEB_SEARCH_URL = "https://qianfan.baidubce.com/v2/ai_search/web_search"
MIN_BAIDU_CANDIDATES = 6


class BaiduSearchRunner(Protocol):
    def post_json(self, url: str, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class UrlLibBaiduSearchRunner:
    def post_json(self, url: str, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        http_request = request.Request(url, data=body, headers=headers, method="POST")
        with request.urlopen(http_request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))


@dataclass(frozen=True)
class BaiduSearchCollector:
    api_key: str
    runner: BaiduSearchRunner | None = None

    def collect(self, keyword: str, limit: int = 10) -> list[CandidateContent]:
        clean_keyword = keyword.strip()
        if not clean_keyword:
            raise ValueError("keyword cannot be empty")
        if not self.api_key.strip():
            raise RuntimeError("BAIDU_SEARCH_API_KEY is required for baidu_search collector")
        headers = {
            "Authorization": f"Bearer {self.api_key.strip()}",
            "X-Appbuilder-Authorization": f"Bearer {self.api_key.strip()}",
            "Content-Type": "application/json",
            "User-Agent": "content-agent/0.1",
        }
        runner = self.runner or UrlLibBaiduSearchRunner()
        candidates: list[CandidateContent] = []
        seen: set[str] = set()
        target_count = min(limit, MIN_BAIDU_CANDIDATES)
        for query in build_search_queries(clean_keyword):
            payload = _search_payload(query, limit=limit)
            data = runner.post_json(BAIDU_WEB_SEARCH_URL, payload, headers)
            references = data.get("references") or data.get("results") or []
            for candidate in _references_to_candidates(references, keyword=query, limit=limit):
                key = candidate.url or candidate.title
                if key in seen:
                    continue
                seen.add(key)
                candidates.append(candidate)
                if len(candidates) >= limit:
                    return candidates[:limit]
            if len(candidates) >= target_count:
                break
        return candidates[:limit]


def collect_baidu_search_candidates(
    keyword: str,
    api_key: str,
    limit: int = 10,
    runner: BaiduSearchRunner | None = None,
) -> list[CandidateContent]:
    return BaiduSearchCollector(api_key=api_key, runner=runner).collect(keyword, limit=limit)


def _search_payload(query: str, limit: int) -> dict[str, Any]:
    return {
        "messages": [{"content": query.strip(), "role": "user"}],
        "search_source": "baidu_search_v2",
        "resource_type_filter": [{"type": "web", "top_k": limit}],
    }


def _references_to_candidates(references: list[dict[str, Any]], keyword: str, limit: int) -> list[CandidateContent]:
    candidates: list[CandidateContent] = []
    seen: set[str] = set()
    for index, item in enumerate(references):
        title = _clean_text(str(item.get("title") or item.get("name") or ""))
        url = str(item.get("url") or item.get("link") or "").strip() or None
        snippet = _clean_text(str(item.get("content") or item.get("summary") or item.get("snippet") or ""))
        if not title or _looks_like_ad(title, snippet):
            continue
        key = url or title
        if key in seen:
            continue
        seen.add(key)
        candidates.append(_candidate(title=title, url=url, snippet=snippet, rank=index, keyword=keyword))
        if len(candidates) >= limit:
            break
    return candidates


def _candidate(title: str, url: str | None, snippet: str, rank: int, keyword: str) -> CandidateContent:
    text = f"{title} {snippet}".lower()
    rank_boost = max(0, 22 - rank * 2)
    match_boost = 16 if keyword.lower() in text else _term_match_boost(keyword, text)
    return CandidateContent(
        title=title,
        source="baidu_search",
        url=url,
        heat=min(94, 58 + rank_boost + match_boost),
        interaction=min(88, 52 + rank_boost + match_boost / 2),
        hook=min(92, 60 + _signal(title, ["如何", "教程", "案例", "步骤", "清单", "避坑", "实战"]) + (8 if any(char.isdigit() for char in title) else 0)),
        pain=min(90, 56 + _signal(text, ["难", "问题", "避坑", "失败", "成本", "不会", "卡住"])),
        reuse=min(92, 60 + _signal(text, ["教程", "步骤", "清单", "方法", "实战", "案例", "模板"])),
        material=min(90, 62 + _signal(text, ["案例", "教程", "文档", "工具", "网站", "项目", "平台"])),
    )


def _clean_text(value: str) -> str:
    cleaned = re.sub(r"<[^>]+>", "", value)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def _looks_like_ad(title: str, snippet: str) -> bool:
    text = f"{title} {snippet}".lower()
    ad_terms = ["广告", "推广", "赞助", "立即咨询", "联系电话", "招商加盟"]
    return any(term in text for term in ad_terms)


def _signal(text: str, terms: list[str]) -> int:
    return sum(7 for term in terms if term.lower() in text.lower())


def _term_match_boost(keyword: str, text: str) -> float:
    terms = [term for term in keyword.replace("/", " ").replace("-", " ").split() if len(term) >= 2]
    if not terms and len(keyword) > 2:
        terms = [keyword[index : index + 2] for index in range(0, len(keyword) - 1)]
    return min(14, sum(4 for term in terms if term.lower() in text))
