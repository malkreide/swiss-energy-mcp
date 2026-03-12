"""Swiss Energy MCP Server.

MCP Server für Schweizer Energiedaten des Bundesamts für Energie (BFE).

Metapher: Wenn der swiss-road-mobility-mcp die Mobilitätskarte der Schweiz ist,
dann ist dieser Server das Energieatlas-Pendant – er zeigt, wo die Schweiz
Strom produziert, speichert und verteilt, und wo das Potenzial für mehr liegt.

Datenquellen (alle Auth-frei, öffentlich):
  - GeoAdmin REST API (api3.geo.admin.ch): BFE-Layer mit Geo-Referenzierung
  - opendata.swiss CKAN API: Metadaten-Katalog des BFE

Tools (10):
  - energy_find_power_plants:      Elektrizitätsproduktionsanlagen (alle Typen)
  - energy_find_wind_turbines:     Windenergieanlagen
  - energy_find_hydro_plants:      Wasserkraftwerke (Statistik)
  - energy_find_pv_installations:  Photovoltaik-Grossanlagen
  - energy_find_biogas_plants:     Biogasanlagen
  - energy_find_energy_cities:     Energiestädte (Label «Energiestadt»)
  - energy_solar_potential:        Solareignung Dächer für einen Standort
  - energy_location_profile:       Vollständiges Energieprofil für einen Standort
  - energy_search_bfe_datasets:    Datensätze des BFE auf opendata.swiss suchen
  - energy_check_status:           Systemstatus und Verfügbarkeit der APIs
"""

import json
import logging
import os
import sys
from enum import Enum
from typing import Optional

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .api_client import (
    DEFAULT_RADIUS_M,
    GEOADMIN_BASE,
    LAYER_BIOGAS,
    LAYER_ENERGY_CITIES,
    LAYER_HYDRO_PLANTS,
    LAYER_POWER_PLANTS,
    LAYER_PV_LARGE,
    LAYER_SOLAR_ROOFS,
    LAYER_WIND_TURBINES,
    OPENDATA_SWISS_BASE,
    EnergyHTTPClient,
    clean_label,
    find_geoadmin_by_name,
    format_power_value,
    format_year,
    query_geoadmin_layer,
    search_opendata_swiss,
    wgs84_to_lv95,
)

logger = logging.getLogger("swiss-energy-mcp")

# ---------------------------------------------------------------------------
# Server-Initialisierung
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "swiss_energy_mcp",
    instructions=(
        "Swiss Energy MCP Server – Energiedaten des Bundesamts für Energie (BFE) via GeoAdmin REST API "
        "und opendata.swiss. Alle Tools sind auth-frei und benötigen keinen API-Key. "
        "Koordinaten werden als WGS84 (Lat/Lon) übergeben und intern nach LV95 konvertiert. "
        "Verfügbare Tools: "
        "energy_find_power_plants (alle Elektrizitätsproduktionsanlagen im Umkreis), "
        "energy_find_wind_turbines (Windenergieanlagen mit Produktionsdaten), "
        "energy_find_hydro_plants (Wasserkraftwerke), "
        "energy_find_pv_installations (Photovoltaik-Grossanlagen), "
        "energy_find_biogas_plants (Biogasanlagen), "
        "energy_find_energy_cities (Gemeinden mit Label 'Energiestadt'), "
        "energy_solar_potential (Solareignung Dächer für eine Adresse/Standort), "
        "energy_location_profile (vollständiges Energieprofil für einen Standort), "
        "energy_search_bfe_datasets (BFE-Datensätze auf opendata.swiss suchen), "
        "energy_check_status (API-Verfügbarkeit prüfen). "
        "Koordinaten-Tipp: Zürich ≈ lat=47.3769, lon=8.5417; Bern ≈ lat=46.9480, lon=7.4474; "
        "Genf ≈ lat=46.2044, lon=6.1432."
    ),
)

# ---------------------------------------------------------------------------
# Lazy HTTP-Client
# ---------------------------------------------------------------------------

_client: EnergyHTTPClient | None = None


def _get_client() -> EnergyHTTPClient:
    global _client
    if _client is None:
        _client = EnergyHTTPClient()
    return _client


# ---------------------------------------------------------------------------
# Pydantic-Modelle
# ---------------------------------------------------------------------------

class ResponseFormat(str, Enum):
    MARKDOWN = "markdown"
    JSON = "json"


class LocationInput(BaseModel):
    """Standort-Parameter für räumliche Abfragen."""

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    lat: float = Field(
        ...,
        description="Breitengrad (WGS84, z. B. 47.3769 für Zürich)",
        ge=45.0,
        le=48.0,
    )
    lon: float = Field(
        ...,
        description="Längengrad (WGS84, z. B. 8.5417 für Zürich)",
        ge=5.5,
        le=10.7,
    )
    radius_m: int = Field(
        default=DEFAULT_RADIUS_M,
        description="Suchradius in Metern (Standard: 5000 m = 5 km, max: 50000 m = 50 km)",
        ge=500,
        le=50000,
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Ausgabeformat: 'markdown' (lesbar) oder 'json' (maschinell)",
    )


class PowerPlantInput(LocationInput):
    """Abfrage von Elektrizitätsproduktionsanlagen mit optionalem Typ-Filter."""

    category_filter: Optional[str] = Field(
        default=None,
        description=(
            "Optionaler Filter für Hauptkategorie (Deutsch, Gross-/Kleinschreibung ignoriert). "
            "Beispiele: 'Photovoltaik', 'Wasserkraft', 'Wind', 'Kernkraft', "
            "'Übrige erneuerbare Energien', 'Nicht erneuerbare Energien'"
        ),
        max_length=100,
    )


class SearchInput(BaseModel):
    """Suchparameter für opendata.swiss."""

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    query: str = Field(
        default="",
        description=(
            "Suchbegriff (leer = alle BFE-Datensätze). "
            "Beispiele: 'solar', 'wasserkraft', 'windenergie', 'elektrizität'"
        ),
        max_length=200,
    )
    limit: int = Field(
        default=10,
        description="Maximale Anzahl Ergebnisse (1–50)",
        ge=1,
        le=50,
    )
    offset: int = Field(
        default=0,
        description="Offset für Paginierung (Standard: 0)",
        ge=0,
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Ausgabeformat: 'markdown' oder 'json'",
    )


