"""Доступ к данным: пользователи, сессии, логи."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import BotUser, DialogSession, DialogState, MessageLog, RecognitionLog, Platform


def get_or_create_user(db: Session, chat_id: str, platform: Platform, platform_user_id: str | None = None) -> BotUser:
    user = (
        db.query(BotUser)
        .filter(BotUser.chat_id == chat_id, BotUser.platform == platform.value)
        .one_or_none()
    )
    if user is None:
        user = BotUser(
            chat_id=chat_id,
            platform=platform.value,
            platform_user_id=platform_user_id,
            is_active=True,
            is_verified=False,
        )
        db.add(user)
        db.flush()
    elif platform_user_id and not user.platform_user_id:
        user.platform_user_id = platform_user_id
    return user


def get_active_session(db: Session, user: BotUser) -> DialogSession:
    session = (
        db.query(DialogSession)
        .filter(DialogSession.user_id == user.id)
        .order_by(DialogSession.updated_at.desc())
        .first()
    )
    if session is None:
        session = DialogSession(user_id=user.id, state=DialogState.IDLE.value, context_json={})
        db.add(session)
        db.flush()
    return session


def log_message(
    db: Session,
    *,
    direction: str,
    platform: Platform,
    chat_id: str,
    payload: dict | None = None,
    error: str | None = None,
) -> None:
    db.add(
        MessageLog(
            direction=direction,
            platform=platform.value,
            chat_id=chat_id,
            payload_json=payload,
            error_text=error,
        )
    )


def log_recognition(
    db: Session,
    *,
    session: DialogSession,
    image_ref: str | None,
    vision_response: dict,
) -> None:
    db.add(
        RecognitionLog(
            session_id=session.id,
            image_ref=image_ref,
            vision_response=vision_response,
        )
    )
