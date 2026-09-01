from __future__ import annotations

import json
import os
import secrets
import base64
import hashlib
import hmac
import struct
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from time import time
from typing import Any
from urllib import parse, request

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from .database import ComponentStateRow, ExternalAuthAccountRow, OAuthStateRow, PlatformAccountRow, UserRow, UserSessionRow


SESSION_COOKIE = "media_agent_session"


@dataclass(frozen=True)
class ServerOwnerConfig:
    login_password: str = ""
    display_name: str = "服务器管理员"
    wechat_app_id: str = ""
    wechat_app_secret: str = ""
    wechat_access_token: str = ""

    @classmethod
    def from_env(cls) -> "ServerOwnerConfig":
        return cls(
            login_password=os.environ.get("OWNER_LOGIN_PASSWORD", "") or _read_env_value("OWNER_LOGIN_PASSWORD"),
            display_name=os.environ.get("OWNER_DISPLAY_NAME", "")
            or _read_env_value("OWNER_DISPLAY_NAME")
            or "服务器管理员",
            wechat_app_id=os.environ.get("WECHAT_APP_ID", "") or _read_env_value("WECHAT_APP_ID"),
            wechat_app_secret=os.environ.get("WECHAT_APP_SECRET", "") or _read_env_value("WECHAT_APP_SECRET"),
            wechat_access_token=os.environ.get("WECHAT_ACCESS_TOKEN", "") or _read_env_value("WECHAT_ACCESS_TOKEN"),
        )

    def is_configured(self) -> bool:
        return bool(len(self.login_password) >= 16 and self.wechat_app_id and self.wechat_app_secret)

    def authenticate(self, password: str) -> bool:
        return bool(self.is_configured() and hmac.compare_digest(self.login_password, password))


@dataclass(frozen=True)
class WeChatLoginConfig:
    app_id: str = ""
    app_secret: str = ""
    redirect_uri: str = ""
    scope: str = "snsapi_login"

    @classmethod
    def from_env(cls) -> "WeChatLoginConfig":
        return cls(
            app_id=os.environ.get("WECHAT_LOGIN_APP_ID", "") or _read_env_value("WECHAT_LOGIN_APP_ID"),
            app_secret=os.environ.get("WECHAT_LOGIN_APP_SECRET", "") or _read_env_value("WECHAT_LOGIN_APP_SECRET"),
            redirect_uri=os.environ.get("WECHAT_LOGIN_REDIRECT_URI", "") or _read_env_value("WECHAT_LOGIN_REDIRECT_URI"),
            scope=os.environ.get("WECHAT_LOGIN_SCOPE", "") or _read_env_value("WECHAT_LOGIN_SCOPE") or "snsapi_login",
        )

    def is_configured(self) -> bool:
        return bool(self.app_id and self.app_secret and self.redirect_uri)


@dataclass(frozen=True)
class WeChatComponentConfig:
    app_id: str = ""
    app_secret: str = ""
    token: str = ""
    aes_key: str = ""
    auth_redirect_uri: str = ""
    verify_ticket: str = ""
    access_token: str = ""

    @classmethod
    def from_env(cls) -> "WeChatComponentConfig":
        return cls(
            app_id=os.environ.get("WECHAT_COMPONENT_APP_ID", "") or _read_env_value("WECHAT_COMPONENT_APP_ID"),
            app_secret=os.environ.get("WECHAT_COMPONENT_APP_SECRET", "")
            or _read_env_value("WECHAT_COMPONENT_APP_SECRET"),
            token=os.environ.get("WECHAT_COMPONENT_TOKEN", "") or _read_env_value("WECHAT_COMPONENT_TOKEN"),
            aes_key=os.environ.get("WECHAT_COMPONENT_AES_KEY", "") or _read_env_value("WECHAT_COMPONENT_AES_KEY"),
            auth_redirect_uri=os.environ.get("WECHAT_COMPONENT_AUTH_REDIRECT_URI", "")
            or _read_env_value("WECHAT_COMPONENT_AUTH_REDIRECT_URI"),
            verify_ticket=os.environ.get("WECHAT_COMPONENT_VERIFY_TICKET", "")
            or _read_env_value("WECHAT_COMPONENT_VERIFY_TICKET"),
            access_token=os.environ.get("WECHAT_COMPONENT_ACCESS_TOKEN", "")
            or _read_env_value("WECHAT_COMPONENT_ACCESS_TOKEN"),
        )

    def is_configured_for_auth(self) -> bool:
        return bool(self.app_id and self.app_secret and self.auth_redirect_uri)

    def can_fetch_component_token(self) -> bool:
        return bool(self.access_token or (self.app_id and self.app_secret and self.verify_ticket))


