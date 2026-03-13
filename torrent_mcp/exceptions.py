"""Custom exception hierarchy."""


class TorrentMCPError(Exception):
    """Base exception for all torrent-mcp errors."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class TransmissionError(TorrentMCPError):
    """Error from Transmission JSON-RPC."""


class JackettError(TorrentMCPError):
    """Error from Jackett Torznab API."""


class ConfigError(TorrentMCPError):
    """Invalid or missing configuration."""
