"""FastMCP server setup and tool registration."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx
import structlog
from fastmcp import Context, FastMCP

from torrent_mcp.clients.jackett import JackettClient
from torrent_mcp.clients.transmission import TransmissionClient
from torrent_mcp.config import Settings
from torrent_mcp.tools import manage, search

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(server: FastMCP) -> AsyncIterator[dict[str, Any]]:
    """Manage HTTP client lifecycles."""
    settings = Settings()  # type: ignore[call-arg]

    transmission_auth: tuple[str, str] | None = None
    if settings.transmission_username and settings.transmission_password:
        transmission_auth = (settings.transmission_username, settings.transmission_password)

    async with (
        httpx.AsyncClient(
            timeout=settings.http_timeout,
            auth=transmission_auth,
        ) as transmission_http,
        httpx.AsyncClient(
            timeout=settings.http_timeout,
        ) as jackett_http,
    ):
        transmission = TransmissionClient(transmission_http, settings.transmission_url)
        jackett = JackettClient(jackett_http, settings.jackett_url, settings.jackett_api_key)

        log.info(
            "server started",
            transmission_url=settings.transmission_url,
            jackett_url=settings.jackett_url,
        )

        yield {
            "settings": settings,
            "transmission": transmission,
            "jackett": jackett,
        }

        log.info("server shutting down")


mcp = FastMCP("torrent-mcp", lifespan=lifespan)


def _transmission(ctx: Context) -> TransmissionClient:
    """Extract TransmissionClient from lifespan context."""
    return ctx.lifespan_context["transmission"]  # type: ignore[no-any-return]


def _jackett(ctx: Context) -> JackettClient:
    """Extract JackettClient from lifespan context."""
    return ctx.lifespan_context["jackett"]  # type: ignore[no-any-return]


# --- Search tools ---


@mcp.tool()
async def search_torrents(
    query: str,
    ctx: Context,
    category: str | None = None,
    limit: int = 25,
) -> str:
    """Search for torrents across all configured Jackett indexers.

    Args:
        query: Search terms to look for
        category: Optional category filter (e.g. movies, tv, music)
        limit: Maximum number of results to return (default: 25)
    """
    return await search.search_torrents(
        _jackett(ctx), query, category=category, limit=limit
    )


@mcp.tool()
async def list_indexers(ctx: Context) -> str:
    """List all configured and active Jackett indexers."""
    return await search.list_indexers(_jackett(ctx))


# --- Management tools ---


@mcp.tool()
async def list_torrents(ctx: Context, status_filter: str | None = None) -> str:
    """List all torrents from Transmission with their current status.

    Args:
        status_filter: Filter by status: downloading, seeding, stopped, all (default: all)
    """
    return await manage.list_torrents(_transmission(ctx), status_filter=status_filter)


@mcp.tool()
async def get_torrent(id_or_hash: str, ctx: Context) -> str:
    """Get detailed information about a specific torrent.

    Args:
        id_or_hash: Torrent ID (integer) or hash string
    """
    return await manage.get_torrent(_transmission(ctx), id_or_hash)


@mcp.tool()
async def add_torrent(
    url: str,
    ctx: Context,
    download_dir: str | None = None,
    paused: bool = False,
) -> str:
    """Add a torrent by magnet link or URL.

    Args:
        url: Magnet link or URL to a .torrent file
        download_dir: Optional override for download directory
        paused: Add in paused state (default: false)
    """
    return await manage.add_torrent(
        _transmission(ctx), url, download_dir=download_dir, paused=paused
    )


@mcp.tool()
async def start_torrent(id_or_hash: str, ctx: Context) -> str:
    """Resume a stopped torrent.

    Args:
        id_or_hash: Torrent ID (integer) or hash string
    """
    return await manage.start_torrent(_transmission(ctx), id_or_hash)


@mcp.tool()
async def stop_torrent(id_or_hash: str, ctx: Context) -> str:
    """Pause an active torrent.

    Args:
        id_or_hash: Torrent ID (integer) or hash string
    """
    return await manage.stop_torrent(_transmission(ctx), id_or_hash)


@mcp.tool()
async def remove_torrent(
    id_or_hash: str,
    ctx: Context,
    delete_data: bool = False,
) -> str:
    """Remove a torrent from Transmission.

    Args:
        id_or_hash: Torrent ID (integer) or hash string
        delete_data: Also delete downloaded files (default: false)
    """
    return await manage.remove_torrent(
        _transmission(ctx), id_or_hash, delete_data=delete_data
    )


@mcp.tool()
async def get_session_stats(ctx: Context) -> str:
    """Get Transmission global transfer statistics and disk space."""
    return await manage.get_session_stats(_transmission(ctx))
