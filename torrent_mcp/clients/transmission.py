"""Transmission JSON-RPC client."""

from typing import Any

import httpx
import structlog

from torrent_mcp.exceptions import TransmissionError
from torrent_mcp.models.torrent import (
    CumulativeStats,
    FileInfo,
    SessionStats,
    TorrentDetail,
    TorrentInfo,
    TrackerInfo,
)

log = structlog.get_logger()

STATUS_MAP: dict[int, str] = {
    0: "stopped",
    1: "checking queue",
    2: "checking",
    3: "download queue",
    4: "downloading",
    5: "seed queue",
    6: "seeding",
}

ESSENTIAL_FIELDS = [
    "name",
    "hashString",
    "status",
    "percentDone",
    "rateDownload",
    "rateUpload",
    "totalSize",
    "eta",
    "uploadRatio",
    "error",
    "errorString",
]

DETAIL_FIELDS = [
    *ESSENTIAL_FIELDS,
    "downloadDir",
    "addedDate",
    "doneDate",
    "peersConnected",
    "labels",
    "magnetLink",
    "files",
    "trackers",
]


def _parse_ids(id_or_hash: str) -> list[int] | list[str]:
    """Parse a torrent ID or hash string into the ids format Transmission expects."""
    try:
        return [int(id_or_hash)]
    except ValueError:
        return [id_or_hash]


def _map_status(code: int) -> str:
    return STATUS_MAP.get(code, f"unknown({code})")


def _to_torrent_info(t: dict[str, Any]) -> TorrentInfo:
    return TorrentInfo(
        name=str(t.get("name", "")),
        hash_string=str(t.get("hashString", "")),
        status=_map_status(int(t.get("status", 0))),
        percent_done=float(t.get("percentDone", 0)),
        rate_download=int(t.get("rateDownload", 0)),
        rate_upload=int(t.get("rateUpload", 0)),
        total_size=int(t.get("totalSize", 0)),
        eta=int(t.get("eta", -1)),
        upload_ratio=float(t.get("uploadRatio", 0)),
        error=int(t.get("error", 0)),
        error_string=str(t.get("errorString", "")),
    )


def _to_torrent_detail(t: dict[str, Any]) -> TorrentDetail:
    raw_files = t.get("files", [])
    files: list[FileInfo] = []
    if isinstance(raw_files, list):
        for f in raw_files:
            if isinstance(f, dict):
                files.append(
                    FileInfo(
                        name=str(f.get("name", "")),
                        length=int(f.get("length", 0)),
                        bytes_completed=int(f.get("bytesCompleted", 0)),
                    )
                )

    raw_trackers = t.get("trackers", [])
    trackers: list[TrackerInfo] = []
    if isinstance(raw_trackers, list):
        for tr in raw_trackers:
            if isinstance(tr, dict):
                trackers.append(
                    TrackerInfo(
                        announce=str(tr.get("announce", "")),
                        sitename=str(tr.get("sitename", "")),
                    )
                )

    raw_labels = t.get("labels", [])
    labels: list[str] = [str(lbl) for lbl in raw_labels] if isinstance(raw_labels, list) else []

    return TorrentDetail(
        name=str(t.get("name", "")),
        hash_string=str(t.get("hashString", "")),
        status=_map_status(int(t.get("status", 0))),
        percent_done=float(t.get("percentDone", 0)),
        rate_download=int(t.get("rateDownload", 0)),
        rate_upload=int(t.get("rateUpload", 0)),
        total_size=int(t.get("totalSize", 0)),
        eta=int(t.get("eta", -1)),
        upload_ratio=float(t.get("uploadRatio", 0)),
        error=int(t.get("error", 0)),
        error_string=str(t.get("errorString", "")),
        download_dir=str(t.get("downloadDir", "")),
        added_date=int(t.get("addedDate", 0)),
        done_date=int(t.get("doneDate", 0)),
        peers_connected=int(t.get("peersConnected", 0)),
        labels=labels,
        magnet_link=str(t.get("magnetLink", "")),
        files=files,
        trackers=trackers,
    )


STATUS_FILTER_MAP: dict[str, int] = {
    "stopped": 0,
    "downloading": 4,
    "seeding": 6,
    "checking": 2,
}


