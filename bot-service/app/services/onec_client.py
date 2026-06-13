"""HTTP-клиент API 1С:УНФ для поиска номенклатуры."""

from __future__ import annotations

from typing import Any

import httpx

from app.config import settings


class OneCClient:
    def __init__(self) -> None:
        self._base = settings.onec_base_url.rstrip("/") + "/hs/nomenclature_bot/v1"
        self._auth = (settings.onec_username, settings.onec_password)
        self._timeout = settings.onec_timeout_sec

    async def search(self, query: str, limit: int | None = None) -> list[dict[str, Any]]:
        params = {"q": query, "limit": limit or settings.onec_search_limit}
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(f"{self._base}/search", params=params, auth=self._auth)
            response.raise_for_status()
            data = response.json()
        return data.get("items", data if isinstance(data, list) else [])

    async def search_smart(
        self,
        params: dict[str, Any],
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        payload = {
            "barcode": params.get("barcode") or "",
            "article": params.get("article") or "",
            "tokens": params.get("tokens") or [],
            "q": params.get("q") or "",
            "limit": limit or settings.onec_search_limit,
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(f"{self._base}/search", json=payload, auth=self._auth)
            response.raise_for_status()
            data = response.json()
        return data.get("items", data if isinstance(data, list) else [])

    async def get_stock(self, ref: str, warehouse: str = "") -> dict[str, Any]:
        params = {"ref": ref}
        if warehouse:
            params["warehouse"] = warehouse
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(f"{self._base}/stock", params=params, auth=self._auth)
            response.raise_for_status()
            return response.json()

    async def get_details(self, ref: str) -> dict[str, Any]:
        params = {"ref": ref}
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(f"{self._base}/details", params=params, auth=self._auth)
            response.raise_for_status()
            return response.json()

    async def get_image(self, ref: str) -> dict[str, Any] | None:
        params = {"ref": ref}
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(f"{self._base}/image", params=params, auth=self._auth)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            content_type = response.headers.get("content-type", "image/jpeg").split(";")[0].strip()
            return {
                "bytes": response.content,
                "mime_type": content_type or "image/jpeg",
            }

    async def verify_phone(self, phone: str) -> dict[str, Any]:
        payload = {"phone": phone}
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(f"{self._base}/auth/verify", json=payload, auth=self._auth)
            if response.status_code >= 400:
                detail = response.text.strip()
                raise RuntimeError(f"HTTP {response.status_code}: {detail[:500]}")
            return response.json()
