"""Swiss Energy MCP server.

MCP server for Swiss energy data from the Federal Office of Energy (SFOE/BFE),
served via the GeoAdmin REST API and opendata.swiss. All upstream APIs are
public and auth-free.

The module wires the pieces together: configuration (:mod:`settings`),
structured logging (:mod:`logging_config`), a shared HTTP client managed by a
FastMCP lifespan, and the tool / resource / prompt registrations.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP

from .api_client import AppContext, EnergyHTTPClient
from .logging_config import configure_logging, get_logger
from .resources import register_capabilities
from .settings import Settings
from .tools import register_tools

try:  # The supported MCP protocol version is pinned by the installed mcp SDK.
    from mcp.types import LATEST_PROTOCOL_VERSION as SUPPORTED_PROTOCOL_VERSION
except ImportError:  # pragma: no cover - defensive
    SUPPORTED_PROTOCOL_VERSION = "2025-06-18"

INSTRUCTIONS = (
    "Swiss Energy MCP – energy data from the Swiss Federal Office of Energy (BFE) "
    "via the GeoAdmin REST API and opendata.swiss. All tools are read-only and "
    "auth-free. Pass coordinates as WGS84 (lat/lon); conversion to LV95 is internal. "
    "Every search tool returns an EnergyResponse envelope with structured `results`, "
    "a Markdown `summary`, explicit `source`/`license`, and a `match_type` "
    "('exact' or 'none'). Use `energy_location_profile` to answer broad questions "
    "in a single call. Coordinate hints: Zürich lat=47.3769 lon=8.5417; "
    "Bern lat=46.9480 lon=7.4474; Geneva lat=46.2044 lon=6.1432."
)


def _make_lifespan(settings: Settings):
    """Build a FastMCP lifespan that owns the shared HTTP client."""

    @asynccontextmanager
    async def lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
        log = get_logger()
        client = EnergyHTTPClient(timeout=settings.http_timeout)
        log.info(
            "server.start",
            transport=settings.transport,
            protocol_version=SUPPORTED_PROTOCOL_VERSION,
        )
        try:
            yield AppContext(client=client)
        finally:
            await client.close()
            log.info("server.stop")

    return lifespan


def build_server(settings: Settings | None = None) -> FastMCP:
    """Construct a fully configured FastMCP server instance."""
    settings = settings or Settings()
    mcp = FastMCP(
        "swiss_energy_mcp",
        instructions=INSTRUCTIONS,
        host=settings.host,
        port=settings.port,
        lifespan=_make_lifespan(settings),
        dependencies=["httpx", "pydantic", "pydantic-settings", "structlog"],
    )
    register_tools(mcp)
    register_capabilities(mcp)
    return mcp


# Module-level server instance for `uvx swiss-energy-mcp` and tests.
mcp = build_server()


def main() -> None:
    """Start the Swiss Energy MCP server."""
    settings = Settings()
    configure_logging(settings.log_level)
    server = build_server(settings)

    if settings.transport == "http":
        import uvicorn
        from starlette.middleware.cors import CORSMiddleware

        app = server.streamable_http_app()
        # SDK-004: browser-based MCP clients must be able to read Mcp-Session-Id.
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
            allow_headers=[
                "Content-Type",
                "Authorization",
                "Mcp-Session-Id",
                "Mcp-Protocol-Version",
                "Last-Event-ID",
            ],
            expose_headers=["Mcp-Session-Id"],
            allow_credentials=False,
        )
        get_logger().info("server.http", host=settings.host, port=settings.port)
        uvicorn.run(app, host=settings.host, port=settings.port, log_config=None)
    else:
        server.run(transport="stdio")


if __name__ == "__main__":
    main()
