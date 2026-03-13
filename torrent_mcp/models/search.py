"""Pydantic models for Jackett search data."""

from pydantic import BaseModel


class SearchResult(BaseModel):
    """A single torrent search result from Jackett."""

    title: str
    size: int = 0
    seeders: int = 0
    leechers: int = 0
    magnet_url: str = ""
    link: str = ""
    category: str = ""
    publish_date: str = ""


class IndexerInfo(BaseModel):
    """A configured Jackett indexer."""

    name: str
    id: str
    configured: bool = True
