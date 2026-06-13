"""Модели входящих сообщений."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.db.models import Platform


@dataclass
class IncomingMessage:
    platform: Platform
    chat_id: str
    user_id: str | None = None
    text: str | None = None
    phone: str | None = None
    image_url: str | None = None
    image_file_id: str | None = None
    callback_data: str | None = None
    raw: dict = field(default_factory=dict)
