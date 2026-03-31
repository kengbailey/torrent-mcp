FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml .
COPY torrent_mcp/ torrent_mcp/
RUN pip install --no-cache-dir .

CMD ["python", "-m", "torrent_mcp"]
