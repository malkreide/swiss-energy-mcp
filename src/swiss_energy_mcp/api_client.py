"""HTTP client, egress guard and GeoAdmin/CKAN query helpers.

Security model
--------------
The server only ever contacts a fixed set of public Swiss government APIs.
:func:`assert_url_allowed` enforces this as a code-layer egress allow-list
(SEC-021), rejecting non-HTTPS targets, hosts outside the allow-list, and any
host that resolves to a private, loopback, link-local or otherwise reserved IP
(SSRF prevention, SEC-004). Redirects are not followed automatically: each hop's
target is re-validated against the same allow-list before the redirected request
is sent, so a response cannot bounce the client onto an unvetted host.

DNS pinning (SEC-005): the IP that was validated is the IP that is connected to.
:class:`_PinnedDNSBackend` resolves and re-validates the host at the network
layer and opens the TCP connection to that exact address, closing the TOCTOU gap
between validation and connect. TLS SNI and certificate verification still use
the original hostname, so pinning does not weaken transport security.
"""

from __future__ import annotations

import socket
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from ipaddress import ip_address, ip_network
from typing import Any
from urllib.parse import urlparse

import httpx
from httpcore import AsyncNetworkStream
from httpcore._backends.auto import AutoBackend  # concrete async backend (anyio/trio)

try:
    _VERSION = version("swiss-energy-mcp")
except PackageNotFoundError:  # pragma: no cover - source checkout without install
    _VERSION = "0.0.0"
USER_AGENT = f"swiss-energy-mcp/{_VERSION} (github.com/malkreide/swiss-energy-mcp)"

# ---------------------------------------------------------------------------
# API base addresses
# ---------------------------------------------------------------------------

GEOADMIN_BASE = "https://api3.geo.admin.ch/rest/services/api/MapServer"
OPENDATA_SWISS_BASE = "https://www.opendata.swiss/api/3/action"

DEFAULT_TIMEOUT = 20.0
DEFAULT_RADIUS_M = 5000  # 5 km

# Data-source attribution (CH-004 — OGD licence compliance).
SOURCE_GEOADMIN = "Bundesamt für Energie (BFE) / swisstopo"
SOURCE_OPENDATA = "Bundesamt für Energie (BFE)"
API_GEOADMIN = "GeoAdmin REST API (api3.geo.admin.ch)"
API_OPENDATA = "opendata.swiss CKAN API"
LICENSE_OGD = (
    "Open Government Data via opendata.swiss — free use with attribution "
    "(BFE / swisstopo); subject to the source's terms of use"
)

# ---------------------------------------------------------------------------
# Egress allow-list (SEC-021)
# ---------------------------------------------------------------------------

ALLOWED_HOSTS: frozenset[str] = frozenset(
    {"api3.geo.admin.ch", "opendata.swiss", "www.opendata.swiss"}
)

_BLOCKED_NETWORKS = tuple(
    ip_network(cidr)
    for cidr in (
        "0.0.0.0/8",
        "10.0.0.0/8",
        "100.64.0.0/10",
        "127.0.0.0/8",
        "169.254.0.0/16",  # link-local incl. cloud metadata 169.254.169.254
        "172.16.0.0/12",
        "192.0.0.0/24",
        "192.168.0.0/16",
        "198.18.0.0/15",
        "::1/128",
        "fc00::/7",
        "fe80::/10",
    )
)


def _is_blocked_ip(raw_ip: str) -> bool:
    """Return True if the IP is private, loopback, reserved or otherwise blocked."""
    addr = ip_address(raw_ip)
    return (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_reserved
        or addr.is_multicast
        or addr.is_unspecified
        or any(addr in network for network in _BLOCKED_NETWORKS)
    )


def resolve_allowed_ip(host: str) -> str:
    """Resolve an allow-listed host and return a single validated IP to connect to.

    Every resolved address is checked; if *any* of them is private/reserved the
    host is rejected outright (a partially poisoned record is still poisoned).
    The first address is returned so the caller can pin the connection to it.

    Raises:
        ValueError: if the host is not allow-listed, cannot be resolved, or
            resolves to a private/reserved IP address.
    """
    if host not in ALLOWED_HOSTS:
        raise ValueError("Ziel-Host ist nicht in der Egress-Allow-List zugelassen.")

    try:
        infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:  # pragma: no cover - network dependent
        raise ValueError("Ziel-Host konnte nicht aufgelöst werden.") from exc

    pinned: str | None = None
    for info in infos:
        raw_ip = info[4][0]
        if _is_blocked_ip(raw_ip):
            raise ValueError("Ziel-Host löst auf eine nicht erlaubte IP-Adresse auf.")
        if pinned is None:
            pinned = raw_ip
    if pinned is None:  # pragma: no cover - getaddrinfo returns at least one entry
        raise ValueError("Ziel-Host konnte nicht aufgelöst werden.")
    return pinned


