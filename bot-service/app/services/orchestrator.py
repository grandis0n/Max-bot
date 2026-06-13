"""Оркестратор: MAX/Telegram → Vision → 1С → ответ пользователю."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import DialogState, Platform
from app.db.repository import get_active_session, get_or_create_user, log_message, log_recognition
from app.services.auth_service import AuthService, is_user_authorized, looks_like_phone
from app.services.dialog_manager import DialogManager
from app.services.max_client import MaxClient
from app.services.messages import IncomingMessage
from app.services.onec_client import OneCClient
from app.services.telegram_client import TelegramClient
from app.services.vision.base import tokenize_search_text
from app.services.vision_service import VisionService

logger = logging.getLogger(__name__)


class BotOrchestrator:
    def __init__(self) -> None:
        self._vision = VisionService()
        self._onec = OneCClient()
        self._dialog = DialogManager(self._onec)
        self._auth = AuthService(self._onec)
        self._max = MaxClient()
        self._telegram = TelegramClient()

    async def handle(self, db: Session, message: IncomingMessage) -> None:
        log_message(db, direction="in", platform=message.platform, chat_id=message.chat_id, payload=message.raw)
        user = get_or_create_user(db, message.chat_id, message.platform, message.user_id)
        session = get_active_session(db, user)
        context: dict[str, Any] = dict(session.context_json or {})

        try:
            if settings.auth_enabled and not is_user_authorized(user):
                reply = await self._handle_auth(db, user, session, message)
            else:
                reply = await self._dispatch(db, session, context, message)
            if reply:
                await self._send_reply(message.platform, message.chat_id, reply)
                log_message(
                    db,
                    direction="out",
                    platform=message.platform,
                    chat_id=message.chat_id,
                    payload={"text": reply.get("text", ""), "has_photo": bool(reply.get("photo"))},
                )
            session.context_json = context
            db.commit()
        except Exception as exc:
            db.rollback()
            logger.exception("Ошибка обработки сообщения")
            error_text = "Произошла ошибка при обработке запроса. Попробуйте позже."
            await self._send(message.platform, message.chat_id, error_text)
            log_message(
                db,
                direction="out",
                platform=message.platform,
                chat_id=message.chat_id,
                error=str(exc),
            )
            db.commit()

    async def _handle_auth(self, db, user, session, message: IncomingMessage) -> dict[str, Any]:
        phone = message.phone
        if not phone and message.text and looks_like_phone(message.text):
            phone = message.text.strip()

        if phone:
            auth = await self._auth.verify_phone(phone)
            if auth.allowed:
                self._auth.save_authorization(db, user, phone, auth)
                session.state = DialogState.IDLE.value
                session.context_json = self._dialog.reset_context()
                extra = self._auth.build_remove_keyboard_extra(message.platform)
                return {"text": self._auth.auth_success_message(auth), "extra": extra}

            return {"text": auth.message or self._auth.auth_required_message(message.platform)}

        session.state = DialogState.AWAIT_PHONE_AUTH.value
        return {
            "text": self._auth.auth_required_message(message.platform),
            "extra": self._auth.build_auth_prompt_extra(message.platform),
        }

    async def _dispatch(
        self,
        db: Session,
        session,
        context: dict[str, Any],
        message: IncomingMessage,
    ) -> dict[str, Any] | None:
        if message.callback_data:
            return await self._handle_callback(session, context, message)

        if message.text:
            text = message.text.strip()
            if text in ("/start", "start", "поиск", "/search"):
                context.clear()
                context.update(self._dialog.reset_context())
                session.state = self._dialog.state_idle()
                return {"text": "Отправьте фото товара для поиска в каталоге 1С:УНФ."}

            if session.state == self._dialog.state_after_search():
                idx = self._dialog.parse_pick_index(text, len(context.get("candidates", [])))
                if idx:
                    return await self._pick_by_index(session, context, idx)

            if session.state in (self._dialog.state_idle(), self._dialog.state_after_search()):
                items = await self._search_by_text(text)
                if items is not None:
                    context.clear()
                    context.update(self._dialog.reset_context())
                    context["candidates"] = items
                    session.state = self._dialog.state_after_search()
                    reply_text = self._dialog.format_candidates(items)
                    extra: dict[str, Any] = {}
                    if message.platform == Platform.MAX:
                        extra["attachments"] = self._dialog.build_max_keyboard(items)
                    else:
                        extra["reply_markup"] = self._dialog.build_telegram_keyboard(items)
                    return {"text": reply_text, "extra": extra}

            if session.state == self._dialog.state_after_pick() and context.get("selected_ref"):
                action_map = {
                    "/stock": "stock",
                    "остатки": "stock",
                    "/details": "details",
                    "характеристики": "details",
                    "/price": "price",
                    "цена": "price",
                    "/image": "image",
                    "фото": "image",
                    "картинка": "image",
                }
                action = action_map.get(text.lower())
                if action:
                    return await self._build_followup_reply(message.platform, action, context["selected_ref"])

            return {"text": "Отправьте фото товара или используйте кнопки."}

        if message.image_url or message.image_file_id:
            return await self._handle_image(db, session, context, message)

        return {"text": "Поддерживаются фото товара и команды. Отправьте изображение."}

    async def _handle_image(self, db, session, context, message: IncomingMessage) -> dict[str, Any]:
        image_bytes = await self._load_image(message)
        vision_result = await self._vision.analyze_image(image_bytes)
        log_recognition(db, session=session, image_ref=message.image_url or message.image_file_id, vision_response=vision_result)

        search_params = self._vision.build_search_params(vision_result)
        if not self._vision.has_search_params(search_params):
            return {"text": "Не удалось распознать товар на изображении. Попробуйте другое фото."}

        items = await self._onec.search_smart(search_params)
        context.clear()
        context.update(self._dialog.reset_context())
        context["candidates"] = items
        context["vision"] = vision_result
        context["search_params"] = search_params
        session.state = self._dialog.state_after_search()

        if not items:
            hint = self._format_search_hint(search_params, vision_result)
            return {"text": f"По изображению ничего не найдено.{hint}\nПопробуйте другое фото или уточните запрос текстом."}

        text = self._dialog.format_candidates(items)
        extra: dict[str, Any] = {}
        if message.platform == Platform.MAX:
            extra["attachments"] = self._dialog.build_max_keyboard(items)
        else:
            extra["reply_markup"] = self._dialog.build_telegram_keyboard(items)
        return {"text": text, "extra": extra}

    async def _search_by_text(self, text: str) -> list[dict[str, Any]] | None:
        normalized = text.strip()
        if not normalized or normalized.startswith("/"):
            return None

        tokens = tokenize_search_text(normalized)
        params = {
            "barcode": "",
            "article": "",
            "tokens": tokens,
            "q": normalized if not tokens else "",
        }
        if not self._vision.has_search_params(params):
            return None

        return await self._onec.search_smart(params)

    def _format_search_hint(self, search_params: dict[str, Any], vision_result: dict[str, Any]) -> str:
        parts: list[str] = []
        if search_params.get("barcode"):
            parts.append(f"штрихкод {search_params['barcode']}")
        if search_params.get("article"):
            parts.append(f"артикул {search_params['article']}")
        if search_params.get("tokens"):
            parts.append("слова: " + ", ".join(search_params["tokens"][:5]))
        if vision_result.get("ocr_text"):
            ocr_preview = str(vision_result["ocr_text"]).replace("\n", " ")[:120]
            parts.append(f"OCR: {ocr_preview}")
        if not parts:
            return ""
        return "\nРаспознано: " + "; ".join(parts) + "."

    async def _handle_callback(self, session, context, message: IncomingMessage) -> dict[str, Any]:
        data = message.callback_data or ""

        if data == "action:new_search":
            context.clear()
            context.update(self._dialog.reset_context())
            session.state = self._dialog.state_idle()
            return {"text": "Отправьте новое фото товара."}

        if data.startswith("pick:"):
            ref = data.split(":", 1)[1]
            candidates = context.get("candidates", [])
            selected = next((c for c in candidates if (c.get("ref") or c.get("Ссылка")) == ref), None)
            if selected is None and candidates:
                selected = candidates[0]
                ref = selected.get("ref") or selected.get("Ссылка") or ref

            context["selected_ref"] = ref
            context["selected_name"] = selected.get("name") or selected.get("Наименование") if selected else ref
            session.state = self._dialog.state_after_pick()
            name = context.get("selected_name") or "товар"
            extra = self._followup_extra(message.platform)
            return {
                "text": f"Выбран: {name}\nЧто показать?",
                "extra": extra,
            }

        if data.startswith("action:") and context.get("selected_ref"):
            action = data.split(":", 1)[1]
            return await self._build_followup_reply(message.platform, action, context["selected_ref"])

        return {"text": "Команда не распознана."}

    async def _pick_by_index(self, session, context, idx: int) -> dict[str, Any]:
        candidates = context.get("candidates", [])
        selected = candidates[idx - 1]
        ref = selected.get("ref") or selected.get("Ссылка")
        context["selected_ref"] = ref
        context["selected_name"] = selected.get("name") or selected.get("Наименование")
        session.state = self._dialog.state_after_pick()
        return {
            "text": f"Выбран: {context['selected_name']}\nЧто показать?\n/stock — остатки\n/details — характеристики\n/price — цена",
        }

    async def _load_image(self, message: IncomingMessage) -> bytes:
        if message.platform == Platform.MAX and message.image_url:
            return await self._max.download_file(message.image_url)
        if message.platform == Platform.TELEGRAM and message.image_file_id:
            return await self._telegram.download_file(message.image_file_id)
        raise ValueError("Изображение не найдено в сообщении")

    def _followup_extra(self, platform: Platform) -> dict[str, Any]:
        if platform == Platform.MAX:
            return {"attachments": self._dialog.build_followup_keyboard_max()}
        return {"reply_markup": self._dialog.build_followup_keyboard_telegram()}

    async def _build_followup_reply(self, platform: Platform, action: str, selected_ref: str) -> dict[str, Any]:
        result = await self._dialog.handle_followup(action, selected_ref)
        result["extra"] = self._followup_extra(platform)
        return result

    async def _send_reply(self, platform: Platform, chat_id: str, reply: dict[str, Any]) -> None:
        photo = reply.get("photo")
        extra = reply.get("extra") or {}
        text = reply.get("text") or ""

        if photo:
            photo_bytes = photo["bytes"]
            mime_type = photo.get("mime_type") or "image/jpeg"
            if platform == Platform.MAX:
                await self._max.send_photo(
                    chat_id,
                    photo_bytes,
                    caption=text,
                    attachments=extra.get("attachments"),
                    mime_type=mime_type,
                )
            else:
                await self._telegram.send_photo(
                    chat_id,
                    photo_bytes,
                    caption=text,
                    reply_markup=extra.get("reply_markup"),
                    mime_type=mime_type,
                )
            return

        await self._send(platform, chat_id, text, extra)

    async def _send(self, platform: Platform, chat_id: str, text: str, extra: dict | None = None) -> None:
        extra = extra or {}
        if platform == Platform.MAX:
            await self._max.send_message(chat_id, text, attachments=extra.get("attachments"))
        else:
            await self._telegram.send_message(chat_id, text, reply_markup=extra.get("reply_markup"))
