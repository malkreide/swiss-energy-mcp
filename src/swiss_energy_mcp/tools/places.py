"""Place-centric tools: solar roof potential, Energiestadt lookup, location profile."""

from __future__ import annotations

import asyncio

from mcp.server.mcpserver import Context, MCPServer

from ..api_client import (
    API_GEOADMIN,
    LAYER_ENERGY_CITIES,
    LAYER_HYDRO_PLANTS,
    LAYER_POWER_PLANTS,
    LAYER_PV_LARGE,
    LAYER_SOLAR_ROOFS,
    LAYER_WIND_TURBINES,
    LICENSE_OGD,
    SOURCE_GEOADMIN,
    find_geoadmin_by_name,
    query_geoadmin_layer,
    wgs84_to_lv95,
)
from ..formatting import format_energy_cities, format_power_value
from ..models import EnergyCityInput, EnergyResponse, LocationInput, Provenance
from ._common import get_client, make_response, radius_hint

_READ_ONLY = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": True,
}

_SOLAR_CLASS_MEANING = {
    "1": "Sehr gut geeignet",
    "2": "Gut geeignet",
    "3": "Mittelmässig geeignet",
    "4": "Wenig geeignet",
    "5": "Nicht geeignet",
}


def register(mcp: MCPServer) -> None:
    """Register the place-centric tools on the server."""

    @mcp.tool(
        name="energy_solar_potential",
        description=(
            "Fragt die Solareignung von Dächern für einen Standort ab.\n\n"
            "<use_case>Entscheide über PV-Anlagen auf Schulhäusern und öffentlichen "
            "Gebäuden, Solarpotenzial-Analysen.</use_case>\n"
            "<important_notes>Quelle: ch.bfe.solarenergie-eignung-daecher (Rasterdaten). "
            "Kleine Radien liefern evtl. keine Treffer; der Radius wird intern auf "
            "mindestens 2000 m angehoben. Eignungsklassen: 1 (sehr gut) bis 5 (nicht "
            "geeignet).</important_notes>\n"
            "<example>lat=47.37, lon=8.54, radius_m=3000</example>"
        ),
        annotations={"title": "Solareignung Dächer abfragen", **_READ_ONLY},
    )
    async def energy_solar_potential(params: LocationInput, ctx: Context) -> EnergyResponse:
        """Query roof solar suitability near a location."""
        client = get_client(ctx)
        effective_radius = max(params.radius_m, 2000)
        await ctx.info("energy_solar_potential", radius_m=effective_radius)
        features = await query_geoadmin_layer(
            client, LAYER_SOLAR_ROOFS, params.lat, params.lon, effective_radius
        )
        e, n = wgs84_to_lv95(params.lat, params.lon)
        map_url = (
            f"https://map.geo.admin.ch/?layers=ch.bfe.solarenergie-eignung-daecher"
            f"&E={round(e)}&N={round(n)}&zoom=10"
        )
        title = f"Solareignung Dächer – Standort ({params.lat:.4f}°N, {params.lon:.4f}°E)"
        lines = [
            f"## {title}",
            "",
            f"**Suchradius:** {effective_radius / 1000:.1f} km",
            f"**Ergebnisse:** {len(features)} Dachflächen-Einträge",
            "",
        ]
        if features:
            class_counts: dict[str, int] = {}
            for feat in features:
                for key, val in feat.get("attributes", {}).items():
                    if any(k in key.lower() for k in ("class", "klasse", "eignung")):
                        class_counts[str(val)] = class_counts.get(str(val), 0) + 1
            if class_counts:
                lines.append("| Klasse | Bedeutung | Anzahl Flächen |")
                lines.append("|--------|-----------|----------------|")
                for cls, count in sorted(class_counts.items()):
                    meaning = _SOLAR_CLASS_MEANING.get(cls, "Unbekannt")
                    lines.append(f"| {cls} | {meaning} | {count} |")
        else:
            lines.append(
                "Keine Eignungsdaten für diesen Standort gefunden. Mögliche Ursachen: "
                "Standort ausserhalb der Schweiz oder Daten noch nicht erfasst."
            )
        lines.append("")
        lines.append(f"🗺️ Solardachkataster: [{map_url}]({map_url})")
        lines.append(f"\n*Quelle: {SOURCE_GEOADMIN}*")

        return make_response(
            features,
            source=SOURCE_GEOADMIN,
            license=LICENSE_OGD,
            layer=LAYER_SOLAR_ROOFS,
            api=API_GEOADMIN,
            summary="\n".join(lines),
            empty_note=(
                "Keine Solareignungsdaten gefunden. Versuche einen grösseren Radius "
                "oder prüfe, ob der Standort in der Schweiz liegt."
            ),
        )

    @mcp.tool(
        name="energy_find_energy_cities",
        description=(
            "Sucht Gemeinden mit dem Label «Energiestadt» per Name oder Standort.\n\n"
            "<use_case>Vergleich der Energiepolitik von Gemeinden, kommunale "
            "Recherche.</use_case>\n"
            "<important_notes>Quelle: ch.bfe.energiestaedte. Entweder name ODER lat/lon "
            "angeben — nicht beides leer lassen.</important_notes>\n"
            "<example>name='Zürich'  |  lat=47.35, lon=8.65, radius_m=50000</example>"
        ),
        annotations={"title": "Energiestädte suchen", **_READ_ONLY},
    )
    async def energy_find_energy_cities(params: EnergyCityInput, ctx: Context) -> EnergyResponse:
        """Find 'Energiestadt'-labelled municipalities by name or location."""
        client = get_client(ctx)
        if params.name:
            await ctx.info("energy_find_energy_cities", mode="name")
            features = await find_geoadmin_by_name(client, LAYER_ENERGY_CITIES, params.name, "name")
            empty_note = (
                f"Keine Energiestadt mit dem Namen '{params.name}' gefunden. "
                f"Prüfe die Schreibweise oder suche per lat/lon im Umkreis."
            )
            scope = params.name
        elif params.lat is not None and params.lon is not None:
            await ctx.info("energy_find_energy_cities", mode="location")
            features = await query_geoadmin_layer(
                client, LAYER_ENERGY_CITIES, params.lat, params.lon, params.radius_m
            )
            empty_note = radius_hint("Energiestädte", params.radius_m)
            scope = f"Umkreis {params.radius_m / 1000:.0f} km"
        else:
            raise ValueError(
                "Bitte entweder einen Gemeindenamen (name) oder Koordinaten (lat und lon) angeben."
            )

        title = f"Energiestädte – {scope}"
        summary = (
            format_energy_cities(features, title)
            + f"\n*Quelle: {SOURCE_GEOADMIN} / energiestadt.ch*"
            if features
            else f"## {title}\n\nKeine Energiestadt gefunden."
        )
        return make_response(
            features,
            source=SOURCE_GEOADMIN,
            license=LICENSE_OGD,
            layer=LAYER_ENERGY_CITIES,
            api=API_GEOADMIN,
            summary=summary,
            empty_note=empty_note,
        )

    @mcp.tool(
        name="energy_location_profile",
        description=(
            "Erstellt ein vollständiges Energieprofil für einen Standort und aggregiert "
            "dafür fünf BFE-Layer (Produktionsanlagen, Wind, Wasser, PV-Gross, "
            "Energiestädte) in einem einzigen Aufruf.\n\n"
            "<use_case>Schneller Gesamtüberblick für Berichte der Stadtverwaltung, "
            "Standortentscheide und Demos — beantwortet die Anchor-Frage in einem "
            "Aufruf.</use_case>\n"
            "<important_notes>Aggregiert mehrere parallele API-Calls; typische Laufzeit "
            "unter 5 s. Quelle: GeoAdmin / BFE.</important_notes>\n"
            "<example>lat=47.05, lon=8.31, radius_m=20000</example>"
        ),
        annotations={"title": "Vollständiges Energieprofil", **_READ_ONLY},
    )
    async def energy_location_profile(params: LocationInput, ctx: Context) -> EnergyResponse:
        """Build a combined energy profile for a location."""
        client = get_client(ctx)
        await ctx.info("energy_location_profile", radius_m=params.radius_m)
        await ctx.report_progress(0.0, 1.0, "Energie-Layer werden abgefragt")

        layers = (
            LAYER_POWER_PLANTS,
            LAYER_WIND_TURBINES,
            LAYER_HYDRO_PLANTS,
            LAYER_PV_LARGE,
            LAYER_ENERGY_CITIES,
        )
        gathered = await asyncio.gather(
            *(
                query_geoadmin_layer(client, layer, params.lat, params.lon, params.radius_m)
                for layer in layers
            ),
            return_exceptions=True,
        )
        power, wind, hydro, pv, cities = (
            result if not isinstance(result, BaseException) else [] for result in gathered
        )
        await ctx.report_progress(1.0, 1.0, "Profil zusammengestellt")

        pv_single = sum(
            1
            for f in power
            if "photovoltaik" in f.get("attributes", {}).get("sub_category_de", "").lower()
        )
        other_renewable = len(power) - pv_single
        total = len(power) + len(wind) + len(hydro) + len(pv) + len(cities)

        e, n = wgs84_to_lv95(params.lat, params.lon)
        map_url = (
            "https://map.geo.admin.ch/?layers=ch.bfe.elektrizitaetsproduktionsanlagen,"
            "ch.bfe.windenergieanlagen,ch.bfe.statistik-wasserkraftanlagen"
            f"&E={round(e)}&N={round(n)}&zoom=10"
        )
        lines = [
            f"# Energieprofil – Umkreis {params.radius_m / 1000:.0f} km",
            f"**Standort:** {params.lat:.4f}°N, {params.lon:.4f}°E",
            "",
            "| Energiequelle | Anzahl Anlagen |",
            "|---------------|----------------|",
            f"| Photovoltaik (Einzelanlagen) | {pv_single} |",
            f"| PV-Grossanlagen | {len(pv)} |",
            f"| Windenergie | {len(wind)} |",
            f"| Wasserkraft | {len(hydro)} |",
            f"| Übrige Produktionsanlagen | {other_renewable} |",
            f"| Energiestädte | {len(cities)} |",
            "",
        ]
        if hydro:
            top = sorted(
                hydro,
                key=lambda f: float(
                    f.get("attributes", {}).get("performanceturbinemaximum", 0) or 0
                ),
                reverse=True,
            )[:3]
            lines.append("## Wasserkraftwerke (Top 3 nach Leistung)")
            for feat in top:
                attrs = feat.get("attributes", {})
                mw = format_power_value(attrs.get("performanceturbinemaximum", ""), "MW")
                lines.append(f"- **{attrs.get('name', '?')}** – {mw}")
            lines.append("")
        lines.append(f"🗺️ Karte: [{map_url}]({map_url})")
        lines.append(f"\n*Quelle: {SOURCE_GEOADMIN} via GeoAdmin REST API*")

        results = [
            {"category": "power_plants", "count": len(power)},
            {"category": "wind_turbines", "count": len(wind)},
            {"category": "hydro_plants", "count": len(hydro)},
            {"category": "pv_large", "count": len(pv)},
            {"category": "energy_cities", "count": len(cities)},
        ]
        return EnergyResponse(
            source=SOURCE_GEOADMIN,
            license=LICENSE_OGD,
            provenance=Provenance(layer="multiple (5 BFE layers)", api=API_GEOADMIN),
            match_type="exact" if total else "none",
            count=total,
            results=results,
            summary="\n".join(lines),
            notes=None if total else radius_hint("Energieanlagen", params.radius_m),
        )
