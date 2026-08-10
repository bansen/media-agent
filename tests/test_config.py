import tempfile
import unittest
from pathlib import Path

from content_agent.config import AgentConfig


class ConfigTests(unittest.TestCase):
    def test_loads_env_file_without_exposing_secret_values(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / ".env"
            env_path.write_text(
                "\n".join(
                    [
                        "LLM_PROVIDER=deepseek",
                        "LLM_BASE_URL=https://api.deepseek.com",
                        "LLM_MODEL=deepseek-chat",
                        "LLM_API_KEY=secret",
                        "REPLICATE_API_TOKEN=replicate-secret",
                        "REPLICATE_COVER_MODEL_VERSION=model-version",
                        "WECHAT_APP_ID=appid",
                        "WECHAT_APP_SECRET=appsecret",
                        "WECHAT_COMPONENT_APP_ID=component-appid",
                        "WECHAT_COMPONENT_APP_SECRET=component-secret",
                        "WECHAT_COMPONENT_TOKEN=component-token",
                        "WECHAT_COMPONENT_AES_KEY=component-aes-key",
                        "WECHAT_COMPONENT_AUTH_REDIRECT_URI=https://media-agent.createbeauty.top/auth/wechat-official/callback",
                        "WECHAT_COMPONENT_VERIFY_TICKET=component-ticket",
                        "WECHAT_COMPONENT_ACCESS_TOKEN=component-access-token",
                        "BAIDU_SEARCH_API_KEY=baidu-secret",
                        "WEBSEARCH_MCP_ENABLED=true",
                        "WEBSEARCH_MCP_COMMAND=npx",
                        "WEBSEARCH_MCP_ARGS=-y,tavily-mcp@0.1.3",
                        "WEBSEARCH_MCP_TIMEOUT=45",
                        "TAVILY_API_KEY=tavily-secret",
                        "PUBLIC_SEARCH_PROVIDER=all",
                        "BING_SEARCH_API_KEY=bing-secret",
                        "NEWSAPI_API_KEY=news-secret",
                        "FREE_HOT_SOURCES=google_news_rss,hn,github",
                        "DATABASE_URL=postgresql+psycopg://user:password@db:5432/media_agent",
                        "RSSHUB_BASE_URL=https://rsshub.example",
                        "DAILYHOT_BASE_URL=https://dailyhot.example",
                    ]
                ),
                encoding="utf-8",
            )

            config = AgentConfig.from_env_file(env_path)

            self.assertEqual(config.llm_provider, "deepseek")
            self.assertEqual(config.llm_model, "deepseek-chat")
            self.assertEqual(config.replicate_cover_model_version, "model-version")
            self.assertFalse(hasattr(config, "public_search_provider"))
            self.assertFalse(hasattr(config, "bing_search_api_key"))
            self.assertFalse(hasattr(config, "newsapi_api_key"))
            self.assertFalse(hasattr(config, "rsshub_base_url"))
            self.assertFalse(hasattr(config, "dailyhot_base_url"))
            self.assertEqual(config.free_hot_sources, ["google_news_rss", "hn", "github"])
            self.assertEqual(config.wechat_component_app_id, "component-appid")
            self.assertEqual(config.baidu_search_api_key, "baidu-secret")
            self.assertTrue(config.websearch_mcp_enabled)
            self.assertEqual(config.websearch_mcp_command, "npx")
            self.assertEqual(config.websearch_mcp_args, ["-y", "tavily-mcp@0.1.3"])
            self.assertEqual(config.websearch_mcp_timeout, 45)
            self.assertEqual(
                config.wechat_component_auth_redirect_uri,
                "https://media-agent.createbeauty.top/auth/wechat-official/callback",
            )
            self.assertEqual(config.redacted_status()["LLM_API_KEY"], "SET")
            self.assertEqual(config.redacted_status()["DATABASE_URL"], "SET")
            self.assertEqual(config.redacted_status()["WECHAT_ACCESS_TOKEN"], "EMPTY")
            self.assertEqual(config.redacted_status()["WECHAT_COMPONENT_APP_ID"], "SET")
            self.assertEqual(config.redacted_status()["WECHAT_COMPONENT_APP_SECRET"], "SET")
            self.assertEqual(config.redacted_status()["WECHAT_COMPONENT_TOKEN"], "SET")
            self.assertEqual(config.redacted_status()["WECHAT_COMPONENT_AES_KEY"], "SET")
            self.assertEqual(config.redacted_status()["WECHAT_COMPONENT_VERIFY_TICKET"], "SET")
            self.assertEqual(config.redacted_status()["WECHAT_COMPONENT_ACCESS_TOKEN"], "SET")
            self.assertEqual(config.redacted_status()["BAIDU_SEARCH_API_KEY"], "SET")
            self.assertEqual(config.redacted_status()["TAVILY_API_KEY"], "SET")
            self.assertEqual(config.redacted_status()["WEBSEARCH_MCP_ENABLED"], "true")
            self.assertNotIn("BING_SEARCH_API_KEY", config.redacted_status())
            self.assertNotIn("NEWSAPI_API_KEY", config.redacted_status())
            self.assertNotIn("PUBLIC_SEARCH_PROVIDER", config.redacted_status())
            self.assertNotIn("FREE_HOT_SOURCES", config.redacted_status())
            self.assertNotIn("BAIJIAHAO_APP_ID", config.redacted_status())

    def test_builds_provider_instances_from_config(self):
        config = AgentConfig(
            llm_provider="deepseek",
            llm_base_url="https://api.deepseek.com",
            llm_model="deepseek-chat",
            llm_api_key="secret",
            replicate_api_token="replicate-secret",
            replicate_cover_model_version="model-version",
            replicate_cover_model="black-forest-labs/flux-1.1-pro",
            wechat_app_id="appid",
            wechat_app_secret="appsecret",
            wechat_access_token="",
            free_hot_sources=["google_news_rss", "hn"],
            database_url="postgresql+psycopg://user:password@db:5432/media_agent",
        )

        llm = config.build_llm_provider()
        image = config.build_image_provider()
        wechat = config.build_wechat_publisher()
        free_hot = config.build_free_hot_config()

        self.assertEqual(llm.model, "deepseek-chat")
        self.assertEqual(image.model_version, "black-forest-labs/flux-1.1-pro")
        self.assertEqual(wechat.app_id, "appid")
        self.assertEqual(free_hot.sources, ["google_news_rss", "hn"])


if __name__ == "__main__":
    unittest.main()
