"""Клиент Telegram Bot API."""

from __future__ import annotations

import json
from typing import Any

import httpx

from app.config import settings


class TelegramClient:
    def __init__(self) -> None:
        token = settings.telegram_bot_token
        self._base = f"https://api.telegram.org/bot{token}"

    async def get_updates(self, offset: int | None = None, timeout: int = 30) -> dict[str, Any]:
        params: dict[str, Any] = {"timeout": timeout}
        if offset is not None:
            params["offset"] = offset
        async with httpx.AsyncClient(timeout=timeout + 5) as client:
            response = await client.get(f"{self._base}/getUpdates", params=params)
            response.raise_for_status()
            return response.json()

    async def send_message(
        self,
        chat_id: int | str,
        text: str,
        reply_markup: dict | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"chat_id": chat_id, "text": text}
        if reply_markup:
            body["reply_markup"] = reply_markup
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(f"{self._base}/sendMessage", json=body)
            response.raise_for_status()
            return response.json()

    async def send_photo(
        self,
        chat_id: int | str,
        photo_bytes: bytes,
        caption: str = "",
        reply_markup: dict | None = None,
        mime_type: str = "image/jpeg",
    ) -> dict[str, Any]:
        extension = "jpg"
        if mime_type == "image/png":
            extension = "png"
        elif mime_type == "image/gif":
            extension = "gif"
        elif mime_type == "image/webp":
            extension = "webp"

        data: dict[str, Any] = {"chat_id": chat_id}
        if caption:
            data["caption"] = caption
        if reply_markup:
            data["reply_markup"] = json.dumps(reply_markup)

        files = {"photo": (f"product.{extension}", photo_bytes, mime_type)}
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(f"{self._base}/sendPhoto", data=data, files=files)
            response.raise_for_status()
            return response.json()

    async def download_file(self, file_id: str) -> bytes:
        async with httpx.AsyncClient(timeout=60) as client:
            file_resp = await client.get(f"{self._base}/getFile", params={"file_id": file_id})
            file_resp.raise_for_status()
            file_path = file_resp.json()["result"]["file_path"]
            content_resp = await client.get(f"https://api.telegram.org/file/bot{settings.telegram_bot_token}/{file_path}")
            content_resp.raise_for_status()
            return content_resp.content
