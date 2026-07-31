import unittest

from content_agent.mock_data import get_mock_candidates


class MockDataTests(unittest.TestCase):
    def test_returns_ai_side_hustle_candidates_for_wechat(self):
        candidates = get_mock_candidates("AI副业", channel="wechat")

        self.assertGreaterEqual(len(candidates), 3)
        self.assertTrue(any("AI" in candidate.title for candidate in candidates))
        self.assertTrue(any("副业" in candidate.title for candidate in candidates))
        self.assertTrue(all(candidate.source == "mock" for candidate in candidates))

    def test_returns_health_candidates_for_xiaohongshu(self):
        candidates = get_mock_candidates("养生", channel="xiaohongshu")

        self.assertGreaterEqual(len(candidates), 3)
        self.assertTrue(any("职场女性" in candidate.title for candidate in candidates))
        self.assertTrue(any("宝妈" in candidate.title for candidate in candidates))

    def test_falls_back_to_channel_candidates_for_unknown_keyword(self):
        candidates = get_mock_candidates("时间管理", channel="wechat")

        self.assertGreaterEqual(len(candidates), 1)
        self.assertTrue(any("副业" in candidate.title or "AI" in candidate.title for candidate in candidates))


if __name__ == "__main__":
    unittest.main()
