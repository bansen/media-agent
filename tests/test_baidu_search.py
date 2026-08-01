import unittest

from content_agent.collectors.baidu_search import BaiduSearchCollector


class FakeBaiduSearchRunner:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def post_json(self, url, payload, headers):
        self.calls.append((url, payload, headers))
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


if __name__ == "__main__":
    unittest.main()
