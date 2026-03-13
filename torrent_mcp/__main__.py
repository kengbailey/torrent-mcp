"""Entry point for python -m torrent_mcp."""

from torrent_mcp.config import Settings
from torrent_mcp.logging import configure_logging
from torrent_mcp.server import mcp


def main() -> None:
    settings = Settings()  # type: ignore[call-arg]
    configure_logging(log_level=settings.log_level, json_output=settings.log_json)
    mcp.run(transport="streamable-http", host=settings.mcp_host, port=settings.mcp_port)


if __name__ == "__main__":
    main()
