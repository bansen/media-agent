import pathlib
import unittest


class EnvExampleTests(unittest.TestCase):
    def test_wechat_thumb_media_id_is_not_required_static_config(self):
        env_example = pathlib.Path(".env.example").read_text(encoding="utf-8")

        self.assertNotIn("WECHAT_THUMB_MEDIA_ID", env_example)

    def test_baijiahao_api_is_not_required_static_config(self):
        env_example = pathlib.Path(".env.example").read_text(encoding="utf-8")

        self.assertNotIn("BAIJIAHAO_APP_ID", env_example)
        self.assertNotIn("BAIJIAHAO_APP_TOKEN", env_example)

    def test_paid_public_search_keys_are_not_documented(self):
        env_example = pathlib.Path(".env.example").read_text(encoding="utf-8")

        self.assertNotIn("PUBLIC_SEARCH_PROVIDER", env_example)
        self.assertNotIn("BING_SEARCH_API_KEY", env_example)
        self.assertNotIn("NEWSAPI_API_KEY", env_example)

    def test_only_keyword_search_free_hot_sources_are_documented(self):
        env_example = pathlib.Path(".env.example").read_text(encoding="utf-8")

        self.assertIn("FREE_HOT_SOURCES=google_news_rss,hn,github", env_example)
        self.assertNotIn("RSSHUB_BASE_URL", env_example)
        self.assertNotIn("DAILYHOT_BASE_URL", env_example)


if __name__ == "__main__":
    unittest.main()
