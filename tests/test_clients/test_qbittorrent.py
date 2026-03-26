"""Tests for the qBittorrent Web API v2 client."""

import httpx
import pytest

from tests.conftest import (
    SAMPLE_QB_TORRENT,
    MockTransport,
    make_qb_login_response,
)
from torrent_mcp.clients.qbittorrent import (
    QBittorrentClient,
    _map_state,
    _parse_magnet_hash,
    _to_torrent_info,
)
from torrent_mcp.exceptions import QBittorrentError

# --- _map_state ---


def test_map_state_downloading() -> None:
    assert _map_state("downloading") == "downloading"
    assert _map_state("stalledDL") == "downloading"
    assert _map_state("metaDL") == "downloading"


def test_map_state_seeding() -> None:
    assert _map_state("uploading") == "seeding"
    assert _map_state("stalledUP") == "seeding"
    assert _map_state("forcedUP") == "seeding"


def test_map_state_stopped() -> None:
    assert _map_state("stoppedDL") == "stopped"
    assert _map_state("stoppedUP") == "stopped"


def test_map_state_unknown() -> None:
    assert _map_state("some_weird_state") == "unknown"


# --- _parse_magnet_hash ---


def test_parse_magnet_hash_hex40() -> None:
    url = "magnet:?xt=urn:btih:abc123def456abc123def456abc123def456abcd&dn=Test"
    assert _parse_magnet_hash(url) == "abc123def456abc123def456abc123def456abcd"


def test_parse_magnet_hash_base32() -> None:
    url = "magnet:?xt=urn:btih:JBSWY3DPEHPK3PXPJZSFY3DPEHPK3PXP&dn=Test"
    result = _parse_magnet_hash(url)
    assert result is not None
    assert result == "jbswy3dpehpk3pxpjzsfy3dpehpk3pxp"


def test_parse_magnet_hash_no_match() -> None:
    assert _parse_magnet_hash("http://example.com/file.torrent") is None


# --- _to_torrent_info ---


def test_to_torrent_info() -> None:
    info = _to_torrent_info(SAMPLE_QB_TORRENT)
    assert info.name == "Test.Torrent"
    assert info.hash_string == "abc123def456abc123def456abc123def456abcd"
    assert info.status == "downloading"
    assert info.percent_done == 0.75
    assert info.rate_download == 1048576
    assert info.total_size == 1073741824
    assert info.eta == 3600
    assert info.upload_ratio == 1.5


def test_to_torrent_info_unknown_eta() -> None:
    t = {**SAMPLE_QB_TORRENT, "eta": 8640000}
    info = _to_torrent_info(t)
    assert info.eta == -1


# --- Authentication ---


async def test_login_success(
    mock_transport: MockTransport, qbittorrent_client: QBittorrentClient
) -> None:
    mock_transport.add_response(make_qb_login_response(success=True))
    mock_transport.add_response(httpx.Response(200, json=[]))

    result = await qbittorrent_client.list_torrents()
    assert result == []
    assert len(mock_transport.requests) == 2
    # First request is login
    assert b"username=admin" in mock_transport.requests[0].content


async def test_login_failure(mock_transport: MockTransport) -> None:
    mock_transport.add_response(make_qb_login_response(success=False))

    http = httpx.AsyncClient(transport=mock_transport, base_url="http://localhost:8080")
    client = QBittorrentClient(http, "admin", "wrongpass")

    with pytest.raises(QBittorrentError, match="invalid credentials"):
        await client.list_torrents()


async def test_login_ip_banned(mock_transport: MockTransport) -> None:
    mock_transport.add_response(httpx.Response(403, text="Your IP address has been banned"))

    http = httpx.AsyncClient(transport=mock_transport, base_url="http://localhost:8080")
    client = QBittorrentClient(http, "admin", "admin")

    with pytest.raises(QBittorrentError, match="banned"):
        await client.list_torrents()


async def test_403_session_retry(
    mock_transport: MockTransport, qbittorrent_client: QBittorrentClient
) -> None:
    """First call succeeds login, second call gets 403 (session expired), re-login and retry."""
    # Initial login
    mock_transport.add_response(make_qb_login_response())
    # First request returns 403 (session expired)
    mock_transport.add_response(httpx.Response(403))
    # Re-login
    mock_transport.add_response(make_qb_login_response())
    # Retry succeeds
    mock_transport.add_response(httpx.Response(200, json=[]))

    result = await qbittorrent_client.list_torrents()
    assert result == []
    assert len(mock_transport.requests) == 4


