import unittest

from content_agent.collectors.baidu_search import BaiduSearchCollector


class FakeBaiduSearchRunner:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def post_json(self, url, payload, headers):
        self.calls.append((url, payload, headers))
        if isinstance(self.response, list):
            index = min(len(self.calls) - 1, len(self.response) - 1)
            return self.response[index]
        return self.response


class BaiduSearchTests(unittest.TestCase):
    def test_baidu_search_maps_references_to_candidates(self):
        runner = FakeBaiduSearchRunner(
            {
                "references": [
                    {
                        "title": "Codex 制作出海网站的 5 个关键步骤",
                        "url": "https://example.com/codex-site",
                        "content": "从定位、页面结构、英文文案到上线部署的完整流程。",
                    },
                    {
                        "title": "广告：海外建站服务",
                        "url": "https://example.com/ad",
                        "content": "推广链接",
                    },
                ]
            }
        )
        collector = BaiduSearchCollector(api_key="secret", runner=runner)

        candidates = collector.collect("codex制作出海网站", limit=10)

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].source, "baidu_search")
        self.assertEqual(candidates[0].url, "https://example.com/codex-site")
        self.assertIn("Codex 制作出海网站", candidates[0].title)
        self.assertIn("Bearer secret", runner.calls[0][2]["Authorization"])
        self.assertIn("Bearer secret", runner.calls[0][2]["X-Appbuilder-Authorization"])
        self.assertEqual(runner.calls[0][1]["messages"][0]["content"], "codex制作出海网站")
        self.assertEqual(runner.calls[0][1]["search_source"], "baidu_search_v2")

    def test_baidu_search_requires_api_key(self):
        collector = BaiduSearchCollector(api_key="")

        with self.assertRaisesRegex(RuntimeError, "BAIDU_SEARCH_API_KEY"):
            collector.collect("AI副业")

    def test_baidu_search_cleans_descriptive_keyword_before_querying(self):
        runner = FakeBaiduSearchRunner({"references": []})
        collector = BaiduSearchCollector(api_key="secret", runner=runner)

        collector.collect("minimax h3介绍，要突出核心能力（如视频相关等）", limit=10)

        first_query = runner.calls[0][1]["messages"][0]["content"]
        self.assertEqual(first_query, "MiniMax H3 核心能力 视频")
        self.assertNotIn("介绍", first_query)
        self.assertNotIn("要突出", first_query)

    def test_baidu_search_expands_queries_when_sources_are_too_few(self):
        runner = FakeBaiduSearchRunner(
            [
                {
                    "references": [
                        {"title": "MiniMax H3官网入口分享", "url": "https://example.com/a", "content": "视频生成工具体验。"},
                        {"title": "MiniMax H3全模态模型详解", "url": "https://example.com/b", "content": "参数能力和 API。"},
                    ]
                },
                {
                    "references": [
                        {"title": "MiniMax H3视频能力实测", "url": "https://example.com/c", "content": "视频相关能力。"},
                        {"title": "MiniMax H3核心能力拆解", "url": "https://example.com/d", "content": "模型能力分析。"},
                    ]
                },
                {
                    "references": [
                        {"title": "MiniMax H3适合哪些场景", "url": "https://example.com/e", "content": "真实使用场景。"},
                        {"title": "MiniMax H3接入要点", "url": "https://example.com/f", "content": "API 接入。"},
                    ]
                },
            ]
        )
        collector = BaiduSearchCollector(api_key="secret", runner=runner)

        candidates = collector.collect("minimax h3介绍，要突出核心能力（如视频相关等）", limit=10)

        self.assertGreaterEqual(len(candidates), 6)
        self.assertGreaterEqual(len(runner.calls), 3)
        queries = [call[1]["messages"][0]["content"] for call in runner.calls]
        self.assertIn("MiniMax H3 核心能力 视频", queries)
        self.assertIn("MiniMax H3 视频能力", queries)


if __name__ == "__main__":
    unittest.main()
