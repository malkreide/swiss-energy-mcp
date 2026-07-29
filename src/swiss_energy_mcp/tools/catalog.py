"""Catalogue tools: opendata.swiss dataset search and API status check."""

from __future__ import annotations

import time

from mcp.server.mcpserver import Context, MCPServer

from ..api_client import (
    API_GEOADMIN,
    API_OPENDATA,
    GEOADMIN_BASE,
    LAYER_CATALOG,
    LAYER_ENERGY_CITIES,
    LICENSE_OGD,
    SOURCE_OPENDATA,
    search_opendata_swiss,
)
from ..models import ApiStatus, EnergyResponse, Provenance, SearchInput, StatusResponse
from ._common import get_client

_READ_ONLY = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": True,
}


def _localized(value: object) -> str:
    if isinstance(value, dict):
        return str(value.get("de", value.get("en", "")))
    return str(value or "")


def register(mcp: MCPServer) -> None:
    """Register the catalogue tools on the server."""

    @mcp.tool(
        name="energy_search_bfe_datasets",
        description=(
            "Durchsucht den opendata.swiss-Katalog nach Datensätzen des Bundesamts "
            "für Energie (BFE).\n\n"
            "<use_case>Auffinden von BFE-Rohdaten und Statistiken, Datenrecherche "
            "jenseits der Geo-Layer.</use_case>\n"
            "<important_notes>Liefert Metadaten (Titel, Beschreibung, Formate, Link) — "
            "keine Rohdaten. Volltextsuche deckt nur Metadaten ab. Paginierung über "
            "offset.</important_notes>\n"
            "<example>query='wasserkraft', limit=10, offset=0</example>"
        ),
        annotations={"title": "BFE-Datensätze suchen", **_READ_ONLY},
    )
    async def energy_search_bfe_datasets(params: SearchInput, ctx: Context) -> EnergyResponse:
        """Search the opendata.swiss catalogue for BFE datasets."""
        client = get_client(ctx)
        await ctx.info("energy_search_bfe_datasets", query=params.query)
        result = await search_opendata_swiss(
            client, query=params.query, rows=params.limit, start=params.offset
        )
        total = result["count"]
        datasets = result["results"]

        simplified: list[dict] = []
        for ds in datasets:
            formats = sorted(
                {r.get("format", "").upper() for r in ds.get("resources", []) if r.get("format")}
            )
            simplified.append(
                {
                    "name": ds.get("name"),
                    "title": _localized(ds.get("title")),
                    "notes": _localized(ds.get("notes"))[:300],
                    "formats": formats,
                    "url": f"https://opendata.swiss/de/dataset/{ds.get('name', '')}",
                }
            )

        scope = f'"{params.query}"' if params.query else "alle BFE-Datensätze"
        lines = [
            f"## BFE-Datensätze auf opendata.swiss – {scope}",
            f"\n**{total} Datensätze total**, "
            f"zeige {params.offset + 1}–{params.offset + len(datasets)}\n",
        ]
        for ds in simplified:
            lines.append(f"### {ds['title']}")
            if ds["notes"]:
                lines.append(ds["notes"])
            lines.append(f"- **Formate:** {', '.join(ds['formats']) or 'k.A.'}")
            lines.append(f"- **Link:** {ds['url']}")
            lines.append("")
        if params.offset + len(datasets) < total:
            lines.append(f"*Weitere Ergebnisse mit offset={params.offset + params.limit}.*")
        lines.append(f"\n*Quelle: {API_OPENDATA} – {SOURCE_OPENDATA}*")

        return EnergyResponse(
            source=SOURCE_OPENDATA,
            license=LICENSE_OGD,
            provenance=Provenance(layer="organization:bundesamt-fur-energie-bfe", api=API_OPENDATA),
            match_type="exact" if datasets else "none",
            count=len(datasets),
            results=simplified,
            summary="\n".join(lines),
            notes=(
                None
                if datasets
                else f"Keine BFE-Datensätze für '{params.query}'. Versuche einen "
                "anderen Suchbegriff (z. B. 'solar', 'windenergie') oder eine leere Suche."
            ),
        )

    @mcp.tool(
        name="energy_check_status",
        description=(
            "Prüft die Verfügbarkeit der GeoAdmin- und opendata.swiss-APIs.\n\n"
            "<use_case>Diagnose bei unerwartetem Verhalten, Monitoring.</use_case>\n"
            "<important_notes>Führt zwei leichtgewichtige Test-Requests aus.</important_notes>"
        ),
        annotations={
            "title": "API-Status prüfen",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": True,
        },
    )
    async def energy_check_status(ctx: Context) -> StatusResponse:
        """Check availability of the upstream APIs."""
        client = get_client(ctx)
        await ctx.info("energy_check_status")
        apis: list[ApiStatus] = []

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
            apis.append(
                ApiStatus(
                    name=API_GEOADMIN,
                    available=True,
                    response_time_ms=round((time.monotonic() - start) * 1000),
                    detail=f"{len(data.get('results', []))} Treffer für Testabfrage",
                )
            )
        except ValueError as exc:
            apis.append(
                ApiStatus(
                    name=API_GEOADMIN,
                    available=False,
                    response_time_ms=-1,
                    detail=str(exc),
                )
            )

        start = time.monotonic()
        try:
            data = await search_opendata_swiss(client, query="solar", rows=1)
            apis.append(
                ApiStatus(
                    name=API_OPENDATA,
                    available=True,
                    response_time_ms=round((time.monotonic() - start) * 1000),
                    detail=f"{data['count']} BFE-Datensätze im Katalog",
                )
            )
        except ValueError as exc:
            apis.append(
                ApiStatus(
                    name=API_OPENDATA,
                    available=False,
                    response_time_ms=-1,
                    detail=str(exc),
                )
            )

        lines = ["## Swiss Energy MCP – API-Status", ""]
        for api in apis:
            mark = "✅" if api.available else "❌"
            lines.append(f"### {api.name}")
            lines.append(f"- Status: {mark} ({api.response_time_ms} ms)")
            lines.append(f"- Detail: {api.detail}")
            lines.append("")
        return StatusResponse(
            source=f"{SOURCE_OPENDATA} / swisstopo",
            apis=apis,
            layers=sorted(LAYER_CATALOG),
            summary="\n".join(lines),
        )
