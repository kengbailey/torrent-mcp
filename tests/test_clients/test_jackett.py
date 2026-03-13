"""Tests for the Jackett Torznab client."""

import httpx
import pytest

from tests.conftest import (
    SAMPLE_SEARCH_ITEM_XML,
    MockTransport,
    make_jackett_xml,
)
from torrent_mcp.clients.jackett import JackettClient, _ensure_list, _safe_int
from torrent_mcp.exceptions import JackettError

# --- Helper functions ---


def test_ensure_list_none() -> None:
    assert _ensure_list(None) == []


def test_ensure_list_dict() -> None:
    result = _ensure_list({"key": "value"})
    assert result == [{"key": "value"}]


def test_ensure_list_list() -> None:
    result = _ensure_list([{"a": 1}, {"b": 2}])
    assert len(result) == 2


def test_ensure_list_other() -> None:
    assert _ensure_list("string") == []


def test_safe_int_valid() -> None:
    assert _safe_int("42") == 42
    assert _safe_int(10) == 10


def test_safe_int_invalid() -> None:
    assert _safe_int("not_a_number") == 0
    assert _safe_int(None) == 0
    assert _safe_int(None, default=-1) == -1


# --- Search ---


async def test_search(
    mock_transport: MockTransport, jackett_client: JackettClient
) -> None:
    mock_transport.add_response(make_jackett_xml(items_xml=SAMPLE_SEARCH_ITEM_XML))

    results = await jackett_client.search("test movie")
    assert len(results) == 1
    r = results[0]
    assert r.title == "Test.Movie.2024.1080p"
    assert r.seeders == 50
    assert r.leechers == 10
    assert r.size == 2147483648
    assert r.magnet_url == "magnet:?xt=urn:btih:deadbeef"
    assert r.category == "Movies"


async def test_search_empty(
    mock_transport: MockTransport, jackett_client: JackettClient
) -> None:
    mock_transport.add_response(make_jackett_xml())

    results = await jackett_client.search("nonexistent")
    assert results == []


async def test_search_multiple_items(
    mock_transport: MockTransport, jackett_client: JackettClient
) -> None:
    two_items = SAMPLE_SEARCH_ITEM_XML + """
    <item>
      <title>Another.Movie.2024</title>
      <size>1073741824</size>
      <torznab:attr name="seeders" value="20"/>
      <torznab:attr name="peers" value="5"/>
    </item>
    """
    mock_transport.add_response(make_jackett_xml(items_xml=two_items))

    results = await jackett_client.search("movie", limit=25)
    assert len(results) == 2
    assert results[1].title == "Another.Movie.2024"


async def test_search_respects_limit(
    mock_transport: MockTransport, jackett_client: JackettClient
) -> None:
    two_items = SAMPLE_SEARCH_ITEM_XML + """
    <item>
      <title>Another.Movie</title>
      <torznab:attr name="seeders" value="5"/>
    </item>
    """
    mock_transport.add_response(make_jackett_xml(items_xml=two_items))

    results = await jackett_client.search("movie", limit=1)
    assert len(results) == 1


# --- Error handling ---


async def test_search_connection_error(mock_transport: MockTransport) -> None:
    class FailTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("refused")

    http = httpx.AsyncClient(transport=FailTransport())
    client = JackettClient(http, "http://localhost:9117", "key")

    with pytest.raises(JackettError, match="Cannot connect"):
        await client.search("test")


async def test_search_auth_failure(
    mock_transport: MockTransport, jackett_client: JackettClient
) -> None:
    mock_transport.add_response(httpx.Response(401))

    with pytest.raises(JackettError, match="invalid API key"):
        await jackett_client.search("test")


async def test_search_http_error(
    mock_transport: MockTransport, jackett_client: JackettClient
) -> None:
    mock_transport.add_response(httpx.Response(500))

    with pytest.raises(JackettError, match="HTTP 500"):
        await jackett_client.search("test")


async def test_search_invalid_xml(
    mock_transport: MockTransport, jackett_client: JackettClient
) -> None:
    mock_transport.add_response(httpx.Response(200, text="not xml at all <<<"))

    with pytest.raises(JackettError, match="parse"):
        await jackett_client.search("test")


# --- list_indexers ---


async def test_list_indexers(
    mock_transport: MockTransport, jackett_client: JackettClient
) -> None:
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<indexers>"
        '<indexer id="test1" configured="true">'
        "<title>Test Indexer 1</title>"
        "</indexer>"
        '<indexer id="test2" configured="true">'
        "<title>Test Indexer 2</title>"
        "</indexer>"
        "</indexers>"
    )
    mock_transport.add_response(httpx.Response(200, text=xml))

    indexers = await jackett_client.list_indexers()
    assert len(indexers) == 2
    assert indexers[0].id == "test1"
    assert indexers[1].id == "test2"


async def test_list_indexers_empty(
    mock_transport: MockTransport, jackett_client: JackettClient
) -> None:
    xml = '<?xml version="1.0" encoding="UTF-8"?><indexers></indexers>'
    mock_transport.add_response(httpx.Response(200, text=xml))

    indexers = await jackett_client.list_indexers()
    assert indexers == []