async def test_connection_error(mock_transport: MockTransport) -> None:
    class FailTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("refused")

    http = httpx.AsyncClient(transport=FailTransport(), base_url="http://localhost:8080")
    client = QBittorrentClient(http, "admin", "admin")

    with pytest.raises(QBittorrentError, match="Cannot connect"):
        await client.list_torrents()


# --- list_torrents ---


async def test_list_torrents(
    mock_transport: MockTransport, qbittorrent_client: QBittorrentClient
) -> None:
    mock_transport.add_response(make_qb_login_response())
    mock_transport.add_response(httpx.Response(200, json=[SAMPLE_QB_TORRENT]))

    result = await qbittorrent_client.list_torrents()
    assert len(result) == 1
    assert result[0].name == "Test.Torrent"
    assert result[0].status == "downloading"


async def test_list_torrents_empty(
    mock_transport: MockTransport, qbittorrent_client: QBittorrentClient
) -> None:
    mock_transport.add_response(make_qb_login_response())
    mock_transport.add_response(httpx.Response(200, json=[]))

    result = await qbittorrent_client.list_torrents()
    assert result == []


async def test_list_torrents_status_filter(
    mock_transport: MockTransport, qbittorrent_client: QBittorrentClient
) -> None:
    mock_transport.add_response(make_qb_login_response())
    mock_transport.add_response(httpx.Response(200, json=[]))

    await qbittorrent_client.list_torrents(status_filter="stopped")
    # Check that filter=paused was passed
    url = str(mock_transport.requests[1].url)
    assert "filter=paused" in url


# --- get_torrent ---


async def test_get_torrent(
    mock_transport: MockTransport, qbittorrent_client: QBittorrentClient
) -> None:
    mock_transport.add_response(make_qb_login_response())
    # torrents/info
    mock_transport.add_response(httpx.Response(200, json=[SAMPLE_QB_TORRENT]))
    # torrents/files
    mock_transport.add_response(
        httpx.Response(
            200,
            json=[{"name": "movie.mkv", "size": 1073741824, "progress": 0.75}],
        )
    )
    # torrents/trackers
    mock_transport.add_response(
        httpx.Response(
            200,
            json=[
                {"url": "http://tracker.example.com/announce", "status": 2},
                {"url": "** [DHT] **", "status": 2},
                {"url": "** [PeX] **", "status": 2},
            ],
        )
    )

    result = await qbittorrent_client.get_torrent("abc123def456abc123def456abc123def456abcd")
    assert result is not None
    assert result.name == "Test.Torrent"
    assert result.download_dir == "/downloads/"
    assert len(result.files) == 1
    assert result.files[0].name == "movie.mkv"
    assert result.files[0].bytes_completed == 805306368  # 0.75 * 1073741824
    # DHT and PeX filtered out
    assert len(result.trackers) == 1
    assert result.trackers[0].sitename == "tracker.example.com"
    # Tags parsed
    assert result.labels == ["movies", "linux"]


async def test_get_torrent_not_found(
    mock_transport: MockTransport, qbittorrent_client: QBittorrentClient
) -> None:
    mock_transport.add_response(make_qb_login_response())
    mock_transport.add_response(httpx.Response(200, json=[]))

    result = await qbittorrent_client.get_torrent("nonexistent")
    assert result is None


# --- add_torrent ---


async def test_add_torrent_new(
    mock_transport: MockTransport, qbittorrent_client: QBittorrentClient
) -> None:
    info_hash = "abc123def456abc123def456abc123def456abcd"
    magnet = f"magnet:?xt=urn:btih:{info_hash}&dn=New.Torrent"

    mock_transport.add_response(make_qb_login_response())
    # Duplicate check - empty
    mock_transport.add_response(httpx.Response(200, json=[]))
    # Add torrent
    mock_transport.add_response(httpx.Response(200, text="Ok."))
    # Fetch after add
    added = {**SAMPLE_QB_TORRENT, "name": "New.Torrent", "hash": info_hash}
    mock_transport.add_response(httpx.Response(200, json=[added]))

    result = await qbittorrent_client.add_torrent(magnet)
    assert result.name == "New.Torrent"
    assert result.hash_string == info_hash


