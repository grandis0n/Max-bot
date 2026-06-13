"""Парсинг обновлений MAX и Telegram."""

from __future__ import annotations

from typing import Any

from app.db.models import Platform
from app.services.messages import IncomingMessage


def parse_max_update(update: dict[str, Any]) -> IncomingMessage | None:
    message = update.get("message") or update
    chat = message.get("chat") or message.get("recipient") or {}
    chat_id = str(chat.get("chat_id") or chat.get("id") or message.get("chat_id") or "")
    if not chat_id:
        return None

    body = message.get("body") or message
    text = body.get("text") if isinstance(body, dict) else None
    if text is None:
        text = message.get("text")

    callback = update.get("callback") or message.get("callback")
    callback_data = None
    if callback:
        callback_data = callback.get("payload") or callback.get("data")

    image_url = None
    attachments = body.get("attachments") if isinstance(body, dict) else message.get("attachments")
    if attachments:
        for att in attachments:
            att_type = att.get("type")
            payload = att.get("payload") or att
            if att_type in ("image", "photo", "file"):
                image_url = payload.get("url") or payload.get("file_url")
                if image_url:
                    break

    sender = message.get("sender") or message.get("from") or {}
    user_id = str(sender.get("user_id") or sender.get("id") or "")

    return IncomingMessage(
        platform=Platform.MAX,
        chat_id=chat_id,
        user_id=user_id or None,
        text=text,
        image_url=image_url,
        callback_data=callback_data,
        raw=update,
    )


def parse_telegram_update(update: dict[str, Any]) -> IncomingMessage | None:
    if "callback_query" in update:
        cq = update["callback_query"]
        chat_id = str(cq["message"]["chat"]["id"])
        return IncomingMessage(
            platform=Platform.TELEGRAM,
            chat_id=chat_id,
            user_id=str(cq.get("from", {}).get("id", "")),
            callback_data=cq.get("data"),
            raw=update,
        )

    message = update.get("message")
    if not message:
        return None

    chat_id = str(message["chat"]["id"])
    text = message.get("text") or message.get("caption")
    user_id = str(message.get("from", {}).get("id", ""))

    phone = None
    contact = message.get("contact")
    if contact:
        phone = contact.get("phone_number")
        contact_user_id = str(contact.get("user_id", ""))
        if contact_user_id and user_id and contact_user_id != user_id:
            phone = None

    image_file_id = None
    photos = message.get("photo")
    if photos:
        image_file_id = photos[-1]["file_id"]
    elif message.get("document"):
        image_file_id = message["document"].get("file_id")

    return IncomingMessage(
        platform=Platform.TELEGRAM,
        chat_id=chat_id,
        user_id=user_id or None,
        text=text,
        phone=phone,
        image_file_id=image_file_id,
        raw=update,
    )
