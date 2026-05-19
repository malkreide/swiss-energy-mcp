"""Shared helpers for tool modules."""

from __future__ import annotations

from mcp.server.fastmcp import Context

from ..api_client import AppContext, EnergyHTTPClient
from ..models import EnergyResponse, Provenance


def get_client(ctx: Context) -> EnergyHTTPClient:
    """Return the shared HTTP client from the lifespan context."""
    app: AppContext = ctx.request_context.lifespan_context
    return app.client


def radius_hint(subject: str, radius_m: int) -> str:
    """Build an actionable hint for an empty radius-search result."""
    return (
        f"Keine {subject} im Umkreis von {radius_m / 1000:.0f} km gefunden. "
        f"Versuche einen grösseren Radius (radius_m bis 50000 m) oder prüfe die "
        f"Koordinaten (lat 45–48, lon 5.5–10.7)."
    )


def make_response(
    features: list[dict],
    *,
    source: str,
    license: str,
    layer: str,
    api: str,
    summary: str,
    empty_note: str,
) -> EnergyResponse:
    """Build the standard :class:`EnergyResponse` envelope from GeoAdmin features."""
    return EnergyResponse(
        source=source,
        license=license,
        provenance=Provenance(layer=layer, api=api),
        match_type="exact" if features else "none",
        count=len(features),
        results=[f.get("attributes", {}) for f in features],
        summary=summary,
        notes=None if features else empty_note,
    )
