"""Подключение к PostgreSQL."""

from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.db.models import Base

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

_AUTH_COLUMNS: tuple[tuple[str, str], ...] = (
    ("platform_user_id", "VARCHAR(64)"),
    ("phone", "VARCHAR(32)"),
    ("is_verified", "BOOLEAN DEFAULT FALSE"),
    ("employee_ref", "VARCHAR(64)"),
    ("employee_name", "VARCHAR(256)"),
    ("verified_at", "TIMESTAMP WITH TIME ZONE"),
)


def _migrate_bot_users() -> None:
    inspector = inspect(engine)
    if "bot_users" not in inspector.get_table_names():
        return

    existing = {column["name"] for column in inspector.get_columns("bot_users")}
    with engine.begin() as connection:
        for name, ddl in _AUTH_COLUMNS:
            if name not in existing:
                connection.execute(text(f"ALTER TABLE bot_users ADD COLUMN {name} {ddl}"))


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _migrate_bot_users()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
