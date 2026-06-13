"""SQLAlchemy-модели PostgreSQL."""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Platform(str, enum.Enum):
    MAX = "max"
    TELEGRAM = "telegram"


class DialogState(str, enum.Enum):
    IDLE = "idle"
    AWAIT_PHONE_AUTH = "await_phone_auth"
    AWAIT_PRODUCT_CHOICE = "await_product_choice"
    PRODUCT_SELECTED = "product_selected"


class BotUser(Base):
    __tablename__ = "bot_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chat_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(16), nullable=False)
    platform_user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    employee_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    employee_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    sessions: Mapped[list[DialogSession]] = relationship(back_populates="user")


class DialogSession(Base):
    __tablename__ = "dialog_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("bot_users.id"), nullable=False)
    state: Mapped[str] = mapped_column(String(32), default=DialogState.IDLE.value)
    context_json: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[BotUser] = relationship(back_populates="sessions")
    recognition_logs: Mapped[list[RecognitionLog]] = relationship(back_populates="session")


class RecognitionLog(Base):
    __tablename__ = "recognition_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int | None] = mapped_column(ForeignKey("dialog_sessions.id"))
    image_ref: Mapped[str | None] = mapped_column(String(512))
    vision_response: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    session: Mapped[DialogSession | None] = relationship(back_populates="recognition_logs")


class MessageLog(Base):
    __tablename__ = "message_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    direction: Mapped[str] = mapped_column(String(8), nullable=False)  # in / out
    platform: Mapped[str] = mapped_column(String(16), nullable=False)
    chat_id: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_json: Mapped[dict | None] = mapped_column(JSONB)
    error_text: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
