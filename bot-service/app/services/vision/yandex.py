"""Распознавание через Yandex Cloud: Vision OCR + YandexGPT."""

from __future__ import annotations

import base64
import json
import logging
import re
from typing import Any

import httpx

from app.config import settings
from app.services.vision.base import (
    VISION_PRODUCT_PROMPT,
    extract_barcode_from_text,
    normalize_search_text,
)

logger = logging.getLogger(__name__)

PRODUCT_PROMPT = VISION_PRODUCT_PROMPT


class YandexVisionProvider:
    async def analyze_image(self, image_bytes: bytes, mime_type: str = "image/jpeg") -> dict[str, Any]:
        if not settings.yandex_api_key and not settings.yandex_iam_token:
            return _empty_result(error="Задайте YANDEX_API_KEY или YANDEX_IAM_TOKEN")
        if not settings.yandex_folder_id:
            return _empty_result(error="Задайте YANDEX_FOLDER_ID")

        ocr_text, ocr_lines = await self._recognize_text(image_bytes)
        barcode = extract_barcode_from_text(ocr_text)

        if settings.yandex_use_gpt_enrichment and ocr_text.strip():
            structured = await self._enrich_with_yandexgpt(ocr_text)
        else:
            structured = _structure_from_ocr(ocr_lines, barcode)

        structured["ocr_text"] = ocr_text
        structured["provider"] = "yandex"
        if not structured.get("barcode") and barcode:
            structured["barcode"] = barcode
        return structured

    async def _recognize_text(self, image_bytes: bytes) -> tuple[str, list[str]]:
        encoded = base64.b64encode(image_bytes).decode("ascii")
        payload = {
            "folderId": settings.yandex_folder_id,
            "analyze_specs": [
                {
                    "content": encoded,
                    "features": [
                        {
                            "type": "TEXT_DETECTION",
                            "textDetectionConfig": {
                                "languageCodes": [
                                    lang.strip()
                                    for lang in settings.yandex_ocr_languages.split(",")
                                    if lang.strip()
                                ],
                            },
                        }
                    ],
                }
            ],
        }

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                settings.yandex_vision_url,
                headers=_auth_headers(),
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        lines = _extract_ocr_lines(data)
        return "\n".join(lines), lines

    async def _enrich_with_yandexgpt(self, ocr_text: str) -> dict[str, Any]:
        model_uri = settings.yandex_gpt_model_uri
        if not model_uri:
            model_uri = f"gpt://{settings.yandex_folder_id}/{settings.yandex_gpt_model}/latest"

        payload = {
            "modelUri": model_uri,
            "completionOptions": {
                "stream": False,
                "temperature": 0.2,
                "maxTokens": 600,
            },
            "messages": [
                {
                    "role": "user",
                    "text": PRODUCT_PROMPT.format(ocr_text=ocr_text[:4000]),
                }
            ],
        }

        headers = {
            **_auth_headers(),
            "x-folder-id": settings.yandex_folder_id,
        }

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(settings.yandex_gpt_url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        content = (
            data.get("result", {})
            .get("alternatives", [{}])[0]
            .get("message", {})
            .get("text", "")
        )
        return _parse_json_content(content)


def _auth_headers() -> dict[str, str]:
    if settings.yandex_api_key:
        return {"Authorization": f"Api-Key {settings.yandex_api_key}"}
    return {"Authorization": f"Bearer {settings.yandex_iam_token}"}


def _extract_ocr_lines(data: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for result in data.get("results", []):
        for inner in result.get("results", []):
            text_detection = inner.get("textDetection") or inner.get("text_detection")
            if not text_detection:
                continue
            for page in text_detection.get("pages", []):
                for block in page.get("blocks", []):
                    for line in block.get("lines", []):
                        words = [
                            w.get("text", "")
                            for w in line.get("words", [])
                            if w.get("text")
                        ]
                        line_text = " ".join(words).strip()
                        if line_text:
                            lines.append(line_text)
                        elif line.get("text"):
                            lines.append(str(line["text"]).strip())
    return lines


def _structure_from_ocr(lines: list[str], barcode: str) -> dict[str, Any]:
    description = lines[0] if lines else ""
    tags = lines[1:6]
    return {
        "description": description,
        "tags": tags,
        "barcode": barcode,
        "article": "",
        "brand": "",
        "category": "",
        "search_terms": tokenize_ocr_lines(lines),
    }


def tokenize_ocr_lines(lines: list[str]) -> list[str]:
    terms: list[str] = []
    for line in lines[:6]:
        normalized = normalize_search_text(line)
        if normalized and len(normalized) >= 2:
            terms.append(normalized)
    return terms[:5]


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
        logger.warning("Не удалось распарсить JSON от YandexGPT")
    return {
        "description": content.strip(),
        "tags": [],
        "barcode": "",
        "article": "",
        "brand": "",
        "category": "",
        "search_terms": [],
    }


def _empty_result(error: str) -> dict[str, Any]:
    return {
        "description": "",
        "tags": [],
        "barcode": "",
        "article": "",
        "brand": "",
        "category": "",
        "search_terms": [],
        "ocr_text": "",
        "provider": "yandex",
        "error": error,
    }
