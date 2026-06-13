"""Настройки приложения из переменных окружения."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Общие
    app_name: str = "max-bot-nomenclature"
    log_level: str = "INFO"
    polling_enabled: bool = True
    polling_interval_sec: int = 2

    # PostgreSQL
    database_url: str = "postgresql+psycopg2://bot:bot@db:5432/botdb"

    # MAX
    max_bot_token: str = ""
    max_api_base_url: str = "https://platform-api.max.ru"
    max_webhook_secret: str = ""

    # Telegram
    telegram_bot_token: str = ""
    telegram_enabled: bool = False

    # Vision / ИИ
    vision_provider: str = "yandex"

    # Yandex Cloud (основной провайдер)
    yandex_api_key: str = ""
    yandex_iam_token: str = ""
    yandex_folder_id: str = ""
    yandex_vision_url: str = "https://vision.api.cloud.yandex.net/vision/v1/batchAnalyze"
    yandex_gpt_url: str = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
    yandex_gpt_model: str = "yandexgpt"
    yandex_gpt_model_uri: str = ""
    yandex_use_gpt_enrichment: bool = True
    yandex_ocr_languages: str = "ru,en"

    # OpenAI-compatible Vision (fallback, vision_provider=openai)
    vision_api_url: str = "https://api.openai.com/v1/chat/completions"
    vision_api_key: str = ""
    vision_model: str = "gpt-4o-mini"

    # 1С:УНФ HTTP API
    onec_base_url: str = "http://localhost/unf/ru"
    onec_username: str = ""
    onec_password: str = ""
    onec_search_limit: int = 5
    onec_timeout_sec: int = 30

    # Авторизация по номеру телефона (привязка к сотруднику УНФ)
    auth_enabled: bool = False


settings = Settings()
