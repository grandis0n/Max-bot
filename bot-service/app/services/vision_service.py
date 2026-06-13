"""Фасад распознавания: выбор провайдера по настройкам."""

from __future__ import annotations

from typing import Any

from app.config import settings
from app.services.vision.base import build_search_params, build_search_query, has_search_params
from app.services.vision.openai import OpenAIVisionProvider
from app.services.vision.yandex import YandexVisionProvider


class VisionService:
    def __init__(self) -> None:
        provider = settings.vision_provider.lower().strip()
        if provider == "openai":
            self._provider = OpenAIVisionProvider()
        else:
            self._provider = YandexVisionProvider()

    async def analyze_image(self, image_bytes: bytes, mime_type: str = "image/jpeg") -> dict[str, Any]:
        return await self._provider.analyze_image(image_bytes, mime_type)

    def build_search_params(self, vision_result: dict[str, Any]) -> dict[str, Any]:
        return build_search_params(vision_result)

    def build_search_query(self, vision_result: dict[str, Any]) -> str:
        return build_search_query(vision_result)

    def has_search_params(self, params: dict[str, Any]) -> bool:
        return has_search_params(params)
