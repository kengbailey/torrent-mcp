"""qBittorrent Web API v2 client (targeting v5.x)."""

from __future__ import annotations

import asyncio
import re
from typing import Any
from urllib.parse import unquote_plus, urlparse

import httpx
import structlog

from torrent_mcp.exceptions import QBittorrentError
from torrent_mcp.models.torrent import (
    CumulativeStats,
    FileInfo,
    SessionStats,
    TorrentDetail,
    TorrentInfo,
    TrackerInfo,
)

log = structlog.get_logger()

_STATE_MAP: dict[str, str] = {
    "downloading": "downloading",
    "stalledDL": "downloading",
    "metaDL": "downloading",
    "forcedMetaDL": "downloading",
    "forcedDL": "downloading",
    "allocating": "downloading",
    "queuedDL": "queued",
    "checkingDL": "checking",
    "uploading": "seeding",
    "stalledUP": "seeding",
    "forcedUP": "seeding",
    "queuedUP": "queued",
    "checkingUP": "checking",
    "stoppedDL": "stopped",
    "stoppedUP": "stopped",
    "error": "error",
    "missingFiles": "error",
    "moving": "moving",
    "checkingResumeData": "checking",
    "unknown": "unknown",
}

_STATUS_FILTER_MAP: dict[str, str] = {
    "downloading": "downloading",
    "seeding": "seeding",
    "stopped": "paused",
}

_MAGNET_HASH_RE = re.compile(r"xt=urn:btih:([a-fA-F0-9]{40}|[a-zA-Z2-7]{32})", re.IGNORECASE)

_QB_ETA_UNKNOWN = 8640000


def _map_state(state: str) -> str:
    return _STATE_MAP.get(state, "unknown")


def _to_torrent_info(t: dict[str, Any]) -> TorrentInfo:
    eta = int(t.get("eta", -1))
    if eta == _QB_ETA_UNKNOWN:
        eta = -1
    return TorrentInfo(
        name=str(t.get("name", "")),
        hash_string=str(t.get("hash", "")),
        status=_map_state(str(t.get("state", "unknown"))),
        percent_done=float(t.get("progress", 0)),
        rate_download=int(t.get("dlspeed", 0)),
        rate_upload=int(t.get("upspeed", 0)),
        total_size=int(t.get("size", 0)),
        eta=eta,
        upload_ratio=float(t.get("ratio", 0)),
    )


def _parse_magnet_hash(url: str) -> str | None:
    """Extract info-hash from a magnet URI, or return None."""
    match = _MAGNET_HASH_RE.search(url)
    if not match:
        return None
    return match.group(1).lower()


