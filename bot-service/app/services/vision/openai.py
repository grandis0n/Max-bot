"""Распознавание через OpenAI-compatible Vision API (опциональный fallback)."""

from __future__ import annotations

import base64
import json
import re
from typing import Any

import httpx

from app.config import settings

VISION_PROMPT = (
    "Проанализируй изображение товара для поиска в каталоге 1С:УНФ. "
    "Игнорируй срок годности, состав, адрес производителя.\n"
    "Верни ТОЛЬКО JSON без markdown:\n"
    '{"description":"краткое торговое название",'
    '"article":"артикул если виден или пустая строка",'
    '"barcode":"штрихкод EAN/UPC или пустая строка",'
    '"brand":"бренд или пустая строка",'
    '"category":"категория или пустая строка",'
    '"search_terms":["ключевое слово 1","ключевое слово 2"],'
    '"tags":["дополнительный тег"]}'
)


class OpenAIVisionProvider:
    async def analyze_image(self, image_bytes: bytes, mime_type: str = "image/jpeg") -> dict[str, Any]:
        if not settings.vision_api_key:
            return {
                "description": "",
                "tags": [],
                "barcode": "",
                "article": "",
                "brand": "",
                "category": "",
                "search_terms": [],
                "provider": "openai",
                "error": "VISION_API_KEY не задан",
            }

        encoded = base64.b64encode(image_bytes).decode("ascii")
        data_url = f"data:{mime_type};base64,{encoded}"

        payload = {
            "model": settings.vision_model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": VISION_PROMPT},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
            "max_tokens": 500,
        }

        headers = {
            "Authorization": f"Bearer {settings.vision_api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(settings.vision_api_url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        content = data["choices"][0]["message"]["content"]
        result = _parse_json_content(content)
        result["provider"] = "openai"
        return result


def _parse_json_content(content: str) -> dict[str, Any]:
    try:
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            parsed = json.loads(match.group())
            search_terms = list(parsed.get("search_terms") or [])
            tags = list(parsed.get("tags") or [])
            if not search_terms and tags:
                search_terms = tags
            return {
                "description": str(parsed.get("description", "")),
                "tags": tags,
                "barcode": str(parsed.get("barcode", "")),
                "article": str(parsed.get("article", "")),
                "brand": str(parsed.get("brand", "")),
                "category": str(parsed.get("category", "")),
                "search_terms": [str(item) for item in search_terms if str(item).strip()],
            }
    except (json.JSONDecodeError, TypeError):
        pass
    return {
        "description": content.strip(),
        "tags": [],
        "barcode": "",
        "article": "",
        "brand": "",
        "category": "",
        "search_terms": [],
    }
