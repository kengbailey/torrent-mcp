"""Tests for the Transmission JSON-RPC client."""


import httpx
import pytest

from tests.conftest import SAMPLE_TORRENT, MockTransport, make_transmission_response
from torrent_mcp.clients.transmission import TransmissionClient, _parse_ids
from torrent_mcp.exceptions import TransmissionError

# --- _parse_ids ---


def test_parse_ids_integer() -> None:
    assert _parse_ids("42") == [42]


def test_parse_ids_hash() -> None:
    assert _parse_ids("abc123def") == ["abc123def"]


# --- 409 Session ID retry ---


async def test_rpc_409_retry(
    mock_transport: MockTransport, transmission_client: TransmissionClient
) -> None:
    """First call returns 409 with session id, retry succeeds."""
    session_id = "test-session-id-xyz"
    mock_transport.add_response(
        httpx.Response(409, headers={"X-Transmission-Session-Id": session_id})
    )
    mock_transport.add_response(
        make_transmission_response(arguments={"torrents": []})
    )

    result = await transmission_client.list_torrents()
    assert result == []
    assert len(mock_transport.requests) == 2
    # Second request should include the session id header
    assert mock_transport.requests[1].headers["X-Transmission-Session-Id"] == session_id


async def test_rpc_connection_error(mock_transport: MockTransport) -> None:
    """ConnectError raises TransmissionError."""

    class FailTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("refused")

    http = httpx.AsyncClient(transport=FailTransport())
    client = TransmissionClient(http, "http://localhost:9091/transmission/rpc")

    with pytest.raises(TransmissionError, match="Cannot connect"):
        await client.list_torrents()


async def test_rpc_error_result(
    mock_transport: MockTransport, transmission_client: TransmissionClient
) -> None:
    """Non-success result raises TransmissionError."""
    mock_transport.add_response(make_transmission_response(result="no such torrent"))

    with pytest.raises(TransmissionError, match="no such torrent"):
        await transmission_client._rpc("torrent-get")


async def test_rpc_http_error(
    mock_transport: MockTransport, transmission_client: TransmissionClient
) -> None:
    """Non-200/409 status raises TransmissionError."""
    mock_transport.add_response(httpx.Response(500))

    with pytest.raises(TransmissionError, match="HTTP 500"):
        await transmission_client._rpc("torrent-get")


# --- list_torrents ---


async def test_list_torrents(
    mock_transport: MockTransport, transmission_client: TransmissionClient
) -> None:
    mock_transport.add_response(
        make_transmission_response(arguments={"torrents": [SAMPLE_TORRENT]})
    )

    result = await transmission_client.list_torrents()
    assert len(result) == 1
    assert result[0].name == "Test.Torrent"
    assert result[0].status == "downloading"
    assert result[0].percent_done == 0.75


async def test_list_torrents_empty(
    mock_transport: MockTransport, transmission_client: TransmissionClient
) -> None:
    mock_transport.add_response(
        make_transmission_response(arguments={"torrents": []})
    )

    result = await transmission_client.list_torrents()
    assert result == []


async def test_list_torrents_status_filter(
    mock_transport: MockTransport, transmission_client: TransmissionClient
) -> None:
    stopped_torrent = {**SAMPLE_TORRENT, "status": 0, "name": "Stopped.Torrent"}
    mock_transport.add_response(
        make_transmission_response(
            arguments={"torrents": [SAMPLE_TORRENT, stopped_torrent]}
        )
    )

    result = await transmission_client.list_torrents(status_filter="stopped")
    assert len(result) == 1
    assert result[0].name == "Stopped.Torrent"


# --- get_torrent ---


async def test_get_torrent(
    mock_transport: MockTransport, transmission_client: TransmissionClient
) -> None:
    mock_transport.add_response(
        make_transmission_response(arguments={"torrents": [SAMPLE_TORRENT]})
    )

    result = await transmission_client.get_torrent("abc123def456abc123def456abc123def456abcd")
    assert result is not None
    assert result.name == "Test.Torrent"
    assert len(result.files) == 1
    assert result.files[0].name == "movie.mkv"
    assert len(result.trackers) == 1
    assert result.labels == ["movies"]
    assert result.download_dir == "/downloads"


async def test_get_torrent_not_found(
    mock_transport: MockTransport, transmission_client: TransmissionClient
) -> None:
    mock_transport.add_response(
        make_transmission_response(arguments={"torrents": []})
    )

    result = await transmission_client.get_torrent("nonexistent")
    assert result is None


