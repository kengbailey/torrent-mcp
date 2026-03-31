# torrent-mcp

MCP server for torrent search and management. Search via [Jackett](https://github.com/Jackett/Jackett) (Torznab API), manage downloads via [Transmission](https://transmissionbt.com/) or [qBittorrent](https://www.qbittorrent.org/).

Built with [FastMCP](https://gofastmcp.com) 3.x using streamable HTTP transport.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .
```

## Configuration

All configuration via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `TORRENT_BACKEND` | `transmission` | `transmission` or `qbittorrent` |
| `JACKETT_URL` | `http://localhost:9117` | Jackett base URL |
| `JACKETT_API_KEY` | *(required)* | Jackett API key |
| `TRANSMISSION_URL` | `http://localhost:9091/transmission/rpc` | Transmission RPC URL |
| `TRANSMISSION_USERNAME` | | Transmission username |
| `TRANSMISSION_PASSWORD` | | Transmission password |
| `QBITTORRENT_URL` | `http://localhost:8080` | qBittorrent WebUI URL |
| `QBITTORRENT_USERNAME` | `admin` | qBittorrent username |
| `QBITTORRENT_PASSWORD` | `adminadmin` | qBittorrent password |
| `MCP_HOST` | `127.0.0.1` | Server bind host |
| `MCP_PORT` | `8000` | Server bind port |

## Run

```bash
JACKETT_API_KEY=your-key TORRENT_BACKEND=qbittorrent python -m torrent_mcp
```

## MCP Tools

- `search_torrents` / `list_indexers` -- Jackett search
- `list_torrents` / `get_torrent` / `add_torrent` -- torrent management
- `start_torrent` / `stop_torrent` / `remove_torrent` -- torrent control
- `get_session_stats` -- transfer stats and disk space

## Tests

```bash
pip install -e ".[dev]"
pytest
```
