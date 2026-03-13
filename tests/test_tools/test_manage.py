"""Tests for manage tool formatting."""

from unittest.mock import AsyncMock

from torrent_mcp.models.torrent import (
    CumulativeStats,
    FileInfo,
    SessionStats,
    TorrentDetail,
    TorrentInfo,
    TrackerInfo,
)
from torrent_mcp.tools.manage import (
    _format_eta,
    _format_size,
    _format_speed,
    add_torrent,
    get_session_stats,
    get_torrent,
    list_torrents,
    remove_torrent,
    start_torrent,
    stop_torrent,
)

# --- Formatting helpers ---


def test_format_size() -> None:
    assert _format_size(0) == "Unknown"
    assert _format_size(500) == "500.0 B"
    assert _format_size(1024) == "1.0 KB"
    assert _format_size(1048576) == "1.0 MB"
    assert _format_size(1073741824) == "1.0 GB"


def test_format_speed() -> None:
    assert _format_speed(0) == "0 B/s"
    assert _format_speed(1024) == "1.0 KB/s"
    assert _format_speed(1048576) == "1.0 MB/s"


def test_format_eta() -> None:
    assert _format_eta(-1) == "Unknown"
    assert _format_eta(0) == "Done"
    assert _format_eta(30) == "30s"
    assert _format_eta(90) == "1m 30s"
    assert _format_eta(3661) == "1h 1m"


# --- list_torrents ---


async def test_list_torrents_formats() -> None:
    client = AsyncMock()
    client.list_torrents.return_value = [
        TorrentInfo(
            name="Test.Torrent",
            hash_string="abc123def456abc123def456abc123def456abcd",
            status="downloading",
            percent_done=0.75,
            rate_download=1048576,
            rate_upload=524288,
            total_size=1073741824,
            eta=3600,
            upload_ratio=1.5,
        ),
    ]

    result = await list_torrents(client)
    assert "Test.Torrent" in result
    assert "75.0%" in result
    assert "1.0 MB/s" in result
    assert "ETA: 1h 0m" in result
    assert "abc123def456" in result


async def test_list_torrents_empty() -> None:
    client = AsyncMock()
    client.list_torrents.return_value = []

    result = await list_torrents(client)
    assert "No torrents found" in result


async def test_list_torrents_with_error() -> None:
    client = AsyncMock()
    client.list_torrents.return_value = [
        TorrentInfo(
            name="Bad.Torrent",
            hash_string="abc123",
            status="stopped",
            percent_done=0.0,
            rate_download=0,
            rate_upload=0,
            total_size=100,
            eta=-1,
            upload_ratio=0.0,
            error=3,
            error_string="Tracker error",
        ),
    ]

    result = await list_torrents(client)
    assert "Tracker error" in result


# --- get_torrent ---


async def test_get_torrent_formats() -> None:
    client = AsyncMock()
    client.get_torrent.return_value = TorrentDetail(
        name="Detailed.Torrent",
        hash_string="fullhash123",
        status="seeding",
        percent_done=1.0,
        rate_download=0,
        rate_upload=524288,
        total_size=1073741824,
        eta=0,
        upload_ratio=2.5,
        download_dir="/downloads",
        peers_connected=5,
        files=[FileInfo(name="file.mkv", length=1073741824, bytes_completed=1073741824)],
        trackers=[TrackerInfo(announce="http://tracker.example.com", sitename="example")],
        magnet_link="magnet:?xt=urn:btih:fullhash123",
    )

    result = await get_torrent(client, "fullhash123")
    assert "Detailed.Torrent" in result
    assert "seeding" in result
    assert "100.0%" in result
    assert "file.mkv" in result
    assert "example" in result
    assert "magnet:" in result


async def test_get_torrent_not_found() -> None:
    client = AsyncMock()
    client.get_torrent.return_value = None

    result = await get_torrent(client, "missing")
    assert "not found" in result


# --- add_torrent ---


async def test_add_torrent_new() -> None:
    client = AsyncMock()
    client.add_torrent.return_value = TorrentInfo(
        name="New.Torrent",
        hash_string="newhash",
        status="download queue",
        percent_done=0.0,
        rate_download=0,
        rate_upload=0,
        total_size=0,
        eta=-1,
        upload_ratio=0.0,
    )

    result = await add_torrent(client, "magnet:?xt=urn:btih:newhash")
    assert "Torrent added" in result
    assert "New.Torrent" in result


async def test_add_torrent_duplicate() -> None:
    client = AsyncMock()
    client.add_torrent.return_value = TorrentInfo(
        name="[duplicate] Existing.Torrent",
        hash_string="existhash",
        status="downloading",
        percent_done=0.5,
        rate_download=0,
        rate_upload=0,
        total_size=0,
        eta=-1,
        upload_ratio=0.0,
    )

    result = await add_torrent(client, "magnet:?xt=urn:btih:existhash")
    assert "already exists" in result


# --- start/stop/remove ---


async def test_start_torrent() -> None:
    client = AsyncMock()
    client.start_torrent.return_value = "My.Torrent"

    result = await start_torrent(client, "1")
    assert "Started" in result
    assert "My.Torrent" in result


async def test_stop_torrent() -> None:
    client = AsyncMock()
    client.stop_torrent.return_value = "My.Torrent"

    result = await stop_torrent(client, "1")
    assert "Stopped" in result


async def test_remove_torrent_keep_files() -> None:
    client = AsyncMock()
    client.remove_torrent.return_value = "My.Torrent"

    result = await remove_torrent(client, "1")
    assert "Removed" in result
    assert "files kept" in result


async def test_remove_torrent_delete_files() -> None:
    client = AsyncMock()
    client.remove_torrent.return_value = "My.Torrent"

    result = await remove_torrent(client, "1", delete_data=True)
    assert "files deleted" in result


# --- get_session_stats ---


async def test_get_session_stats() -> None:
    client = AsyncMock()
    client.get_session_stats.return_value = SessionStats(
        active_torrent_count=2,
        paused_torrent_count=1,
        torrent_count=3,
        download_speed=5242880,
        upload_speed=1048576,
        cumulative_stats=CumulativeStats(
            uploaded_bytes=10737418240,
            downloaded_bytes=21474836480,
            files_added=42,
            seconds_active=86400,
        ),
        free_space_bytes=107374182400,
        download_dir="/downloads",
    )

    result = await get_session_stats(client)
    assert "2 active" in result
    assert "3 total" in result
    assert "5.0 MB/s" in result
    assert "42" in result
    assert "100.0 GB" in result  # free space
    assert "/downloads" in result
