"""Tests for the Prowlarr REST API client."""

import httpx
import pytest

from tests.conftest import MockTransport
from torrent_mcp.clients.prowlarr import ProwlarrClient
from torrent_mcp.exceptions import ProwlarrError

SAMPLE_SEARCH_RESPONSE = [
    {
        "title": "Test.Movie.2024.1080p",
        "size": 2147483648,
        "seeders": 50,
        "leechers": 10,
        "downloadUrl": "http://prowlarr:9696/1/download?link=abc",
        "magnetUrl": "magnet:?xt=urn:btih:deadbeef",
        "categories": [{"id": 2000, "name": "Movies", "subCategories": []}],
        "publishDate": "2024-01-01T00:00:00Z",
        "indexer": "1337x",
        "indexerId": 1,
    },
    {
        "title": "Another.Movie.2024",
        "size": 1073741824,
        "seeders": 20,
        "leechers": 5,
        "downloadUrl": "http://prowlarr:9696/2/download?link=def",
        "categories": [{"id": 2040, "name": "Movies/HD", "subCategories": []}],
        "publishDate": "2024-02-01T00:00:00Z",
        "indexer": "YTS",
        "indexerId": 2,
    },
]

SAMPLE_INDEXER_RESPONSE = [
    {"id": 1, "name": "1337x", "enable": True, "protocol": "torrent"},
    {"id": 2, "name": "YTS", "enable": True, "protocol": "torrent"},
    {"id": 3, "name": "Disabled Indexer", "enable": False, "protocol": "torrent"},
]


@pytest.fixture
def prowlarr_client(mock_transport: MockTransport) -> ProwlarrClient:
    http = httpx.AsyncClient(
        transport=mock_transport, base_url="http://localhost:9696"
    )
    return ProwlarrClient(http, "test-api-key")


# --- Search ---


async def test_search(
    mock_transport: MockTransport, prowlarr_client: ProwlarrClient
) -> None:
    mock_transport.add_response(httpx.Response(200, json=SAMPLE_SEARCH_RESPONSE))

    results = await prowlarr_client.search("test movie")
    assert len(results) == 2

    r = results[0]
    assert r.title == "Test.Movie.2024.1080p"
    assert r.seeders == 50
    assert r.leechers == 10
    assert r.size == 2147483648
    assert r.magnet_url == "magnet:?xt=urn:btih:deadbeef"
    assert r.download_url == "http://prowlarr:9696/1/download?link=abc"
    assert r.category == "Movies"
    assert r.indexer == "1337x"


async def test_search_includes_indexer_per_result(
    mock_transport: MockTransport, prowlarr_client: ProwlarrClient
) -> None:
    mock_transport.add_response(httpx.Response(200, json=SAMPLE_SEARCH_RESPONSE))

    results = await prowlarr_client.search("movie")
    assert results[0].indexer == "1337x"
    assert results[1].indexer == "YTS"


async def test_search_empty(
    mock_transport: MockTransport, prowlarr_client: ProwlarrClient
) -> None:
    mock_transport.add_response(httpx.Response(200, json=[]))

    results = await prowlarr_client.search("nonexistent")
    assert results == []


async def test_search_respects_limit(
    mock_transport: MockTransport, prowlarr_client: ProwlarrClient
) -> None:
    mock_transport.add_response(httpx.Response(200, json=SAMPLE_SEARCH_RESPONSE))

    results = await prowlarr_client.search("movie", limit=1)
    assert len(results) == 1


async def test_search_result_without_magnet(
    mock_transport: MockTransport, prowlarr_client: ProwlarrClient
) -> None:
    """Results without magnetUrl should have empty magnet_url."""
    mock_transport.add_response(httpx.Response(200, json=[SAMPLE_SEARCH_RESPONSE[1]]))

    results = await prowlarr_client.search("movie")
    assert results[0].magnet_url == ""
    assert results[0].download_url != ""


async def test_search_sends_api_key_header(
    mock_transport: MockTransport, prowlarr_client: ProwlarrClient
) -> None:
    mock_transport.add_response(httpx.Response(200, json=[]))

    await prowlarr_client.search("test")
    request = mock_transport.requests[0]
    assert request.headers["X-Api-Key"] == "test-api-key"


# --- Error handling ---


async def test_search_connection_error() -> None:
    class FailTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("refused")

    http = httpx.AsyncClient(transport=FailTransport(), base_url="http://localhost:9696")
    client = ProwlarrClient(http, "key")

    with pytest.raises(ProwlarrError, match="Cannot connect"):
        await client.search("test")


async def test_search_auth_failure(
    mock_transport: MockTransport, prowlarr_client: ProwlarrClient
) -> None:
    mock_transport.add_response(httpx.Response(401))

    with pytest.raises(ProwlarrError, match="invalid API key"):
        await prowlarr_client.search("test")


async def test_search_http_error(
    mock_transport: MockTransport, prowlarr_client: ProwlarrClient
) -> None:
    mock_transport.add_response(httpx.Response(500))

    with pytest.raises(ProwlarrError, match="HTTP 500"):
        await prowlarr_client.search("test")


# --- list_indexers ---


async def test_list_indexers(
    mock_transport: MockTransport, prowlarr_client: ProwlarrClient
) -> None:
    mock_transport.add_response(httpx.Response(200, json=SAMPLE_INDEXER_RESPONSE))

    indexers = await prowlarr_client.list_indexers()
    assert len(indexers) == 3
    assert indexers[0].name == "1337x"
    assert indexers[0].id == 1
    assert indexers[0].enabled is True
    assert indexers[2].name == "Disabled Indexer"
    assert indexers[2].enabled is False


async def test_list_indexers_empty(
    mock_transport: MockTransport, prowlarr_client: ProwlarrClient
) -> None:
    mock_transport.add_response(httpx.Response(200, json=[]))

    indexers = await prowlarr_client.list_indexers()
    assert indexers == []


async def test_list_indexers_sends_api_key(
    mock_transport: MockTransport, prowlarr_client: ProwlarrClient
) -> None:
    mock_transport.add_response(httpx.Response(200, json=[]))

    await prowlarr_client.list_indexers()
    request = mock_transport.requests[0]
    assert request.headers["X-Api-Key"] == "test-api-key"
