from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from .collectors.free_hot import FreeHotConfig
from .providers.image import ReplicateImageProvider
from .providers.llm import OpenAICompatibleLLMProvider
from .providers.wechat import WeChatDraftPublisher


@dataclass(frozen=True)
class AgentConfig:
    llm_provider: str
    llm_base_url: str
    llm_model: str
    llm_api_key: str
    replicate_api_token: str
    replicate_cover_model_version: str
    replicate_cover_model: str
    wechat_app_id: str
    wechat_app_secret: str
    wechat_access_token: str
    free_hot_sources: list[str]
    database_url: str
    baidu_search_api_key: str = ""
    websearch_mcp_enabled: bool = False
    websearch_mcp_command: str = "npx"
    websearch_mcp_args: list[str] = field(default_factory=lambda: ["-y", "tavily-mcp@0.1.3"])
    websearch_mcp_timeout: int = 60
    tavily_api_key: str = ""
    wechat_component_app_id: str = ""
    wechat_component_app_secret: str = ""
    wechat_component_token: str = ""
    wechat_component_aes_key: str = ""
    wechat_component_auth_redirect_uri: str = ""
    wechat_component_verify_ticket: str = ""
    wechat_component_access_token: str = ""

    @classmethod
    def from_env_file(cls, path: str | Path = ".env") -> "AgentConfig":
        values = dict(os.environ)
        env_path = Path(path)
        if env_path.exists():
            values.update(_parse_env_file(env_path))
        return cls(
            llm_provider=values.get("LLM_PROVIDER", "deepseek"),
            llm_base_url=values.get("LLM_BASE_URL", "https://api.deepseek.com"),
            llm_model=values.get("LLM_MODEL", "deepseek-chat"),
            llm_api_key=values.get("LLM_API_KEY", ""),
            replicate_api_token=values.get("REPLICATE_API_TOKEN", ""),
            replicate_cover_model_version=values.get("REPLICATE_COVER_MODEL_VERSION", ""),
            replicate_cover_model=values.get(
                "REPLICATE_COVER_MODEL",
                values.get("REPLICATE_COVER_MODEL_VERSION", "black-forest-labs/flux-1.1-pro"),
            ),
            wechat_app_id=values.get("WECHAT_APP_ID", ""),
            wechat_app_secret=values.get("WECHAT_APP_SECRET", ""),
            wechat_access_token=values.get("WECHAT_ACCESS_TOKEN", ""),
            free_hot_sources=_parse_csv(values.get("FREE_HOT_SOURCES", "google_news_rss,hn,github")),
            database_url=values.get("DATABASE_URL", ""),
            baidu_search_api_key=values.get("BAIDU_SEARCH_API_KEY", ""),
            websearch_mcp_enabled=_parse_bool(values.get("WEBSEARCH_MCP_ENABLED", "")),
            websearch_mcp_command=values.get("WEBSEARCH_MCP_COMMAND", "npx"),
            websearch_mcp_args=_parse_csv(values.get("WEBSEARCH_MCP_ARGS", "-y,tavily-mcp@0.1.3")),
            websearch_mcp_timeout=int(values.get("WEBSEARCH_MCP_TIMEOUT", "60") or "60"),
            tavily_api_key=values.get("TAVILY_API_KEY", ""),
            wechat_component_app_id=values.get("WECHAT_COMPONENT_APP_ID", ""),
            wechat_component_app_secret=values.get("WECHAT_COMPONENT_APP_SECRET", ""),
            wechat_component_token=values.get("WECHAT_COMPONENT_TOKEN", ""),
            wechat_component_aes_key=values.get("WECHAT_COMPONENT_AES_KEY", ""),
            wechat_component_auth_redirect_uri=values.get("WECHAT_COMPONENT_AUTH_REDIRECT_URI", ""),
            wechat_component_verify_ticket=values.get("WECHAT_COMPONENT_VERIFY_TICKET", ""),
            wechat_component_access_token=values.get("WECHAT_COMPONENT_ACCESS_TOKEN", ""),
        )

    def redacted_status(self) -> dict[str, str]:
        return {
            "LLM_PROVIDER": self.llm_provider or "EMPTY",
            "LLM_BASE_URL": "SET" if self.llm_base_url else "EMPTY",
            "LLM_MODEL": self.llm_model or "EMPTY",
            "LLM_API_KEY": "SET" if self.llm_api_key else "EMPTY",
            "REPLICATE_API_TOKEN": "SET" if self.replicate_api_token else "EMPTY",
            "REPLICATE_COVER_MODEL_VERSION": "SET" if self.replicate_cover_model_version else "EMPTY",
            "REPLICATE_COVER_MODEL": self.replicate_cover_model or "EMPTY",
            "WECHAT_APP_ID": "SET" if self.wechat_app_id else "EMPTY",
            "WECHAT_APP_SECRET": "SET" if self.wechat_app_secret else "EMPTY",
            "WECHAT_ACCESS_TOKEN": "SET" if self.wechat_access_token else "EMPTY",
            "WECHAT_COMPONENT_APP_ID": "SET" if self.wechat_component_app_id else "EMPTY",
            "WECHAT_COMPONENT_APP_SECRET": "SET" if self.wechat_component_app_secret else "EMPTY",
            "WECHAT_COMPONENT_TOKEN": "SET" if self.wechat_component_token else "EMPTY",
            "WECHAT_COMPONENT_AES_KEY": "SET" if self.wechat_component_aes_key else "EMPTY",
            "WECHAT_COMPONENT_AUTH_REDIRECT_URI": "SET" if self.wechat_component_auth_redirect_uri else "EMPTY",
            "WECHAT_COMPONENT_VERIFY_TICKET": "SET" if self.wechat_component_verify_ticket else "EMPTY",
            "WECHAT_COMPONENT_ACCESS_TOKEN": "SET" if self.wechat_component_access_token else "EMPTY",
            "DATABASE_URL": "SET" if self.database_url else "EMPTY",
            "BAIDU_SEARCH_API_KEY": "SET" if self.baidu_search_api_key else "EMPTY",
            "WEBSEARCH_MCP_ENABLED": "true" if self.websearch_mcp_enabled else "false",
            "WEBSEARCH_MCP_COMMAND": self.websearch_mcp_command or "EMPTY",
            "WEBSEARCH_MCP_ARGS": "SET" if self.websearch_mcp_args else "EMPTY",
            "TAVILY_API_KEY": "SET" if self.tavily_api_key else "EMPTY",
        }

    def build_llm_provider(self) -> OpenAICompatibleLLMProvider:
        return OpenAICompatibleLLMProvider(
            api_key=self.llm_api_key,
            base_url=self.llm_base_url,
            model=self.llm_model,
        )

    def build_image_provider(self) -> ReplicateImageProvider:
        return ReplicateImageProvider(
            api_token=self.replicate_api_token,
            model_version=self.replicate_cover_model,
        )

    def build_wechat_publisher(self) -> WeChatDraftPublisher:
        return WeChatDraftPublisher(app_id=self.wechat_app_id, app_secret=self.wechat_app_secret)

    def build_free_hot_config(self) -> FreeHotConfig:
        return FreeHotConfig(
            sources=self.free_hot_sources,
        )


def _parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = _strip_quotes(value.strip())
    return values


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _parse_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _parse_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}
