FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY torrent_mcp/ torrent_mcp/
RUN pip install --no-cache-dir .

CMD ["python", "-m", "torrent_mcp"]
