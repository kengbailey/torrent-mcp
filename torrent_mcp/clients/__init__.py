"""External service clients."""

from __future__ import annotations

from typing import Protocol

from torrent_mcp.models.torrent import SessionStats, TorrentDetail, TorrentInfo

__all__ = [
    "ProwlarrClient",
    "QBittorrentClient",
    "TorrentClient",
    "TransmissionClient",
]


class TorrentClient(Protocol):
    """Structural protocol for torrent management backends.

    Both TransmissionClient and QBittorrentClient satisfy this protocol
    without inheriting from it. mypy verifies structural compatibility.
    """

    async def list_torrents(
        self, status_filter: str | None = None
    ) -> list[TorrentInfo]: ...

    async def get_torrent(self, id_or_hash: str) -> TorrentDetail | None: ...

    async def add_torrent(
        self,
        url: str,
        download_dir: str | None = None,
        paused: bool = False,
        torrent_data: bytes | None = None,
    ) -> TorrentInfo: ...

    async def start_torrent(self, id_or_hash: str) -> str: ...

    async def stop_torrent(self, id_or_hash: str) -> str: ...

    async def remove_torrent(
        self, id_or_hash: str, delete_data: bool = False
    ) -> str: ...

    async def get_session_stats(self) -> SessionStats: ...


from torrent_mcp.clients.prowlarr import ProwlarrClient  # noqa: E402
from torrent_mcp.clients.qbittorrent import QBittorrentClient  # noqa: E402
from torrent_mcp.clients.transmission import TransmissionClient  # noqa: E402
