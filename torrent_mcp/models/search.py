"""Pydantic models for Prowlarr search data."""

from pydantic import BaseModel


class SearchResult(BaseModel):
    """A single torrent search result from Prowlarr."""

    title: str
    size: int = 0
    seeders: int = 0
    leechers: int = 0
    download_url: str = ""
    magnet_url: str = ""
    category: str = ""
    publish_date: str = ""
    indexer: str = ""


class IndexerInfo(BaseModel):
    """A configured Prowlarr indexer."""

    name: str
    id: int
    enabled: bool = True
