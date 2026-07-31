from __future__ import annotations

import json
from dataclasses import dataclass
from urllib import request


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
        with request.urlopen(http_request, timeout=60) as response:
            data = json.loads(response.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"]