class WeChatOAuthProvider:
    def __init__(self, config: WeChatLoginConfig):
        self.config = config

    def authorization_url(self, state: str) -> str:
        params = parse.urlencode(
            {
                "appid": self.config.app_id,
                "redirect_uri": self.config.redirect_uri,
                "response_type": "code",
                "scope": self.config.scope,
                "state": state,
            }
        )
        return f"https://open.weixin.qq.com/connect/qrconnect?{params}#wechat_redirect"

    def fetch_access_token(self, code: str) -> dict[str, Any]:
        params = parse.urlencode(
            {
                "appid": self.config.app_id,
                "secret": self.config.app_secret,
                "code": code,
                "grant_type": "authorization_code",
            }
        )
        return _get_json(f"https://api.weixin.qq.com/sns/oauth2/access_token?{params}")

    def fetch_userinfo(self, access_token: str, openid: str) -> dict[str, Any]:
        params = parse.urlencode({"access_token": access_token, "openid": openid, "lang": "zh_CN"})
        return _get_json(f"https://api.weixin.qq.com/sns/userinfo?{params}")


class WeChatComponentProvider:
    def __init__(self, config: WeChatComponentConfig):
        self.config = config

    def authorization_url(self, pre_auth_code: str, state: str = "") -> str:
        redirect_uri = self.config.auth_redirect_uri
        if state:
            separator = "&" if parse.urlparse(redirect_uri).query else "?"
            redirect_uri = f"{redirect_uri}{separator}{parse.urlencode({'state': state})}"
        params = parse.urlencode(
            {
                "component_appid": self.config.app_id,
                "pre_auth_code": pre_auth_code,
                "redirect_uri": redirect_uri,
                "auth_type": "3",
            }
        )
        return f"https://mp.weixin.qq.com/cgi-bin/componentloginpage?{params}"

    def fetch_component_access_token(self) -> str:
        if self.config.access_token:
            return self.config.access_token
        if not self.config.verify_ticket:
            raise RuntimeError("WECHAT_COMPONENT_VERIFY_TICKET is required to fetch component_access_token")
        payload = {
            "component_appid": self.config.app_id,
            "component_appsecret": self.config.app_secret,
            "component_verify_ticket": self.config.verify_ticket,
        }
        result = _post_json("https://api.weixin.qq.com/cgi-bin/component/api_component_token", payload)
        if not result.get("component_access_token"):
            raise RuntimeError(f"WeChat did not return component_access_token: {result}")
        return str(result["component_access_token"])

    def fetch_pre_auth_code(self, component_access_token: str | None = None) -> str:
        token = component_access_token or self.fetch_component_access_token()
        url = "https://api.weixin.qq.com/cgi-bin/component/api_create_preauthcode?" + parse.urlencode(
            {"component_access_token": token}
        )
        result = _post_json(url, {"component_appid": self.config.app_id})
        if not result.get("pre_auth_code"):
            raise RuntimeError(f"WeChat did not return pre_auth_code: {result}")
        return str(result["pre_auth_code"])

    def query_auth(self, authorization_code: str, component_access_token: str | None = None) -> dict[str, Any]:
        token = component_access_token or self.fetch_component_access_token()
        url = "https://api.weixin.qq.com/cgi-bin/component/api_query_auth?" + parse.urlencode(
            {"component_access_token": token}
        )
        result = _post_json(
            url,
            {
                "component_appid": self.config.app_id,
                "authorization_code": authorization_code,
            },
        )
        info = result.get("authorization_info") or {}
        if not info.get("authorizer_appid"):
            raise RuntimeError(f"WeChat did not return authorization_info: {result}")
        return info

    def refresh_authorizer_access_token(
        self,
        authorizer_appid: str,
        authorizer_refresh_token: str,
        component_access_token: str | None = None,
    ) -> dict[str, Any]:
        token = component_access_token or self.fetch_component_access_token()
        url = "https://api.weixin.qq.com/cgi-bin/component/api_authorizer_token?" + parse.urlencode(
            {"component_access_token": token}
        )
        result = _post_json(
            url,
            {
                "component_appid": self.config.app_id,
                "authorizer_appid": authorizer_appid,
                "authorizer_refresh_token": authorizer_refresh_token,
            },
        )
        if not result.get("authorizer_access_token"):
            raise RuntimeError(f"WeChat did not return authorizer_access_token: {result}")
        return result

    def fetch_authorizer_info(
        self,
        authorizer_appid: str,
        component_access_token: str | None = None,
    ) -> dict[str, Any]:
        token = component_access_token or self.fetch_component_access_token()
        url = "https://api.weixin.qq.com/cgi-bin/component/api_get_authorizer_info?" + parse.urlencode(
            {"component_access_token": token}
        )
        result = _post_json(
            url,
            {
                "component_appid": self.config.app_id,
                "authorizer_appid": authorizer_appid,
            },
        )
        return result.get("authorizer_info") or result


