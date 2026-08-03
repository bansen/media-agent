from __future__ import annotations

from io import BytesIO
from dataclasses import dataclass
import os
import json
from pathlib import Path
from typing import Protocol
from urllib import request

from PIL import Image, ImageOps, UnidentifiedImageError


class ReplicateRunner(Protocol):
    def run(self, model: str, input: dict):
        ...


@dataclass(frozen=True)
class GeneratedCover:
    path: Path
    url: str
    model: str
    prompt: str


@dataclass(frozen=True)
class ReplicateHttpRunner:
    api_token: str

    def build_prediction_request(self, model: str, input_payload: dict) -> tuple[str, dict, dict]:
        if "/" not in model:
            raise ValueError("replicate model must use owner/name format")
        owner, name = model.split("/", 1)
        endpoint = f"https://api.replicate.com/v1/models/{owner}/{name}/predictions"
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
            "Prefer": "wait=60",
        }
        return endpoint, headers, {"input": input_payload}

    def run(self, model: str, input: dict):
        endpoint, headers, body = self.build_prediction_request(model, input)
        http_request = request.Request(
            endpoint,
            data=json.dumps(body).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with request.urlopen(http_request, timeout=90) as response:
            result = json.loads(response.read().decode("utf-8"))
        output = result.get("output")
        if result.get("status") not in {"succeeded", "processing", "starting"}:
            raise RuntimeError(f"Replicate prediction failed: {result}")
        if isinstance(output, list) and output:
            return _HttpFileOutput(output[0])
        if isinstance(output, str):
            return _HttpFileOutput(output)
        raise RuntimeError(f"Replicate did not return an output URL within sync wait: {result}")


@dataclass(frozen=True)
class _HttpFileOutput:
    url: str

    def read(self) -> bytes:
        with request.urlopen(self.url, timeout=90) as response:
            return response.read()


def generate_cover_image(
    prompt: str,
    output_dir: Path,
    basename: str,
    model: str,
    runner: ReplicateRunner | None = None,
    api_token: str = "",
) -> GeneratedCover:
    if not prompt.strip():
        raise ValueError("prompt cannot be empty")
    if not model.strip():
        raise ValueError("replicate model cannot be empty")
    if api_token:
        os.environ["REPLICATE_API_TOKEN"] = api_token
    output_dir.mkdir(parents=True, exist_ok=True)

    active_runner = runner or _default_runner(api_token)
    clean_prompt = _clean_replicate_prompt(prompt)
    output = active_runner.run(
        model,
        input={
            "prompt": clean_prompt,
            "prompt_upsampling": True,
            "aspect_ratio": "16:9",
        },
    )
    file_output = output[0] if isinstance(output, list) else output
    image_bytes = file_output.read()
    path = output_dir / f"{basename}_cover.jpg"
    _write_cover_image(image_bytes, path)
    return GeneratedCover(
        path=path,
        url=getattr(file_output, "url", ""),
        model=model,
        prompt=clean_prompt,
    )


def _default_runner(api_token: str):
    try:
        import replicate
    except ImportError:
        if not api_token:
            raise RuntimeError("REPLICATE_API_TOKEN is required for --generate-cover when the replicate package is not installed")
        return ReplicateHttpRunner(api_token=api_token)
    return replicate


def _clean_replicate_prompt(prompt: str) -> str:
    return prompt.removeprefix("Replicate image prompt:").strip()


def _write_cover_image(image_bytes: bytes, path: Path) -> None:
    try:
        with Image.open(BytesIO(image_bytes)) as image:
            cover = ImageOps.fit(image.convert("RGB"), (1600, 900), method=Image.Resampling.LANCZOS)
            cover.save(path, format="JPEG", quality=94, optimize=True, progressive=False)
    except (OSError, UnidentifiedImageError):
        path.write_bytes(image_bytes)
