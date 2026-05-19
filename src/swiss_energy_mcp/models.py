"""Pydantic input and output models for the Swiss Energy MCP tools.

Every search/list tool returns the same :class:`EnergyResponse` envelope:
machine-readable ``results`` plus a human-readable ``summary`` and explicit
``source`` / ``license`` provenance. ``match_type`` lets the calling model
distinguish a real empty result from an error and react accordingly.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .api_client import DEFAULT_RADIUS_M

MatchType = Literal["exact", "fuzzy", "none"]

# ---------------------------------------------------------------------------
# Tool input models
# ---------------------------------------------------------------------------


class LocationInput(BaseModel):
    """Location parameters for spatial queries."""

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    lat: float = Field(
        ..., description="Latitude (WGS84, e.g. 47.3769 for Zürich)", ge=45.0, le=48.0
    )
    lon: float = Field(
        ..., description="Longitude (WGS84, e.g. 8.5417 for Zürich)", ge=5.5, le=10.7
    )
    radius_m: int = Field(
        default=DEFAULT_RADIUS_M,
        description="Search radius in metres (500–50000, default 5000)",
        ge=500,
        le=50000,
    )


class PowerPlantInput(LocationInput):
    """Electricity-production-plant query with an optional category filter."""

    category_filter: str | None = Field(
        default=None,
        description=(
            "Optional main-/sub-category filter (German, case-insensitive). "
            "Examples: 'Photovoltaik', 'Wasserkraft', 'Wind', 'Kernkraft'"
        ),
        max_length=100,
    )


class SearchInput(BaseModel):
    """Search parameters for the opendata.swiss catalogue."""

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    query: str = Field(
        default="",
        description="Search term (empty = all BFE datasets)",
        max_length=200,
    )
    limit: int = Field(default=10, description="Number of results (1–50)", ge=1, le=50)
    offset: int = Field(default=0, description="Pagination offset", ge=0)


class EnergyCityInput(BaseModel):
    """Search for 'Energiestadt'-labelled municipalities by name or location."""

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    name: str | None = Field(
        default=None,
        description="Municipality name (e.g. 'Zürich'). Empty = use lat/lon instead.",
        max_length=100,
    )
    lat: float | None = Field(
        default=None, description="Latitude for a radius search (WGS84)", ge=45.0, le=48.0
    )
    lon: float | None = Field(
        default=None, description="Longitude for a radius search (WGS84)", ge=5.5, le=10.7
    )
    radius_m: int = Field(
        default=20000,
        description="Search radius in metres for a location search (default 20 km)",
        ge=1000,
        le=100000,
    )


# ---------------------------------------------------------------------------
# Tool output models (consistent response envelope)
# ---------------------------------------------------------------------------


class Provenance(BaseModel):
    """Per-response data provenance."""

    layer: str = Field(description="GeoAdmin layer ID or CKAN organisation")
    api: str = Field(description="Upstream API the data was retrieved from")


class EnergyResponse(BaseModel):
    """Standard envelope returned by every search/list tool."""

    source: str = Field(description="Originating authority for the data")
    license: str = Field(description="Licence and attribution terms")
    provenance: Provenance
    match_type: MatchType = Field(description="'exact', 'fuzzy' or 'none' (no results)")
    count: int = Field(description="Number of results", ge=0)
    results: list[dict[str, Any]] = Field(default_factory=list)
    summary: str = Field(description="Human-readable Markdown summary")
    notes: str | None = Field(default=None, description="Actionable hint when match_type is 'none'")


class ApiStatus(BaseModel):
    """Availability of a single upstream API."""

    name: str
    available: bool
    response_time_ms: int
    detail: str


class StatusResponse(BaseModel):
    """Response of the energy_check_status tool."""

    source: str
    apis: list[ApiStatus]
    layers: list[str]
    summary: str
