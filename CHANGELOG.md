# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- DNS pinning (SEC-005): a custom `httpcore` network backend connects to the
  exact IP that was validated against the egress allow-list, closing the
  time-of-check/time-of-use gap between host validation and the TCP connect. TLS
  SNI and certificate verification still use the original hostname, so transport
  security is unchanged. See `docs/security.md`.

### Changed
- Internal housekeeping (no behaviour change): the `User-Agent` is derived from
  the installed package version instead of a hardcoded string; the constant
  `compute_tolerance()` helper became the `IDENTIFY_TOLERANCE` constant; the
  unused `LAYER_SOLAR_FACADES` layer constant was removed.

## [0.2.1] - 2026-05-19

### Fixed
- HTTP redirects are no longer dropped. `0.2.0` disabled redirects entirely,
  which could break upstream endpoints that issue a 3xx (e.g. opendata.swiss).
  Redirects are now followed manually, with every hop re-validated against the
  egress allow-list — keeping the SEC-021 guarantee without losing redirects.

## [0.2.0] - 2026-05-19

This release implements the remediation of the MCP best-practice audit
(see `audits/2026-05-19-swiss-energy-mcp.md`).

### Changed (breaking)
- Tools no longer take a `response_format` parameter. Every search tool now
  returns a structured `EnergyResponse` envelope (`source`, `license`,
  `provenance`, `match_type`, `count`, `results`, `summary`, `notes`) instead
  of a Markdown or JSON string. `energy_check_status` returns a `StatusResponse`.
- Configuration moved to a typed `Settings` object; all environment variables
  use the `SWISS_ENERGY_` prefix. The HTTP transport now binds `127.0.0.1` by
  default — bind `0.0.0.0` only inside a container.

### Added
- Egress allow-list with SSRF / DNS-rebinding protection; redirects disabled.
- FastMCP lifespan managing a shared, properly closed HTTP client.
- `Context` injection: per-call logging and progress reporting.
- CORS middleware for the HTTP transport (exposes `Mcp-Session-Id`).
- Structured JSON logging to stderr (`structlog`).
- `energy://layers` resource and `energy_site_assessment` prompt.
- `Dockerfile` (multi-stage, non-root user), `.dockerignore`, `.gitignore`,
  `.env.example`, Dependabot config and a nightly live-test workflow.
- `docs/roadmap.md` (phased architecture) and `docs/security.md`
  (egress policy, lethal-trifecta assessment).
- `tools/` package (one module per tool group); test suite split into
  `test_unit.py` / `test_tools.py` / `test_live.py` with `respx`-mocked APIs.

### Fixed
- HTTP transport was non-functional (`mcp.run(transport="streamable_http",
  port=...)` is not a valid call); the server now serves Streamable HTTP via
  uvicorn with the correct transport.
- Tool execution errors now surface as `isError` results instead of being
  returned as plain success strings.

### Protocol
- MCP SDK pinned to `mcp[cli] >= 1.20.0`; protocol version follows the SDK.

## [0.1.0] - 2026-03-11

### Added
- Initial release
- `energy_find_power_plants` — electricity production plants (all types) with optional category filter
- `energy_find_wind_turbines` — wind turbines with manufacturer, model, hub height, annual production
- `energy_find_hydro_plants` — hydropower plants with capacity and expected annual output
- `energy_find_pv_installations` — large photovoltaic installations with seasonal production data
- `energy_find_biogas_plants` — biogas plants
- `energy_find_energy_cities` — Swiss "Energiestadt"-labelled municipalities (by name or location)
- `energy_solar_potential` — solar roof suitability at a given location
- `energy_location_profile` — combined energy profile (5 layers) for any Swiss location
- `energy_search_bfe_datasets` — full-text search over SFOE/BFE datasets on opendata.swiss
- `energy_check_status` — API availability check for GeoAdmin and opendata.swiss
- WGS84 → LV95 coordinate conversion (swisstopo approximation formula, ±1 m accuracy)
- Dual transport: stdio (Claude Desktop) + Streamable HTTP (cloud deployment)
- 78 unit/integration tests + 7 live integration tests
- Bilingual documentation (English README + German README.de.md)
