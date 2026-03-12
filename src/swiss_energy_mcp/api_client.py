"""HTTP-Client und Hilfsfunktionen für den Swiss Energy MCP Server.

Metapher: Dieser Client ist der Dolmetscher zwischen GeoAdmin und dem MCP-Server.
Er übersetzt Koordinaten, formuliert Anfragen und bereitet Antworten auf.
"""

import math
from typing import Any

import httpx

# ---------------------------------------------------------------------------
# API-Basisadressen
# ---------------------------------------------------------------------------

GEOADMIN_BASE = "https://api3.geo.admin.ch/rest/services/api/MapServer"
OPENDATA_SWISS_BASE = "https://opendata.swiss/api/3/action"

# Standardwerte
DEFAULT_TIMEOUT = 20.0
DEFAULT_RADIUS_M = 5000  # 5 km

# ---------------------------------------------------------------------------
# BFE Layer-IDs (GeoAdmin)
# ---------------------------------------------------------------------------

LAYER_POWER_PLANTS = "ch.bfe.elektrizitaetsproduktionsanlagen"
LAYER_WIND_TURBINES = "ch.bfe.windenergieanlagen"
LAYER_HYDRO_PLANTS = "ch.bfe.statistik-wasserkraftanlagen"
LAYER_PV_LARGE = "ch.bfe.photovoltaik-grossanlagen"
LAYER_SOLAR_ROOFS = "ch.bfe.solarenergie-eignung-daecher"
LAYER_SOLAR_FACADES = "ch.bfe.solarenergie-eignung-fassaden"
LAYER_ENERGY_CITIES = "ch.bfe.energiestaedte"
LAYER_BIOGAS = "ch.bfe.biogasanlagen"
LAYER_BIOMASS_WOODY = "ch.bfe.biomasse-verholzt"
LAYER_BIOMASS_NONWOODY = "ch.bfe.biomasse-nicht-verholzt"
LAYER_WIND_SPEED_H100 = "ch.bfe.windenergie-geschwindigkeit_h100"
LAYER_TRANSMISSION_LINES = "ch.bfe.sachplan-uebertragungsleitungen_kraft"

# ---------------------------------------------------------------------------
# Koordinaten-Konvertierung: WGS84 → LV95 (näherungsweise)
# ---------------------------------------------------------------------------

def wgs84_to_lv95(lat: float, lon: float) -> tuple[float, float]:
    """Konvertiert WGS84-Koordinaten (lat/lon) in Schweizer LV95 (E, N).

    Verwendet die offizielle Näherungsformel des swisstopo.
    Genauigkeit: ±1 m, ausreichend für API-Abfragen.

    Args:
        lat: Breitengrad (z. B. 47.3769 für Zürich)
        lon: Längengrad (z. B. 8.5417 für Zürich)

    Returns:
        Tuple (E, N) in LV95-Koordinaten (Meter)
    """
    # Hilfsgrössen (swisstopo-Formel)
    lat_aux = (lat * 3600 - 169028.66) / 10000
    lon_aux = (lon * 3600 - 26782.5) / 10000

    # Rechtswert (E)
    e = (
        2600072.37
        + 211455.93 * lon_aux
        - 10938.51 * lon_aux * lat_aux
        - 0.36 * lon_aux * lat_aux**2
        - 44.54 * lon_aux**3
    )

    # Hochwert (N)
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
    """Berechnet mapExtent-Parameter für GeoAdmin identify-Endpoint.

    Der identify-Endpoint braucht einen mapExtent (Kartenausschnitt) und
    eine tolerance (Suchradius in Pixel). Wir simulieren einen quadratischen
    Ausschnitt um den Punkt.

    Args:
        lat: Breitengrad des Mittelpunkts
        lon: Längengrad des Mittelpunkts
        radius_m: Suchradius in Metern

    Returns:
        Dict mit xmin, ymin, xmax, ymax in LV95
    """
    e, n = wgs84_to_lv95(lat, lon)
    return {
        "xmin": e - radius_m,
        "ymin": n - radius_m,
        "xmax": e + radius_m,
        "ymax": n + radius_m,
        "e": e,
        "n": n,
    }


