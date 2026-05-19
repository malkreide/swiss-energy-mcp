# Multi-stage build for the Swiss Energy MCP server (HTTP transport).
FROM python:3.12-slim AS builder

WORKDIR /build
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir --prefix=/install .

FROM python:3.12-slim AS runtime

# Run as a non-root user (SEC-007).
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin appuser

COPY --from=builder /install /usr/local

# 0.0.0.0 binding is intentional and confined to the container (SEC-016).
ENV SWISS_ENERGY_TRANSPORT=http \
    SWISS_ENERGY_HOST=0.0.0.0 \
    SWISS_ENERGY_PORT=8000 \
    PYTHONUNBUFFERED=1

EXPOSE 8000
USER appuser

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import socket,os; s=socket.create_connection(('127.0.0.1', int(os.environ['SWISS_ENERGY_PORT'])), 3); s.close()"

CMD ["swiss-energy-mcp"]
