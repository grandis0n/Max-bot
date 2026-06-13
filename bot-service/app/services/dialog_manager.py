"""Диалоговый менеджер: выбор товара и уточняющие вопросы."""

from __future__ import annotations

from typing import Any

from app.db.models import DialogState
from app.services.onec_client import OneCClient


class DialogManager:
    def __init__(self, onec: OneCClient) -> None:
        self._onec = onec

    def format_candidates(self, items: list[dict[str, Any]]) -> str:
        if not items:
            return "По изображению ничего не найдено. Попробуйте другое фото или уточните запрос текстом."

        lines = ["Найдены похожие товары:"]
        for idx, item in enumerate(items, start=1):
            name = item.get("name") or item.get("Наименование") or "Без названия"
            article = item.get("article") or item.get("Артикул") or ""
            suffix = f" (арт. {article})" if article else ""
            lines.append(f"{idx}. {name}{suffix}")
        lines.append("\nВыберите номер товара (1–{}) или нажмите кнопку.".format(len(items)))
        return "\n".join(lines)

    def build_max_keyboard(self, items: list[dict[str, Any]]) -> list[dict]:
        buttons = []
        for idx, item in enumerate(items[:5], start=1):
            ref = item.get("ref") or item.get("Ссылка") or str(idx)
            name = (item.get("name") or item.get("Наименование") or f"Товар {idx}")[:40]
            buttons.append([{"type": "callback", "text": f"{idx}. {name}", "payload": f"pick:{ref}"}])
        buttons.append([{"type": "callback", "text": "Новый поиск", "payload": "action:new_search"}])
        return [{"type": "inline_keyboard", "payload": {"buttons": buttons}}]

    def build_telegram_keyboard(self, items: list[dict[str, Any]]) -> dict:
        keyboard = []
        for idx, item in enumerate(items[:5], start=1):
            ref = item.get("ref") or item.get("Ссылка") or str(idx)
            name = (item.get("name") or item.get("Наименование") or f"Товар {idx}")[:30]
            keyboard.append([{"text": f"{idx}. {name}", "callback_data": f"pick:{ref}"}])
        keyboard.append([{"text": "Новый поиск", "callback_data": "action:new_search"}])
        return {"inline_keyboard": keyboard}

    def build_followup_keyboard_max(self) -> list[dict]:
        buttons = [
            [
                {"type": "callback", "text": "Остатки", "payload": "action:stock"},
                {"type": "callback", "text": "Цена", "payload": "action:price"},
            ],
            [
                {"type": "callback", "text": "Характеристики", "payload": "action:details"},
                {"type": "callback", "text": "Фото", "payload": "action:image"},
            ],
            [{"type": "callback", "text": "Новый поиск", "payload": "action:new_search"}],
        ]
        return [{"type": "inline_keyboard", "payload": {"buttons": buttons}}]

    def build_followup_keyboard_telegram(self) -> dict:
        return {
            "inline_keyboard": [
                [
                    {"text": "Остатки", "callback_data": "action:stock"},
                    {"text": "Цена", "callback_data": "action:price"},
                ],
                [
                    {"text": "Характеристики", "callback_data": "action:details"},
                    {"text": "Фото", "callback_data": "action:image"},
                ],
                [{"text": "Новый поиск", "callback_data": "action:new_search"}],
            ]
        }

    async def handle_followup(self, action: str, selected_ref: str) -> dict[str, Any]:
        if action == "stock":
            data = await self._onec.get_stock(selected_ref)
            return {"text": self._format_stock(data)}

        if action == "details":
            data = await self._onec.get_details(selected_ref)
            name = data.get("name") or data.get("Наименование") or ""
            article = data.get("article") or data.get("Артикул") or "—"
            unit = data.get("unit") or data.get("ЕдиницаИзмерения") or "—"
            chars = data.get("characteristics") or data.get("Характеристики") or []
            return {
                "text": (
                    f"Товар: {name}\n"
                    f"Артикул: {article}\n"
                    f"Ед. изм.: {unit}\n"
                    f"Характеристики:\n{self._format_characteristics(chars)}"
                )
            }

        if action == "price":
            data = await self._onec.get_details(selected_ref)
            name = data.get("name") or data.get("Наименование") or ""
            return {"text": f"{name}\n\n{self._format_prices(data)}"}

        if action == "image":
            image = await self._onec.get_image(selected_ref)
            if image is None:
                return {"text": "У этой номенклатуры нет изображения в 1С."}
            return {
                "text": "Изображение из карточки 1С:",
                "photo": image,
            }

        return {"text": "Неизвестная команда."}

    @staticmethod
    def _format_stock(data: dict[str, Any]) -> str:
        items = data.get("items") or []
        if not items:
            total = data.get("quantity") or data.get("Количество") or 0
            return f"Остатки по всем складам: {total}"

        by_warehouse: dict[str, float] = {}
        detail_lines: list[str] = []
        for item in items:
            warehouse = str(item.get("warehouse") or item.get("Склад") or "—")
            characteristic = str(item.get("characteristic") or item.get("Характеристика") or "").strip()
            quantity = float(item.get("quantity") or item.get("Количество") or 0)
            by_warehouse[warehouse] = by_warehouse.get(warehouse, 0) + quantity
            char_suffix = f", {characteristic}" if characteristic and characteristic != warehouse else ""
            detail_lines.append(f"• {warehouse}: {quantity:g}{char_suffix}")

        lines = ["Остатки по складам:"]
        lines.extend(detail_lines)
        total = sum(by_warehouse.values())
        lines.append(f"Итого: {total:g}")
        return "\n".join(lines)

    @staticmethod
    def _format_characteristics(chars: list[Any]) -> str:
        if not chars:
            return "—"

        lines: list[str] = []
        for char in chars:
            if isinstance(char, dict):
                name = char.get("name") or char.get("Наименование") or "—"
                article = char.get("article") or char.get("Артикул") or ""
                suffix = f" (арт. {article})" if article else ""
                lines.append(f"• {name}{suffix}")
            else:
                lines.append(f"• {char}")
        return "\n".join(lines)

    @staticmethod
    def _format_prices(data: dict[str, Any]) -> str:
        prices = data.get("prices") or []
        if prices:
            lines = ["Цены по видам:"]
            for price_item in prices:
                if not isinstance(price_item, dict):
                    continue
                price_type = price_item.get("priceType") or price_item.get("type") or "—"
                price = price_item.get("price") or price_item.get("Цена") or "—"
                characteristic = price_item.get("characteristic") or price_item.get("Характеристика") or ""
                currency = price_item.get("currency") or price_item.get("Валюта") or ""
                unit = price_item.get("unit") or price_item.get("ЕдиницаИзмерения") or ""
                suffix_parts = [part for part in (characteristic, unit) if part]
                suffix = f" ({', '.join(suffix_parts)})" if suffix_parts else ""
                currency_suffix = f" {currency}" if currency else ""
                lines.append(f"• {price_type}{suffix}: {price}{currency_suffix}")
            return "\n".join(lines)

        price = data.get("price") or data.get("Цена")
        price_type = data.get("priceType") or data.get("ВидЦен") or ""
        if price not in (None, "", 0):
            prefix = f"{price_type}: " if price_type else ""
            return f"Цена: {prefix}{price}"
        return "Цены не указаны."

    def parse_pick_index(self, text: str, max_index: int) -> int | None:
        text = text.strip()
        if text.isdigit():
            idx = int(text)
            if 1 <= idx <= max_index:
                return idx
        return None

    @staticmethod
    def reset_context() -> dict:
        return {"candidates": [], "selected_ref": None, "selected_name": None}

    @staticmethod
    def state_after_search() -> str:
        return DialogState.AWAIT_PRODUCT_CHOICE.value

    @staticmethod
    def state_after_pick() -> str:
        return DialogState.PRODUCT_SELECTED.value

    @staticmethod
    def state_idle() -> str:
        return DialogState.IDLE.value
