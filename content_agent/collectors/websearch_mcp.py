from __future__ import annotations

import json
import os
import re
import select
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

from ..models import CandidateContent


URL_PATTERN = re.compile(r"https?://[^\s，。；、）)】\]\"'<>]+")
DEFAULT_SEARCH_TOOL = "tavily-search"
DEFAULT_EXTRACT_TOOL = "tavily-extract"


class MCPToolRunner(Protocol):
    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class StdioMCPToolRunner:
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    timeout: int = 60

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        process_env = os.environ.copy()
        process_env.update({key: value for key, value in self.env.items() if value})
        process = subprocess.Popen(
            [self.command, *self.args],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=process_env,
        )
        try:
            self._send_message(
                process,
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "content-agent", "version": "0.1"},
                    },
                },
            )
            self._read_message(process)
            self._send_message(process, {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
            self._send_message(
                process,
                {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": name, "arguments": arguments}},
            )
            response = self._read_message(process)
        finally:
            process.terminate()
        if "error" in response:
            raise RuntimeError(f"WebSearch MCP tool {name} failed: {response['error']}")
        result = response.get("result")
        return result if isinstance(result, dict) else {}

    def _send_message(self, process: subprocess.Popen, payload: dict[str, Any]) -> None:
        if process.stdin is None:
            raise RuntimeError("WebSearch MCP stdin is unavailable")
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        process.stdin.write(body + b"\n")
        process.stdin.flush()

    def _read_message(self, process: subprocess.Popen) -> dict[str, Any]:
        if process.stdout is None:
            raise RuntimeError("WebSearch MCP stdout is unavailable")
        line = b""
        deadline = time.time() + self.timeout
        while True:
            if time.time() > deadline:
                raise RuntimeError("WebSearch MCP response timed out")
            ready, _, _ = select.select([process.stdout], [], [], 0.25)
            if not ready:
                continue
            chunk = os.read(process.stdout.fileno(), 4096)
            if not chunk:
                stderr = process.stderr.read().decode("utf-8", errors="ignore") if process.stderr else ""
                raise RuntimeError(f"WebSearch MCP stopped before responding: {stderr[:500]}")
            line += chunk
            if len(line) > 2_000_000:
                raise RuntimeError("WebSearch MCP response is too large")
            while b"\n" in line:
                raw_line, line = line.split(b"\n", 1)
                text = raw_line.decode("utf-8", errors="ignore").strip()
                if not text:
                    continue
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    continue


def collect_websearch_mcp_candidates(
    prompt: str,
    runner: MCPToolRunner,
    limit: int = 6,
    search_tool: str = DEFAULT_SEARCH_TOOL,
    extract_tool: str = DEFAULT_EXTRACT_TOOL,
) -> list[CandidateContent]:
    clean_prompt = prompt.strip()
    if not clean_prompt:
        raise ValueError("prompt cannot be empty")
    urls = [_normalize_url(url) for url in extract_prompt_urls(clean_prompt)]
    if urls:
        extraction_urls = [_github_raw_readme_url(url) or url for url in urls[:3]]
        result = runner.call_tool(extract_tool, {"urls": extraction_urls, "extract_depth": "advanced"})
        return _extract_result_to_candidates(result, urls=urls, limit=limit)
    result = runner.call_tool(search_tool, {"query": clean_prompt, "max_results": limit, "search_depth": "advanced"})
    return _search_result_to_candidates(result, limit=limit)


def extract_prompt_urls(prompt: str) -> list[str]:
    seen: set[str] = set()
    urls: list[str] = []
    for match in URL_PATTERN.finditer(prompt):
        url = _normalize_url(match.group(0))
        if url in seen:
            continue
        seen.add(url)
        urls.append(url)
    return urls


def _extract_result_to_candidates(result: dict[str, Any], urls: list[str], limit: int) -> list[CandidateContent]:
    payload = _payload_from_tool_result(result)
    items = _result_items(payload)
    if not items:
        items = [{"url": url, "title": _title_from_url(url), "content": ""} for url in urls]
    candidates: list[CandidateContent] = []
    for index, item in enumerate(items[:limit]):
        url = urls[min(index, len(urls) - 1)]
        title = _clean_text(str(item.get("title") or _title_from_url(url)))
        raw_content = str(item.get("raw_content") or item.get("content") or item.get("summary") or "")
        if _github_raw_readme_url(url) and not _usable_github_readme(raw_content):
            raise RuntimeError("GitHub README 正文读取失败，请稍后重试或确认 README 链接可以公开访问。")
        content = _clean_readme_content(raw_content) if _github_raw_readme_url(url) else _clean_text(raw_content)
        summary_limit = 6000 if _github_raw_readme_url(url) else 1200
        candidates.append(
            _candidate(
                title=_websearch_title(title, url),
                url=url,
                summary=_summary_for(title, content, max_chars=summary_limit),
                rank=index,
                from_link=True,
            )
        )
    return candidates


def _search_result_to_candidates(result: dict[str, Any], limit: int) -> list[CandidateContent]:
    payload = _payload_from_tool_result(result)
    candidates: list[CandidateContent] = []
    for index, item in enumerate(_result_items(payload)[:limit]):
        title = _clean_text(str(item.get("title") or item.get("name") or ""))
        url = str(item.get("url") or item.get("link") or "").strip() or None
        content = _clean_text(str(item.get("content") or item.get("summary") or item.get("snippet") or ""))
        if not title:
            continue
        candidates.append(_candidate(title=title, url=url, summary=_summary_for(title, content), rank=index, from_link=False))
    return candidates


def _candidate(title: str, url: str | None, summary: str, rank: int, from_link: bool) -> CandidateContent:
    rank_boost = max(0, 18 - rank * 2)
    link_boost = 10 if from_link else 0
    material_boost = 10 if summary else 0
    return CandidateContent(
        title=title,
        source="websearch_mcp",
        url=url,
        heat=min(98, 64 + rank_boost + link_boost),
        interaction=min(92, 58 + rank_boost + link_boost),
        hook=min(94, 64 + _signal(title, ["如何", "教程", "案例", "步骤", "清单", "避坑", "开源"]) + link_boost),
        pain=min(92, 58 + _signal(f"{title} {summary}", ["难", "问题", "避坑", "失败", "卡住"])),
        reuse=min(96, 66 + _signal(f"{title} {summary}", ["教程", "步骤", "清单", "方法", "项目", "文档", "开源"])),
        material=min(98, 70 + material_boost + link_boost),
        summary=summary,
    )


def _payload_from_tool_result(result: dict[str, Any]) -> dict[str, Any]:
    if "results" in result:
        return result
    for content in result.get("content", []):
        if not isinstance(content, dict) or content.get("type") != "text":
            continue
        text = str(content.get("text") or "").strip()
        if not text:
            continue
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return {"results": [{"content": text}]}
        if isinstance(parsed, dict):
            return parsed
        if isinstance(parsed, list):
            return {"results": parsed}
    return {}


def _result_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    items = payload.get("results") or payload.get("data") or []
    return [item for item in items if isinstance(item, dict)]


def _websearch_title(title: str, url: str) -> str:
    github_ref = _github_repo_ref(url)
    if github_ref:
        detail = title if title and _normalize_match(title) != _normalize_match(github_ref) else "项目资料"
        return f"GitHub 开源项目：{github_ref} - {detail}"
    return title or _title_from_url(url)


def _github_repo_ref(url: str) -> str:
    match = re.search(r"github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)", url, flags=re.IGNORECASE)
    if not match:
        return ""
    return f"{match.group(1)}/{match.group(2).removesuffix('.git')}"


def _github_raw_readme_url(url: str) -> str:
    match = re.match(
        r"https?://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)/blob/([^/]+)/((?:.*/)?README(?:\.[A-Za-z0-9_.-]+)?)$",
        url,
        flags=re.IGNORECASE,
    )
    if not match:
        return ""
    owner, repository, revision, path = match.groups()
    return f"https://raw.githubusercontent.com/{owner}/{repository}/{revision}/{path}"


def _usable_github_readme(content: str) -> bool:
    clean = content.strip()
    navigation_hits = sum(
        term.lower() in clean.lower()
        for term in ["Navigation Menu", "Sign in", "Sign up", "Appearance settings", "Notifications"]
    )
    markdown_signal = bool(re.search(r"(?:^|\n)\s*#{1,3}\s+\S", clean)) or "Raw Content: #" in clean
    return len(clean) >= 60 and markdown_signal and navigation_hits < 3


def _title_from_url(url: str) -> str:
    github_ref = _github_repo_ref(url)
    if github_ref:
        return github_ref
    return re.sub(r"^https?://", "", url).strip("/") or "网页资料"


def _summary_for(title: str, content: str, max_chars: int = 1200) -> str:
    parts = [part for part in [title, content] if part]
    summary = "；".join(parts)
    return summary[:max_chars]


def _normalize_url(url: str) -> str:
    clean = url.rstrip(".,;:!?，。；：！？")
    github = re.match(
        r"https?://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:/(?:blob|tree)/[A-Za-z0-9_.\-/]+)?",
        clean,
        flags=re.IGNORECASE,
    )
    return github.group(0).rstrip("/") if github else clean


def _normalize_match(text: str) -> str:
    return text.lower().replace("-", "").replace("_", "").replace("/", "").replace(" ", "")


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _clean_readme_content(value: str) -> str:
    useful_lines: list[str] = []
    for raw_line in value.splitlines():
        line = raw_line.strip()
        is_heading = bool(re.match(r"^#{1,6}\s+", line))
        lower = line.lower()
        if not line:
            continue
        if line.startswith("[![") or "img.shields.io" in lower or "badge.svg" in lower:
            continue
        if line.startswith("![") or re.fullmatch(r"<img\b[^>]*>", line, flags=re.IGNORECASE):
            continue
        if lower.startswith(("title:", "url source:", "markdown content:")):
            continue
        line = re.sub(r"<!--.*?-->", "", line)
        line = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", line)
        line = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", line)
        line = re.sub(r"^#{1,6}\s*", "", line)
        line = re.sub(r"^[-*+]\s+", "", line)
        line = re.sub(r"\s+", " ", line).strip()
        if line:
            if is_heading and not re.search(r"[。！？!?；;：:]$", line):
                line += "。"
            useful_lines.append(line)
    return _clean_text(" ".join(useful_lines))


def _signal(text: str, terms: list[str]) -> int:
    return sum(6 for term in terms if term.lower() in text.lower())
