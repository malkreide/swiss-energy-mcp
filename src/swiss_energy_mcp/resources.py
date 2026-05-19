"""MCP resources and prompts.

Beyond tools, the server exposes one Resource (the static BFE layer catalogue)
and one Prompt (a guided site-assessment template), so all three MCP primitives
are used (ARCH-008).
"""

from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP

from .api_client import API_GEOADMIN, LAYER_CATALOG, LICENSE_OGD, SOURCE_GEOADMIN


def register_capabilities(mcp: FastMCP) -> None:
    """Register the layer-catalogue resource and the site-assessment prompt."""

    @mcp.resource(
        "energy://layers",
        name="bfe-layer-catalogue",
        title="BFE layer catalogue",
        description="Static catalogue of the BFE GeoAdmin layers this server queries.",
        mime_type="application/json",
    )
    def bfe_layers() -> str:
        """Return the BFE layer catalogue as JSON."""
        return json.dumps(
            {
                "source": SOURCE_GEOADMIN,
                "api": API_GEOADMIN,
                "license": LICENSE_OGD,
                "layers": [
                    {"id": layer_id, "description": description}
                    for layer_id, description in sorted(LAYER_CATALOG.items())
                ],
            },
            ensure_ascii=False,
            indent=2,
        )

    @mcp.prompt(
        name="energy_site_assessment",
        title="Energy site assessment",
        description="Guided prompt for assessing the energy situation around a location.",
    )
    def energy_site_assessment(location: str, radius_km: str = "10") -> str:
        """Build a site-assessment prompt for the given location."""
        return (
            f"Erstelle eine strukturierte Energie-Standortanalyse für «{location}» "
            f"im Umkreis von {radius_km} km.\n\n"
            "Vorgehen:\n"
            "1. Rufe `energy_location_profile` für den Standort auf (Koordinaten ggf. "
            "aus dem Ortsnamen ableiten; lat 45–48, lon 5.5–10.7).\n"
            "2. Falls relevant, vertiefe einzelne Energiequellen mit den "
            "`energy_find_*`-Tools.\n"
            "3. Prüfe mit `energy_find_energy_cities`, ob die Gemeinde das Label "
            "«Energiestadt» trägt.\n\n"
            "Fasse das Ergebnis zusammen: vorhandene Produktionsanlagen, Schwerpunkt "
            "der lokalen Energieerzeugung und allfälliges Ausbaupotenzial. Nenne immer "
            "die Datenquelle (BFE / swisstopo)."
        )
