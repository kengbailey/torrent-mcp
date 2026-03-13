"""MCP tools for Transmission torrent management."""

from torrent_mcp.clients.transmission import TransmissionClient


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


def _format_speed(bytes_per_sec: int) -> str:
    """Format bytes/sec into human-readable speed."""
    if bytes_per_sec <= 0:
        return "0 B/s"
    value = float(bytes_per_sec)
    for unit in ("B/s", "KB/s", "MB/s", "GB/s"):
        if value < 1024:
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB/s"


def _format_eta(seconds: int) -> str:
    """Format ETA seconds into human-readable string."""
    if seconds < 0:
        return "Unknown"
    if seconds == 0:
        return "Done"
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours > 0:
        return f"{hours}h {minutes}m"
    if minutes > 0:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


async def list_torrents(
    client: TransmissionClient,
    status_filter: str | None = None,
) -> str:
    """List all torrents from Transmission with their current status.

    Args:
        status_filter: Filter by status: downloading, seeding, stopped, all (default: all)
    """
    torrents = await client.list_torrents(status_filter=status_filter)

    if not torrents:
        filter_msg = f" (filter: {status_filter})" if status_filter else ""
        return f"No torrents found{filter_msg}."

    lines: list[str] = [f"Torrents ({len(torrents)})\n"]

    for i, t in enumerate(torrents, 1):
        lines.append(f"{i}. {t.name}")
        parts: list[str] = [f"Status: {t.status}"]
        parts.append(f"Progress: {t.percent_done:.1%}")
        if t.rate_download > 0:
            parts.append(f"DL: {_format_speed(t.rate_download)}")
        if t.rate_upload > 0:
            parts.append(f"UL: {_format_speed(t.rate_upload)}")
        if t.status == "downloading" and t.eta >= 0:
            parts.append(f"ETA: {_format_eta(t.eta)}")
        if t.upload_ratio > 0:
            parts.append(f"Ratio: {t.upload_ratio:.2f}")
        lines.append(f"   {' | '.join(parts)}")
        lines.append(f"   Size: {_format_size(t.total_size)} | Hash: {t.hash_string[:12]}...")
        if t.error and t.error_string:
            lines.append(f"   Error: {t.error_string}")
        lines.append("")

    return "\n".join(lines)


async def get_torrent(client: TransmissionClient, id_or_hash: str) -> str:
    """Get detailed information about a specific torrent.

    Args:
        id_or_hash: Torrent ID (integer) or hash string
    """
    detail = await client.get_torrent(id_or_hash)

    if not detail:
        return f"Torrent not found: {id_or_hash}"

    lines: list[str] = [
        f"Torrent: {detail.name}\n",
        f"Hash: {detail.hash_string}",
        f"Status: {detail.status}",
        f"Progress: {detail.percent_done:.1%}",
        f"Size: {_format_size(detail.total_size)}",
        f"Download: {_format_speed(detail.rate_download)}",
        f"Upload: {_format_speed(detail.rate_upload)}",
        f"Ratio: {detail.upload_ratio:.2f}",
        f"ETA: {_format_eta(detail.eta)}",
        f"Peers: {detail.peers_connected}",
        f"Directory: {detail.download_dir}",
    ]

    if detail.labels:
        lines.append(f"Labels: {', '.join(detail.labels)}")

    if detail.error and detail.error_string:
        lines.append(f"Error: {detail.error_string}")

    if detail.files:
        lines.append(f"\nFiles ({len(detail.files)}):")
        for f in detail.files[:20]:
            pct = (f.bytes_completed / f.length * 100) if f.length > 0 else 0
            lines.append(f"  - {f.name} ({_format_size(f.length)}, {pct:.0f}%)")
        if len(detail.files) > 20:
            lines.append(f"  ... and {len(detail.files) - 20} more files")

    if detail.trackers:
        lines.append(f"\nTrackers ({len(detail.trackers)}):")
        for tr in detail.trackers:
            lines.append(f"  - {tr.sitename} ({tr.announce})")

    if detail.magnet_link:
        lines.append(f"\nMagnet: {detail.magnet_link}")

    return "\n".join(lines)


async def add_torrent(
    client: TransmissionClient,
    url: str,
    download_dir: str | None = None,
    paused: bool = False,
) -> str:
    """Add a torrent by magnet link or URL.

    Args:
        url: Magnet link or URL to a .torrent file
        download_dir: Optional override for download directory
        paused: Add in paused state (default: false)
    """
    info = await client.add_torrent(url, download_dir=download_dir, paused=paused)

    is_dup = info.name.startswith("[duplicate] ")
    name = info.name.removeprefix("[duplicate] ")

    if is_dup:
        return f"Torrent already exists: {name}\nHash: {info.hash_string}"

    return f"Torrent added: {name}\nHash: {info.hash_string}\nStatus: {info.status}"


async def start_torrent(client: TransmissionClient, id_or_hash: str) -> str:
    """Resume a stopped torrent.

    Args:
        id_or_hash: Torrent ID (integer) or hash string
    """
    name = await client.start_torrent(id_or_hash)
    return f"Started: {name}"


async def stop_torrent(client: TransmissionClient, id_or_hash: str) -> str:
    """Pause an active torrent.

    Args:
        id_or_hash: Torrent ID (integer) or hash string
    """
    name = await client.stop_torrent(id_or_hash)
    return f"Stopped: {name}"


async def remove_torrent(
    client: TransmissionClient,
    id_or_hash: str,
    delete_data: bool = False,
) -> str:
    """Remove a torrent from Transmission.

    Args:
        id_or_hash: Torrent ID (integer) or hash string
        delete_data: Also delete downloaded files (default: false)
    """
    name = await client.remove_torrent(id_or_hash, delete_data=delete_data)
    suffix = " (files deleted)" if delete_data else " (files kept)"
    return f"Removed: {name}{suffix}"


async def get_session_stats(client: TransmissionClient) -> str:
    """Get Transmission global transfer statistics and disk space."""
    stats = await client.get_session_stats()

    lines: list[str] = [
        "Transmission Session Stats\n",
        f"Torrents: {stats.active_torrent_count} active, "
        f"{stats.paused_torrent_count} paused, "
        f"{stats.torrent_count} total",
        f"Download Speed: {_format_speed(stats.download_speed)}",
        f"Upload Speed: {_format_speed(stats.upload_speed)}",
        "",
        "Cumulative:",
        f"  Downloaded: {_format_size(stats.cumulative_stats.downloaded_bytes)}",
        f"  Uploaded: {_format_size(stats.cumulative_stats.uploaded_bytes)}",
        f"  Files Added: {stats.cumulative_stats.files_added}",
    ]

    if stats.free_space_bytes > 0:
        lines.append(f"\nFree Space: {_format_size(stats.free_space_bytes)}")
    if stats.download_dir:
        lines.append(f"Download Dir: {stats.download_dir}")

    return "\n".join(lines)
