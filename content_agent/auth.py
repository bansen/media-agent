from __future__ import annotations

import json
import os
import secrets
from dataclasses import dataclass
from time import time
from typing import Any
from urllib import parse, request

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from .database import ExternalAuthAccountRow, OAuthStateRow, PlatformAccountRow, UserRow, UserSessionRow


SESSION_COOKIE = "media_agent_session"


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


@dataclass(frozen=True)
class AuthUser:
    id: int
    display_name: str
    provider: str
    provider_user_id: str


class AuthStore:
    def __init__(self, session_factory: sessionmaker):
        self._session_factory = session_factory

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
