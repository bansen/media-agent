from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Protocol
from urllib import request
from urllib.parse import urlparse

from ..models import CandidateContent
from .websearch_mcp import (
    _clean_readme_content,
    _clean_text,
    _github_raw_readme_url,
    _normalize_url,
    _title_from_url,
    extract_prompt_urls,
)


class PageFetcher(Protocol):
    def fetch(self, url: str) -> tuple[str, str]:
        """Return (final_url, raw_body_text)."""
        ...


@dataclass(frozen=True)
class UrlLibPageFetcher:
    timeout: int = 30

    def fetch(self, url: str) -> tuple[str, str]:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (compatible; content-agent/0.1; +https://github.com/bansen/media-agent)"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,text/plain;q=0.8,*/*;q=0.7",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        http_request = request.Request(url, headers=headers, method="GET")
        with request.urlopen(http_request, timeout=self.timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            raw = response.read()
            try:
                body = raw.decode(charset, errors="replace")
            except LookupError:
                body = raw.decode("utf-8", errors="replace")
            final_url = response.geturl() or url
            return final_url, body


@dataclass(frozen=True)
class SourceUrlCollector:
    fetcher: PageFetcher | None = None

    def collect(self, urls: list[str], limit: int = 10) -> list[CandidateContent]:
        normalized = _normalize_url_list(urls)
        if not normalized:
            raise ValueError("source_urls cannot be empty")
        fetcher = self.fetcher or UrlLibPageFetcher()
        candidates: list[CandidateContent] = []
        errors: list[str] = []
        for index, url in enumerate(normalized[:limit]):
            try:
                fetch_url = _github_raw_readme_url(url) or url
                final_url, body = fetcher.fetch(fetch_url)
                title, summary = _extract_title_and_text(body, url=url, final_url=final_url)
                candidates.append(
                    _candidate(
                        title=title,
                        url=url,
                        summary=summary,
                        rank=index,
                    )
                )
            except Exception as exc:  # noqa: BLE001 - surface per-URL failures later
                errors.append(f"{url}: {exc}")
        if not candidates:
            detail = "；".join(errors[:3]) if errors else "未知原因"
            raise RuntimeError(f"原链接未能提取到可用内容：{detail}")
        return candidates


def collect_source_url_candidates(
    urls: list[str],
    limit: int = 10,
    fetcher: PageFetcher | None = None,
) -> list[CandidateContent]:
    return SourceUrlCollector(fetcher=fetcher).collect(urls, limit=limit)


def resolve_source_urls(explicit_urls: list[str] | tuple[str, ...] | None, prompt: str = "") -> list[str]:
    combined: list[str] = []
    seen: set[str] = set()
    for url in list(explicit_urls or []) + extract_prompt_urls(prompt or ""):
        clean = _normalize_url(str(url).strip())
        if not clean or not clean.lower().startswith(("http://", "https://")):
            continue
        if clean in seen:
            continue
        seen.add(clean)
        combined.append(clean)
    return combined


def parse_source_urls_field(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        parts = re.split(r"[\n,]+", value)
        return [part.strip() for part in parts if part.strip()]
    if isinstance(value, (list, tuple)):
        items: list[str] = []
        for item in value:
            items.extend(parse_source_urls_field(item))
        return items
    return [str(value).strip()] if str(value).strip() else []


def _normalize_url_list(urls: list[str]) -> list[str]:
    return resolve_source_urls(urls, prompt="")


def _extract_title_and_text(body: str, url: str, final_url: str) -> tuple[str, str]:
    if _looks_like_markdown(body) or _github_raw_readme_url(url) or "raw.githubusercontent.com" in final_url:
        title = _title_from_url(url)
        content = _clean_readme_content(body) if body.strip() else ""
        if not content:
            content = _clean_text(body)
        return title, _summary_for(title, content, max_chars=6000)

    parsed = _HtmlTextExtractor()
    parsed.feed(body)
    parsed.close()
    title = _clean_text(html.unescape(parsed.title)) or _title_from_meta(body) or _title_from_url(url)
    content = parsed.text
    if not content:
        raise RuntimeError("页面正文为空")
    return title, _summary_for(title, content, max_chars=4000)


def _title_from_meta(body: str) -> str:
    match = re.search(
        r'(?is)<meta[^>]+(?:property|name)=["\'](?:og:title|twitter:title)["\'][^>]+content=["\']([^"\']+)["\']',
        body,
    )
    if match:
        return _clean_text(html.unescape(match.group(1)))
    match = re.search(r"(?is)<title[^>]*>(.*?)</title>", body)
    if match:
        return _clean_text(html.unescape(match.group(1)))
    return ""


def _looks_like_markdown(body: str) -> bool:
    sample = body.lstrip()[:400]
    if sample.startswith("#") or "```" in sample:
        return True
    if re.search(r"(?m)^#{1,3}\s+\S", body[:2000]):
        return True
    return False


def _summary_for(title: str, content: str, max_chars: int = 4000) -> str:
    parts = [part for part in [title, content] if part]
    summary = "；".join(parts)
    return summary[:max_chars]


def _candidate(title: str, url: str, summary: str, rank: int) -> CandidateContent:
    rank_boost = max(0, 18 - rank * 2)
    material_boost = 12 if summary else 0
    text = f"{title} {summary}"
    return CandidateContent(
        title=title,
        source="source_urls",
        url=url,
        heat=min(98, 70 + rank_boost),
        interaction=min(92, 62 + rank_boost),
        hook=min(94, 66 + _signal(title, ["如何", "教程", "案例", "步骤", "清单", "避坑", "开源"])),
        pain=min(92, 60 + _signal(text, ["难", "问题", "避坑", "失败", "卡住"])),
        reuse=min(96, 70 + _signal(text, ["教程", "步骤", "清单", "方法", "项目", "文档", "开源"])),
        material=min(98, 76 + material_boost),
        summary=summary,
    )


def _signal(text: str, terms: list[str]) -> int:
    return sum(6 for term in terms if term.lower() in text.lower())


_VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
_BLOCK_TAGS = {"p", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "section", "article", "main", "blockquote", "pre"}
_SKIP_TAGS = {"head", "title", "script", "style", "noscript", "svg", "iframe", "header", "footer", "nav", "aside", "template"}
_BODY_MARKERS = {"article-body", "article-content", "articlebody", "entry-content", "post-content", "story-body", "story-content", "rich-media-content", "js-content"}
_NOISE_MARKERS = {
    "ad", "ads", "advert", "advertisement", "advertising", "ad-container", "ad-slot", "ad-wrapper",
    "related", "related-posts", "related-articles", "related-content", "related-stories",
    "recommend", "recommended", "recommendation", "recommendations", "recommended-articles",
    "recommended-posts", "navigation", "nav", "sidebar", "social-share", "share-buttons",
    "article-card", "post-card", "story-card",
}


@dataclass
class _HtmlNode:
    tag: str
    attrs: dict[str, str] = field(default_factory=dict)
    children: list[_HtmlNode | str] = field(default_factory=list)

    @property
    def markers(self) -> set[str]:
        return set((self.attrs.get("id", "") + " " + self.attrs.get("class", "")).lower().replace("_", "-").split())

    @property
    def skipped(self) -> bool:
        return (
            self.tag in _SKIP_TAGS
            or bool(self.markers & _NOISE_MARKERS)
            or self.attrs.get("role", "").lower() in {"navigation", "banner", "contentinfo", "complementary"}
        )

    @property
    def is_article_body(self) -> bool:
        return bool(self.markers & _BODY_MARKERS) or "articlebody" in self.attrs.get("itemprop", "").lower().split()

    def nodes(self):
        if not self.skipped:
            yield self
            for child in self.children:
                if isinstance(child, _HtmlNode):
                    yield from child.nodes()

    def render(self) -> str:
        if self.skipped:
            return ""
        if self.tag == "br":
            return "\n"
        # Normalize source indentation, but preserve spaces across inline tags.
        text = "".join(child.render() if isinstance(child, _HtmlNode) else re.sub(r"\s+", " ", child) for child in self.children)
        return f"\n\n{text}\n\n" if self.tag in _BLOCK_TAGS else text

    def text(self) -> str:
        text = re.sub(r" *\n *", "\n", self.render())
        return re.sub(r"\n{3,}", "\n\n", text).strip()


class _HtmlTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self._root = _HtmlNode("")
        self._stack = [self._root]
        self._capture_title = False

    @property
    def text(self) -> str:
        nodes = list(self._root.nodes())
        # A main region prevents unrelated article cards elsewhere from winning.
        mains = [node for node in nodes if (node.tag == "main" or node.attrs.get("role") == "main") and node.text()]
        scope = max(mains, key=lambda node: len(node.text())) if mains else self._root
        candidates = [node for node in scope.nodes() if node.is_article_body or node.tag == "article"]
        candidates = [node for node in candidates if node.text()]
        if candidates:
            scope = max(candidates, key=lambda node: (node.is_article_body, len(node.text())))
        return scope.text()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "body":
            # HTML permits </head> to be omitted before the body starts.
            self.handle_endtag("head")
            self._capture_title = False
        if tag == "title":
            self._capture_title = not self.title and not any(
                node.skipped and node.tag != "head" for node in self._stack
            )
        node = _HtmlNode(tag, {key: value or "" for key, value in attrs})
        self._stack[-1].children.append(node)
        if tag not in _VOID_TAGS:
            self._stack.append(node)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in _VOID_TAGS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._capture_title = False
        # Close only an actual open element; stray closes never alter filtering.
        for index in range(len(self._stack) - 1, 0, -1):
            if self._stack[index].tag == tag:
                del self._stack[index:]
                break

    def handle_data(self, data: str) -> None:
        if self._capture_title:
            self.title += data
        self._stack[-1].children.append(data)


def is_http_url(value: str) -> bool:
    try:
        parsed = urlparse(value)
    except Exception:
        return False
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
