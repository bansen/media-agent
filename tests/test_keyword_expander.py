import unittest

from content_agent.keyword_expander import expand_keywords


class KeywordExpanderTests(unittest.TestCase):
    def test_expands_ai_side_hustle_keywords_for_wechat(self):
        keywords = expand_keywords("AI副业", channel="wechat")

        self.assertIn("AI副业", keywords)
        self.assertIn("AI赚钱", keywords)
        self.assertIn("AI工具变现", keywords)
        self.assertGreaterEqual(len(keywords), 6)
        self.assertEqual(len(keywords), len(set(keywords)))

    def test_expands_health_keywords_for_xiaohongshu(self):
        keywords = expand_keywords("养生", channel="xiaohongshu")

        self.assertIn("养生", keywords)
        self.assertIn("职场女性养生", keywords)
        self.assertIn("宝妈养生", keywords)
        self.assertGreaterEqual(len(keywords), 6)


if __name__ == "__main__":
    unittest.main()
