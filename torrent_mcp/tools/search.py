"""MCP tools for Prowlarr torrent search."""

from torrent_mcp.clients.prowlarr import ProwlarrClient


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
    limit: int = 25,
) -> str:
    """Search for torrents across all configured Prowlarr indexers.

    Args:
        query: Search terms to look for
        category: Optional category filter (e.g. movies, tv, music)
        limit: Maximum number of results to return (default: 25)
    """
    results = await client.search(query, category=category, limit=limit)

    if not results:
        return f"No results found for '{query}'."

    lines: list[str] = [f"Search Results for '{query}' ({len(results)} found)\n"]

    for i, r in enumerate(results, 1):
        prefix = f"[{r.indexer}] " if r.indexer else ""
        lines.append(f"{i}. {prefix}{r.title}")
        parts: list[str] = [f"Size: {_format_size(r.size)}"]
        parts.append(f"Seeders: {r.seeders}")
        parts.append(f"Leechers: {r.leechers}")
        if r.category:
            parts.append(f"Category: {r.category}")
        lines.append(f"   {' | '.join(parts)}")
        if r.magnet_url:
            lines.append(f"   Magnet: {r.magnet_url}")
        elif r.download_url:
            lines.append(f"   Link: {r.download_url}")
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
