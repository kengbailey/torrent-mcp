"""Prowlarr REST API v1 client."""

from typing import Any

import httpx
import structlog

from torrent_mcp.exceptions import ProwlarrError
from torrent_mcp.models.search import IndexerInfo, SearchResult

log = structlog.get_logger()

# Newznab/Torznab standard category IDs
CATEGORY_MAP: dict[str, int] = {
    "movies": 2000,
    "music": 3000,
    "tv": 5000,
    "books": 7000,
    "other": 8000,
}


class ProwlarrClient:
    """Async client for Prowlarr's REST API v1."""

    def __init__(self, http_client: httpx.AsyncClient, api_key: str) -> None:
        self._client = http_client
        self._api_key = api_key

    def _headers(self) -> dict[str, str]:
        return {"X-Api-Key": self._api_key}

    async def search(
        self,
        query: str,
        category: str | None = None,
        limit: int = 25,
    ) -> list[SearchResult]:
        """Search for torrents across all enabled indexers."""
        params: dict[str, str | int] = {
            "query": query,
            "type": "search",
            "limit": limit,
        }
        if category:
            cat_id = CATEGORY_MAP.get(category.lower())
            if cat_id is not None:
                params["categories"] = cat_id
            else:
                # Allow raw numeric IDs
                params["categories"] = category

        try:
            response = await self._client.get(
                "/api/v1/search", params=params, headers=self._headers()
            )
        except httpx.ConnectError as exc:
            raise ProwlarrError(
                f"Cannot connect to Prowlarr at {self._client.base_url}"
            ) from exc

        if response.status_code == 401:
            raise ProwlarrError("Prowlarr authentication failed: invalid API key")
        if response.status_code != 200:
            raise ProwlarrError(f"Prowlarr returned HTTP {response.status_code}")

        raw: list[dict[str, Any]] = response.json()
        log.debug("prowlarr search results", query=query, result_count=len(raw))

        results: list[SearchResult] = []
        for item in raw:
            categories = item.get("categories", [])
            category_name = ""
            if isinstance(categories, list) and categories:
                first_cat = categories[0]
                if isinstance(first_cat, dict):
                    category_name = str(first_cat.get("name", ""))

            results.append(
                SearchResult(
                    title=str(item.get("title", "")),
                    size=int(item.get("size", 0)),
                    seeders=int(item.get("seeders", 0)),
                    leechers=int(item.get("leechers", 0)),
                    download_url=str(item.get("downloadUrl", "")),
                    magnet_url=str(item.get("magnetUrl", "")),
                    category=category_name,
                    publish_date=str(item.get("publishDate", "")),
                    indexer=str(item.get("indexer", "")),
                )
            )

        return results[:limit]

    async def list_indexers(self) -> list[IndexerInfo]:
        """List all configured indexers."""
        try:
            response = await self._client.get(
                "/api/v1/indexer", headers=self._headers()
            )
        except httpx.ConnectError as exc:
            raise ProwlarrError(
                f"Cannot connect to Prowlarr at {self._client.base_url}"
            ) from exc

        if response.status_code != 200:
            raise ProwlarrError(f"Prowlarr returned HTTP {response.status_code}")

        raw: list[dict[str, Any]] = response.json()
        log.debug("prowlarr indexers", count=len(raw))

        return [
            IndexerInfo(
                name=str(idx.get("name", "Unknown")),
                id=int(idx.get("id", 0)),
                enabled=bool(idx.get("enable", False)),
            )
            for idx in raw
        ]