class TransmissionClient:
    """Async client for Transmission's JSON-RPC API."""

    def __init__(self, http_client: httpx.AsyncClient, url: str) -> None:
        self._client = http_client
        self._url = url
        self._session_id: str = ""

    async def _rpc(
        self, method: str, arguments: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Make an RPC call with automatic 409 session-id retry."""
        payload: dict[str, Any] = {"method": method}
        if arguments:
            payload["arguments"] = arguments

        headers: dict[str, str] = {}
        if self._session_id:
            headers["X-Transmission-Session-Id"] = self._session_id

        try:
            response = await self._client.post(self._url, json=payload, headers=headers)
        except httpx.ConnectError as exc:
            raise TransmissionError(f"Cannot connect to Transmission at {self._url}") from exc

        if response.status_code == 409:
            self._session_id = response.headers.get("X-Transmission-Session-Id", "")
            headers["X-Transmission-Session-Id"] = self._session_id
            log.debug("transmission session id acquired")
            response = await self._client.post(self._url, json=payload, headers=headers)

        if response.status_code != 200:
            raise TransmissionError(f"Transmission returned HTTP {response.status_code}")

        data = response.json()
        result_str = data.get("result", "")
        if result_str != "success":
            raise TransmissionError(f"Transmission RPC error: {result_str}")

        arguments_resp = data.get("arguments", {})
        if not isinstance(arguments_resp, dict):
            return {}
        return arguments_resp

    async def list_torrents(self, status_filter: str | None = None) -> list[TorrentInfo]:
        """List torrents, optionally filtered by status."""
        args = await self._rpc("torrent-get", {"fields": ESSENTIAL_FIELDS})
        raw_torrents = args.get("torrents", [])
        if not isinstance(raw_torrents, list):
            return []

        torrents = [_to_torrent_info(t) for t in raw_torrents if isinstance(t, dict)]

        if status_filter and status_filter != "all":
            target_code = STATUS_FILTER_MAP.get(status_filter)
            if target_code is not None:
                target_status = _map_status(target_code)
                torrents = [t for t in torrents if t.status == target_status]

        return torrents

    async def get_torrent(self, id_or_hash: str) -> TorrentDetail | None:
        """Get detailed info for a specific torrent."""
        ids = _parse_ids(id_or_hash)
        args = await self._rpc("torrent-get", {"ids": ids, "fields": DETAIL_FIELDS})
        raw_torrents = args.get("torrents", [])
        if not isinstance(raw_torrents, list) or not raw_torrents:
            return None
        first = raw_torrents[0]
        if not isinstance(first, dict):
            return None
        return _to_torrent_detail(first)

    async def add_torrent(
        self,
        url: str,
        download_dir: str | None = None,
        paused: bool = False,
        torrent_data: bytes | None = None,
    ) -> TorrentInfo:
        """Add a torrent by magnet link, URL, or raw .torrent file content."""
        add_args: dict[str, Any] = {"paused": paused}
        if torrent_data:
            import base64

            add_args["metainfo"] = base64.b64encode(torrent_data).decode()
        else:
            add_args["filename"] = url
        if download_dir:
            add_args["download-dir"] = download_dir

        result = await self._rpc("torrent-add", add_args)

        torrent_data = result.get("torrent-added") or result.get("torrent-duplicate")
        if not isinstance(torrent_data, dict):
            raise TransmissionError("Unexpected response from torrent-add")

        name = str(torrent_data.get("name", "Unknown"))
        hash_str = str(torrent_data.get("hashString", ""))
        torrent_id = torrent_data.get("id", 0)

        log.info("torrent added", name=name, hash=hash_str, id=torrent_id)

        is_duplicate = "torrent-duplicate" in result
        return TorrentInfo(
            name=f"{'[duplicate] ' if is_duplicate else ''}{name}",
            hash_string=hash_str,
            status="stopped" if paused else "download queue",
            percent_done=0.0,
            rate_download=0,
            rate_upload=0,
            total_size=0,
            eta=-1,
            upload_ratio=0.0,
        )

    async def start_torrent(self, id_or_hash: str) -> str:
        """Start a torrent. Returns the torrent name."""
        detail = await self.get_torrent(id_or_hash)
        name = detail.name if detail else id_or_hash
        await self._rpc("torrent-start", {"ids": _parse_ids(id_or_hash)})
        log.info("torrent started", name=name)
        return name

    async def stop_torrent(self, id_or_hash: str) -> str:
        """Stop a torrent. Returns the torrent name."""
        detail = await self.get_torrent(id_or_hash)
        name = detail.name if detail else id_or_hash
        await self._rpc("torrent-stop", {"ids": _parse_ids(id_or_hash)})
        log.info("torrent stopped", name=name)
        return name

    async def remove_torrent(self, id_or_hash: str, delete_data: bool = False) -> str:
        """Remove a torrent. Returns the torrent name."""
        detail = await self.get_torrent(id_or_hash)
        name = detail.name if detail else id_or_hash
        await self._rpc(
            "torrent-remove",
            {"ids": _parse_ids(id_or_hash), "delete-local-data": delete_data},
        )
        log.info("torrent removed", name=name, deleted_data=delete_data)
        return name

    async def get_session_stats(self) -> SessionStats:
        """Get session statistics including free disk space."""
        stats = await self._rpc("session-stats")
        session = await self._rpc("session-get", {"fields": ["download-dir"]})
        download_dir = str(session.get("download-dir", ""))

        free_space_bytes = 0
        if download_dir:
            try:
                space = await self._rpc("free-space", {"path": download_dir})
                free_space_bytes = int(space.get("size-bytes", 0))
            except TransmissionError:
                log.warning("failed to get free space", download_dir=download_dir)

        raw_cumulative = stats.get("cumulative-stats", {})
        if not isinstance(raw_cumulative, dict):
            raw_cumulative = {}

        return SessionStats(
            active_torrent_count=int(stats.get("activeTorrentCount", 0)),
            paused_torrent_count=int(stats.get("pausedTorrentCount", 0)),
            torrent_count=int(stats.get("torrentCount", 0)),
            download_speed=int(stats.get("downloadSpeed", 0)),
            upload_speed=int(stats.get("uploadSpeed", 0)),
            cumulative_stats=CumulativeStats(
                uploaded_bytes=int(raw_cumulative.get("uploadedBytes", 0)),
                downloaded_bytes=int(raw_cumulative.get("downloadedBytes", 0)),
                files_added=int(raw_cumulative.get("filesAdded", 0)),
                seconds_active=int(raw_cumulative.get("secondsActive", 0)),
            ),
            free_space_bytes=free_space_bytes,
            download_dir=download_dir,
        )
