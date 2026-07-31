from __future__ import annotations

import json
from dataclasses import dataclass
from urllib import request


@dataclass(frozen=True)
class ReplicateImageProvider:
    api_token: str
    model_version: str

    def build_prediction_payload(self, prompt: str) -> dict:
        if not prompt.strip():
            raise ValueError("prompt cannot be empty")
        return {
            "version": self.model_version,
            "input": {
                "prompt": prompt,
                "num_outputs": 1,
                "aspect_ratio": "16:9",
            },
        }

    def create_prediction(self, prompt: str) -> dict:
        payload = json.dumps(self.build_prediction_payload(prompt)).encode("utf-8")
        http_request = request.Request(
            "https://api.replicate.com/v1/predictions",
            data=payload,
            headers={
                "Authorization": f"Token {self.api_token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with request.urlopen(http_request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