# --- add_torrent ---


async def test_add_torrent(
    mock_transport: MockTransport, transmission_client: TransmissionClient
) -> None:
    mock_transport.add_response(
        make_transmission_response(
            arguments={
                "torrent-added": {
                    "name": "New.Torrent",
                    "hashString": "newhash123",
                    "id": 5,
                }
            }
        )
    )

    result = await transmission_client.add_torrent("magnet:?xt=urn:btih:newhash123")
    assert result.name == "New.Torrent"
    assert result.hash_string == "newhash123"


async def test_add_torrent_duplicate(
    mock_transport: MockTransport, transmission_client: TransmissionClient
) -> None:
    mock_transport.add_response(
        make_transmission_response(
            arguments={
                "torrent-duplicate": {
                    "name": "Existing.Torrent",
                    "hashString": "existhash",
                    "id": 3,
                }
            }
        )
    )

    result = await transmission_client.add_torrent("magnet:?xt=urn:btih:existhash")
    assert result.name.startswith("[duplicate] ")
    assert "Existing.Torrent" in result.name


async def test_add_torrent_metainfo(
    mock_transport: MockTransport, transmission_client: TransmissionClient
) -> None:
    """When torrent_data is provided, use metainfo instead of filename."""
    mock_transport.add_response(
        make_transmission_response(
            arguments={
                "torrent-added": {
                    "name": "File.Torrent",
                    "hashString": "filehash123",
                    "id": 7,
                }
            }
        )
    )

    torrent_bytes = b"fake torrent file content"
    result = await transmission_client.add_torrent(
        "", torrent_data=torrent_bytes
    )
    assert result.name == "File.Torrent"

    # Verify metainfo was sent, not filename
    import json

    request = mock_transport.requests[0]
    body = json.loads(request.content)
    assert "metainfo" in body["arguments"]
    assert "filename" not in body["arguments"]


# --- start/stop/remove ---


async def test_start_torrent(
    mock_transport: MockTransport, transmission_client: TransmissionClient
) -> None:
    # get_torrent call
    mock_transport.add_response(
        make_transmission_response(arguments={"torrents": [SAMPLE_TORRENT]})
    )
    # start call
    mock_transport.add_response(make_transmission_response())

    name = await transmission_client.start_torrent("1")
    assert name == "Test.Torrent"


async def test_stop_torrent(
    mock_transport: MockTransport, transmission_client: TransmissionClient
) -> None:
    mock_transport.add_response(
        make_transmission_response(arguments={"torrents": [SAMPLE_TORRENT]})
    )
    mock_transport.add_response(make_transmission_response())

    name = await transmission_client.stop_torrent("1")
    assert name == "Test.Torrent"


async def test_remove_torrent(
    mock_transport: MockTransport, transmission_client: TransmissionClient
) -> None:
    mock_transport.add_response(
        make_transmission_response(arguments={"torrents": [SAMPLE_TORRENT]})
    )
    mock_transport.add_response(make_transmission_response())

    name = await transmission_client.remove_torrent("1", delete_data=True)
    assert name == "Test.Torrent"


# --- get_session_stats ---


async def test_get_session_stats(
    mock_transport: MockTransport, transmission_client: TransmissionClient
) -> None:
    # session-stats
    mock_transport.add_response(
        make_transmission_response(
            arguments={
                "activeTorrentCount": 2,
                "pausedTorrentCount": 1,
                "torrentCount": 3,
                "downloadSpeed": 5242880,
                "uploadSpeed": 1048576,
                "cumulative-stats": {
                    "uploadedBytes": 10737418240,
                    "downloadedBytes": 21474836480,
                    "filesAdded": 42,
                    "secondsActive": 86400,
                },
            }
        )
    )
    # session-get
    mock_transport.add_response(
        make_transmission_response(arguments={"download-dir": "/downloads"})
    )
    # free-space
    mock_transport.add_response(
        make_transmission_response(arguments={"size-bytes": 107374182400})
    )

    stats = await transmission_client.get_session_stats()
    assert stats.active_torrent_count == 2
    assert stats.torrent_count == 3
    assert stats.download_speed == 5242880
    assert stats.cumulative_stats.files_added == 42
    assert stats.free_space_bytes == 107374182400
    assert stats.download_dir == "/downloads"
