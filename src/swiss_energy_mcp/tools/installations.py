"""Tools for locating energy-production installations (power, wind, hydro, PV, biogas)."""

from __future__ import annotations

from mcp.server.mcpserver import Context, MCPServer

from ..api_client import (
    API_GEOADMIN,
    LAYER_BIOGAS,
    LAYER_HYDRO_PLANTS,
    LAYER_POWER_PLANTS,
    LAYER_PV_LARGE,
    LAYER_WIND_TURBINES,
    LICENSE_OGD,
    SOURCE_GEOADMIN,
    query_geoadmin_layer,
)
from ..formatting import (
    format_biogas_plants,
    format_hydro_plants,
    format_power_plants,
    format_pv_plants,
    format_wind_turbines,
)
from ..models import EnergyResponse, LocationInput, PowerPlantInput
from ._common import get_client, make_response, radius_hint

_READ_ONLY = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": True,
}


def register(mcp: MCPServer) -> None:
    """Register all installation-search tools on the server."""

    @mcp.tool(
        name="energy_find_power_plants",
        description=(
            "Sucht Elektrizitätsproduktionsanlagen aller Typen (Photovoltaik, "
            "Wasserkraft, Wind, Biomasse, Kernkraft) im Umkreis eines Standorts.\n\n"
            "<use_case>Standortanalysen, politische und journalistische Recherche, "
            "Schul- und Verwaltungsprojekte zur lokalen Stromproduktion.</use_case>\n"
            "<important_notes>Quelle: BFE-Layer ch.bfe.elektrizitaetsproduktionsanlagen. "
            "Optionaler category_filter grenzt auf einen Anlagentyp ein. Liefert max. "
            "201 Treffer pro Aufruf.</important_notes>\n"
            "<example>lat=46.948, lon=7.447, radius_m=20000, "
            "category_filter='Photovoltaik'</example>"
        ),
        annotations={"title": "Elektrizitätsproduktionsanlagen suchen", **_READ_ONLY},
    )
    async def energy_find_power_plants(params: PowerPlantInput, ctx: Context) -> EnergyResponse:
        """Find electricity-production plants near a location."""
        client = get_client(ctx)
        await ctx.info("energy_find_power_plants", radius_m=params.radius_m)
        features = await query_geoadmin_layer(
            client, LAYER_POWER_PLANTS, params.lat, params.lon, params.radius_m
        )
        if params.category_filter:
            needle = params.category_filter.lower()
            features = [
                f
                for f in features
                if needle in f.get("attributes", {}).get("sub_category_de", "").lower()
                or needle in f.get("attributes", {}).get("main_category_de", "").lower()
            ]
        title = f"Elektrizitätsproduktionsanlagen im Umkreis von {params.radius_m / 1000:.0f} km"
        if params.category_filter:
            title += f" (Filter: {params.category_filter})"
        summary = (
            format_power_plants(features, title)
            if features
            else f"## {title}\n\nKeine Anlagen im angegebenen Umkreis gefunden."
        )
        return make_response(
            features,
            source=SOURCE_GEOADMIN,
            license=LICENSE_OGD,
            layer=LAYER_POWER_PLANTS,
            api=API_GEOADMIN,
            summary=summary,
            empty_note=radius_hint("Anlagen", params.radius_m),
        )

    @mcp.tool(
        name="energy_find_wind_turbines",
        description=(
            "Sucht Windenergieanlagen im Umkreis eines Standorts inkl. Betreiber, "
            "Hersteller, Modell, Nabenhöhe und Leistung.\n\n"
            "<use_case>Recherche zu Windkraft-Standorten, regionale Energieplanung.</use_case>\n"
            "<important_notes>Quelle: ch.bfe.windenergieanlagen. Windkraft konzentriert "
            "sich auf Jura, Wallis und Mittelland — für landesweite Suchen radius_m bis "
            "50000 m wählen oder die Koordinaten anpassen.</important_notes>\n"
            "<example>lat=47.22, lon=7.05, radius_m=30000</example>"
        ),
        annotations={"title": "Windenergieanlagen suchen", **_READ_ONLY},
    )
    async def energy_find_wind_turbines(params: LocationInput, ctx: Context) -> EnergyResponse:
        """Find wind turbines near a location."""
        client = get_client(ctx)
        await ctx.info("energy_find_wind_turbines", radius_m=params.radius_m)
        features = await query_geoadmin_layer(
            client, LAYER_WIND_TURBINES, params.lat, params.lon, params.radius_m
        )
        title = f"Windenergieanlagen im Umkreis von {params.radius_m / 1000:.0f} km"
        summary = (
            format_wind_turbines(features, title)
            if features
            else f"## {title}\n\nKeine Windenergieanlagen im angegebenen Umkreis gefunden."
        )
        return make_response(
            features,
            source=SOURCE_GEOADMIN,
            license=LICENSE_OGD,
            layer=LAYER_WIND_TURBINES,
            api=API_GEOADMIN,
            summary=summary,
            empty_note=radius_hint("Windenergieanlagen", params.radius_m),
        )

    @mcp.tool(
        name="energy_find_hydro_plants",
        description=(
            "Sucht Wasserkraftwerke (Lauf-, Speicher-, Pumpspeicher) im Umkreis eines "
            "Standorts inkl. Leistung, Fallhöhe und erwarteter Jahresproduktion.\n\n"
            "<use_case>Analyse der regionalen Wasserkraft, Infrastruktur-Recherche.</use_case>\n"
            "<important_notes>Quelle: ch.bfe.statistik-wasserkraftanlagen.</important_notes>\n"
            "<example>lat=47.05, lon=8.31, radius_m=30000</example>"
        ),
        annotations={"title": "Wasserkraftwerke suchen", **_READ_ONLY},
    )
    async def energy_find_hydro_plants(params: LocationInput, ctx: Context) -> EnergyResponse:
        """Find hydropower plants near a location."""
        client = get_client(ctx)
        await ctx.info("energy_find_hydro_plants", radius_m=params.radius_m)
        features = await query_geoadmin_layer(
            client, LAYER_HYDRO_PLANTS, params.lat, params.lon, params.radius_m
        )
        title = f"Wasserkraftwerke im Umkreis von {params.radius_m / 1000:.0f} km"
        summary = (
            format_hydro_plants(features, title)
            if features
            else f"## {title}\n\nKeine Wasserkraftwerke im angegebenen Umkreis gefunden."
        )
        return make_response(
            features,
            source=SOURCE_GEOADMIN,
            license=LICENSE_OGD,
            layer=LAYER_HYDRO_PLANTS,
            api=API_GEOADMIN,
            summary=summary,
            empty_note=radius_hint("Wasserkraftwerke", params.radius_m),
        )

    @mcp.tool(
        name="energy_find_pv_installations",
        description=(
            "Sucht Photovoltaik-Grossanlagen im Umkreis eines Standorts inkl. Leistung "
            "(MWp), Jahres- und Winterproduktion sowie Projektstatus.\n\n"
            "<use_case>Recherche zu PV-Grossprojekten, Energieplanung.</use_case>\n"
            "<important_notes>Quelle: ch.bfe.photovoltaik-grossanlagen. Erfasst nur "
            "Grossanlagen — Einzel-PV erscheint in energy_find_power_plants.</important_notes>\n"
            "<example>lat=46.2, lon=7.5, radius_m=40000</example>"
        ),
        annotations={"title": "Photovoltaik-Grossanlagen suchen", **_READ_ONLY},
    )
    async def energy_find_pv_installations(params: LocationInput, ctx: Context) -> EnergyResponse:
        """Find large PV installations near a location."""
        client = get_client(ctx)
        await ctx.info("energy_find_pv_installations", radius_m=params.radius_m)
        features = await query_geoadmin_layer(
            client, LAYER_PV_LARGE, params.lat, params.lon, params.radius_m
        )
        title = f"Photovoltaik-Grossanlagen im Umkreis von {params.radius_m / 1000:.0f} km"
        summary = (
            format_pv_plants(features, title)
            if features
            else f"## {title}\n\nKeine PV-Grossanlagen im angegebenen Umkreis gefunden."
        )
        return make_response(
            features,
            source=SOURCE_GEOADMIN,
            license=LICENSE_OGD,
            layer=LAYER_PV_LARGE,
            api=API_GEOADMIN,
            summary=summary,
            empty_note=radius_hint("PV-Grossanlagen", params.radius_m),
        )

    @mcp.tool(
        name="energy_find_biogas_plants",
        description=(
            "Sucht Biogasanlagen im Umkreis eines Standorts. Biogasanlagen erzeugen "
            "Energie aus organischen Abfällen und Biomasse.\n\n"
            "<use_case>Recherche zu Biomasse-Energie, regionale Kreislaufwirtschaft.</use_case>\n"
            "<important_notes>Quelle: ch.bfe.biogasanlagen.</important_notes>\n"
            "<example>lat=47.4, lon=8.5, radius_m=25000</example>"
        ),
        annotations={"title": "Biogasanlagen suchen", **_READ_ONLY},
    )
    async def energy_find_biogas_plants(params: LocationInput, ctx: Context) -> EnergyResponse:
        """Find biogas plants near a location."""
        client = get_client(ctx)
        await ctx.info("energy_find_biogas_plants", radius_m=params.radius_m)
        features = await query_geoadmin_layer(
            client, LAYER_BIOGAS, params.lat, params.lon, params.radius_m
        )
        title = f"Biogasanlagen im Umkreis von {params.radius_m / 1000:.0f} km"
        summary = (
            format_biogas_plants(features, title)
            if features
            else f"## {title}\n\nKeine Biogasanlagen im angegebenen Umkreis gefunden."
        )
        return make_response(
            features,
            source=SOURCE_GEOADMIN,
            license=LICENSE_OGD,
            layer=LAYER_BIOGAS,
            api=API_GEOADMIN,
            summary=summary,
            empty_note=radius_hint("Biogasanlagen", params.radius_m),
        )
