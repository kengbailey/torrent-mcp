"""Tests for search tool formatting."""

from unittest.mock import AsyncMock

from torrent_mcp.models.search import IndexerInfo, SearchResult
from torrent_mcp.tools.search import list_indexers, search_torrents


async def test_search_torrents_formats_results() -> None:
    client = AsyncMock()
    client.search.return_value = [
        SearchResult(
            title="Test.Movie.2024.1080p",
            size=2147483648,
            seeders=50,
            leechers=10,
            magnet_url="magnet:?xt=urn:btih:deadbeef",
            category="Movies",
            indexer="1337x",
        ),
    ]

    result = await search_torrents(client, "test movie")
    assert "Test.Movie.2024.1080p" in result
    assert "[1337x]" in result
    assert "Seeders: 50" in result
    assert "Leechers: 10" in result
    assert "magnet:?xt=urn:btih:deadbeef" in result
    assert "Movies" in result


async def test_search_torrents_no_results() -> None:
    client = AsyncMock()
    client.search.return_value = []

    result = await search_torrents(client, "nothing")
    assert "No results found" in result


async def test_search_torrents_download_url_fallback() -> None:
    """When no magnet_url, should show download_url instead."""
    client = AsyncMock()
    client.search.return_value = [
        SearchResult(
            title="Test",
            download_url="http://prowlarr:9696/1/download?link=abc",
            indexer="1337x",
        ),
    ]

    result = await search_torrents(client, "test")
    assert "http://prowlarr:9696/1/download?link=abc" in result


async def test_search_torrents_multi_indexer() -> None:
    """Results from multiple indexers show source."""
    client = AsyncMock()
    client.search.return_value = [
        SearchResult(title="Movie A", indexer="1337x", seeders=50),
        SearchResult(title="Movie B", indexer="YTS", seeders=20),
    ]

    result = await search_torrents(client, "movie")
    assert "[1337x]" in result
    assert "[YTS]" in result


async def test_list_indexers_formats() -> None:
    client = AsyncMock()
    client.list_indexers.return_value = [
        IndexerInfo(name="Indexer One", id=1, enabled=True),
        IndexerInfo(name="Indexer Two", id=2, enabled=False),
    ]

    result = await list_indexers(client)
    assert "Indexer One" in result
    assert "enabled" in result
    assert "disabled" in result
    assert "Configured Indexers (2)" in result


async def test_list_indexers_empty() -> None:
    client = AsyncMock()
    client.list_indexers.return_value = []

    result = await list_indexers(client)
    assert "No configured indexers" in result
