"""MCP tools for Prowlarr torrent search."""

import hashlib
import time

from torrent_mcp.clients.prowlarr import ProwlarrClient
from torrent_mcp.models.search import SearchResult

_CACHE_TTL = 86400  # 1 day in seconds

# Cache of search results keyed by 5-char hash ID.
# Each entry stores (SearchResult, timestamp).
_result_cache_raw: dict[str, tuple[SearchResult, float]] = {}


def _cache_get(hid: str) -> SearchResult | None:
    """Get a cached result, returning None if expired or missing."""
    entry = _result_cache_raw.get(hid)
    if entry is None:
        return None
    result, ts = entry
    if time.time() - ts > _CACHE_TTL:
        del _result_cache_raw[hid]
        return None
    return result


def _cache_set(hid: str, result: SearchResult) -> None:
    """Store a result in cache with current timestamp."""
    _result_cache_raw[hid] = (result, time.time())




def _hash_id(download_url: str) -> str:
    """Generate a deterministic 5-char hex hash from a download URL."""
    return hashlib.sha256(download_url.encode()).hexdigest()[:5]


def _format_size(size_bytes: int) -> str:
    """Format bytes into human-readable size."""
    if size_bytes <= 0:
        return "Unknown"
    value = float(size_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024:
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} PB"


async def search_torrents(
    client: ProwlarrClient,
    query: str,
    category: str | None = None,
    limit: int = 15,
) -> str:
    """Search for torrents across all configured Prowlarr indexers.

    Args:
        query: Search terms to look for
        category: Optional category filter (e.g. movies, tv, music)
        limit: Maximum number of results to return (default: 15)
    """
    results = await client.search(query, category=category, limit=limit)

    if not results:
        return f"No results found for '{query}'."

    lines: list[str] = [f"Search Results for '{query}' ({len(results)} found)\n"]

    for i, r in enumerate(results, 1):
        hid = _hash_id(r.download_url) if r.download_url else "-----"
        if r.download_url:
            _cache_set(hid, r)

        prefix = f"[{r.indexer}] " if r.indexer else ""
        lines.append(f"{i}. [{hid}] {prefix}{r.title}")
        parts: list[str] = [f"Size: {_format_size(r.size)}"]
        parts.append(f"Seeders: {r.seeders}")
        parts.append(f"Leechers: {r.leechers}")
        if r.category:
            parts.append(f"Category: {r.category}")
        lines.append(f"   {' | '.join(parts)}")
        lines.append("")

    return "\n".join(lines)


async def list_indexers(client: ProwlarrClient) -> str:
    """List all configured Prowlarr indexers."""
    indexers = await client.list_indexers()

    if not indexers:
        return "No configured indexers found in Prowlarr."

    lines: list[str] = [f"Configured Indexers ({len(indexers)})\n"]
    for idx in indexers:
        status = "enabled" if idx.enabled else "disabled"
        lines.append(f"- {idx.name} (id: {idx.id}, {status})")

    return "\n".join(lines)
