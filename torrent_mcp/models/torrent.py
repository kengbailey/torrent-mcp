"""Pydantic models for Transmission torrent data."""

from pydantic import BaseModel


class TorrentInfo(BaseModel):
    """Essential torrent information for list views."""

    name: str
    hash_string: str
    status: str
    percent_done: float
    rate_download: int
    rate_upload: int
    total_size: int
    eta: int
    upload_ratio: float
    error: int = 0
    error_string: str = ""


class FileInfo(BaseModel):
    """Individual file within a torrent."""

    name: str
    length: int
    bytes_completed: int


class TrackerInfo(BaseModel):
    """Tracker associated with a torrent."""

    announce: str
    sitename: str


class TorrentDetail(BaseModel):
    """Detailed torrent information."""

    name: str
    hash_string: str
    status: str
    percent_done: float
    rate_download: int
    rate_upload: int
    total_size: int
    eta: int
    upload_ratio: float
    error: int = 0
    error_string: str = ""
    download_dir: str = ""
    added_date: int = 0
    done_date: int = 0
    peers_connected: int = 0
    labels: list[str] = []
    magnet_link: str = ""
    files: list[FileInfo] = []
    trackers: list[TrackerInfo] = []


class CumulativeStats(BaseModel):
    """Cumulative transfer statistics."""

    uploaded_bytes: int
    downloaded_bytes: int
    files_added: int
    seconds_active: int


class SessionStats(BaseModel):
    """Transmission session statistics."""

    active_torrent_count: int
    paused_torrent_count: int
    torrent_count: int
    download_speed: int
    upload_speed: int
    cumulative_stats: CumulativeStats
    free_space_bytes: int = 0
    download_dir: str = ""