class EnergyCityInput(BaseModel):
    """Suche nach Energiestädten."""

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    name: Optional[str] = Field(
        default=None,
        description="Name der Gemeinde/Stadt (z. B. 'Zürich', 'Bern'). Leer = Standortsuche.",
        max_length=100,
    )
    lat: Optional[float] = Field(
        default=None,
        description="Breitengrad für Standortsuche (WGS84). Nur wenn kein Name angegeben.",
        ge=45.0,
        le=48.0,
    )
    lon: Optional[float] = Field(
        default=None,
        description="Längengrad für Standortsuche (WGS84). Nur wenn kein Name angegeben.",
        ge=5.5,
        le=10.7,
    )
    radius_m: int = Field(
        default=20000,
        description="Suchradius in Metern bei Standortsuche (Standard: 20 km)",
        ge=1000,
        le=100000,
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Ausgabeformat: 'markdown' oder 'json'",
    )

    @field_validator("lat", "lon")
    @classmethod
    def check_coords_if_no_name(cls, v, info):
        return v


# ---------------------------------------------------------------------------
# Hilfsfunktionen für Ausgabe-Formatierung
# ---------------------------------------------------------------------------

def _format_power_plant_list(features: list[dict], title: str) -> str:
    """Formatiert eine Liste von Elektrizitätsproduktionsanlagen als Markdown."""
    if not features:
        return f"## {title}\n\nKeine Anlagen im angegebenen Umkreis gefunden."

    lines = [f"## {title}", f"\n**{len(features)} Anlage(n) gefunden**\n"]
    for feat in features:
        attrs = feat.get("attributes", {})
        subcat = attrs.get("sub_category_de", "Unbekannt")
        address = attrs.get("address", "k.A.")
        canton = attrs.get("canton", "")
        power_init = format_power_value(attrs.get("initial_power", ""), "kW")
        power_total = format_power_value(attrs.get("total_power", ""), "kW")
        op_start = attrs.get("beginning_of_operation", "k.A.")

        lines.append(f"### {subcat} – {address}")
        if canton:
            lines.append(f"- **Kanton:** {canton}")
        lines.append(f"- **Inbetriebnahme:** {op_start}")
        lines.append(f"- **Anfangsleistung:** {power_init}")
        lines.append(f"- **Aktuelle Leistung:** {power_total}")
        lines.append("")

    return "\n".join(lines)


def _format_wind_turbine_list(features: list[dict], title: str) -> str:
    """Formatiert Windenergieanlagen als Markdown."""
    if not features:
        return f"## {title}\n\nKeine Windenergieanlagen im angegebenen Umkreis gefunden."

    lines = [f"## {title}", f"\n**{len(features)} Anlage(n) gefunden**\n"]
    for feat in features:
        attrs = feat.get("attributes", {})
        name = attrs.get("fac_name", "Unbekannt")
        operator = attrs.get("fac_operator", "k.A.")
        power_kw = format_power_value(attrs.get("fac_power", ""), "kW")
        fac_type = attrs.get("fac_type_de", "k.A.")
        website = attrs.get("fac_website", "")

        # Turbinen-Details aus XML parsen (vereinfacht)
        turbines_xml = attrs.get("turbines", "")
        turbine_info = ""
        if "<tur_manufacturer>" in turbines_xml:
            import re
            mfr = re.search(r"<tur_manufacturer>(.*?)</tur_manufacturer>", turbines_xml)
            model = re.search(r"<tur_model>(.*?)</tur_model>", turbines_xml)
            hub = re.search(r"<tur_hubheight>(.*?)</tur_hubheight>", turbines_xml)
            if mfr:
                turbine_info = f"{mfr.group(1)}"
            if model:
                turbine_info += f" {model.group(1)}"
            if hub:
                turbine_info += f" (Nabenhöhe: {hub.group(1)} m)"

        lines.append(f"### {name} ({fac_type})")
        lines.append(f"- **Betreiber:** {operator}")
        lines.append(f"- **Leistung:** {power_kw}")
        if turbine_info:
            lines.append(f"- **Turbine:** {turbine_info}")
        if website:
            lines.append(f"- **Website:** {website}")
        lines.append("")

    return "\n".join(lines)


def _format_hydro_plant_list(features: list[dict], title: str) -> str:
    """Formatiert Wasserkraftwerke als Markdown."""
    if not features:
        return f"## {title}\n\nKeine Wasserkraftwerke im angegebenen Umkreis gefunden."

    lines = [f"## {title}", f"\n**{len(features)} Werk(e) gefunden**\n"]
    for feat in features:
        attrs = feat.get("attributes", {})
        name = attrs.get("name", "Unbekannt")
        location = attrs.get("location", "k.A.")
        canton = attrs.get("canton", "")
        plant_type = attrs.get("hydropowerplanttype_de", "k.A.")
        status = attrs.get("hydropowerplantoperationalstatus_de", "k.A.")
        op_start = format_year(attrs.get("beginningofoperation"))
        turbine_mw = format_power_value(attrs.get("performanceturbinemaximum", ""), "MW")
        production_gwh = attrs.get("productionexpected", "k.A.")
        fall_height = attrs.get("fallheight", "k.A.")

        lines.append(f"### {name}")
        lines.append(f"- **Standort:** {location}{f', {canton}' if canton else ''}")
        lines.append(f"- **Typ:** {plant_type}")
        lines.append(f"- **Status:** {status}")
        lines.append(f"- **Inbetriebnahme:** {op_start}")
        lines.append(f"- **Turbinenleistung:** {turbine_mw}")
        lines.append(f"- **Erwartete Jahresproduktion:** {production_gwh} GWh")
        if fall_height and fall_height != "k.A.":
            lines.append(f"- **Fallhöhe:** {fall_height}")
        lines.append("")

    return "\n".join(lines)


