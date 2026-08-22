"""Swiss Energy MCP server.

MCP server for Swiss energy data from the Federal Office of Energy (SFOE/BFE),
served via the GeoAdmin REST API and opendata.swiss. All upstream APIs are
public and auth-free.

The module wires the pieces together: configuration (:mod:`settings`),
structured logging (:mod:`logging_config`), a shared HTTP client managed by a
MCPServer lifespan, and the tool / resource / prompt registrations.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from mcp.server.caching import CacheableMethod, CacheHint
from mcp.server.mcpserver import MCPServer

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
    """Build a MCPServer lifespan that owns the shared HTTP client."""

    @asynccontextmanager
    async def lifespan(server: MCPServer) -> AsyncIterator[AppContext]:
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


# SEP-2549, Spec 2026-07-28: die auflistenden Methoden tragen `ttlMs` und
# `cacheScope`. Das SDK setzt beides auf «sofort veraltet, nie geteilt» — ein
# Server ohne `cache_hints` laesst also jeden Client bei jeder Verbindung neu
# auflisten, fuer Verzeichnisse, die `register_tools`/`register_capabilities`
# beim Bau festlegen und die nicht vom Aufrufer abhaengen.
#
# `resources/read` und `prompts/get` stehen bewusst nicht dabei: das waere eine
# Zusicherung ueber den INHALT statt ueber das Verzeichnis. Dass
# `energy://layers` sich selbst als «static catalogue» beschreibt, ist kein
# Grund dafuer — die naechste Ressource kann eine Abfrage sein.
LIST_CACHE_TTL_MS = 300_000

# Annotiert, nicht inferiert: `MCPServer` nimmt
# `Mapping[CacheableMethod, CacheHint]`, und ein Dict-Literal ohne Annotation
# inferiert mypy als `str`.
CACHE_HINTS: dict[CacheableMethod, CacheHint] = {
    "tools/list": CacheHint(ttl_ms=LIST_CACHE_TTL_MS, scope="public"),
    "resources/list": CacheHint(ttl_ms=LIST_CACHE_TTL_MS, scope="public"),
    "resources/templates/list": CacheHint(ttl_ms=LIST_CACHE_TTL_MS, scope="public"),
    "prompts/list": CacheHint(ttl_ms=LIST_CACHE_TTL_MS, scope="public"),
    "server/discover": CacheHint(ttl_ms=LIST_CACHE_TTL_MS, scope="public"),
}


def build_server(settings: Settings | None = None) -> MCPServer:
    """Construct a fully configured MCPServer server instance."""
    settings = settings or Settings()
    mcp = MCPServer(
        "swiss_energy_mcp",
        instructions=INSTRUCTIONS,
        cache_hints=CACHE_HINTS,
        lifespan=_make_lifespan(settings),
        dependencies=["httpx", "pydantic", "pydantic-settings", "structlog"],
    )
    register_tools(mcp)
    register_capabilities(mcp)
    return mcp


# Module-level server instance for `uvx swiss-energy-mcp` and tests.
mcp = build_server()


def build_transport_security(settings: Settings):
    """Host/Origin allow-list for the HTTP transport (SEC-005, inbound half).

    The SDK leaves DNS-rebinding protection OFF while ``transport_security`` is
    unset — its own source says "If not specified, disable DNS rebinding
    protection by default for backwards compatibility". Unset therefore means
    no Host and no Origin validation at all.

    Returns ``None`` when no allow-list can be derived: a non-loopback bind
    with no ``SWISS_ENERGY_ALLOWED_HOSTS``. The server is then reached under a
    service or public DNS name this process does not know, and a guessed list
    would reject every real request with HTTP 421. The caller warns instead.
    """
    from mcp.server.transport_security import TransportSecuritySettings

    port = settings.port
    loopback = {f"127.0.0.1:{port}", f"localhost:{port}", f"[::1]:{port}"}
    if settings.allowed_hosts:
        # Loopback stays reachable for container health checks and debugging.
        hosts = set(settings.allowed_hosts) | loopback
    elif settings.host in ("127.0.0.1", "localhost", "::1"):
        hosts = loopback | {f"{settings.host}:{port}"}
    else:
        return None

    # Configured CORS origins must also pass the transport check, or the server
    # rejects exactly the browser clients CORS permits. "*" cannot be expressed
    # here (origins are matched literally, only a trailing ":*" port wildcard
    # is supported), so it is not copied across.
    origins = {o for o in settings.cors_origins if o != "*"}
    origins |= {f"http://{h}" for h in hosts}
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=sorted(hosts),
        allowed_origins=sorted(origins),
    )


# Die Header, nach denen Spec 2026-07-28 eine Streamable-HTTP-Anfrage routet —
# in der Schreibweise des SDK (`mcp.shared.inbound`). Ein Browser darf einen
# nicht safelisteten Header gar nicht erst senden, wenn der Server ihn nicht in
# `Access-Control-Allow-Headers` nennt: ohne sie stirbt jede Cross-Origin-
# Anfrage am Preflight, vor dem ersten MCP-Byte.
CORS_ROUTING_HEADERS = ["Mcp-Method", "Mcp-Name", "Mcp-Protocol-Version"]


def build_http_app(settings: Settings | None = None, server: MCPServer | None = None):
    """Baut die Streamable-HTTP-App samt CORS, ohne einen Socket zu binden.

    Herausgezogen aus `main`, damit die CORS-Schicht pruefbar ist: solange
    Aufbau und `uvicorn.run` in derselben Funktion standen, liess sich die
    Freigabeliste nur lesen, nicht ausprobieren — und eine gelesene Liste kann
    vollstaendig aussehen und trotzdem nie an der Middleware ankommen.
    """
    from starlette.middleware.cors import CORSMiddleware

    settings = settings or Settings()
    server = server or build_server(settings)
    security = build_transport_security(settings)
    if security is None:
        get_logger().warning(
            "server.dns_rebinding_protection_off",
            host=settings.host,
            hint="Set SWISS_ENERGY_ALLOWED_HOSTS to the hostnames this "
            "server is reachable under so Host and Origin are validated; "
            "without it there is no Host check at all.",
        )
    # mcp 2.x: transport_security is a per-app kwarg, not a setting.
    app = server.streamable_http_app(transport_security=security, host=settings.host)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=[
            "Content-Type",
            "Authorization",
            *CORS_ROUTING_HEADERS,
            "Mcp-Session-Id",
            "Last-Event-ID",
        ],
        expose_headers=["Mcp-Session-Id"],
        allow_credentials=False,
    )
    return app


def main() -> None:
    """Start the Swiss Energy MCP server."""
    settings = Settings()
    configure_logging(settings.log_level)
    server = build_server(settings)

    if settings.transport == "http":
        import uvicorn

        get_logger().info("server.http", host=settings.host, port=settings.port)
        uvicorn.run(
            build_http_app(settings, server),
            host=settings.host,
            port=settings.port,
            log_config=None,
        )
    else:
        server.run(transport="stdio")


if __name__ == "__main__":
    main()
