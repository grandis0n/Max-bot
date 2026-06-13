"""Клиент MAX Bot API."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class MaxClient:
    def __init__(self) -> None:
        self._base = settings.max_api_base_url.rstrip("/")
        self._headers = {"Authorization": settings.max_bot_token}

    async def get_updates(self, marker: int | None = None, timeout: int = 30) -> dict[str, Any]:
        params: dict[str, Any] = {"timeout": timeout}
        if marker is not None:
            params["marker"] = marker
        async with httpx.AsyncClient(timeout=timeout + 5) as client:
            response = await client.get(f"{self._base}/updates", headers=self._headers, params=params)
            response.raise_for_status()
            return response.json()

    async def send_message(
        self,
        chat_id: int | str,
        text: str,
        attachments: list[dict] | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"chat_id": int(chat_id), "text": text}
        if attachments:
            body["attachments"] = attachments
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self._base}/messages",
                headers={**self._headers, "Content-Type": "application/json"},
                json=body,
            )
            response.raise_for_status()
            return response.json()

    async def upload_image(self, image_bytes: bytes, mime_type: str = "image/jpeg") -> str:
        async with httpx.AsyncClient(timeout=60) as client:
            upload_response = await client.post(
                f"{self._base}/uploads",
                headers=self._headers,
                params={"type": "image"},
            )
            upload_response.raise_for_status()
            upload_data = upload_response.json()

            upload_url = upload_data.get("url")
            token = upload_data.get("token")
            if not upload_url:
                raise ValueError("MAX uploads: не получен URL загрузки")

            extension = "jpg"
            if mime_type == "image/png":
                extension = "png"
            elif mime_type == "image/webp":
                extension = "webp"

            files = {"data": (f"product.{extension}", image_bytes, mime_type)}
            file_response = await client.post(upload_url, headers=self._headers, files=files)
            file_response.raise_for_status()

            if not token:
                file_data = file_response.json()
                token = file_data.get("token")
            if not token:
                raise ValueError("MAX uploads: не получен token изображения")
            return token

    async def send_photo(
        self,
        chat_id: int | str,
        photo_bytes: bytes,
        caption: str = "",
        attachments: list[dict] | None = None,
        mime_type: str = "image/jpeg",
    ) -> dict[str, Any]:
        token = await self.upload_image(photo_bytes, mime_type=mime_type)
        message_attachments = [{"type": "image", "payload": {"token": token}}]
        if attachments:
            message_attachments.extend(attachments)
        return await self.send_message(chat_id, caption, attachments=message_attachments)

    async def download_file(self, url: str) -> bytes:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.get(url, headers=self._headers)
            response.raise_for_status()
            return response.content