async def test_add_torrent_duplicate(
    mock_transport: MockTransport, qbittorrent_client: QBittorrentClient
) -> None:
    info_hash = "abc123def456abc123def456abc123def456abcd"
    magnet = f"magnet:?xt=urn:btih:{info_hash}"

    mock_transport.add_response(make_qb_login_response())
    # Duplicate check - exists
    existing = {**SAMPLE_QB_TORRENT, "hash": info_hash}
    mock_transport.add_response(httpx.Response(200, json=[existing]))

    result = await qbittorrent_client.add_torrent(magnet)
    assert result.name.startswith("[duplicate] ")


async def test_add_torrent_failed(
    mock_transport: MockTransport, qbittorrent_client: QBittorrentClient
) -> None:
    info_hash = "abc123def456abc123def456abc123def456abcd"
    magnet = f"magnet:?xt=urn:btih:{info_hash}"

    mock_transport.add_response(make_qb_login_response())
    # Duplicate check - empty
    mock_transport.add_response(httpx.Response(200, json=[]))
    # Add fails
    mock_transport.add_response(httpx.Response(415, text="Torrent file is not valid."))

    with pytest.raises(QBittorrentError, match="Failed to add"):
        await qbittorrent_client.add_torrent(magnet)


# --- start/stop/remove ---


async def test_start_torrent(
    mock_transport: MockTransport, qbittorrent_client: QBittorrentClient
) -> None:
    mock_transport.add_response(make_qb_login_response())
    # Get name
    mock_transport.add_response(httpx.Response(200, json=[SAMPLE_QB_TORRENT]))
    # Start
    mock_transport.add_response(httpx.Response(200))

    result = await qbittorrent_client.start_torrent("abc123")
    assert result == "Test.Torrent"


async def test_stop_torrent(
    mock_transport: MockTransport, qbittorrent_client: QBittorrentClient
) -> None:
    mock_transport.add_response(make_qb_login_response())
    mock_transport.add_response(httpx.Response(200, json=[SAMPLE_QB_TORRENT]))
    mock_transport.add_response(httpx.Response(200))

    result = await qbittorrent_client.stop_torrent("abc123")
    assert result == "Test.Torrent"


async def test_remove_torrent(
    mock_transport: MockTransport, qbittorrent_client: QBittorrentClient
) -> None:
    mock_transport.add_response(make_qb_login_response())
    mock_transport.add_response(httpx.Response(200, json=[SAMPLE_QB_TORRENT]))
    mock_transport.add_response(httpx.Response(200))

    result = await qbittorrent_client.remove_torrent("abc123", delete_data=True)
    assert result == "Test.Torrent"
    # Check deleteFiles=true was sent
    body = mock_transport.requests[2].content.decode()
    assert "deleteFiles=true" in body


async def test_start_torrent_not_found(
    mock_transport: MockTransport, qbittorrent_client: QBittorrentClient
) -> None:
    mock_transport.add_response(make_qb_login_response())
    mock_transport.add_response(httpx.Response(200, json=[]))

    with pytest.raises(QBittorrentError, match="not found"):
        await qbittorrent_client.start_torrent("missing")


# --- get_session_stats ---


async def test_get_session_stats(
    mock_transport: MockTransport, qbittorrent_client: QBittorrentClient
) -> None:
    mock_transport.add_response(make_qb_login_response())
    # transfer/info
    mock_transport.add_response(
        httpx.Response(200, json={"dl_info_speed": 5242880, "up_info_speed": 1048576})
    )
    # sync/maindata
    mock_transport.add_response(
        httpx.Response(
            200,
            json={
                "server_state": {
                    "alltime_dl": 21474836480,
                    "alltime_ul": 10737418240,
                    "free_space_on_disk": 107374182400,
                }
            },
        )
    )
    # app/defaultSavePath
    mock_transport.add_response(httpx.Response(200, text="/downloads\n"))
    # torrents/info (for counting)
    stopped_torrent = {**SAMPLE_QB_TORRENT, "state": "stoppedUP"}
    mock_transport.add_response(
        httpx.Response(200, json=[SAMPLE_QB_TORRENT, stopped_torrent])
    )

    result = await qbittorrent_client.get_session_stats()
    assert result.torrent_count == 2
    assert result.active_torrent_count == 1
    assert result.paused_torrent_count == 1
    assert result.download_speed == 5242880
    assert result.upload_speed == 1048576
    assert result.free_space_bytes == 107374182400
    assert result.download_dir == "/downloads"
    assert result.cumulative_stats.downloaded_bytes == 21474836480
    assert result.cumulative_stats.uploaded_bytes == 10737418240
