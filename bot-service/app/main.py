"""FastAPI: health, webhooks."""

from __future__ import annotations

import asyncio
import logging

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request

from app.config import settings
from app.db.session import SessionLocal, init_db
from app.services.orchestrator import BotOrchestrator
from app.services.parsers import parse_max_update, parse_telegram_update

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)

app = FastAPI(title=settings.app_name)
orchestrator = BotOrchestrator()


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    if settings.polling_enabled:
        asyncio.create_task(_start_polling())


async def _start_polling() -> None:
    from app.workers.polling import run_polling

    await run_polling()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}


async def _handle_in_background(parsed) -> None:
    with SessionLocal() as db:
        await orchestrator.handle(db, parsed)


@app.post("/webhooks/max")
async def max_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    secret: str | None = Header(default=None, alias="X-Max-Bot-Api-Secret"),
) -> dict[str, str]:
    if settings.max_webhook_secret and secret != settings.max_webhook_secret:
        raise HTTPException(status_code=403, detail="Invalid webhook secret")

    payload = await request.json()
    parsed = parse_max_update(payload)
    if parsed:
        background_tasks.add_task(_handle_in_background, parsed)
    return {"status": "accepted"}


@app.post("/webhooks/telegram")
async def telegram_webhook(request: Request, background_tasks: BackgroundTasks) -> dict[str, str]:
    payload = await request.json()
    for update in payload if isinstance(payload, list) else [payload]:
        parsed = parse_telegram_update(update)
        if parsed:
            background_tasks.add_task(_handle_in_background, parsed)
    return {"status": "accepted"}