def compute_tolerance(radius_m: int, image_size: int = 1000) -> int:
    """Berechnet die pixel-tolerance für den identify-Endpoint.

    GeoAdmin arbeitet mit Pixeln. Bei einem mapExtent von 2*radius_m Breite
    und einer Bildgrösse von image_size Pixeln entspricht 1 Pixel = 2*radius/image_size Meter.
    Wir verwenden immer die maximale Tolerance (500 px), da der mapExtent
    bereits den Suchbereich einschränkt – die Tolerance definiert nur den
    Suchradius um den Mittelpunkt innerhalb des Extents.

    Args:
        radius_m: Gewünschter Suchradius in Metern
        image_size: Bildbreite in Pixeln (Standard: 1000)

    Returns:
        Tolerance in Pixeln (immer 500 für maximale Abdeckung)
    """
    # Maximale Tolerance verwenden: der mapExtent begrenzt den Bereich bereits
    return 500


# ---------------------------------------------------------------------------
# HTTP-Client
# ---------------------------------------------------------------------------

class EnergyHTTPClient:
    """Async HTTP-Client für GeoAdmin und opendata.swiss APIs.

    Metapher: Ein höflicher Bibliothekar, der Anfragen stellt und
    Fehler klar kommuniziert.
    """

    def __init__(self, timeout: float = DEFAULT_TIMEOUT) -> None:
        self._client = httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers={
                "User-Agent": "swiss-energy-mcp/0.1.0 (github.com/malkreide/swiss-energy-mcp)",
                "Accept": "application/json",
            },
        )

    async def get(self, url: str, params: dict[str, Any] | None = None) -> dict:
        """Führt eine GET-Anfrage aus und gibt das JSON-Ergebnis zurück.

        Args:
            url: Ziel-URL
            params: Query-Parameter

        Returns:
            Geparste JSON-Antwort als dict

        Raises:
            ValueError: Bei API-Fehlern mit benutzerfreundlicher Meldung
        """
        try:
            response = await self._client.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            code = e.response.status_code
            if code == 400:
                raise ValueError(
                    f"Fehlerhafte Anfrage (HTTP 400). Bitte Parameter überprüfen. URL: {url}"
                ) from e
            elif code == 404:
                raise ValueError(
                    f"Ressource nicht gefunden (HTTP 404). Layer oder Endpunkt existiert nicht. URL: {url}"
                ) from e
            elif code == 429:
                raise ValueError(
                    "Zu viele Anfragen (HTTP 429). Bitte kurz warten und erneut versuchen."
                ) from e
            elif code == 503:
                raise ValueError(
                    "GeoAdmin-Dienst vorübergehend nicht verfügbar (HTTP 503). Bitte später erneut versuchen."
                ) from e
            else:
                raise ValueError(
                    f"API-Fehler (HTTP {code}). URL: {url}"
                ) from e
        except httpx.TimeoutException as e:
            raise ValueError(
                "Zeitüberschreitung bei der Anfrage. Bitte Netzwerkverbindung prüfen und erneut versuchen."
            ) from e
        except httpx.RequestError as e:
            raise ValueError(
                f"Netzwerkfehler: {e!s}. Bitte Internetverbindung prüfen."
            ) from e

    async def close(self) -> None:
        """Schliesst den HTTP-Client."""
        await self._client.aclose()


# ---------------------------------------------------------------------------
# GeoAdmin identify-Abfrage (Kernfunktion)
# ---------------------------------------------------------------------------

