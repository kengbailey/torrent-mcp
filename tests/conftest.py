"""Shared test fixtures."""

from typing import Any

import httpx
import pytest

from torrent_mcp.clients.jackett import JackettClient
from torrent_mcp.clients.transmission import TransmissionClient


def make_transmission_response(
    result: str = "success",
    arguments: dict[str, Any] | None = None,
) -> httpx.Response:
    """Build a mock Transmission JSON-RPC response."""

    body = {"result": result, "arguments": arguments or {}}
    return httpx.Response(200, json=body)


def make_jackett_xml(items_xml: str = "", channel_extra: str = "") -> httpx.Response:
    """Build a mock Jackett Torznab XML response."""
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<rss><channel>"
        f"{channel_extra}{items_xml}"
        "</channel></rss>"
    )
    return httpx.Response(200, text=xml)


SAMPLE_TORRENT: dict[str, Any] = {
    "name": "Test.Torrent",
    "hashString": "abc123def456abc123def456abc123def456abcd",
    "status": 4,
    "percentDone": 0.75,
    "rateDownload": 1048576,
    "rateUpload": 524288,
    "totalSize": 1073741824,
    "eta": 3600,
    "uploadRatio": 1.5,
    "error": 0,
    "errorString": "",
    "downloadDir": "/downloads",
    "addedDate": 1700000000,
    "doneDate": 0,
    "peersConnected": 12,
    "labels": ["movies"],
    "magnetLink": "magnet:?xt=urn:btih:abc123",
    "files": [
        {"name": "movie.mkv", "length": 1073741824, "bytesCompleted": 805306368},
    ],
    "trackers": [
        {"announce": "http://tracker.example.com/announce", "sitename": "example"},
    ],
}

SAMPLE_SEARCH_ITEM_XML = """
<item>
  <title>Test.Movie.2024.1080p</title>
  <link>http://example.com/dl/123</link>
  <size>2147483648</size>
  <category>Movies</category>
  <pubDate>Mon, 01 Jan 2024 00:00:00 +0000</pubDate>
  <torznab:attr name="seeders" value="50"/>
  <torznab:attr name="peers" value="10"/>
  <torznab:attr name="size" value="2147483648"/>
  <torznab:attr name="magneturl" value="magnet:?xt=urn:btih:deadbeef"/>
</item>
"""


class MockTransport(httpx.AsyncBaseTransport):
    """Mock transport that returns pre-configured responses."""

    def __init__(self) -> None:
        self.responses: list[httpx.Response] = []
        self.requests: list[httpx.Request] = []

    def add_response(self, response: httpx.Response) -> None:
        self.responses.append(response)

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if not self.responses:
            raise RuntimeError("No mock responses configured")
        return self.responses.pop(0)


@pytest.fixture
def mock_transport() -> MockTransport:
    return MockTransport()


@pytest.fixture
def transmission_client(mock_transport: MockTransport) -> TransmissionClient:
    http = httpx.AsyncClient(transport=mock_transport)
    return TransmissionClient(http, "http://localhost:9091/transmission/rpc")


@pytest.fixture
def jackett_client(mock_transport: MockTransport) -> JackettClient:
    http = httpx.AsyncClient(transport=mock_transport)
    return JackettClient(http, "http://localhost:9117", "test-api-key")
