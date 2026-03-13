"""MCP tools for Jackett torrent search."""

from torrent_mcp.clients.jackett import JackettClient


def _format_size(size_bytes: int) -> str:
    """Format bytes into human-readable size."""
    if size_bytes <= 0:
        return "Unknown"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024  # type: ignore[assignment]
    return f"{size_bytes:.1f} PB"


async def search_torrents(
    client: JackettClient,
    query: str,
    category: str | None = None,
    limit: int = 25,
) -> str:
    """Search for torrents across all configured Jackett indexers.

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
        lines.append(f"{i}. {r.title}")
        parts: list[str] = [f"Size: {_format_size(r.size)}"]
        parts.append(f"Seeders: {r.seeders}")
        parts.append(f"Leechers: {r.leechers}")
        if r.category:
            parts.append(f"Category: {r.category}")
        lines.append(f"   {' | '.join(parts)}")
        if r.magnet_url:
            lines.append(f"   Magnet: {r.magnet_url}")
        elif r.link:
            lines.append(f"   Link: {r.link}")
        lines.append("")

    return "\n".join(lines)


async def list_indexers(client: JackettClient) -> str:
    """List all configured and active Jackett indexers."""
    indexers = await client.list_indexers()

    if not indexers:
        return "No configured indexers found in Jackett."

    lines: list[str] = [f"Configured Indexers ({len(indexers)})\n"]
    for idx in indexers:
        lines.append(f"- {idx.name} (id: {idx.id})")

    return "\n".join(lines)
