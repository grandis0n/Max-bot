"""Базовый контракт провайдера Vision и подготовка параметров поиска."""

from __future__ import annotations

import re
from typing import Any, Protocol

VISION_PRODUCT_PROMPT = (
    "Текст с упаковки/этикетки товара (OCR):\n{ocr_text}\n\n"
    "Определи товар для поиска в каталоге 1С:УНФ. "
    "Игнорируй срок годности, состав, адрес производителя, рекламные слоганы.\n"
    "Верни ТОЛЬКО JSON без markdown:\n"
    '{{"description":"краткое торговое название",'
    '"article":"артикул если виден или пустая строка",'
    '"barcode":"штрихкод EAN/UPC только цифры или пустая строка",'
    '"brand":"бренд или пустая строка",'
    '"category":"категория или пустая строка",'
    '"search_terms":["ключевое слово 1","ключевое слово 2"],'
    '"tags":["дополнительный тег"]}}'
)

EAN_PATTERN = re.compile(r"\b(\d{8}|\d{12}|\d{13}|\d{14})\b")

SEARCH_STOP_WORDS = frozenset(
    {
        "best",
        "before",
        "exp",
        "шт",
        "кг",
        "г",
        "мл",
        "л",
        "срок",
        "годен",
        "годности",
        "до",
        "изг",
        "изготовитель",
        "состав",
        "упаковка",
        "www",
        "http",
        "https",
        "tel",
        "made",
        "in",
        "ru",
        "the",
        "and",
        "for",
        "new",
        "ltd",
        "llc",
        "ооо",
        "зао",
        "ао",
        "пао",
        "net",
        "weight",
        "volume",
    }
)


class VisionProvider(Protocol):
    async def analyze_image(self, image_bytes: bytes, mime_type: str = "image/jpeg") -> dict[str, Any]:
        ...


def normalize_search_text(value: str) -> str:
    text = (value or "").replace("\u00a0", " ").strip()
    text = text.replace("ё", "е").replace("Ё", "Е")
    return re.sub(r"\s+", " ", text)


def normalize_barcode(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def looks_like_barcode(value: str) -> bool:
    digits = normalize_barcode(value)
    return 8 <= len(digits) <= 14


def validate_ean_checksum(digits: str) -> bool:
    if len(digits) not in (8, 12, 13, 14):
        return False
    body = digits[:-1]
    check_digit = int(digits[-1])
    total = 0
    for index, char in enumerate(reversed(body)):
        weight = 3 if index % 2 == 0 else 1
        total += int(char) * weight
    return (10 - (total % 10)) % 10 == check_digit


def extract_barcode_from_text(text: str) -> str:
    compact = re.sub(r"\s+", "", text or "")
    candidates: list[str] = []
    for match in EAN_PATTERN.finditer(compact):
        candidate = match.group(1)
        if len(candidate) in (8, 12, 13, 14):
            candidates.append(candidate)

    for candidate in candidates:
        if len(candidate) in (13, 8) and validate_ean_checksum(candidate):
            return candidate

    return candidates[0] if candidates else ""


def tokenize_search_text(text: str, *, limit: int = 8) -> list[str]:
    normalized = normalize_search_text(text)
    if not normalized:
        return []

    for separator in (",", ";", "|", "/", "\\"):
        normalized = normalized.replace(separator, " ")

    tokens: list[str] = []
    seen: set[str] = set()
    for part in normalized.split():
        token = normalize_search_text(part)
        if not token or looks_like_barcode(token):
            continue
        if len(token) < 2 or token.lower() in SEARCH_STOP_WORDS:
            continue
        key = token.lower()
        if key in seen:
            continue
        seen.add(key)
        tokens.append(token)
        if len(tokens) >= limit:
            break
    return tokens


def build_search_params(vision_result: dict[str, Any]) -> dict[str, Any]:
    barcode = normalize_barcode(str(vision_result.get("barcode") or ""))
    if not barcode:
        barcode = extract_barcode_from_text(str(vision_result.get("ocr_text") or ""))

    article = normalize_search_text(str(vision_result.get("article") or ""))

    tokens: list[str] = []
    for source in (
        vision_result.get("search_terms") or [],
        [vision_result.get("brand")] if vision_result.get("brand") else [],
        [vision_result.get("category")] if vision_result.get("category") else [],
        vision_result.get("tags") or [],
        tokenize_search_text(str(vision_result.get("description") or "")),
    ):
        if isinstance(source, str):
            source = [source]
        for item in source:
            tokens.extend(tokenize_search_text(str(item)))

    deduped: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        key = token.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(token)
        if len(deduped) >= 8:
            break

    return {
        "barcode": barcode,
        "article": article,
        "tokens": deduped,
        "q": "",
    }


def build_search_query(vision_result: dict[str, Any]) -> str:
    params = build_search_params(vision_result)
    parts: list[str] = []
    if params["barcode"]:
        parts.append(params["barcode"])
    if params["article"]:
        parts.append(params["article"])
    parts.extend(params["tokens"])
    return " ".join(parts).strip()


def has_search_params(params: dict[str, Any]) -> bool:
    return bool(
        params.get("barcode")
        or params.get("article")
        or params.get("tokens")
        or params.get("q")
    )
