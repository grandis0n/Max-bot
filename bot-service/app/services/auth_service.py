"""Авторизация пользователей бота по номеру телефона через 1С."""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import BotUser, Platform
from app.services.onec_client import OneCClient

logger = logging.getLogger(__name__)


@dataclass
class AuthResult:
    allowed: bool
    user_name: str = ""
    user_ref: str = ""
    login: str = ""
    employee_name: str = ""
    employee_ref: str = ""
    message: str = ""


def normalize_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    return digits


def looks_like_phone(text: str) -> bool:
    digits = normalize_phone(text)
    return len(digits) >= 10


def is_user_authorized(user: BotUser) -> bool:
    if not settings.auth_enabled:
        return True
    return bool(user.is_verified and user.phone)


def _extract_user_fields(data: dict) -> tuple[str, str, str]:
    user_name = str(data.get("userName") or data.get("employeeName") or "")
    user_ref = str(data.get("userRef") or data.get("employeeRef") or "")
    login = str(data.get("login") or user_name)
    return user_name, user_ref, login


class AuthService:
    def __init__(self, onec: OneCClient | None = None) -> None:
        self._onec = onec or OneCClient()

    async def verify_phone(self, phone: str) -> AuthResult:
        normalized = normalize_phone(phone)
        if len(normalized) < 10:
            return AuthResult(
                allowed=False,
                message="Некорректный номер телефона. Укажите номер в формате +7XXXXXXXXXX.",
            )

        try:
            data = await self._onec.verify_phone(normalized)
        except Exception as exc:
            logger.warning("Ошибка проверки телефона в 1С: %s", exc)
            return AuthResult(
                allowed=False,
                message="Не удалось проверить номер в 1С. Попробуйте позже.",
            )

        if not data.get("allowed"):
            return AuthResult(
                allowed=False,
                message=(
                    "Номер не найден среди пользователей информационной базы.\n"
                    "Убедитесь, что телефон указан в карточке пользователя 1С "
                    "(НСИ и администрирование → Пользователи)."
                ),
            )

        user_name, user_ref, login = _extract_user_fields(data)
        return AuthResult(
            allowed=True,
            user_name=user_name,
            user_ref=user_ref,
            login=login,
            employee_name=user_name,
            employee_ref=user_ref,
        )

    def save_authorization(self, db: Session, user: BotUser, phone: str, auth: AuthResult) -> None:
        user.phone = normalize_phone(phone)
        user.is_verified = True
        user.employee_ref = auth.user_ref or auth.employee_ref or None
        user.employee_name = auth.user_name or auth.employee_name or None
        user.verified_at = datetime.now(timezone.utc)
        db.flush()

    def build_remove_keyboard_extra(self, platform: Platform) -> dict:
        if platform == Platform.TELEGRAM:
            return {"reply_markup": {"remove_keyboard": True}}
        return {}

    def build_auth_prompt_extra(self, platform: Platform) -> dict:
        if platform == Platform.TELEGRAM:
            return {
                "reply_markup": {
                    "keyboard": [[{"text": "Поделиться номером", "request_contact": True}]],
                    "resize_keyboard": True,
                    "one_time_keyboard": True,
                }
            }
        return {}

    def auth_required_message(self, platform: Platform) -> str:
        if platform == Platform.TELEGRAM:
            return (
                "Доступ к боту только для пользователей 1С.\n"
                "Нажмите «Поделиться номером» или отправьте номер текстом (+7…)."
            )
        return (
            "Доступ к боту только для пользователей 1С.\n"
            "Отправьте свой номер телефона в формате +7XXXXXXXXXX."
        )

    def auth_success_message(self, auth: AuthResult) -> str:
        name = auth.user_name or auth.employee_name or auth.login or "пользователь"
        return f"Добро пожаловать, {name}!\nОтправьте фото товара для поиска в каталоге 1С:УНФ."