async def query_geoadmin_layer(
    client: EnergyHTTPClient,
    layer: str,
    lat: float,
    lon: float,
    radius_m: int = DEFAULT_RADIUS_M,
    lang: str = "de",
) -> list[dict]:
    """Abfrage eines GeoAdmin-Layers per identify-Endpoint.

    Der identify-Endpunkt ist der zuverlässigste Weg, räumliche Abfragen
    auf GeoAdmin-Layern durchzuführen. Er gibt bis zu 201 Ergebnisse zurück.

    Args:
        client: EnergyHTTPClient-Instanz
        layer: Layer-ID (z. B. 'ch.bfe.windenergieanlagen')
        lat: Breitengrad des Mittelpunkts (WGS84)
        lon: Längengrad des Mittelpunkts (WGS84)
        radius_m: Suchradius in Metern
        lang: Sprache für Ergebnisse ('de', 'fr', 'it', 'en')

    Returns:
        Liste von Feature-Dicts mit 'attributes' und optional 'geometry'
    """
    coords = radius_to_map_extent(lat, lon, radius_m)
    tolerance = compute_tolerance(radius_m)

    params = {
        "geometry": f"{coords['e']},{coords['n']}",
        "geometryType": "esriGeometryPoint",
        "layers": f"all:{layer}",
        "tolerance": tolerance,
        "imageDisplay": "1000,1000,96",
        "mapExtent": f"{coords['xmin']},{coords['ymin']},{coords['xmax']},{coords['ymax']}",
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
    """Sucht im GeoAdmin-Layer nach einem Textfeld.

    Args:
        client: EnergyHTTPClient-Instanz
        layer: Layer-ID
        search_text: Suchbegriff
        search_field: Feldname für die Suche
        lang: Sprache

    Returns:
        Liste von gefundenen Features
    """
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
# opendata.swiss CKAN-Abfragen
# ---------------------------------------------------------------------------

async def search_opendata_swiss(
    client: EnergyHTTPClient,
    query: str = "",
    organization: str = "bundesamt-fur-energie-bfe",
    rows: int = 20,
    start: int = 0,
) -> dict:
    """Sucht im opendata.swiss-Katalog nach BFE-Datensätzen.

    Args:
        client: EnergyHTTPClient-Instanz
        query: Suchbegriff (leer = alle Datensätze der Organisation)
        organization: CKAN-Organisations-Slug
        rows: Anzahl Ergebnisse
        start: Offset für Paginierung

    Returns:
        Dict mit 'count', 'results' (Liste von Datensätzen)
    """
    q_parts = []
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
        raise ValueError("opendata.swiss API hat keinen Erfolg gemeldet.")

    result = data.get("result", {})
    return {
        "count": result.get("count", 0),
        "results": result.get("results", []),
    }


# ---------------------------------------------------------------------------
# Formatierungs-Hilfsfunktionen
# ---------------------------------------------------------------------------

def format_power_value(value: Any, unit: str = "kW") -> str:
    """Formatiert Leistungswerte leserlich.

    Args:
        value: Rohwert (str, float oder None)
        unit: Einheit (Standard: kW)

    Returns:
        Formatierter String, z. B. '18.81 kW' oder '2.00 MW'
    """
    if value is None or value == "":
        return "k.A."
    try:
        val = float(str(value).replace(",", "."))
        if unit == "kW" and val >= 1000:
            return f"{val / 1000:.2f} MW"
        return f"{val:.2f} {unit}"
    except (ValueError, TypeError):
        return str(value)


def format_year(value: Any) -> str:
    """Formatiert Jahreszahlen.

    Args:
        value: Rohwert (int, str oder None)

    Returns:
        Jahreszahl als String oder 'k.A.'
    """
    if value is None or value == "":
        return "k.A."
    return str(int(value)) if str(value).isdigit() else str(value)


def clean_label(raw: str) -> str:
    """Entfernt HTML-Tags aus GeoAdmin-Labels.

    GeoAdmin gibt Labels manchmal mit <b>...</b> zurück.

    Args:
        raw: Rohstring mit möglichen HTML-Tags

    Returns:
        Bereinigter String
    """
    return raw.replace("<b>", "").replace("</b>", "").strip()
