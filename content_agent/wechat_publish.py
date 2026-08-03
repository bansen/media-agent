from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from PIL import Image

from .config import AgentConfig
from .exporters import build_wechat_draft_payload
from .models import WorkflowResult


class WeChatPublisherProtocol(Protocol):
    def upload_thumb_material(self, access_token: str, image_path: str | Path, mime_type: str = "image/jpeg") -> str:
        ...

    def submit_draft(self, access_token: str, payload: dict) -> dict:
        ...


@dataclass(frozen=True)
class WeChatDraftPublishResult:
    thumb_media_id: str
    payload: dict
    response: dict


def publish_wechat_draft(
    result: WorkflowResult,
    content_html: str,
    cover_image_path: str | Path,
    config: AgentConfig,
    publisher: WeChatPublisherProtocol | None = None,
) -> WeChatDraftPublishResult:
    cover_path = Path(cover_image_path)
    if not cover_path.exists():
        raise FileNotFoundError(f"cover image not found: {cover_path}")
    if not content_html.strip():
        raise ValueError("content_html cannot be empty")

    wechat = publisher or config.build_wechat_publisher()
    access_token = config.wechat_access_token or wechat.fetch_access_token()
    thumb_path = prepare_wechat_thumb_image(cover_path)
    thumb_media_id = wechat.upload_thumb_material(access_token, thumb_path, mime_type="image/jpeg")
    payload = build_wechat_draft_payload(result, thumb_media_id=thumb_media_id, content_html=content_html)
    response = wechat.submit_draft(access_token, payload)
    return WeChatDraftPublishResult(thumb_media_id=thumb_media_id, payload=payload, response=response)


def prepare_wechat_thumb_image(image_path: str | Path, max_bytes: int = 64 * 1024) -> Path:
    path = Path(image_path)
    if _is_jpeg(path) and path.stat().st_size <= max_bytes:
        return path

    output_path = path.with_name(f"{path.stem}_wechat_thumb.jpg")
    with Image.open(path) as image:
        rgb_image = _crop_to_aspect(image.convert("RGB"), 16 / 9)
        rgb_image.thumbnail((900, 506), Image.Resampling.LANCZOS)
        quality = 92
        while True:
            rgb_image.save(output_path, format="JPEG", quality=quality, optimize=True, progressive=False)
            if output_path.stat().st_size <= max_bytes:
                return output_path
            if quality > 48:
                quality -= 10
                continue
            width, height = rgb_image.size
            if width <= 320 or height <= 180:
                return output_path
            rgb_image = rgb_image.resize((int(width * 0.85), int(height * 0.85)), Image.Resampling.LANCZOS)
            quality = 82


def _is_jpeg(path: Path) -> bool:
    with path.open("rb") as file:
        return file.read(2) == b"\xff\xd8"


def _crop_to_aspect(image: Image.Image, aspect_ratio: float) -> Image.Image:
    width, height = image.size
    current_ratio = width / height
    if abs(current_ratio - aspect_ratio) < 0.01:
        return image
    if current_ratio > aspect_ratio:
        new_width = int(height * aspect_ratio)
        left = (width - new_width) // 2
        return image.crop((left, 0, left + new_width, height))
    new_height = int(width / aspect_ratio)
    top = (height - new_height) // 2
    return image.crop((0, top, width, top + new_height))
