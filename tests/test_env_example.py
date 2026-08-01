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
        self.assertIn("BAIDU_SEARCH_API_KEY=", env_example)

    def test_old_free_hot_sources_are_not_documented(self):
        env_example = pathlib.Path(".env.example").read_text(encoding="utf-8")

        self.assertNotIn("FREE_HOT_SOURCES", env_example)
        self.assertNotIn("RSSHUB_BASE_URL", env_example)
        self.assertNotIn("DAILYHOT_BASE_URL", env_example)

    def test_wechat_component_authorization_config_is_documented(self):
        env_example = pathlib.Path(".env.example").read_text(encoding="utf-8")

        self.assertIn("WECHAT_COMPONENT_APP_ID=", env_example)
        self.assertIn("WECHAT_COMPONENT_APP_SECRET=", env_example)
        self.assertIn("WECHAT_COMPONENT_TOKEN=", env_example)
        self.assertIn("WECHAT_COMPONENT_AES_KEY=", env_example)
        self.assertIn(
            "WECHAT_COMPONENT_AUTH_REDIRECT_URI=https://media-agent.createbeauty.top/auth/wechat-official/callback",
            env_example,
        )


if __name__ == "__main__":
    unittest.main()
