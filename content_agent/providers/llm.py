from __future__ import annotations

import json
from dataclasses import dataclass
from urllib import error, request


@dataclass(frozen=True)
class OpenAICompatibleLLMProvider:
    api_key: str
    base_url: str
    model: str

    def build_payload(self, prompt: str) -> dict:
        if not prompt.strip():
            raise ValueError("prompt cannot be empty")
        return {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
        }

    def generate(self, prompt: str) -> str:
        if not self.api_key.strip():
            raise RuntimeError("LLM_API_KEY is empty. Please set it in .env or /opt/media-agent/.env.production.")
        payload = json.dumps(self.build_payload(prompt)).encode("utf-8")
        endpoint = self.base_url.rstrip("/") + "/chat/completions"
        http_request = request.Request(
            endpoint,
            data=payload,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with request.urlopen(http_request, timeout=60) as response:
                data = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            raise RuntimeError(_format_llm_http_error(exc)) from exc
        return data["choices"][0]["message"]["content"]


def _format_llm_http_error(exc: error.HTTPError) -> str:
    if exc.code in {401, 403}:
        return (
            f"LLM API unauthorized ({exc.code}). Please check LLM_API_KEY, "
            "LLM_BASE_URL, and LLM_MODEL in .env or /opt/media-agent/.env.production."
        )
    return f"LLM API request failed with HTTP {exc.code}: {exc.reason}"