@dataclass(frozen=True)
class AuthUser:
    id: int
    display_name: str
    provider: str
    provider_user_id: str


class AuthStore:
    def __init__(self, session_factory: sessionmaker):
        self._session_factory = session_factory

    def create_server_owner_session(self, config: ServerOwnerConfig, password: str) -> str:
        if not config.is_configured():
            raise RuntimeError("服务器管理员登录尚未配置")
        if not config.authenticate(password):
            raise ValueError("管理员密码不正确")
        user = self.create_manual_wechat_user(
            display_name=config.display_name,
            app_id=config.wechat_app_id,
            app_secret=config.wechat_app_secret,
            access_token=config.wechat_access_token,
        )
        return self.create_session(user.id)

    def create_oauth_state(self, provider: str, next_path: str = "/app", ttl_seconds: int = 600) -> str:
        now = time()
        state = secrets.token_urlsafe(24)
        with self._session_factory() as session:
            session.add(
                OAuthStateRow(
                    state=state,
                    provider=provider,
                    next_path=_safe_next_path(next_path),
                    created_at=now,
                    expires_at=now + ttl_seconds,
                )
            )
            session.commit()
        return state

    def consume_oauth_state(self, state: str, provider: str) -> str | None:
        now = time()
        with self._session_factory() as session:
            row = session.get(OAuthStateRow, state)
            if row is None or row.provider != provider or row.consumed_at is not None or row.expires_at < now:
                return None
            row.consumed_at = now
            session.commit()
            return row.next_path or "/app"

    def upsert_external_user(
        self,
        provider: str,
        provider_user_id: str,
        union_id: str = "",
        display_name: str = "",
        profile: dict[str, Any] | None = None,
    ) -> AuthUser:
        now = time()
        profile = profile or {}
        with self._session_factory() as session:
            account = session.scalar(
                select(ExternalAuthAccountRow).where(
                    ExternalAuthAccountRow.provider == provider,
                    ExternalAuthAccountRow.provider_user_id == provider_user_id,
                )
            )
            if account is None:
                user = UserRow(display_name=display_name or provider_user_id, created_at=now, updated_at=now)
                session.add(user)
                session.flush()
                account = ExternalAuthAccountRow(
                    user_id=user.id,
                    provider=provider,
                    provider_user_id=provider_user_id,
                    created_at=now,
                    updated_at=now,
                )
                session.add(account)
            else:
                user = session.get(UserRow, account.user_id)
            user.display_name = display_name or user.display_name or provider_user_id
            user.updated_at = now
            account.union_id = union_id or account.union_id
            account.display_name = user.display_name
            account.profile_json = profile
            account.updated_at = now
            session.commit()
            return AuthUser(
                id=user.id,
                display_name=user.display_name,
                provider=account.provider,
                provider_user_id=account.provider_user_id,
            )

    def create_manual_wechat_user(
        self,
        display_name: str,
        app_id: str,
        app_secret: str,
        access_token: str = "",
    ) -> AuthUser:
        now = time()
        clean_app_id = app_id.strip()
        if not clean_app_id or not app_secret.strip():
            raise ValueError("WECHAT_APP_ID and WECHAT_APP_SECRET are required")
        with self._session_factory() as session:
            account = session.scalar(
                select(PlatformAccountRow).where(
                    PlatformAccountRow.platform == "wechat",
                    PlatformAccountRow.auth_type == "manual",
                    PlatformAccountRow.credentials_json["app_id"].as_string() == clean_app_id,
                )
            )
            if account is None:
                user = UserRow(display_name=display_name.strip() or clean_app_id, created_at=now, updated_at=now)
                session.add(user)
                session.flush()
                account = PlatformAccountRow(
                    user_id=user.id,
                    platform="wechat",
                    auth_type="manual",
                    created_at=now,
                    updated_at=now,
                )
                session.add(account)
            else:
                user = session.get(UserRow, account.user_id)
            user.display_name = display_name.strip() or user.display_name or clean_app_id
            user.updated_at = now
            account.display_name = user.display_name
            account.credentials_json = {
                "app_id": clean_app_id,
                "app_secret": app_secret.strip(),
                "access_token": access_token.strip(),
            }
            account.updated_at = now
            self._upsert_manual_external_account(session, user.id, clean_app_id, user.display_name, now)
            session.commit()
            return AuthUser(
                id=user.id,
                display_name=user.display_name,
                provider="manual_wechat",
                provider_user_id=clean_app_id,
            )

    def manual_wechat_account_for_user(self, user_id: int) -> dict | None:
        with self._session_factory() as session:
            account = session.scalar(
                select(PlatformAccountRow).where(
                    PlatformAccountRow.user_id == user_id,
                    PlatformAccountRow.platform == "wechat",
                    PlatformAccountRow.auth_type == "manual",
                )
            )
            if account is None:
                return None
            credentials = account.credentials_json or {}
            return {
                "id": account.id,
                "display_name": account.display_name,
                "app_id": credentials.get("app_id", ""),
                "app_secret": credentials.get("app_secret", ""),
                "access_token": credentials.get("access_token", ""),
            }

    def update_manual_wechat_account(
        self,
        user_id: int,
        display_name: str,
        app_id: str,
        app_secret: str = "",
        access_token: str = "",
    ) -> None:
        now = time()
        clean_app_id = app_id.strip()
        if not clean_app_id:
            raise ValueError("WECHAT_APP_ID is required")
        with self._session_factory() as session:
            user = session.get(UserRow, user_id)
            if user is None:
                raise ValueError("user not found")
            account = session.scalar(
                select(PlatformAccountRow).where(
                    PlatformAccountRow.user_id == user_id,
                    PlatformAccountRow.platform == "wechat",
                    PlatformAccountRow.auth_type == "manual",
                )
            )
            if account is None:
                account = PlatformAccountRow(
                    user_id=user_id,
                    platform="wechat",
                    auth_type="manual",
                    created_at=now,
                    updated_at=now,
                )
                session.add(account)
            old_credentials = account.credentials_json or {}
            next_secret = app_secret.strip() or old_credentials.get("app_secret", "")
            if not next_secret:
                raise ValueError("WECHAT_APP_SECRET is required")
            user.display_name = display_name.strip() or user.display_name or clean_app_id
            user.updated_at = now
            account.display_name = user.display_name
            account.credentials_json = {
                "app_id": clean_app_id,
                "app_secret": next_secret,
                "access_token": access_token.strip(),
            }
            account.updated_at = now
            self._upsert_manual_external_account(session, user_id, clean_app_id, user.display_name, now)
            session.commit()

    def upsert_component_wechat_account(
        self,
        user_id: int,
        authorizer_appid: str,
        display_name: str = "",
        authorizer_refresh_token: str = "",
        authorizer_access_token: str = "",
        expires_in: int = 7200,
        profile: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        now = time()
        clean_appid = authorizer_appid.strip()
        if not clean_appid:
            raise ValueError("authorizer_appid is required")
        profile = profile or {}
        expires_at = now + max(int(expires_in or 0) - 300, 0) if authorizer_access_token else 0
        with self._session_factory() as session:
            user = session.get(UserRow, user_id)
            if user is None:
                raise ValueError("user not found")
            account = session.scalar(
                select(PlatformAccountRow).where(
                    PlatformAccountRow.platform == "wechat",
                    PlatformAccountRow.auth_type == "component",
                    PlatformAccountRow.credentials_json["authorizer_appid"].as_string() == clean_appid,
                )
            )
            if account is None:
                account = PlatformAccountRow(
                    user_id=user_id,
                    platform="wechat",
                    auth_type="component",
                    created_at=now,
                    updated_at=now,
                )
                session.add(account)
            account.user_id = user_id
            account.display_name = display_name.strip() or profile.get("nick_name", "") or clean_appid
            account.credentials_json = {
                "authorizer_appid": clean_appid,
                "authorizer_refresh_token": authorizer_refresh_token.strip(),
                "authorizer_access_token": authorizer_access_token.strip(),
                "authorizer_access_token_expires_at": expires_at,
            }
            account.profile_json = profile
            account.updated_at = now
            session.commit()
            return self.component_wechat_account_for_user(user_id) or {}

    def component_wechat_account_for_user(self, user_id: int) -> dict | None:
        with self._session_factory() as session:
            account = session.scalar(
                select(PlatformAccountRow).where(
                    PlatformAccountRow.user_id == user_id,
                    PlatformAccountRow.platform == "wechat",
                    PlatformAccountRow.auth_type == "component",
                )
            )
            if account is None:
                return None
            credentials = account.credentials_json or {}
            return {
                "id": account.id,
                "auth_type": account.auth_type,
                "display_name": account.display_name,
                "authorizer_appid": credentials.get("authorizer_appid", ""),
                "authorizer_refresh_token": credentials.get("authorizer_refresh_token", ""),
                "authorizer_access_token": credentials.get("authorizer_access_token", ""),
                "authorizer_access_token_expires_at": credentials.get("authorizer_access_token_expires_at", 0),
                "profile": account.profile_json or {},
            }

    def update_component_wechat_token(
        self,
        user_id: int,
        authorizer_appid: str,
        authorizer_access_token: str,
        expires_in: int,
        authorizer_refresh_token: str = "",
    ) -> dict:
        now = time()
        with self._session_factory() as session:
            account = session.scalar(
                select(PlatformAccountRow).where(
                    PlatformAccountRow.user_id == user_id,
                    PlatformAccountRow.platform == "wechat",
                    PlatformAccountRow.auth_type == "component",
                    PlatformAccountRow.credentials_json["authorizer_appid"].as_string() == authorizer_appid,
                )
            )
            if account is None:
                raise ValueError("component wechat account not found")
            credentials = account.credentials_json or {}
            credentials["authorizer_access_token"] = authorizer_access_token
            credentials["authorizer_access_token_expires_at"] = now + max(int(expires_in or 0) - 300, 0)
            if authorizer_refresh_token:
                credentials["authorizer_refresh_token"] = authorizer_refresh_token
            account.credentials_json = credentials
            account.updated_at = now
            session.commit()
        return self.component_wechat_account_for_user(user_id) or {}

    def save_wechat_component_verify_ticket(self, ticket: str) -> None:
        now = time()
        clean_ticket = ticket.strip()
        if not clean_ticket:
            return
        with self._session_factory() as session:
            row = session.get(ComponentStateRow, "wechat")
            if row is None:
                row = ComponentStateRow(provider="wechat", values_json={}, updated_at=now)
                session.add(row)
            values = dict(row.values_json or {})
            values["component_verify_ticket"] = clean_ticket
            row.values_json = values
            row.updated_at = now
            session.commit()

    def wechat_component_verify_ticket(self) -> str:
        with self._session_factory() as session:
            row = session.get(ComponentStateRow, "wechat")
            if row is None:
                return ""
            return str((row.values_json or {}).get("component_verify_ticket", ""))

    def create_session(self, user_id: int, ttl_seconds: int = 60 * 60 * 24 * 30) -> str:
        now = time()
        token = secrets.token_urlsafe(32)
        with self._session_factory() as session:
            session.add(UserSessionRow(token=token, user_id=user_id, created_at=now, expires_at=now + ttl_seconds))
            session.commit()
        return token

    def user_for_session(self, token: str) -> dict | None:
        if not token:
            return None
        now = time()
        with self._session_factory() as session:
            session_row = session.get(UserSessionRow, token)
            if session_row is None or session_row.expires_at < now:
                return None
            user = session.get(UserRow, session_row.user_id)
            account = session.scalar(select(ExternalAuthAccountRow).where(ExternalAuthAccountRow.user_id == user.id))
            return {
                "id": user.id,
                "display_name": user.display_name,
                "provider": account.provider if account else "",
                "provider_user_id": account.provider_user_id if account else "",
            }

    def delete_session(self, token: str) -> None:
        if not token:
            return
        with self._session_factory() as session:
            row = session.get(UserSessionRow, token)
            if row is not None:
                session.delete(row)
                session.commit()

    def _upsert_manual_external_account(self, session, user_id: int, app_id: str, display_name: str, now: float) -> None:
        account = session.scalar(
            select(ExternalAuthAccountRow).where(
                ExternalAuthAccountRow.provider == "manual_wechat",
                ExternalAuthAccountRow.provider_user_id == app_id,
            )
        )
        if account is None:
            account = ExternalAuthAccountRow(
                user_id=user_id,
                provider="manual_wechat",
                provider_user_id=app_id,
                created_at=now,
                updated_at=now,
            )
            session.add(account)
        account.display_name = display_name
        account.updated_at = now


def _get_json(url: str) -> dict[str, Any]:
    http_request = request.Request(url, headers={"User-Agent": "content-agent/0.1"}, method="GET")
    with request.urlopen(http_request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _post_json(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    http_request = request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "User-Agent": "content-agent/0.1"},
        method="POST",
    )
    with request.urlopen(http_request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def parse_wechat_component_event(
    raw_xml: str,
    config: WeChatComponentConfig,
    query_params: dict[str, list[str] | str],
) -> dict[str, str]:
    root = ET.fromstring(raw_xml.strip())
    encrypted = _xml_text(root, "Encrypt")
    if encrypted:
        return _parse_xml_fields(_decrypt_wechat_component_xml(encrypted, config, query_params))
    return _parse_xml_fields(raw_xml)


def _decrypt_wechat_component_xml(
    encrypted: str,
    config: WeChatComponentConfig,
    query_params: dict[str, list[str] | str],
) -> str:
    signature = _first_query_value(query_params, "msg_signature")
    timestamp = _first_query_value(query_params, "timestamp")
    nonce = _first_query_value(query_params, "nonce")
    if config.token and signature:
        expected = hashlib.sha1("".join(sorted([config.token, timestamp, nonce, encrypted])).encode("utf-8")).hexdigest()
        if expected != signature:
            raise RuntimeError("invalid WeChat component message signature")
    if not config.aes_key:
        raise RuntimeError("WECHAT_COMPONENT_AES_KEY is required to decrypt component event")
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    except Exception as exc:
        raise RuntimeError("cryptography package is required to decrypt WeChat component events") from exc
    aes_key = base64.b64decode(config.aes_key + "=")
    cipher = Cipher(algorithms.AES(aes_key), modes.CBC(aes_key[:16]))
    decryptor = cipher.decryptor()
    padded = decryptor.update(base64.b64decode(encrypted)) + decryptor.finalize()
    plain = _strip_pkcs7_padding(padded)
    message_length = struct.unpack("!I", plain[16:20])[0]
    message = plain[20 : 20 + message_length].decode("utf-8")
    app_id = plain[20 + message_length :].decode("utf-8")
    if config.app_id and app_id != config.app_id:
        raise RuntimeError("invalid WeChat component app id in encrypted event")
    return message


def _strip_pkcs7_padding(value: bytes) -> bytes:
    if not value:
        raise RuntimeError("empty WeChat component encrypted payload")
    padding = value[-1]
    if padding < 1 or padding > 32:
        raise RuntimeError("invalid WeChat component encrypted payload padding")
    return value[:-padding]


def _parse_xml_fields(raw_xml: str) -> dict[str, str]:
    root = ET.fromstring(raw_xml.strip())
    return {child.tag: child.text or "" for child in list(root)}


def _xml_text(root: ET.Element, tag: str) -> str:
    child = root.find(tag)
    return child.text or "" if child is not None else ""


def _first_query_value(query_params: dict[str, list[str] | str], key: str) -> str:
    value = query_params.get(key, "")
    if isinstance(value, list):
        return value[0] if value else ""
    return str(value)


def _safe_next_path(value: str) -> str:
    parsed = parse.urlparse(value or "/app")
    if parsed.scheme or parsed.netloc:
        return "/app"
    return parsed.path or "/app"


def _read_env_value(key: str, path: str = ".env") -> str:
    if not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8") as file:
        for raw_line in file:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, value = line.split("=", 1)
            if name.strip() == key:
                return value.strip().strip("'\"")
    return ""
