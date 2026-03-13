"""Environment-based configuration using pydantic-settings."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = {"env_prefix": ""}

    # Transmission
    transmission_url: str = "http://localhost:9091/transmission/rpc"
    transmission_username: str | None = None
    transmission_password: str | None = None

    # Jackett
    jackett_url: str = "http://localhost:9117"
    jackett_api_key: str

    # MCP Server
    mcp_host: str = "0.0.0.0"
    mcp_port: int = 8000

    # Logging
    log_level: str = "INFO"
    log_json: bool = False

    # HTTP
    http_timeout: float = 30.0
