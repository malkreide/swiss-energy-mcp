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

import asyncio
import random
import socket
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
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
# Canonical CKAN host. opendata.swiss redirects the CKAN API
# (www.opendata.swiss -> opendata.swiss -> ckan.opendata.swiss); hitting the
# final host directly avoids the redirect hops while staying inside the
# egress allow-list.
OPENDATA_SWISS_BASE = "https://ckan.opendata.swiss/api/3/action"

DEFAULT_TIMEOUT = 20.0


# --- Retry policy ------------------------------------------------------------
# Adopted from the mcp-data-source-probe reference template (repaired
# 2026-08-07). Three questions: *what* is retried, *how fast*, and *how long*.
# The first is settled in the retry loop (4xx except 429 fails fast); these
# settle the other two.

RETRY_ATTEMPTS = 4
RETRY_BASE_DELAY = 2.0  # ladder before jitter: 2, 4, 8

# Ceiling on the WHOLE call — every attempt and every wait together. An attempt
# count is not a bound: four attempts against an upstream that takes 30s to time
# out is two minutes inside one tool call, and the number never says so. The
# anchor is measured, not guessed: the Python MCP SDK ships
# MCP_DEFAULT_TIMEOUT = 30.0, so 25s leaves headroom for framing and parsing.
RETRY_TOTAL_BUDGET = 25.0

# Ceiling for a single wait. Bounds the exponential ladder, and bounds a
# `Retry-After` the source may send but we are not obliged to sit through.
RETRY_MAX_DELAY = 20.0

# Jitter spread. Without it every client that hit the same outage retries in
# lockstep, and the load returns as a wave exactly when the source recovers —
# the retry storm extends the outage it was meant to bridge.
RETRY_JITTER_SPREAD = 0.5  # exponential delays land in [0.5x, 1.5x]

# On a `Retry-After`, deliberately one-sided: the source said when to come back,
# so coming back later is fine and coming back earlier is not.
RETRY_AFTER_JITTER = 0.25  # lands in [1.0x, 1.25x]

# Statuses that carry a meaningful `Retry-After` (RFC 9110 section 10.2.3).
RETRY_AFTER_STATUSES = frozenset({429, 503})


def parse_retry_after(resp: httpx.Response | None) -> float | None:
    """Seconds to wait per the response's ``Retry-After``, or ``None``.

    RFC 9110 section 10.2.3 allows two forms — delta-seconds (``120``) and an
    HTTP-date (``Wed, 21 Oct 2026 07:28:00 GMT``). Both appear in the wild, so
    both are read. Anything unparseable yields ``None`` and the caller falls
    back to its own curve: a malformed header must not become a crash on the
    error path, which is the one path already going badly.
    """
    if resp is None or resp.status_code not in RETRY_AFTER_STATUSES:
        return None
    raw = (resp.headers.get("retry-after") or "").strip()
    if not raw:
        return None
    if raw.isdigit():
        return float(raw)
    try:
        when = parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        return None
    if when is None:
        return None
    if when.tzinfo is None:  # RFC 9110 dates are GMT; a naive one means UTC
        when = when.replace(tzinfo=UTC)
    return max(0.0, (when - datetime.now(UTC)).total_seconds())


