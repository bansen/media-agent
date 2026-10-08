"""Fact checks at asset and submission boundaries, including legacy drafts."""
from pathlib import Path

from .cover_copy import _ArticleTextParser
from .fact_review import FactReviewError, require_review


class _ReviewHTMLParser(_ArticleTextParser):
    def handle_starttag(self, tag, attrs):
        super().handle_starttag(tag, attrs)
        if tag == "a" and not self.hidden:
            href = dict(attrs).get("href")
            if href:
                self.parts.append(f" [链接：{href}] ")


def html_review_text(result, html):
    parser = _ReviewHTMLParser()
    parser.feed(html)
    parser.close()
    # Include the title actually sent to WeChat, even if HTML has no heading.
    body = "".join(parser.parts).strip()
    return result.topics[0].optimized_title + "\n" + body if body else ""


def ensure_article_review(result, payload, llm, content_html=None):
    if content_html is None and payload.get("wechat_content_html"):
        content_html = Path(payload["wechat_content_html"]).read_text(encoding="utf-8")
    if content_html is not None:
        article = html_review_text(result, content_html)
        key = "publication_fact_review"
        previous = payload.get(key)
    else:
        drafts = payload.get("llm_drafts") or {}
        article = str(drafts.get("wechat_article") or "")
        key = "fact_review"
        previous = payload.get(key) or drafts.get(key)
        # A changed published title must not reuse a review of the old heading.
        if not article.startswith("# " + result.topics[0].optimized_title + "\n"):
            article = result.topics[0].optimized_title + "\n" + article
    try:
        payload[key] = require_review(result, article, llm, previous)
    except FactReviewError as exc:
        payload[key] = exc.report
        exc.payload = payload
        raise
    return payload[key]


def retain_rejected_draft(payload, exc):
    payload["llm_drafts"] = {"wechat_article": exc.article, "fact_review": exc.report}
    for key in ("gzh_formatting", "wechat_content_html", "cover_image", "cover_copy",
                "wechat_draft", "xhs_layout", "fact_review", "publication_fact_review"):
        payload.pop(key, None)
    exc.payload = payload
