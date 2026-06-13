"""Фоновый long polling для MAX и Telegram (режим разработки)."""

from __future__ import annotations

import asyncio
import logging

from app.config import settings
from app.db.session import SessionLocal, init_db
from app.services.max_client import MaxClient
from app.services.orchestrator import BotOrchestrator
from app.services.parsers import parse_max_update, parse_telegram_update
from app.services.telegram_client import TelegramClient

logger = logging.getLogger(__name__)


async def run_polling() -> None:
    init_db()
    orchestrator = BotOrchestrator()
    max_client = MaxClient()
    telegram_client = TelegramClient()

    max_marker: int | None = None
    telegram_offset: int | None = None

    logger.info("Polling started (interval=%ss)", settings.polling_interval_sec)

    while True:
        if settings.max_bot_token:
            try:
                data = await max_client.get_updates(marker=max_marker, timeout=25)
                for update in data.get("updates", data.get("result", [])):
                    marker = update.get("marker") or update.get("update_id")
                    if marker is not None:
                        max_marker = int(marker) + 1
                    parsed = parse_max_update(update)
                    if parsed:
                        with SessionLocal() as db:
                            await orchestrator.handle(db, parsed)
            except Exception:
                logger.exception("MAX polling error")

        if settings.telegram_enabled and settings.telegram_bot_token:
            try:
                data = await telegram_client.get_updates(offset=telegram_offset, timeout=25)
                for update in data.get("result", []):
                    telegram_offset = update["update_id"] + 1
                    parsed = parse_telegram_update(update)
                    if parsed:
                        with SessionLocal() as db:
                            await orchestrator.handle(db, parsed)
            except Exception:
                logger.exception("Telegram polling error")

        await asyncio.sleep(settings.polling_interval_sec)
