from __future__ import annotations

from io import BytesIO
from dataclasses import dataclass
import os
import json
from pathlib import Path
from typing import Protocol
from urllib import request
from urllib.error import HTTPError

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


@dataclass(frozen=True)
class SeedreamHttpRunner:
    api_token: str

    def run(self, model: str, input: dict):
        if not self.api_token.strip():
            raise ValueError("请配置 ARK_API_KEY（火山方舟 API Key）")
        sizes = {"16:9": "2560x1440", "3:4": "1728x2304"}
        payload = {
            "model": model,
            "prompt": input["prompt"],
            "size": sizes[input["aspect_ratio"]],
            "response_format": "url",
            "sequential_image_generation": "disabled",
            "stream": False,
            "watermark": False,
        }
        req = request.Request(
            "https://ark.cn-beijing.volces.com/api/v3/images/generations",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": f"Bearer {self.api_token}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=180) as response:
                result = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            reasons = {401: "API Key 无效", 403: "请检查模型开通权限", 400: "请检查模型 ID、尺寸或提示词", 404: "模型不存在或当前账号未开通，请核对 SEEDREAM_MODEL 并在模型广场开通", 429: "额度不足或请求过于频繁"}
            raise RuntimeError(f"Seedream 请求失败（HTTP {exc.code}）：{reasons.get(exc.code, '请稍后重试')}；请在方舟控制台核对") from None
        images = result.get("data") or []
        if result.get("error") or not images or not images[0].get("url"):
            raise RuntimeError("Seedream 未返回图片，请检查内容审核结果、模型权限或稍后重试")
        return _HttpFileOutput(images[0]["url"])


def generate_cover_image(
    prompt: str,
    output_dir: Path,
    basename: str,
    model: str,
    runner: ReplicateRunner | None = None,
    api_token: str = "",
    aspect_ratio: str = "16:9",
    provider: str = "replicate",
) -> GeneratedCover:
    if provider not in {"replicate", "seedream"}:
        raise ValueError(f"unsupported image provider: {provider}")
    if not prompt.strip():
        raise ValueError("prompt cannot be empty")
    if not model.strip():
        raise ValueError("请配置 SEEDREAM_MODEL" if provider == "seedream" else "replicate model cannot be empty")
    output_sizes = {"16:9": (1600, 900), "3:4": (1080, 1440)}
    if aspect_ratio not in output_sizes:
        raise ValueError(f"unsupported cover aspect ratio: {aspect_ratio}")
    if api_token and provider == "replicate":
        os.environ["REPLICATE_API_TOKEN"] = api_token
    output_dir.mkdir(parents=True, exist_ok=True)

    active_runner = runner or (SeedreamHttpRunner(api_token) if provider == "seedream" else _default_runner(api_token))
    clean_prompt = _clean_replicate_prompt(prompt)
    output = active_runner.run(
        model,
        input={
            "prompt": clean_prompt,
            "prompt_upsampling": True,
            "aspect_ratio": aspect_ratio,
        },
    )
    file_output = output[0] if isinstance(output, list) else output
    image_bytes = file_output.read()
    path = output_dir / f"{basename}_cover.jpg"
    _write_cover_image(image_bytes, path, output_sizes[aspect_ratio])
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


def _write_cover_image(image_bytes: bytes, path: Path, output_size: tuple[int, int]) -> None:
    try:
        with Image.open(BytesIO(image_bytes)) as image:
            cover = ImageOps.fit(image.convert("RGB"), output_size, method=Image.Resampling.LANCZOS)
            cover.save(path, format="JPEG", quality=94, optimize=True, progressive=False)
    except (OSError, UnidentifiedImageError):
        path.write_bytes(image_bytes)