def _format_pv_list(features: list[dict], title: str) -> str:
    """Formatiert PV-Grossanlagen als Markdown."""
    if not features:
        return f"## {title}\n\nKeine PV-Grossanlagen im angegebenen Umkreis gefunden."

    lines = [f"## {title}", f"\n**{len(features)} Anlage(n) gefunden**\n"]
    for feat in features:
        attrs = feat.get("attributes", {})
        name = attrs.get("projectname", "Unbekannt")
        mgmt = attrs.get("projectmanagement", "k.A.")
        power_mwp = attrs.get("power", "k.A.")
        annual_gwh = attrs.get("annualproduction", "k.A.")
        winter_gwh = attrs.get("winterproduction", "k.A.")
        status = attrs.get("statuscategory_de", "k.A.")
        elevation = attrs.get("elevation", "k.A.")
        website = attrs.get("projectweb", "")

        lines.append(f"### {name}")
        lines.append(f"- **Projektleitung:** {mgmt}")
        lines.append(f"- **Status:** {status}")
        if power_mwp != "k.A.":
            lines.append(f"- **Leistung:** {power_mwp} MWp")
        if annual_gwh != "k.A.":
            lines.append(f"- **Jahresproduktion:** {annual_gwh} GWh")
        if winter_gwh != "k.A.":
            lines.append(f"- **Winterproduktion:** {winter_gwh} GWh")
        if elevation != "k.A.":
            lines.append(f"- **Höhe über Meer:** {elevation} m")
        if website:
            lines.append(f"- **Website:** {website}")
        lines.append("")

    return "\n".join(lines)


def _format_energy_city(attrs: dict) -> str:
    """Formatiert eine Energiestadt als Markdown-Block."""
    name = attrs.get("name", "Unbekannt")
    score = attrs.get("punktezahl", "k.A.")
    since = attrs.get("energiestadtseit", "k.A.")
    if since and since != "k.A.":
        since = since[:4]  # Nur Jahreszahl
    residents = attrs.get("einwohner", "k.A.")
    if residents and residents != "k.A.":
        residents = f"{int(residents):,}".replace(",", "'")
    audits = attrs.get("anzahlaudits", "k.A.")
    consultant = attrs.get("berater", "k.A.")
    link = attrs.get("linkenergiestadtweb", "")

    lines = [
        f"### {name}",
        f"- **Energiestadt seit:** {since}",
        f"- **Punktezahl:** {score}%",
        f"- **Einwohner:** {residents}",
        f"- **Anzahl Audits:** {audits}",
        f"- **Berater:** {consultant}",
    ]
    if link:
        lines.append(f"- **Link:** {link}")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool 1: Elektrizitätsproduktionsanlagen
# ---------------------------------------------------------------------------

