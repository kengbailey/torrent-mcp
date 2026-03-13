"""Jackett Torznab search client."""

from typing import Any

import httpx
import structlog
import xmltodict

from torrent_mcp.exceptions import JackettError
from torrent_mcp.models.search import IndexerInfo, SearchResult

log = structlog.get_logger()


def _ensure_list(value: Any) -> list[dict[str, Any]]:
    """Normalize xmltodict output: single item becomes a list."""
    if value is None:
        return []
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        return value
    return []


def _safe_int(value: Any, default: int = 0) -> int:
    """Safely convert a value to int."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _extract_torznab_attr(item: dict[str, Any], name: str) -> str:
    """Extract a named attribute from torznab:attr elements."""
    attrs = item.get("torznab:attr", [])
    for attr in _ensure_list(attrs):
        if isinstance(attr, dict) and attr.get("@name") == name:
            return str(attr.get("@value", ""))
    return ""


class JackettClient:
    """Async client for Jackett's Torznab API."""

    def __init__(self, http_client: httpx.AsyncClient, base_url: str, api_key: str) -> None:
        self._client = http_client
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key

    async def _get(self, params: dict[str, str]) -> dict[str, Any]:
        """Make a Torznab API request and parse the XML response."""
        params["apikey"] = self._api_key
        url = f"{self._base_url}/api/v2.0/indexers/all/results/torznab/api"

        try:
            response = await self._client.get(url, params=params)
        except httpx.ConnectError as exc:
            raise JackettError(f"Cannot connect to Jackett at {self._base_url}") from exc

        if response.status_code == 401:
            raise JackettError("Jackett authentication failed: invalid API key")
        if response.status_code != 200:
            raise JackettError(f"Jackett returned HTTP {response.status_code}")

        try:
            parsed: Any = xmltodict.parse(response.text)
        except Exception as e:
            raise JackettError(f"Failed to parse Jackett XML response: {e}") from e

        if not isinstance(parsed, dict):
            raise JackettError("Unexpected Jackett response format")
        return parsed

    async def search(
        self,
        query: str,
        category: str | None = None,
        limit: int = 25,
    ) -> list[SearchResult]:
        """Search for torrents across all configured indexers."""
        params: dict[str, str] = {"t": "search", "q": query, "limit": str(limit)}
        if category:
            params["cat"] = category

        data = await self._get(params)

        rss = data.get("rss", {})
        if not isinstance(rss, dict):
            return []
        channel = rss.get("channel", {})
        if not isinstance(channel, dict):
            return []

        items = _ensure_list(channel.get("item"))
        log.debug("jackett search results", query=query, result_count=len(items))

        results: list[SearchResult] = []
        for item in items:
            if not isinstance(item, dict):
                continue

            size = _safe_int(_extract_torznab_attr(item, "size"))
            if size == 0:
                size = _safe_int(item.get("size"))

            magnet_url = _extract_torznab_attr(item, "magneturl")
            link = str(item.get("link", ""))

            # Jackett proxy links often 302-redirect to magnet URIs.
            # Resolve them so callers always get a usable magnet.
            if not magnet_url and link:
                magnet_url = await self._resolve_magnet(link)

            results.append(
                SearchResult(
                    title=str(item.get("title", "")),
                    size=size,
                    seeders=_safe_int(_extract_torznab_attr(item, "seeders")),
                    leechers=_safe_int(_extract_torznab_attr(item, "peers")),
                    magnet_url=magnet_url,
                    link=link,
                    category=str(item.get("category", "")),
                    publish_date=str(item.get("pubDate", "")),
                )
            )

        return results[:limit]

    async def _resolve_magnet(self, url: str) -> str:
        """Follow a Jackett download link and extract the magnet URI if it redirects to one."""
        try:
            response = await self._client.get(url, follow_redirects=False)
            if response.status_code in (301, 302, 303, 307, 308):
                location = response.headers.get("location", "")
                if location.startswith("magnet:"):
                    return str(location)
        except Exception:
            log.debug("failed to resolve magnet", url=url[:80])
        return ""

    async def list_indexers(self) -> list[IndexerInfo]:
        """List configured Jackett indexers."""
        data = await self._get({"t": "indexers", "configured": "true"})

        indexers_data = data.get("indexers", {})
        if not isinstance(indexers_data, dict):
            return []

        raw_indexers = _ensure_list(indexers_data.get("indexer"))
        log.debug("jackett indexers", count=len(raw_indexers))

        indexers: list[IndexerInfo] = []
        for idx in raw_indexers:
            if not isinstance(idx, dict):
                continue
            indexers.append(
                IndexerInfo(
                    name=str(idx.get("@name", idx.get("title", "Unknown"))),
                    id=str(idx.get("@id", "")),
                    configured=True,
                )
            )

        return indexers
