from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from sqlalchemy import JSON, Float, ForeignKey, Integer, String, Text, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker


DEFAULT_DATABASE_URL = "sqlite:///output/content_agent.db"


class Base(DeclarativeBase):
    pass


class UserRow(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    display_name: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[float] = mapped_column(Float)
    updated_at: Mapped[float] = mapped_column(Float)


class WeChatAccountRow(Base):
    __tablename__ = "wechat_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    authorizer_appid: Mapped[str] = mapped_column(String(120), default="")
    nick_name: Mapped[str] = mapped_column(String(200), default="")
    refresh_token: Mapped[str] = mapped_column(Text, default="")
    permissions_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[float] = mapped_column(Float)
    updated_at: Mapped[float] = mapped_column(Float)


class PlatformAccountRow(Base):
    __tablename__ = "platform_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    platform: Mapped[str] = mapped_column(String(40))
    auth_type: Mapped[str] = mapped_column(String(40))
    display_name: Mapped[str] = mapped_column(String(200), default="")
    credentials_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    profile_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[float] = mapped_column(Float)
    updated_at: Mapped[float] = mapped_column(Float)


class ExternalAuthAccountRow(Base):
    __tablename__ = "external_auth_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    provider: Mapped[str] = mapped_column(String(40))
    provider_user_id: Mapped[str] = mapped_column(String(200))
    union_id: Mapped[str] = mapped_column(String(200), default="")
    display_name: Mapped[str] = mapped_column(String(200), default="")
    profile_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[float] = mapped_column(Float)
    updated_at: Mapped[float] = mapped_column(Float)


class UserSessionRow(Base):
    __tablename__ = "user_sessions"

    token: Mapped[str] = mapped_column(String(96), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[float] = mapped_column(Float)
    expires_at: Mapped[float] = mapped_column(Float)


class OAuthStateRow(Base):
    __tablename__ = "oauth_states"

    state: Mapped[str] = mapped_column(String(96), primary_key=True)
    provider: Mapped[str] = mapped_column(String(40))
    next_path: Mapped[str] = mapped_column(Text, default="/app")
    created_at: Mapped[float] = mapped_column(Float)
    expires_at: Mapped[float] = mapped_column(Float)
    consumed_at: Mapped[float | None] = mapped_column(Float, nullable=True)


class ContentJobRow(Base):
    __tablename__ = "content_jobs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    wechat_account_id: Mapped[int | None] = mapped_column(ForeignKey("wechat_accounts.id"), nullable=True)
    keyword: Mapped[str] = mapped_column(String(200), default="")
    channel: Mapped[str] = mapped_column(String(40), default="wechat")
    collector: Mapped[str] = mapped_column(String(40), default="free_hot")
    status: Mapped[str] = mapped_column(String(40), default="queued")
    options_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    result_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[float] = mapped_column(Float)
    updated_at: Mapped[float] = mapped_column(Float)

    events: Mapped[list["JobEventRow"]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="JobEventRow.id",
    )
    assets: Mapped[list["ContentAssetRow"]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="ContentAssetRow.id",
    )
    publish_attempts: Mapped[list["PublishAttemptRow"]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="PublishAttemptRow.id",
    )


class ContentAssetRow(Base):
    __tablename__ = "content_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("content_jobs.id"))
    kind: Mapped[str] = mapped_column(String(60))
    path: Mapped[str] = mapped_column(Text, default="")
    url: Mapped[str] = mapped_column(Text, default="")
    mime_type: Mapped[str] = mapped_column(String(120), default="")
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[float] = mapped_column(Float)

    job: Mapped[ContentJobRow] = relationship(back_populates="assets")


class PublishAttemptRow(Base):
    __tablename__ = "publish_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("content_jobs.id"))
    platform: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(40))
    response_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[float] = mapped_column(Float)
    updated_at: Mapped[float] = mapped_column(Float)

    job: Mapped[ContentJobRow] = relationship(back_populates="publish_attempts")


class JobEventRow(Base):
    __tablename__ = "job_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("content_jobs.id"))
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[float] = mapped_column(Float)

    job: Mapped[ContentJobRow] = relationship(back_populates="events")


def database_url_from_env() -> str:
    return os.environ.get("DATABASE_URL") or _read_env_value("DATABASE_URL") or DEFAULT_DATABASE_URL


def build_engine(database_url: str | None = None) -> Engine:
    url = database_url or database_url_from_env()
    if url.startswith("sqlite:///"):
        db_path = Path(url.removeprefix("sqlite:///"))
        if str(db_path) != ":memory:":
            db_path.parent.mkdir(parents=True, exist_ok=True)
        return create_engine(url, connect_args={"check_same_thread": False})
    return create_engine(url, pool_pre_ping=True)


def init_schema(engine: Engine) -> None:
    Base.metadata.create_all(engine)


def session_factory(engine: Engine):
    return sessionmaker(bind=engine, expire_on_commit=False)


def _read_env_value(key: str, path: str = ".env") -> str:
    env_path = Path(path)
    if not env_path.exists():
        return ""
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        if name.strip() == key:
            return value.strip().strip("'\"")
    return ""
