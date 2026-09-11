import unittest
from unittest.mock import patch

from content_agent.collectors.source_urls import (
    collect_source_url_candidates,
    parse_source_urls_field,
    resolve_source_urls,
)
from content_agent.web import WebRunOptions, _collect_candidates, _options_from_payload


class FakePageFetcher:
    def __init__(self, pages: dict[str, tuple[str, str]] | None = None, body: str = ""):
        self.pages = pages or {}
        self.body = body
        self.calls: list[str] = []

    def fetch(self, url: str) -> tuple[str, str]:
        self.calls.append(url)
        if url in self.pages:
            return self.pages[url]
        return url, self.body


class SourceUrlCollectorTests(unittest.TestCase):
    def test_fetch_builds_candidates_from_html(self):
        html = """
        <html><head><title>开源项目怎么做公众号</title></head>
        <body>
          <article>
            <h1>开源项目怎么做公众号</h1>
            <p>这是一篇关于教程、步骤和避坑的真实案例文章，适合自媒体作者参考。</p>
            <p>先整理材料，再写结构，最后发布到公众号草稿箱。</p>
          </article>
        </body></html>
        """
        fetcher = FakePageFetcher(body=html)

        candidates = collect_source_url_candidates(
            ["https://example.com/open-source-wechat"],
            fetcher=fetcher,
        )

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].source, "source_urls")
        self.assertEqual(candidates[0].url, "https://example.com/open-source-wechat")
        self.assertIn("开源项目怎么做公众号", candidates[0].title)
        self.assertIn("教程", candidates[0].summary)
        self.assertEqual(fetcher.calls, ["https://example.com/open-source-wechat"])

    def test_resolve_merges_explicit_and_prompt_urls(self):
        urls = resolve_source_urls(
            ["https://example.com/a"],
            "选题 https://example.com/b 以及重复 https://example.com/a",
        )
        self.assertEqual(urls, ["https://example.com/a", "https://example.com/b"])

    def test_parse_source_urls_field_supports_newlines_and_lists(self):
        self.assertEqual(
            parse_source_urls_field("https://a.example\nhttps://b.example"),
            ["https://a.example", "https://b.example"],
        )
        self.assertEqual(
            parse_source_urls_field(["https://a.example", "https://b.example"]),
            ["https://a.example", "https://b.example"],
        )


class CollectCandidatesRoutingTests(unittest.TestCase):
    def test_briefing_with_urls_skips_baidu(self):
        options = WebRunOptions(
            keyword="简报选题标题",
            use_prompt_as_title=True,
            source_urls=("https://example.com/briefing",),
        )
        from content_agent.models import CandidateContent

        fake_candidates = [
            CandidateContent(
                title="简报原文",
                source="source_urls",
                url="https://example.com/briefing",
                heat=80,
                interaction=70,
                hook=70,
                pain=60,
                reuse=70,
                material=80,
                summary="正文摘要",
            )
        ]
        with patch("content_agent.web.collect_source_url_candidates", return_value=fake_candidates) as source_mock, patch(
            "content_agent.web.collect_baidu_search_candidates"
        ) as baidu_mock:
            candidates = _collect_candidates(options)

        self.assertEqual(candidates, fake_candidates)
        source_mock.assert_called_once()
        baidu_mock.assert_not_called()

    def test_briefing_without_urls_errors_in_chinese(self):
        options = WebRunOptions(keyword="只有标题没有链接", use_prompt_as_title=True)
        with self.assertRaisesRegex(ValueError, "简报选题已勾选但未提供原链接"):
            _collect_candidates(options)

    def test_manual_keyword_still_uses_baidu(self):
        options = WebRunOptions(keyword="AI副业", use_prompt_as_title=False, source_urls=())
        from content_agent.models import CandidateContent

        fake = [
            CandidateContent(
                title="AI副业案例",
                source="baidu_search",
                url="https://example.com/ai",
                heat=70,
                interaction=60,
                hook=60,
                pain=50,
                reuse=60,
                material=60,
            )
        ]
        with patch("content_agent.web.AgentConfig.from_env_file") as config_mock, patch(
            "content_agent.web.collect_baidu_search_candidates", return_value=fake
        ) as baidu_mock, patch("content_agent.web.collect_source_url_candidates") as source_mock:
            config_mock.return_value.baidu_search_api_key = "secret"
            candidates = _collect_candidates(options)

        self.assertEqual(candidates, fake)
        baidu_mock.assert_called_once()
        source_mock.assert_not_called()

    def test_source_urls_in_prompt_skip_baidu_even_without_briefing_checkbox(self):
        options = WebRunOptions(
            keyword="写这篇 https://example.com/doc",
            use_prompt_as_title=False,
        )
        from content_agent.models import CandidateContent

        fake = [
            CandidateContent(
                title="文档",
                source="source_urls",
                url="https://example.com/doc",
                heat=80,
                interaction=70,
                hook=70,
                pain=60,
                reuse=70,
                material=80,
                summary="文档正文",
            )
        ]
        with patch("content_agent.web.collect_source_url_candidates", return_value=fake) as source_mock, patch(
            "content_agent.web.collect_baidu_search_candidates"
        ) as baidu_mock:
            candidates = _collect_candidates(options)

        self.assertEqual(candidates, fake)
        source_mock.assert_called_once()
        self.assertEqual(source_mock.call_args.args[0], ["https://example.com/doc"])
        baidu_mock.assert_not_called()

    def test_options_payload_accepts_source_urls(self):
        options = _options_from_payload(
            {
                "keyword": "选题",
                "use_prompt_as_title": True,
                "source_urls": "https://example.com/a\nhttps://example.com/b",
            }
        )
        self.assertEqual(options.source_urls, ("https://example.com/a", "https://example.com/b"))
        self.assertTrue(options.use_prompt_as_title)


if __name__ == "__main__":
    unittest.main()
