import unittest

from content_agent.collectors.free_hot import (
    FreeHotConfig,
    GitHubSearchCollector,
    GoogleNewsRssCollector,
    HNAlgoliaCollector,
    collect_free_hot_candidates,
)


class FakeRunner:
    def __init__(self, json_response=None, text_response=""):
        self.json_response = json_response
        self.text_response = text_response
        self.calls = []

    def get_json(self, url, headers):
        self.calls.append(("json", url, headers))
        return self.json_response

    def get_text(self, url, headers):
        self.calls.append(("text", url, headers))
        return self.text_response


class FreeHotTests(unittest.TestCase):
    def test_google_news_rss_maps_items_to_candidates(self):
        runner = FakeRunner(
            text_response="""<?xml version="1.0" encoding="UTF-8"?>
<rss><channel>
  <item><title>AI 副业工具正在流行</title><link>https://news.example/a</link><description>普通人学习案例</description></item>
  <item><title>另一个 AI 学习路线</title><link>https://news.example/b</link><description>工具清单</description></item>
</channel></rss>"""
        )
        collector = GoogleNewsRssCollector(runner=runner)

        candidates = collector.collect("AI副业", limit=2)

        self.assertEqual(len(candidates), 2)
        self.assertEqual(candidates[0].source, "google_news_rss")
        self.assertEqual(candidates[0].url, "https://news.example/a")
        self.assertIn("q=AI%E5%89%AF%E4%B8%9A", runner.calls[0][1])

    def test_hn_algolia_maps_hits_to_candidates(self):
        runner = FakeRunner(
            json_response={
                "hits": [
                    {
                        "title": "Show HN: AI agent for side projects",
                        "url": "https://hn.example/a",
                        "points": 120,
                        "num_comments": 32,
                    }
                ]
            }
        )
        collector = HNAlgoliaCollector(runner=runner)

        candidates = collector.collect("AI agent", limit=5)

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].source, "hn_algolia")
        self.assertGreaterEqual(candidates[0].interaction, 70)
        self.assertIn("query=AI+agent", runner.calls[0][1])

    def test_github_search_maps_repositories_to_candidates(self):
        runner = FakeRunner(
            json_response={
                "items": [
                    {
                        "full_name": "example/ai-agent",
                        "html_url": "https://github.com/example/ai-agent",
                        "description": "AI agent workflow toolkit",
                        "stargazers_count": 3600,
                        "forks_count": 280,
                    }
                ]
            }
        )
        collector = GitHubSearchCollector(runner=runner)

        candidates = collector.collect("AI agent", limit=3)

        self.assertEqual(candidates[0].source, "github")
        self.assertEqual(candidates[0].title, "GitHub 项目：example/ai-agent")
        self.assertNotIn("workflow toolkit", candidates[0].title)
        self.assertGreaterEqual(candidates[0].heat, 80)
        self.assertIn("sort=stars", runner.calls[0][1])

    def test_github_search_filters_noisy_pdf_book_repositories(self):
        runner = FakeRunner(
            json_response={
                "items": [
                    {
                        "full_name": "example/books",
                        "html_url": "https://github.com/example/books",
                        "description": "PDF下载 百度云 电子书下载 计算机应用基础",
                        "stargazers_count": 9999,
                        "forks_count": 1000,
                    },
                    {
                        "full_name": "example/ai-tool",
                        "html_url": "https://github.com/example/ai-tool",
                        "description": "AI automation toolkit",
                        "stargazers_count": 1200,
                        "forks_count": 80,
                    },
                ]
            }
        )
        collector = GitHubSearchCollector(runner=runner)

        candidates = collector.collect("AI", limit=5)

        self.assertEqual([candidate.title for candidate in candidates], ["GitHub 项目：example/ai-tool"])

    def test_collect_free_hot_aggregates_configured_sources(self):
        google_runner = FakeRunner(
            text_response="<rss><channel><item><title>AI 新闻</title><link>https://g.example</link></item></channel></rss>"
        )
        hn_runner = FakeRunner(json_response={"hits": [{"title": "AI HN", "url": "https://hn.example"}]})
        config = FreeHotConfig(
            sources=["google_news_rss", "hn"],
            google_news_runner=google_runner,
            hn_runner=hn_runner,
        )

        candidates = collect_free_hot_candidates("AI", config=config, limit=10)

        self.assertEqual([candidate.source for candidate in candidates], ["google_news_rss", "hn_algolia"])

    def test_collect_free_hot_rejects_non_keyword_hot_sources(self):
        config = FreeHotConfig(sources=["dailyhot", "rsshub_weibo"])

        with self.assertRaisesRegex(ValueError, "does not support keyword search"):
            collect_free_hot_candidates("AI", config=config, limit=10)

    def test_collect_free_hot_balances_sources_when_first_source_has_many_items(self):
        google_runner = FakeRunner(
            text_response="""<rss><channel>
<item><title>AI 新闻 1</title><link>https://g.example/1</link></item>
<item><title>AI 新闻 2</title><link>https://g.example/2</link></item>
<item><title>AI 新闻 3</title><link>https://g.example/3</link></item>
</channel></rss>"""
        )
        hn_runner = FakeRunner(json_response={"hits": [{"title": "AI HN", "url": "https://hn.example"}]})
        config = FreeHotConfig(
            sources=["google_news_rss", "hn"],
            google_news_runner=google_runner,
            hn_runner=hn_runner,
        )

        candidates = collect_free_hot_candidates("AI", config=config, limit=3)

        self.assertEqual([candidate.source for candidate in candidates], ["google_news_rss", "hn_algolia", "google_news_rss"])


if __name__ == "__main__":
    unittest.main()