def compute_delay(attempt: int, last_error: Exception | None) -> float:
    """Seconds to wait before ``attempt`` (1-based for the first retry).

    The source's own answer beats our guess: a ``Retry-After`` on a 429 or 503
    wins over the exponential curve. Everything is spread, then capped.

    The cap wraps the jitter and not the other way round. ``min(cap, base) *
    jitter`` and ``min(cap, base * jitter)`` both contain a cap and a jitter;
    only the second is bounded — a value capped at 20s and then multiplied by
    up to 1.5 lands at 30s, and the constant would claim a ceiling it does not
    hold.
    """
    hinted = parse_retry_after(getattr(last_error, "response", None))
    if hinted is not None:
        return min(
            hinted * (1.0 + random.random() * RETRY_AFTER_JITTER),
            RETRY_MAX_DELAY,
        )
    return min(
        RETRY_BASE_DELAY
        * 2 ** (attempt - 1)
        * (1.0 - RETRY_JITTER_SPREAD + random.random() * 2 * RETRY_JITTER_SPREAD),
        RETRY_MAX_DELAY,
    )


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
    {
        "api3.geo.admin.ch",
        "opendata.swiss",
        "www.opendata.swiss",
        "ckan.opendata.swiss",
    }
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

    async def _send_once(self, url: str, params: dict[str, Any] | None) -> httpx.Response:
        """Ein Versuch, inklusive Redirect-Kette. Wirft die httpx-Fehler roh."""
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
        return response

    async def get(self, url: str, params: dict[str, Any] | None = None) -> dict:
        """Perform a validated GET request and return the parsed JSON body.

        Wiederholt 5xx, 429 und Netzwerkfehler mit gestreutem Backoff und einem
        Gesamtbudget in Sekunden; 4xx ausser 429 werden sofort durchgereicht —
        ein Client-Fehler wird durch Wiederholen nicht besser.

        Raises:
            ValueError: on egress-policy violations or upstream API errors,
                with a user-facing message that contains no internal details.
        """
        assert_url_allowed(url)
        last_error: Exception | None = None
        deadline = time.monotonic() + RETRY_TOTAL_BUDGET

        for attempt in range(RETRY_ATTEMPTS):
            if attempt > 0:
                delay = compute_delay(attempt, last_error)
                # Eine Wartezeit, die das Budget überdauert, wartet für
                # niemanden: Der Aufrufende hat aufgegeben, bevor sie endet.
                if delay >= deadline - time.monotonic():
                    break
                await asyncio.sleep(delay)

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                # httpx begrenzt pro Operation, und sein Read-Timeout beginnt
                # mit jedem Chunk von vorn — eine tröpfelnde Antwort überdauert
                # jede Einzelschranke, ohne dass ein Read abläuft.
                async with asyncio.timeout(remaining):
                    return (await self._send_once(url, params)).json()
            except TimeoutError as exc:  # Budget weg, nicht bloss dieser Versuch
                last_error = exc
                break
            except httpx.HTTPStatusError as exc:
                last_error = exc
                code = exc.response.status_code
                if code == 429 or 500 <= code < 600:
                    continue  # wiederholbar — Wartezeit kommt aus compute_delay
                break
            except httpx.RequestError as exc:
                last_error = exc
                continue

        # Ab hier ist der Versuch endgültig gescheitert. Die Fehlerabbildung
        # unten ist unverändert: Sie war nie das Problem, es fehlte der Retry
        # davor.
        try:
            if last_error is None:
                raise ValueError("Zeitüberschreitung bei der Anfrage. Bitte erneut versuchen.")
            raise last_error
        except httpx.HTTPStatusError as exc:
            code = exc.response.status_code
            if code == 400:
                raise ValueError("Fehlerhafte Anfrage (HTTP 400). Bitte Parameter prüfen.") from exc
            if code == 404:
                raise ValueError("Ressource nicht gefunden (HTTP 404).") from exc
            # 429 und 503 sind die beiden Status, die dieser Client jetzt selbst
            # wiederholt — inklusive `Retry-After`, wenn die Quelle eines sendet.
            # Wer diese Meldung sieht, hat die Wiederholungen also schon hinter
            # sich; «bitte kurz warten und erneut versuchen» wäre jetzt ein Rat,
            # der bereits befolgt wurde.
            if code == 429:
                raise ValueError(
                    "Zu viele Anfragen (HTTP 429) — auch nach mehreren "
                    "Wiederholungen. Die Quelle drosselt gerade; später erneut "
                    "versuchen."
                ) from exc
            if code == 503:
                raise ValueError(
                    "Der Dienst ist vorübergehend nicht verfügbar (HTTP 503) — "
                    "auch nach mehreren Wiederholungen."
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


class UpstreamSchemaError(ValueError):
    """Die Antwort kam an, sieht aber anders aus, als der Code sie liest.

    Von einem echten CKAN-Fehler (`success: false`) getrennt, weil die Behebung
    eine andere ist: Dort hat die Quelle geantwortet und Nein gesagt, hier hat
    sie ihre Form geändert.

    Erbt von ``ValueError``, damit die Aufrufer in ``server.py``, die heute
    schon auf ``ValueError`` verzweigen, den Fall weiterhin als API-Fehler
    behandeln statt ihn als unerwartete Ausnahme durchzureichen.
    """


def _ckan_result(data: dict, action: str) -> dict:
    """Den ``result``-Block holen, oder laut scheitern (FID-006).

    ``data.get("result", {})`` schrieb jede Strukturänderung in ein gültiges
    leeres Ergebnis um — und weil die Aufrufer danach ``count`` und ``results``
    ebenfalls defaulteten, kam am Ende buchstäblich ``{"count": 0,
    "results": []}`` heraus: nicht von «opendata.swiss hat nichts» zu
    unterscheiden.
    """
    if "result" not in data:
        raise UpstreamSchemaError(
            f"opendata.swiss `{action}`: Antwort ohne `result`. Vorhandene "
            f"Schlüssel: {sorted(data)}. Das ist keine Leermenge — die Struktur "
            "der Quelle hat sich geändert."
        )
    result = data["result"]
    if not isinstance(result, dict):
        raise UpstreamSchemaError(
            f"opendata.swiss `{action}`: `result` ist {type(result).__name__} und kein Objekt."
        )
    return result


def _ckan_field(result: dict, field: str, action: str) -> object:
    """Ein gelesenes Feld des ``result``-Blocks bestätigen.

    Die Ebene darunter, und sie zählt genauso: ``package_search`` liefert
    ``count`` und ``results`` **immer** — auch bei null Treffern. Fehlt eines,
    ist das keine leere Suche, sondern eine andere Antwort.
    """
    if field not in result:
        raise UpstreamSchemaError(
            f"opendata.swiss `{action}`: `result` ohne `{field}`. Vorhandene "
            f"Schlüssel: {sorted(result)}. `package_search` liefert `count` und "
            "`results` auch bei null Treffern — dies ist keine leere Suche."
        )
    return result[field]


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
    if not isinstance(data, dict):
        raise UpstreamSchemaError(
            f"opendata.swiss `package_search`: Antwort ist {type(data).__name__} "
            "und kein Objekt. Erwartet wird die CKAN-Hülle mit `success` und `result`."
        )
    if not data.get("success"):
        raise ValueError("Die opendata.swiss-API hat keinen Erfolg gemeldet.")

    result = _ckan_result(data, "package_search")
    return {
        "count": _ckan_field(result, "count", "package_search"),
        "results": _ckan_field(result, "results", "package_search"),
    }
