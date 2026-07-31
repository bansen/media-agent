import unittest

from content_agent.collectors.public_search import (
    BingSearchCollector,
    NewsAPISearchCollector,
    PublicSearchConfig,
    PublicSearchError,
    collect_public_search_candidates,
)


class FakeJsonRunner:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get_json(self, url, headers):
        self.calls.append((url, headers))
        return self.response


class PublicSearchTests(unittest.TestCase):
    def test_bing_collector_builds_request_and_maps_web_pages(self):
        runner = FakeJsonRunner(
            {
                "webPages": {
                    "value": [
                        {
                            "name": "普通人用 AI 做副业，先避开这 5 个坑",
                            "url": "https://example.com/ai-side-hustle",
                            "snippet": "工具、接单、案例复盘。",
                        },
                        {
                            "name": "AI 工具清单",
                            "url": "https://example.com/tools",
                            "snippet": "适合下班后学习。",
                        },
                    ]
                }
            }
        )
        collector = BingSearchCollector(api_key="bing-secret", runner=runner)

        candidates = collector.collect("AI副业", limit=2)

        self.assertEqual(len(candidates), 2)
        self.assertEqual(candidates[0].source, "bing")
        self.assertEqual(candidates[0].url, "https://example.com/ai-side-hustle")
        self.assertGreater(candidates[0].heat, candidates[1].heat)
        self.assertGreaterEqual(candidates[0].hook, 70)
        self.assertIn("q=AI%E5%89%AF%E4%B8%9A", runner.calls[0][0])
        self.assertEqual(runner.calls[0][1]["Ocp-Apim-Subscription-Key"], "bing-secret")

    def test_newsapi_collector_builds_request_and_maps_articles(self):
        runner = FakeJsonRunner(
            {
                "status": "ok",
                "articles": [
                    {
                        "title": "AI 学习路线正在被重新拆解",
                        "url": "https://example.com/news",
                        "description": "从普通人的真实任务开始。",
                        "publishedAt": "2026-08-01T08:00:00Z",
                        "source": {"name": "Example News"},
                    }
                ],
            }
        )
        collector = NewsAPISearchCollector(api_key="news-secret", runner=runner)

        candidates = collector.collect("AI学习", limit=5)

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].source, "newsapi:Example News")
        self.assertEqual(candidates[0].url, "https://example.com/news")
        self.assertIn("sortBy=popularity", runner.calls[0][0])
        self.assertEqual(runner.calls[0][1]["X-Api-Key"], "news-secret")

    def test_public_search_requires_configured_provider_key(self):
        config = PublicSearchConfig(provider="bing", bing_api_key="", newsapi_api_key="")

        with self.assertRaises(PublicSearchError):
            collect_public_search_candidates("AI副业", config=config)

    def test_public_search_aggregates_multiple_configured_providers(self):
        bing_runner = FakeJsonRunner({"webPages": {"value": [{"name": "AI 副业案例", "url": "https://b.example"}]}})
        news_runner = FakeJsonRunner(
            {"status": "ok", "articles": [{"title": "AI 学习新闻", "url": "https://n.example", "source": {"name": "N"}}]}
        )
        config = PublicSearchConfig(
            provider="all",
            bing_api_key="bing-secret",
            newsapi_api_key="news-secret",
            bing_runner=bing_runner,
            newsapi_runner=news_runner,
        )

        candidates = collect_public_search_candidates("AI副业", config=config, limit=10)

        self.assertEqual([candidate.source for candidate in candidates], ["bing", "newsapi:N"])


if __name__ == "__main__":
    unittest.main()