@mcp.tool(
    name="energy_find_power_plants",
    annotations={
        "title": "Elektrizitätsproduktionsanlagen suchen",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def energy_find_power_plants(params: PowerPlantInput) -> str:
    """Sucht nach Elektrizitätsproduktionsanlagen im Umkreis eines Standorts.

    Durchsucht den BFE-Layer 'Elektrizitätsproduktionsanlagen' (ch.bfe.elektrizitaetsproduktionsanlagen)
    via GeoAdmin REST API. Enthält alle Anlagentypen: Photovoltaik, Wasserkraft,
    Windkraft, Biomasse, Kernkraft, etc. Optionaler Filter für Anlagentyp.

    Args:
        params (PowerPlantInput): Standort (lat/lon), Radius, optionaler Kategorie-Filter.
            - lat (float): Breitengrad (45.0–48.0)
            - lon (float): Längengrad (5.5–10.7)
            - radius_m (int): Suchradius in Metern (500–50000, Standard: 5000)
            - category_filter (Optional[str]): Z. B. 'Photovoltaik', 'Wasserkraft', 'Wind'
            - response_format (str): 'markdown' oder 'json'

    Returns:
        str: Liste der gefundenen Anlagen mit Typ, Adresse, Leistung und Inbetriebnahme.
             Bei JSON: strukturiertes Dict mit allen Feldern.
    """
    client = _get_client()

    try:
        features = await query_geoadmin_layer(
            client, LAYER_POWER_PLANTS, params.lat, params.lon, params.radius_m
        )
    except ValueError as e:
        return f"Fehler bei der Abfrage: {e}"

    # Kategorie-Filter anwenden
    if params.category_filter:
        cf = params.category_filter.lower()
        features = [
            f for f in features
            if cf in f.get("attributes", {}).get("sub_category_de", "").lower()
            or cf in f.get("attributes", {}).get("main_category_de", "").lower()
        ]

    if params.response_format == ResponseFormat.JSON:
        return json.dumps(
            {
                "layer": LAYER_POWER_PLANTS,
                "location": {"lat": params.lat, "lon": params.lon},
                "radius_m": params.radius_m,
                "count": len(features),
                "category_filter": params.category_filter,
                "features": [f.get("attributes", {}) for f in features],
            },
            indent=2,
            ensure_ascii=False,
        )

    title = f"Elektrizitätsproduktionsanlagen im Umkreis von {params.radius_m / 1000:.0f} km"
    if params.category_filter:
        title += f" (Filter: {params.category_filter})"
    return _format_power_plant_list(features, title)


# ---------------------------------------------------------------------------
# Tool 2: Windenergieanlagen
# ---------------------------------------------------------------------------

@mcp.tool(
    name="energy_find_wind_turbines",
    annotations={
        "title": "Windenergieanlagen suchen",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def energy_find_wind_turbines(params: LocationInput) -> str:
    """Sucht nach Windenergieanlagen im Umkreis eines Standorts.

    Durchsucht den BFE-Layer 'Windenergieanlagen' (ch.bfe.windenergieanlagen) via GeoAdmin.
    Enthält Angaben zu Betreiber, Leistung, Hersteller, Modell und Jahresproduktion.

    Args:
        params (LocationInput): Standort und Suchparameter.
            - lat (float): Breitengrad (45.0–48.0)
            - lon (float): Längengrad (5.5–10.7)
            - radius_m (int): Suchradius in Metern (500–50000, Standard: 5000)
            - response_format (str): 'markdown' oder 'json'

    Returns:
        str: Liste der Windenergieanlagen mit Betreiber, Leistung, Turbinentyp und Website.
             Hinweis: Windenergieanlagen sind in der Schweiz hauptsächlich im Jura, Wallis
             und Mitteland anzutreffen. Für die ganze Schweiz radius_m=200000 verwenden
             (oder die Koordinaten anpassen).
    """
    client = _get_client()

    try:
        features = await query_geoadmin_layer(
            client, LAYER_WIND_TURBINES, params.lat, params.lon, params.radius_m
        )
    except ValueError as e:
        return f"Fehler bei der Abfrage: {e}"

    if params.response_format == ResponseFormat.JSON:
        return json.dumps(
            {
                "layer": LAYER_WIND_TURBINES,
                "location": {"lat": params.lat, "lon": params.lon},
                "radius_m": params.radius_m,
                "count": len(features),
                "features": [f.get("attributes", {}) for f in features],
            },
            indent=2,
            ensure_ascii=False,
        )

    title = f"Windenergieanlagen im Umkreis von {params.radius_m / 1000:.0f} km"
    return _format_wind_turbine_list(features, title)


# ---------------------------------------------------------------------------
# Tool 3: Wasserkraftwerke
# ---------------------------------------------------------------------------

@mcp.tool(
    name="energy_find_hydro_plants",
    annotations={
        "title": "Wasserkraftwerke suchen",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def energy_find_hydro_plants(params: LocationInput) -> str:
    """Sucht nach Wasserkraftwerken im Umkreis eines Standorts.

    Durchsucht den BFE-Layer 'Statistik Wasserkraft' (ch.bfe.statistik-wasserkraftanlagen).
    Enthält Laufwasserkraftwerke, Speicherkraftwerke und Pumpspeicher mit
    Leistungsdaten, Fallhöhe und erwarteter Jahresproduktion.

    Args:
        params (LocationInput): Standort und Suchparameter.
            - lat (float): Breitengrad (45.0–48.0)
            - lon (float): Längengrad (5.5–10.7)
            - radius_m (int): Suchradius in Metern (500–50000, Standard: 5000)
            - response_format (str): 'markdown' oder 'json'

    Returns:
        str: Liste der Wasserkraftwerke mit Name, Standort, Typ, Leistung und Produktion.
    """
    client = _get_client()

    try:
        features = await query_geoadmin_layer(
            client, LAYER_HYDRO_PLANTS, params.lat, params.lon, params.radius_m
        )
    except ValueError as e:
        return f"Fehler bei der Abfrage: {e}"

    if params.response_format == ResponseFormat.JSON:
        return json.dumps(
            {
                "layer": LAYER_HYDRO_PLANTS,
                "location": {"lat": params.lat, "lon": params.lon},
                "radius_m": params.radius_m,
                "count": len(features),
                "features": [f.get("attributes", {}) for f in features],
            },
            indent=2,
            ensure_ascii=False,
        )

    title = f"Wasserkraftwerke im Umkreis von {params.radius_m / 1000:.0f} km"
    return _format_hydro_plant_list(features, title)


# ---------------------------------------------------------------------------
# Tool 4: Photovoltaik-Grossanlagen
# ---------------------------------------------------------------------------

@mcp.tool(
    name="energy_find_pv_installations",
    annotations={
        "title": "Photovoltaik-Grossanlagen suchen",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def energy_find_pv_installations(params: LocationInput) -> str:
    """Sucht nach Photovoltaik-Grossanlagen im Umkreis eines Standorts.

    Durchsucht den BFE-Layer 'Photovoltaik-Grossanlagen' (ch.bfe.photovoltaik-grossanlagen).
    Enthält grosse PV-Projekte mit Leistung (MWp), Jahres- und Winterproduktion (GWh),
    Status (in Betrieb, geplant, zurückgezogen) und Projektkontakt.

    Args:
        params (LocationInput): Standort und Suchparameter.
            - lat (float): Breitengrad (45.0–48.0)
            - lon (float): Längengrad (5.5–10.7)
            - radius_m (int): Suchradius in Metern (500–50000, Standard: 5000)
            - response_format (str): 'markdown' oder 'json'

    Returns:
        str: Liste der PV-Grossanlagen mit Projektname, Leistung, Produktion und Status.
    """
    client = _get_client()

    try:
        features = await query_geoadmin_layer(
            client, LAYER_PV_LARGE, params.lat, params.lon, params.radius_m
        )
    except ValueError as e:
        return f"Fehler bei der Abfrage: {e}"

    if params.response_format == ResponseFormat.JSON:
        return json.dumps(
            {
                "layer": LAYER_PV_LARGE,
                "location": {"lat": params.lat, "lon": params.lon},
                "radius_m": params.radius_m,
                "count": len(features),
                "features": [f.get("attributes", {}) for f in features],
            },
            indent=2,
            ensure_ascii=False,
        )

    title = f"Photovoltaik-Grossanlagen im Umkreis von {params.radius_m / 1000:.0f} km"
    return _format_pv_list(features, title)


# ---------------------------------------------------------------------------
# Tool 5: Biogasanlagen
# ---------------------------------------------------------------------------

@mcp.tool(
    name="energy_find_biogas_plants",
    annotations={
        "title": "Biogasanlagen suchen",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def energy_find_biogas_plants(params: LocationInput) -> str:
    """Sucht nach Biogasanlagen im Umkreis eines Standorts.

    Durchsucht den BFE-Layer 'Biogasanlagen' (ch.bfe.biogasanlagen).
    Biogasanlagen nutzen organische Abfälle und Biomasse zur Energiegewinnung.

    Args:
        params (LocationInput): Standort und Suchparameter.
            - lat (float): Breitengrad (45.0–48.0)
            - lon (float): Längengrad (5.5–10.7)
            - radius_m (int): Suchradius in Metern (500–50000, Standard: 5000)
            - response_format (str): 'markdown' oder 'json'

    Returns:
        str: Liste der Biogasanlagen mit verfügbaren Attributen.
    """
    client = _get_client()

    try:
        features = await query_geoadmin_layer(
            client, LAYER_BIOGAS, params.lat, params.lon, params.radius_m
        )
    except ValueError as e:
        return f"Fehler bei der Abfrage: {e}"

    if not features:
        return f"## Biogasanlagen\n\nKeine Biogasanlagen im Umkreis von {params.radius_m / 1000:.0f} km gefunden."

    if params.response_format == ResponseFormat.JSON:
        return json.dumps(
            {
                "layer": LAYER_BIOGAS,
                "location": {"lat": params.lat, "lon": params.lon},
                "radius_m": params.radius_m,
                "count": len(features),
                "features": [f.get("attributes", {}) for f in features],
            },
            indent=2,
            ensure_ascii=False,
        )

    lines = [
        f"## Biogasanlagen im Umkreis von {params.radius_m / 1000:.0f} km",
        f"\n**{len(features)} Anlage(n) gefunden**\n",
    ]
    for feat in features:
        attrs = feat.get("attributes", {})
        label = attrs.get("label", attrs.get("name", "Unbekannt"))
        lines.append(f"- **{label}**")
        for key, val in attrs.items():
            if key not in ("label", "name") and val and val != "k.A.":
                lines.append(f"  - {key}: {val}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool 6: Energiestädte
# ---------------------------------------------------------------------------

@mcp.tool(
    name="energy_find_energy_cities",
    annotations={
        "title": "Energiestädte suchen",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def energy_find_energy_cities(params: EnergyCityInput) -> str:
    """Sucht nach Gemeinden mit dem Label «Energiestadt».

    Das Label «Energiestadt» (europäisch: «European Energy Award») zeichnet Gemeinden
    aus, die eine vorbildliche Energiepolitik verfolgen. Suche per Name oder Standort.

    Args:
        params (EnergyCityInput): Suchparameter.
            - name (Optional[str]): Gemeindename (z. B. 'Zürich')
            - lat/lon (Optional[float]): Standort für Umkreissuche
            - radius_m (int): Suchradius bei Standortsuche (Standard: 20 km)
            - response_format (str): 'markdown' oder 'json'

    Returns:
        str: Liste der Energiestädte mit Punktezahl, Label-Datum, Einwohnerzahl und Beratung.

    Beispiele:
        - Zürich: name='Zürich' → Detailinfo zur Stadt Zürich
        - Kanton Zürich: lat=47.35, lon=8.65, radius_m=50000 → alle Energiestädte im Kt. ZH
        - Alle Grossstädte: lat=47.0, lon=8.0, radius_m=100000 (Schweizzentrum)
    """
    client = _get_client()

    try:
        if params.name:
            features = await find_geoadmin_by_name(
                client, LAYER_ENERGY_CITIES, params.name, "name"
            )
        elif params.lat is not None and params.lon is not None:
            features = await query_geoadmin_layer(
                client, LAYER_ENERGY_CITIES, params.lat, params.lon, params.radius_m
            )
        else:
            return (
                "Bitte entweder einen Gemeindenamen (name) oder Koordinaten (lat/lon) angeben."
            )
    except ValueError as e:
        return f"Fehler bei der Abfrage: {e}"

    if not features:
        scope = params.name or f"Umkreis {params.radius_m / 1000:.0f} km"
        return f"## Energiestädte\n\nKeine Energiestadt gefunden für: {scope}"

    if params.response_format == ResponseFormat.JSON:
        return json.dumps(
            {
                "layer": LAYER_ENERGY_CITIES,
                "search": {"name": params.name, "lat": params.lat, "lon": params.lon},
                "count": len(features),
                "features": [f.get("attributes", {}) for f in features],
            },
            indent=2,
            ensure_ascii=False,
        )

    lines = [f"## Energiestädte", f"\n**{len(features)} Gemeinde(n) gefunden**\n"]
    for feat in features:
        lines.append(_format_energy_city(feat.get("attributes", {})))

    lines.append(
        "\n*Quelle: BFE / energiestadt.ch – Daten via GeoAdmin (ch.bfe.energiestaedte)*"
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool 7: Solareignung Dächer
# ---------------------------------------------------------------------------

@mcp.tool(
    name="energy_solar_potential",
    annotations={
        "title": "Solareignung Dächer abfragen",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def energy_solar_potential(params: LocationInput) -> str:
    """Fragt die Solareignung von Dächern für einen Standort ab.

    Durchsucht den BFE-Layer 'Solarenergie: Eignung Dächer' (ch.bfe.solarenergie-eignung-daecher).
    Dieser Layer enthält die Solareignungsklassen für Dachflächen in der ganzen Schweiz
    und ist besonders relevant für Entscheide über PV-Anlagen auf Schulhäusern und
    öffentlichen Gebäuden.

    Hinweis: Der Layer arbeitet mit Rasterdaten (Eignungsklassen pro Dachfläche).
    Bei einem kleinen Radius (< 500 m) sind möglicherweise keine Ergebnisse vorhanden;
    grössere Radien empfohlen.

    Args:
        params (LocationInput): Standort und Suchparameter.
            - lat (float): Breitengrad (45.0–48.0)
            - lon (float): Längengrad (5.5–10.7)
            - radius_m (int): Suchradius in Metern (min. 1000 empfohlen)
            - response_format (str): 'markdown' oder 'json'

    Returns:
        str: Solareignungsklassen der Dachflächen im Umkreis.
             Klassen: 1 (sehr gut geeignet) bis 5 (wenig geeignet).
             Zusätzliche Hinweise zur Nutzung des Solardachkatasters map.geo.admin.ch.
    """
    client = _get_client()
    # Für Solar-Raster etwas grösseren Radius verwenden
    effective_radius = max(params.radius_m, 2000)

    try:
        features = await query_geoadmin_layer(
            client, LAYER_SOLAR_ROOFS, params.lat, params.lon, effective_radius
        )
    except ValueError as e:
        return f"Fehler bei der Abfrage: {e}"

    coords_lv95 = wgs84_to_lv95(params.lat, params.lon)

    if params.response_format == ResponseFormat.JSON:
        return json.dumps(
            {
                "layer": LAYER_SOLAR_ROOFS,
                "location": {"lat": params.lat, "lon": params.lon},
                "lv95": {"e": round(coords_lv95[0]), "n": round(coords_lv95[1])},
                "radius_m": effective_radius,
                "count": len(features),
                "features": [f.get("attributes", {}) for f in features],
                "visualization": f"https://map.geo.admin.ch/?layers=ch.bfe.solarenergie-eignung-daecher&E={round(coords_lv95[0])}&N={round(coords_lv95[1])}&zoom=10",
            },
            indent=2,
            ensure_ascii=False,
        )

    map_url = (
        f"https://map.geo.admin.ch/?layers=ch.bfe.solarenergie-eignung-daecher"
        f"&E={round(coords_lv95[0])}&N={round(coords_lv95[1])}&zoom=10"
    )

    lines = [
        f"## Solareignung Dächer – Standort ({params.lat:.4f}°N, {params.lon:.4f}°E)",
        "",
        f"**Suchradius:** {effective_radius / 1000:.1f} km",
        f"**Ergebnisse:** {len(features)} Dachflächen-Einträge",
        "",
    ]

    if not features:
        lines.append(
            "Keine Eignungsdaten für diesen Standort gefunden. "
            "Mögliche Ursachen: Standort ausserhalb der Schweiz, "
            "oder Daten für diese Dachflächen noch nicht vorhanden."
        )
    else:
        lines.append("### Eignungsklassen der Dachflächen im Umkreis")
        lines.append("")
        lines.append("| Klasse | Bedeutung | Anzahl Flächen |")
        lines.append("|--------|-----------|----------------|")

        # Eignungsklassen zählen
        class_counts: dict[str, int] = {}
        for feat in features:
            attrs = feat.get("attributes", {})
            for key, val in attrs.items():
                if "class" in key.lower() or "klasse" in key.lower() or "eignung" in key.lower():
                    class_counts[str(val)] = class_counts.get(str(val), 0) + 1

        if class_counts:
            class_meanings = {
                "1": "Sehr gut geeignet",
                "2": "Gut geeignet",
                "3": "Mittelmässig geeignet",
                "4": "Wenig geeignet",
                "5": "Nicht geeignet",
            }
            for cls, count in sorted(class_counts.items()):
                meaning = class_meanings.get(cls, "Unbekannt")
                lines.append(f"| {cls} | {meaning} | {count} |")
        else:
            # Rohdaten anzeigen falls Feldnamen unbekannt
            sample = features[0].get("attributes", {}) if features else {}
            lines.append(f"| – | Rohdaten (erstes Objekt) | – |")
            for k, v in list(sample.items())[:5]:
                lines.append(f"| {k} | {v} | – |")

    lines.append("")
    lines.append(f"🗺️ **Solardachkataster visualisieren:** [{map_url}]({map_url})")
    lines.append("")
    lines.append(
        "*Quelle: BFE / swisstopo – Daten via GeoAdmin (ch.bfe.solarenergie-eignung-daecher)*"
    )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool 8: Vollständiges Energieprofil für einen Standort
# ---------------------------------------------------------------------------

@mcp.tool(
    name="energy_location_profile",
    annotations={
        "title": "Vollständiges Energieprofil für einen Standort",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def energy_location_profile(params: LocationInput) -> str:
    """Erstellt ein vollständiges Energieprofil für einen Standort.

    Aggregiert Daten aus mehreren BFE-Layern gleichzeitig:
    - Elektrizitätsproduktionsanlagen (alle Typen)
    - Windenergieanlagen
    - Wasserkraftwerke
    - PV-Grossanlagen
    - Energiestädte

    Ideal für Entscheidungsträger, die einen schnellen Überblick über die
    Energiesituation einer Region benötigen – z. B. für Berichte der
    Stadtverwaltung, KI-Fachgruppe-Demos oder Schulprojekte.

    Args:
        params (LocationInput): Standort und Suchparameter.
            - lat (float): Breitengrad (45.0–48.0)
            - lon (float): Längengrad (5.5–10.7)
            - radius_m (int): Suchradius in Metern (Standard: 5000)
            - response_format (str): 'markdown' oder 'json'

    Returns:
        str: Zusammenfassung mit Zählungen und Top-Ergebnissen aller Energiequellen.
             Enthält Gesamtleistungsschätzung und Links zur Visualisierung.
    """
    client = _get_client()
    import asyncio

    # Alle Layer parallel abfragen
    results = await asyncio.gather(
        query_geoadmin_layer(client, LAYER_POWER_PLANTS, params.lat, params.lon, params.radius_m),
        query_geoadmin_layer(client, LAYER_WIND_TURBINES, params.lat, params.lon, params.radius_m),
        query_geoadmin_layer(client, LAYER_HYDRO_PLANTS, params.lat, params.lon, params.radius_m),
        query_geoadmin_layer(client, LAYER_PV_LARGE, params.lat, params.lon, params.radius_m),
        query_geoadmin_layer(client, LAYER_ENERGY_CITIES, params.lat, params.lon, params.radius_m),
        return_exceptions=True,
    )

    power_plants = results[0] if not isinstance(results[0], Exception) else []
    wind_turbines = results[1] if not isinstance(results[1], Exception) else []
    hydro_plants = results[2] if not isinstance(results[2], Exception) else []
    pv_large = results[3] if not isinstance(results[3], Exception) else []
    energy_cities = results[4] if not isinstance(results[4], Exception) else []

    coords_lv95 = wgs84_to_lv95(params.lat, params.lon)

    if params.response_format == ResponseFormat.JSON:
        return json.dumps(
            {
                "location": {"lat": params.lat, "lon": params.lon},
                "radius_m": params.radius_m,
                "summary": {
                    "power_plants": len(power_plants),
                    "wind_turbines": len(wind_turbines),
                    "hydro_plants": len(hydro_plants),
                    "pv_large_installations": len(pv_large),
                    "energy_cities": len(energy_cities),
                },
                "power_plants": [f.get("attributes", {}) for f in power_plants[:10]],
                "wind_turbines": [f.get("attributes", {}) for f in wind_turbines],
                "hydro_plants": [f.get("attributes", {}) for f in hydro_plants[:10]],
                "pv_large": [f.get("attributes", {}) for f in pv_large],
                "energy_cities": [f.get("attributes", {}) for f in energy_cities],
            },
            indent=2,
            ensure_ascii=False,
        )

    # PV-Anlagen nach Subkategorie gruppieren
    pv_count = sum(
        1 for f in power_plants
        if "photovoltaik" in f.get("attributes", {}).get("sub_category_de", "").lower()
    )
    other_renewable = sum(
        1 for f in power_plants
        if "photovoltaik" not in f.get("attributes", {}).get("sub_category_de", "").lower()
    )

    map_url = (
        f"https://map.geo.admin.ch/?layers=ch.bfe.elektrizitaetsproduktionsanlagen"
        f",ch.bfe.windenergieanlagen,ch.bfe.statistik-wasserkraftanlagen"
        f"&E={round(coords_lv95[0])}&N={round(coords_lv95[1])}&zoom=10"
    )

    lines = [
        f"# Energieprofil – Umkreis {params.radius_m / 1000:.0f} km",
        f"**Standort:** {params.lat:.4f}°N, {params.lon:.4f}°E",
        "",
        "## 📊 Zusammenfassung",
        "",
        f"| Energiequelle | Anzahl Anlagen |",
        f"|---------------|----------------|",
        f"| ☀️ Photovoltaik (Einzelanlagen) | {pv_count} |",
        f"| ☀️ PV-Grossanlagen | {len(pv_large)} |",
        f"| 💨 Windenergie | {len(wind_turbines)} |",
        f"| 💧 Wasserkraft | {len(hydro_plants)} |",
        f"| 🌿 Übrige Erneuerbare | {other_renewable} |",
        f"| 🏙️ Energiestädte | {len(energy_cities)} |",
        "",
    ]

    # Energiestädte
    if energy_cities:
        lines.append("## 🏙️ Energiestädte")
        for feat in energy_cities[:3]:
            attrs = feat.get("attributes", {})
            name = attrs.get("name", "?")
            score = attrs.get("punktezahl", "?")
            since = str(attrs.get("energiestadtseit", "?"))[:4]
            lines.append(f"- **{name}** – {score}% Punkte (seit {since})")
        lines.append("")

    # Top Wasserkraftwerke
    if hydro_plants:
        lines.append("## 💧 Wasserkraftwerke (Top 3 nach Leistung)")
        sorted_hydro = sorted(
            hydro_plants,
            key=lambda f: float(f.get("attributes", {}).get("performanceturbinemaximum", 0) or 0),
            reverse=True,
        )
        for feat in sorted_hydro[:3]:
            attrs = feat.get("attributes", {})
            name = attrs.get("name", "?")
            mw = format_power_value(attrs.get("performanceturbinemaximum", ""), "MW")
            lines.append(f"- **{name}** – {mw}")
        lines.append("")

    # Windenergie
    if wind_turbines:
        lines.append("## 💨 Windenergieanlagen")
        for feat in wind_turbines[:5]:
            attrs = feat.get("attributes", {})
            name = attrs.get("fac_name", "?")
            power = format_power_value(attrs.get("fac_power", ""), "kW")
            lines.append(f"- **{name}** – {power}")
        lines.append("")

    # PV-Grossanlagen
    if pv_large:
        lines.append("## ☀️ PV-Grossanlagen")
        for feat in pv_large[:3]:
            attrs = feat.get("attributes", {})
            name = attrs.get("projectname", "?")
            status = attrs.get("statuscategory_de", "?")
            power = attrs.get("power", "?")
            lines.append(f"- **{name}** – {power} MWp ({status})")
        lines.append("")

    lines.append(f"🗺️ **Karte:** [{map_url}]({map_url})")
    lines.append("")
    lines.append("*Quelle: BFE / swisstopo – Daten via GeoAdmin REST API*")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool 9: BFE-Datensätze auf opendata.swiss suchen
# ---------------------------------------------------------------------------

@mcp.tool(
    name="energy_search_bfe_datasets",
    annotations={
        "title": "BFE-Datensätze auf opendata.swiss suchen",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def energy_search_bfe_datasets(params: SearchInput) -> str:
    """Sucht nach Datensätzen des Bundesamts für Energie (BFE) auf opendata.swiss.

    Durchsucht den CKAN-Katalog von opendata.swiss nach Datensätzen der Organisation
    'bundesamt-fur-energie-bfe'. Gibt Metadaten (Titel, Beschreibung, Formate,
    Links) zurück, keine Rohdaten.

    Args:
        params (SearchInput): Suchparameter.
            - query (str): Suchbegriff (leer = alle BFE-Datensätze)
            - limit (int): Anzahl Ergebnisse (1–50, Standard: 10)
            - offset (int): Offset für Paginierung (Standard: 0)
            - response_format (str): 'markdown' oder 'json'

    Returns:
        str: Liste der gefundenen Datensätze mit Titel, Beschreibung, Formaten und
             direktem Link auf opendata.swiss. Paginierung möglich via offset.
    """
    client = _get_client()

    try:
        result = await search_opendata_swiss(
            client,
            query=params.query,
            rows=params.limit,
            start=params.offset,
        )
    except ValueError as e:
        return f"Fehler bei der opendata.swiss-Abfrage: {e}"

    total = result["count"]
    datasets = result["results"]

    if params.response_format == ResponseFormat.JSON:
        simplified = []
        for ds in datasets:
            title = ds.get("title", {})
            if isinstance(title, dict):
                title = title.get("de", title.get("en", str(title)))
            simplified.append(
                {
                    "name": ds.get("name"),
                    "title": title,
                    "notes": str(ds.get("notes", ""))[:300],
                    "formats": list(
                        {r.get("format", "") for r in ds.get("resources", []) if r.get("format")}
                    ),
                    "url": f"https://opendata.swiss/de/dataset/{ds.get('name', '')}",
                }
            )
        return json.dumps(
            {
                "query": params.query,
                "total": total,
                "count": len(datasets),
                "offset": params.offset,
                "datasets": simplified,
            },
            indent=2,
            ensure_ascii=False,
        )

    search_desc = f'"{params.query}"' if params.query else "alle BFE-Datensätze"
    lines = [
        f"## BFE-Datensätze auf opendata.swiss – {search_desc}",
        f"\n**{total} Datensätze total**, zeige {params.offset + 1}–{params.offset + len(datasets)}\n",
    ]

    for ds in datasets:
        title = ds.get("title", {})
        if isinstance(title, dict):
            title = title.get("de", title.get("en", str(title)))

        name = ds.get("name", "")
        notes = ds.get("notes", "")
        if isinstance(notes, dict):
            notes = notes.get("de", notes.get("en", ""))
        notes_short = str(notes)[:250] + "…" if len(str(notes)) > 250 else str(notes)

        formats = sorted(
            {r.get("format", "").upper() for r in ds.get("resources", []) if r.get("format")}
        )
        formats_str = ", ".join(formats) if formats else "k.A."

        url = f"https://opendata.swiss/de/dataset/{name}"

        lines.append(f"### {title}")
        if notes_short:
            lines.append(f"{notes_short}")
        lines.append(f"- **Formate:** {formats_str}")
        lines.append(f"- **Link:** {url}")
        lines.append("")

    if params.offset + len(datasets) < total:
        next_offset = params.offset + params.limit
        lines.append(
            f"*Weitere Ergebnisse: `offset={next_offset}` für die nächste Seite verwenden.*"
        )

    lines.append("\n*Quelle: opendata.swiss CKAN API – Bundesamt für Energie BFE*")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool 10: Systemstatus
# ---------------------------------------------------------------------------

@mcp.tool(
    name="energy_check_status",
    annotations={
        "title": "API-Status prüfen",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def energy_check_status() -> str:
    """Prüft die Verfügbarkeit der GeoAdmin und opendata.swiss APIs.

    Führt einen leichtgewichtigen Test-Ping auf beide APIs durch und
    gibt den Status zurück. Nützlich zur Diagnose bei unerwartetem Verhalten.

    Returns:
        str: Status-Bericht beider APIs mit Antwortzeiten und verfügbaren Layern.
    """
    import time

    client = _get_client()
    results = {}

    # GeoAdmin Test
    start = time.monotonic()
    try:
        data = await client.get(
            f"{GEOADMIN_BASE}/find",
            params={
                "layer": LAYER_ENERGY_CITIES,
                "searchText": "Zürich",
                "searchField": "name",
                "lang": "de",
                "f": "json",
            },
        )
        elapsed = time.monotonic() - start
        count = len(data.get("results", []))
        results["geoadmin"] = {
            "status": "✅ Verfügbar",
            "response_time_ms": round(elapsed * 1000),
            "test": f"Energiestädte-Layer → {count} Ergebnis(se) für 'Zürich'",
        }
    except Exception as e:
        results["geoadmin"] = {"status": f"❌ Fehler: {e}", "response_time_ms": -1}

    # opendata.swiss Test
    start = time.monotonic()
    try:
        data = await search_opendata_swiss(client, query="solar", rows=1)
        elapsed = time.monotonic() - start
        results["opendata_swiss"] = {
            "status": "✅ Verfügbar",
            "response_time_ms": round(elapsed * 1000),
            "test": f"BFE-Katalog → {data['count']} Datensätze total",
        }
    except Exception as e:
        results["opendata_swiss"] = {"status": f"❌ Fehler: {e}", "response_time_ms": -1}

    lines = [
        "## Swiss Energy MCP – API-Status",
        "",
        f"### GeoAdmin REST API (api3.geo.admin.ch)",
        f"- Status: {results['geoadmin']['status']}",
        f"- Antwortzeit: {results['geoadmin']['response_time_ms']} ms",
        f"- Test: {results['geoadmin'].get('test', '–')}",
        "",
        f"### opendata.swiss CKAN API",
        f"- Status: {results['opendata_swiss']['status']}",
        f"- Antwortzeit: {results['opendata_swiss']['response_time_ms']} ms",
        f"- Test: {results['opendata_swiss'].get('test', '–')}",
        "",
        "### Verfügbare BFE-Layer (GeoAdmin)",
        f"- `{LAYER_POWER_PLANTS}` – Alle Elektrizitätsproduktionsanlagen",
        f"- `{LAYER_WIND_TURBINES}` – Windenergieanlagen",
        f"- `{LAYER_HYDRO_PLANTS}` – Statistik Wasserkraft",
        f"- `{LAYER_PV_LARGE}` – Photovoltaik-Grossanlagen",
        f"- `{LAYER_SOLAR_ROOFS}` – Solarenergie: Eignung Dächer",
        f"- `{LAYER_ENERGY_CITIES}` – Energiestädte",
        f"- `{LAYER_BIOGAS}` – Biogasanlagen",
        "",
        "*Alle APIs sind auth-frei und benötigen keinen API-Key.*",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Einstiegspunkt
# ---------------------------------------------------------------------------

def main() -> None:
    """Startet den Swiss Energy MCP Server."""
    transport = os.environ.get("MCP_TRANSPORT", "stdio")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        stream=sys.stderr,
    )

    if transport == "streamable_http":
        port = int(os.environ.get("PORT", "8000"))
        logger.info("Swiss Energy MCP startet (Streamable HTTP, Port %d)", port)
        mcp.run(transport="streamable_http", port=port)
    else:
        logger.info("Swiss Energy MCP startet (stdio)")
        mcp.run()


if __name__ == "__main__":
    main()
