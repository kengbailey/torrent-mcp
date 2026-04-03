"""Tests for search tool formatting."""

from unittest.mock import AsyncMock

from torrent_mcp.models.search import IndexerInfo, SearchResult
from torrent_mcp.tools.search import (
    _cache_get,
    _hash_id,
    _result_cache_raw,
    list_indexers,
    search_torrents,
)


async def test_search_torrents_shows_hash_ids() -> None:
    client = AsyncMock()
    client.search.return_value = [
        SearchResult(
            title="Test.Movie.2024.1080p",
            size=2147483648,
            seeders=50,
            leechers=10,
            download_url="http://prowlarr:9696/1/download?link=abc",
            category="Movies",
            indexer="1337x",
        ),
    ]

    result = await search_torrents(client, "test movie")
    hid = _hash_id("http://prowlarr:9696/1/download?link=abc")
    assert f"[{hid}]" in result
    assert "[1337x]" in result
    assert "Test.Movie.2024.1080p" in result
    assert "Seeders: 50" in result
    assert "Movies" in result
    # No URLs in output
    assert "http://" not in result
    assert "Link:" not in result


async def test_search_torrents_populates_cache() -> None:
    _result_cache_raw.clear()
    client = AsyncMock()
    url = "http://prowlarr:9696/1/download?link=xyz"
    client.search.return_value = [
        SearchResult(
            title="Cached.Torrent",
            download_url=url,
            indexer="1337x",
            seeders=10,
        ),
    ]

    await search_torrents(client, "test")
    hid = _hash_id(url)
    cached = _cache_get(hid)
    assert cached is not None
    assert cached.title == "Cached.Torrent"


async def test_search_torrents_no_results() -> None:
    client = AsyncMock()
    client.search.return_value = []

    result = await search_torrents(client, "nothing")
    assert "No results found" in result


async def test_search_torrents_multi_indexer() -> None:
    """Results from multiple indexers show source."""
    client = AsyncMock()
    client.search.return_value = [
        SearchResult(
            title="Movie A",
            indexer="1337x",
            seeders=50,
            download_url="http://prowlarr:9696/1/download?link=a",
        ),
        SearchResult(
            title="Movie B",
            indexer="YTS",
            seeders=20,
            download_url="http://prowlarr:9696/2/download?link=b",
        ),
    ]

    result = await search_torrents(client, "movie")
    assert "[1337x]" in result
    assert "[YTS]" in result


async def test_hash_id_deterministic() -> None:
    """Same URL always produces same hash ID."""
    url = "http://prowlarr:9696/1/download?link=test123"
    assert _hash_id(url) == _hash_id(url)
    assert len(_hash_id(url)) == 5


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