def assert_url_allowed(url: str) -> None:
    """Validate an outbound URL against the egress allow-list.

    Raises:
        ValueError: if the scheme is not HTTPS, the host is not allow-listed,
            or the host resolves to a private/reserved IP address.
    """
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ValueError("Nur HTTPS-Verbindungen sind erlaubt.")
    resolve_allowed_ip(parsed.hostname or "")


class _PinnedDNSBackend(AutoBackend):
    """Network backend that connects to a pre-validated, pinned IP (SEC-005).

    httpcore calls :meth:`connect_tcp` with the *hostname*; we resolve and
    validate it once here and open the socket to that exact IP, so there is no
    second, unvalidated DNS lookup before connect. httpcore performs the TLS
    handshake afterwards using the original hostname for SNI and certificate
    verification, so security is preserved while the IP is pinned.
    """

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Any = None,
    ) -> AsyncNetworkStream:
        pinned_ip = resolve_allowed_ip(host)
        return await super().connect_tcp(
            pinned_ip,
            port,
            timeout=timeout,
            local_address=local_address,
            socket_options=socket_options,
        )


class _PinningTransport(httpx.AsyncHTTPTransport):
    """httpx transport whose connection pool pins DNS via :class:`_PinnedDNSBackend`."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._pool._network_backend = _PinnedDNSBackend()


# ---------------------------------------------------------------------------
# BFE Layer-IDs (GeoAdmin)
# ---------------------------------------------------------------------------

LAYER_POWER_PLANTS = "ch.bfe.elektrizitaetsproduktionsanlagen"
LAYER_WIND_TURBINES = "ch.bfe.windenergieanlagen"
LAYER_HYDRO_PLANTS = "ch.bfe.statistik-wasserkraftanlagen"
LAYER_PV_LARGE = "ch.bfe.photovoltaik-grossanlagen"
LAYER_SOLAR_ROOFS = "ch.bfe.solarenergie-eignung-daecher"
LAYER_ENERGY_CITIES = "ch.bfe.energiestaedte"
LAYER_BIOGAS = "ch.bfe.biogasanlagen"

# Catalogue exposed via the energy://layers resource.
LAYER_CATALOG: dict[str, str] = {
    LAYER_POWER_PLANTS: "Alle Elektrizitätsproduktionsanlagen (alle Typen)",
    LAYER_WIND_TURBINES: "Windenergieanlagen mit Betreiber- und Turbinendaten",
    LAYER_HYDRO_PLANTS: "Statistik der Wasserkraftanlagen",
    LAYER_PV_LARGE: "Photovoltaik-Grossanlagen",
    LAYER_SOLAR_ROOFS: "Solarenergie: Eignung der Dächer",
    LAYER_ENERGY_CITIES: "Gemeinden mit dem Label «Energiestadt»",
    LAYER_BIOGAS: "Biogasanlagen",
}


# ---------------------------------------------------------------------------
# Coordinate conversion: WGS84 -> LV95 (swisstopo approximation)
# ---------------------------------------------------------------------------


def wgs84_to_lv95(lat: float, lon: float) -> tuple[float, float]:
    """Convert WGS84 (lat/lon) to Swiss LV95 (E, N) using the swisstopo formula."""
    lat_aux = (lat * 3600 - 169028.66) / 10000
    lon_aux = (lon * 3600 - 26782.5) / 10000

    e = (
        2600072.37
        + 211455.93 * lon_aux
        - 10938.51 * lon_aux * lat_aux
        - 0.36 * lon_aux * lat_aux**2
        - 44.54 * lon_aux**3
    )
    n = (
        1200147.07
        + 308807.95 * lat_aux
        + 3745.25 * lon_aux**2
        + 76.63 * lat_aux**2
        - 194.56 * lon_aux**2 * lat_aux
        + 119.79 * lat_aux**3
    )
    return e, n


def radius_to_map_extent(lat: float, lon: float, radius_m: int) -> dict[str, float]:
    """Build a square mapExtent (LV95) around a point for the identify endpoint."""
    e, n = wgs84_to_lv95(lat, lon)
    return {
        "xmin": e - radius_m,
        "ymin": n - radius_m,
        "xmax": e + radius_m,
        "ymax": n + radius_m,
        "e": e,
        "n": n,
    }


# Pixel tolerance for the identify endpoint. The mapExtent already constrains
# the search area, so the maximum tolerance is used unconditionally.
IDENTIFY_TOLERANCE = 500


# ---------------------------------------------------------------------------
# Async HTTP client
# ---------------------------------------------------------------------------


class EnergyHTTPClient:
    """Async HTTP client for the GeoAdmin and opendata.swiss APIs.

    Redirects are not followed automatically; they are resolved manually so
    every hop can be re-validated against the egress allow-list.
    """

    _MAX_REDIRECTS = 5

    def __init__(self, timeout: float = DEFAULT_TIMEOUT) -> None:
        self._client = httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=False,
            transport=_PinningTransport(),  # SEC-005: pin DNS at the network layer
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/json",
            },
        )

    async def get(self, url: str, params: dict[str, Any] | None = None) -> dict:
        """Perform a validated GET request and return the parsed JSON body.

        Raises:
            ValueError: on egress-policy violations or upstream API errors,
                with a user-facing message that contains no internal details.
        """
        assert_url_allowed(url)
        try:
            response = await self._client.get(url, params=params)
            redirects = 0
            while response.is_redirect and response.next_request is not None:
                redirects += 1
                if redirects > self._MAX_REDIRECTS:
                    raise ValueError("Zu viele Weiterleitungen bei der Anfrage.")
                # Re-validate every redirect hop against the egress allow-list.
                assert_url_allowed(str(response.next_request.url))
                response = await self._client.send(response.next_request)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            code = exc.response.status_code
            if code == 400:
                raise ValueError("Fehlerhafte Anfrage (HTTP 400). Bitte Parameter prüfen.") from exc
            if code == 404:
                raise ValueError("Ressource nicht gefunden (HTTP 404).") from exc
            if code == 429:
                raise ValueError(
                    "Zu viele Anfragen (HTTP 429). Bitte kurz warten und erneut versuchen."
                ) from exc
            if code == 503:
                raise ValueError(
                    "Der Dienst ist vorübergehend nicht verfügbar (HTTP 503)."
                ) from exc
            raise ValueError(f"Die API hat einen Fehler gemeldet (HTTP {code}).") from exc
        except httpx.TimeoutException as exc:
            raise ValueError("Zeitüberschreitung bei der Anfrage. Bitte erneut versuchen.") from exc
        except httpx.RequestError as exc:
            raise ValueError("Netzwerkfehler bei der Anfrage. Bitte Verbindung prüfen.") from exc

    async def close(self) -> None:
        """Close the underlying HTTP connection pool."""
        await self._client.aclose()


@dataclass(slots=True)
class AppContext:
    """Lifespan context shared with every tool invocation."""

    client: EnergyHTTPClient


# ---------------------------------------------------------------------------
# GeoAdmin queries
# ---------------------------------------------------------------------------


async def query_geoadmin_layer(
    client: EnergyHTTPClient,
    layer: str,
    lat: float,
    lon: float,
    radius_m: int = DEFAULT_RADIUS_M,
    lang: str = "de",
) -> list[dict]:
    """Query a GeoAdmin layer via the identify endpoint (spatial search).

    Uses an envelope geometry equal to the requested mapExtent. ``sr=2056``
    is sent explicitly: the identify endpoint defaults the spatial reference
    to LV03 (21781), under which the LV95 coordinates produced here fall off
    the grid and every layer silently returns zero features.
    """
    coords = radius_to_map_extent(lat, lon, radius_m)
    extent = f"{coords['xmin']},{coords['ymin']},{coords['xmax']},{coords['ymax']}"
    params = {
        "geometry": extent,
        "geometryType": "esriGeometryEnvelope",
        "layers": f"all:{layer}",
        "tolerance": IDENTIFY_TOLERANCE,
        "sr": 2056,
        "imageDisplay": "1000,1000,96",
        "mapExtent": extent,
        "lang": lang,
        "f": "json",
        "returnGeometry": "false",
    }
    data = await client.get(f"{GEOADMIN_BASE}/identify", params=params)
    return data.get("results", [])


async def find_geoadmin_by_name(
    client: EnergyHTTPClient,
    layer: str,
    search_text: str,
    search_field: str,
    lang: str = "de",
) -> list[dict]:
    """Search a GeoAdmin layer by a text field."""
    params = {
        "layer": layer,
        "searchText": search_text,
        "searchField": search_field,
        "lang": lang,
        "f": "json",
        "returnGeometry": "false",
    }
    data = await client.get(f"{GEOADMIN_BASE}/find", params=params)
    return data.get("results", [])


# ---------------------------------------------------------------------------
# opendata.swiss CKAN queries
# ---------------------------------------------------------------------------


async def search_opendata_swiss(
    client: EnergyHTTPClient,
    query: str = "",
    organization: str = "bundesamt-fur-energie-bfe",
    rows: int = 20,
    start: int = 0,
) -> dict:
    """Search the opendata.swiss catalogue for BFE datasets."""
    q_parts: list[str] = []
    if query:
        q_parts.append(query)
    if organization:
        q_parts.append(f"organization:{organization}")

    params = {
        "q": " ".join(q_parts) if q_parts else "*:*",
        "rows": rows,
        "start": start,
        "sort": "score desc",
    }
    data = await client.get(f"{OPENDATA_SWISS_BASE}/package_search", params=params)
    if not data.get("success"):
        raise ValueError("Die opendata.swiss-API hat keinen Erfolg gemeldet.")

    result = data.get("result", {})
    return {"count": result.get("count", 0), "results": result.get("results", [])}