class QBittorrentClient:
    """Async client for qBittorrent's Web API v2."""

    def __init__(
        self,
        http_client: httpx.AsyncClient,
        username: str,
        password: str,
    ) -> None:
        self._client = http_client
        self._username = username
        self._password = password
        self._authenticated = False

    async def _login(self) -> None:
        """Authenticate with qBittorrent and obtain a session cookie."""
        try:
            response = await self._client.post(
                "/api/v2/auth/login",
                data={"username": self._username, "password": self._password},
            )
        except httpx.ConnectError as exc:
            raise QBittorrentError(
                "Cannot connect to qBittorrent"
            ) from exc

        if response.status_code == 403:
            raise QBittorrentError("IP address has been banned")

        body = response.text
        if body != "Ok.":
            raise QBittorrentError("Login failed: invalid credentials")

        self._authenticated = True
        log.debug("qbittorrent login successful")

    async def _request(
        self, method: str, path: str, **kwargs: Any
    ) -> httpx.Response:
        """Make an API request with automatic login and 403 retry."""
        if not self._authenticated:
            await self._login()

        try:
            response = await self._client.request(method, path, **kwargs)
        except httpx.ConnectError as exc:
            raise QBittorrentError(
                "Cannot connect to qBittorrent"
            ) from exc

        if response.status_code == 403:
            log.debug("qbittorrent session expired, re-authenticating")
            await self._login()
            try:
                response = await self._client.request(method, path, **kwargs)
            except httpx.ConnectError as exc:
                raise QBittorrentError(
                    "Cannot connect to qBittorrent"
                ) from exc

        return response

    async def list_torrents(
        self, status_filter: str | None = None
    ) -> list[TorrentInfo]:
        """List torrents, optionally filtered by status."""
        params: dict[str, str] = {}
        if status_filter and status_filter in _STATUS_FILTER_MAP:
            params["filter"] = _STATUS_FILTER_MAP[status_filter]

        response = await self._request("GET", "/api/v2/torrents/info", params=params)
        raw: list[dict[str, Any]] = response.json()
        return [_to_torrent_info(t) for t in raw]

    async def get_torrent(self, id_or_hash: str) -> TorrentDetail | None:
        """Get detailed info for a specific torrent."""
        info_resp = await self._request(
            "GET", "/api/v2/torrents/info", params={"hashes": id_or_hash}
        )
        torrents: list[dict[str, Any]] = info_resp.json()
        if not torrents:
            return None

        t = torrents[0]

        files_resp = await self._request(
            "GET", "/api/v2/torrents/files", params={"hash": id_or_hash}
        )
        trackers_resp = await self._request(
            "GET", "/api/v2/torrents/trackers", params={"hash": id_or_hash}
        )

        raw_files: list[dict[str, Any]] = files_resp.json()
        files: list[FileInfo] = []
        for f in raw_files:
            size = int(f.get("size", 0))
            progress = float(f.get("progress", 0))
            files.append(
                FileInfo(
                    name=str(f.get("name", "")),
                    length=size,
                    bytes_completed=round(progress * size),
                )
            )

        raw_trackers: list[dict[str, Any]] = trackers_resp.json()
        trackers: list[TrackerInfo] = []
        for tr in raw_trackers:
            url = str(tr.get("url", ""))
            if url.startswith("** ["):
                continue
            parsed = urlparse(url)
            trackers.append(
                TrackerInfo(
                    announce=url,
                    sitename=parsed.hostname or "",
                )
            )

        raw_tags = str(t.get("tags", ""))
        labels = [tag.strip() for tag in raw_tags.split(",") if tag.strip()]

        eta = int(t.get("eta", -1))
        if eta == _QB_ETA_UNKNOWN:
            eta = -1

        return TorrentDetail(
            name=str(t.get("name", "")),
            hash_string=str(t.get("hash", "")),
            status=_map_state(str(t.get("state", "unknown"))),
            percent_done=float(t.get("progress", 0)),
            rate_download=int(t.get("dlspeed", 0)),
            rate_upload=int(t.get("upspeed", 0)),
            total_size=int(t.get("size", 0)),
            eta=eta,
            upload_ratio=float(t.get("ratio", 0)),
            download_dir=str(t.get("save_path", "")),
            peers_connected=int(t.get("num_seeds", 0)),
            labels=labels,
            magnet_link=str(t.get("magnet_uri", "")),
            files=files,
            trackers=trackers,
        )

    async def add_torrent(
        self,
        url: str,
        download_dir: str | None = None,
        paused: bool = False,
    ) -> TorrentInfo:
        """Add a torrent by magnet link or URL."""
        info_hash = _parse_magnet_hash(url)

        # Duplicate detection
        if info_hash:
            dup_resp = await self._request(
                "GET", "/api/v2/torrents/info", params={"hashes": info_hash}
            )
            existing: list[dict[str, Any]] = dup_resp.json()
            if existing:
                torrent = _to_torrent_info(existing[0])
                torrent.name = f"[duplicate] {torrent.name}"
                log.info("duplicate torrent detected", hash=info_hash)
                return torrent

        # Build multipart form data
        form_data: dict[str, str] = {
            "urls": url,
            "paused": "true" if paused else "false",
        }
        if download_dir:
            form_data["savepath"] = download_dir

        response = await self._request(
            "POST", "/api/v2/torrents/add", data=form_data
        )
        if response.text != "Ok.":
            raise QBittorrentError(f"Failed to add torrent: {response.text}")

        log.info("torrent added", url=url)

        # Fetch the newly added torrent info
        if info_hash:
            for _ in range(2):
                fetch_resp = await self._request(
                    "GET", "/api/v2/torrents/info", params={"hashes": info_hash}
                )
                fetched: list[dict[str, Any]] = fetch_resp.json()
                if fetched:
                    return _to_torrent_info(fetched[0])
                await asyncio.sleep(0.5)

        # Fallback: return minimal info
        name = "Unknown"
        if info_hash:
            # Try to extract name from magnet
            dn_match = re.search(r"[?&]dn=([^&]+)", url)
            if dn_match:
                name = unquote_plus(dn_match.group(1))

        return TorrentInfo(
            name=name,
            hash_string=info_hash or "",
            status="downloading",
            percent_done=0.0,
            rate_download=0,
            rate_upload=0,
            total_size=0,
            eta=-1,
            upload_ratio=0.0,
        )

    async def _get_torrent_name(self, id_or_hash: str) -> str:
        """Fetch a torrent's name by hash, raising if not found."""
        response = await self._request(
            "GET", "/api/v2/torrents/info", params={"hashes": id_or_hash}
        )
        torrents: list[dict[str, Any]] = response.json()
        if not torrents:
            raise QBittorrentError(f"Torrent not found: {id_or_hash}")
        return str(torrents[0].get("name", id_or_hash))

    async def start_torrent(self, id_or_hash: str) -> str:
        """Start a torrent. Returns the torrent name."""
        name = await self._get_torrent_name(id_or_hash)
        await self._request(
            "POST", "/api/v2/torrents/start", data={"hashes": id_or_hash}
        )
        log.info("torrent started", name=name)
        return name

    async def stop_torrent(self, id_or_hash: str) -> str:
        """Stop a torrent. Returns the torrent name."""
        name = await self._get_torrent_name(id_or_hash)
        await self._request(
            "POST", "/api/v2/torrents/stop", data={"hashes": id_or_hash}
        )
        log.info("torrent stopped", name=name)
        return name

    async def remove_torrent(
        self, id_or_hash: str, delete_data: bool = False
    ) -> str:
        """Remove a torrent. Returns the torrent name."""
        name = await self._get_torrent_name(id_or_hash)
        await self._request(
            "POST",
            "/api/v2/torrents/delete",
            data={
                "hashes": id_or_hash,
                "deleteFiles": "true" if delete_data else "false",
            },
        )
        log.info("torrent removed", name=name, deleted_data=delete_data)
        return name

    async def get_session_stats(self) -> SessionStats:
        """Get session statistics including free disk space."""
        transfer_resp = await self._request("GET", "/api/v2/transfer/info")
        transfer: dict[str, Any] = transfer_resp.json()

        maindata_resp = await self._request(
            "GET", "/api/v2/sync/maindata", params={"rid": "0"}
        )
        maindata: dict[str, Any] = maindata_resp.json()
        server_state: dict[str, Any] = maindata.get("server_state", {})

        savepath_resp = await self._request("GET", "/api/v2/app/defaultSavePath")
        download_dir = savepath_resp.text.strip()

        torrents_resp = await self._request("GET", "/api/v2/torrents/info")
        all_torrents: list[dict[str, Any]] = torrents_resp.json()

        torrent_count = len(all_torrents)
        paused_count = sum(
            1
            for t in all_torrents
            if _map_state(str(t.get("state", "unknown"))) == "stopped"
        )
        active_count = torrent_count - paused_count

        free_space = int(server_state.get("free_space_on_disk", 0))
        if free_space < 0:
            free_space = 0

        return SessionStats(
            active_torrent_count=active_count,
            paused_torrent_count=paused_count,
            torrent_count=torrent_count,
            download_speed=int(transfer.get("dl_info_speed", 0)),
            upload_speed=int(transfer.get("up_info_speed", 0)),
            cumulative_stats=CumulativeStats(
                uploaded_bytes=int(server_state.get("alltime_ul", 0)),
                downloaded_bytes=int(server_state.get("alltime_dl", 0)),
                files_added=0,
                seconds_active=0,
            ),
            free_space_bytes=free_space,
            download_dir=download_dir,
        )
