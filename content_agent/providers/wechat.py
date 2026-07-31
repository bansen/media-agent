from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4
from urllib import parse, request


WECHAT_API_BASE = "https://api.weixin.qq.com"


class WeChatAPIError(RuntimeError):
    def __init__(self, operation: str, response: dict):
        self.operation = operation
        self.response = response
        super().__init__(_wechat_error_message(operation, response))


@dataclass(frozen=True)
class WeChatDraftPublisher:
    app_id: str
    app_secret: str

    def access_token_url(self) -> str:
        params = parse.urlencode(
            {
                "grant_type": "client_credential",
                "appid": self.app_id,
                "secret": self.app_secret,
            }
        )
        return f"{WECHAT_API_BASE}/cgi-bin/token?{params}"

    def draft_add_url(self, access_token: str) -> str:
        params = parse.urlencode({"access_token": access_token})
        return f"{WECHAT_API_BASE}/cgi-bin/draft/add?{params}"

    def permanent_material_add_url(self, access_token: str, media_type: str = "thumb") -> str:
        if media_type not in {"image", "voice", "video", "thumb"}:
            raise ValueError("media_type must be image, voice, video, or thumb")
        params = parse.urlencode({"access_token": access_token, "type": media_type})
        return f"{WECHAT_API_BASE}/cgi-bin/material/add_material?{params}"

    def fetch_access_token(self) -> str:
        http_request = request.Request(self.access_token_url(), method="GET")
        with request.urlopen(http_request, timeout=60) as response:
            result = json.loads(response.read().decode("utf-8"))
        token = result.get("access_token")
        if not token:
            raise self.error_from_response(result, operation="fetch_access_token")
        return token

    def error_from_response(self, response: dict, operation: str) -> WeChatAPIError:
        return WeChatAPIError(operation=operation, response=response)

    def build_media_upload_body(
        self,
        filename: str,
        data: bytes,
        mime_type: str,
        boundary: str | None = None,
    ) -> tuple[str, bytes]:
        if not filename.strip():
            raise ValueError("filename cannot be empty")
        if not data:
            raise ValueError("data cannot be empty")
        upload_boundary = boundary or f"----content-agent-{uuid4().hex}"
        lines = [
            f"--{upload_boundary}\r\n".encode("utf-8"),
            f'Content-Disposition: form-data; name="media"; filename="{filename}"\r\n'.encode("utf-8"),
            f"Content-Type: {mime_type}\r\n\r\n".encode("utf-8"),
            data,
            b"\r\n",
            f"--{upload_boundary}--\r\n".encode("utf-8"),
        ]
        return f"multipart/form-data; boundary={upload_boundary}", b"".join(lines)

    def upload_thumb_material(self, access_token: str, image_path: str | Path, mime_type: str = "image/jpeg") -> str:
        path = Path(image_path)
        content_type, body = self.build_media_upload_body(path.name, path.read_bytes(), mime_type)
        http_request = request.Request(
            self.permanent_material_add_url(access_token, media_type="thumb"),
            data=body,
            headers={"Content-Type": content_type},
            method="POST",
        )
        with request.urlopen(http_request, timeout=60) as response:
            result = json.loads(response.read().decode("utf-8"))
        media_id = result.get("media_id")
        if not media_id:
            raise self.error_from_response(result, operation="upload_thumb_material")
        return media_id

    def submit_draft(self, access_token: str, payload: dict) -> dict:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        http_request = request.Request(
            self.draft_add_url(access_token),
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(http_request, timeout=60) as response:
            result = json.loads(response.read().decode("utf-8"))
        if result.get("errcode") not in (None, 0):
            raise self.error_from_response(result, operation="submit_draft")
        return result


def _wechat_error_message(operation: str, response: dict) -> str:
    errcode = response.get("errcode")
    errmsg = response.get("errmsg", "")
    if errcode == 40164:
        return (
            f"WeChat API {operation} failed: errcode=40164，当前公网 IP 不在公众号后台 IP 白名单中。"
            f"微信返回：{errmsg}。请把返回里的 IPv4 地址加入公众号后台「设置与开发 -> 基本配置 -> IP 白名单」，"
            "或在固定公网 IP 的服务器上运行。"
        )
    return f"WeChat API {operation} failed: {response}"
