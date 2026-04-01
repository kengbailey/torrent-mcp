"""Environment-based configuration using pydantic-settings."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = {"env_prefix": ""}

    # Backend selection: "transmission" or "qbittorrent"
    torrent_backend: str = "transmission"

    # Transmission
    transmission_url: str = "http://localhost:9091/transmission/rpc"
    transmission_username: str | None = None
    transmission_password: str | None = None

    # qBittorrent
    qbittorrent_url: str = "http://localhost:8080"
    qbittorrent_username: str = "admin"
    qbittorrent_password: str = "adminadmin"

    # Prowlarr
    prowlarr_url: str = "http://localhost:9696"
    prowlarr_api_key: str

    # MCP Server
    mcp_host: str = "127.0.0.1"
    mcp_port: int = 8000

    # Logging
    log_level: str = "INFO"
    log_json: bool = False

    # HTTP
    http_timeout: float = 30.0
