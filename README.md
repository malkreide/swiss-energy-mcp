# swiss-energy-mcp

![Version](https://img.shields.io/badge/version-0.1.0-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Python](https://img.shields.io/badge/python-3.11+-blue)
![Tests](https://img.shields.io/badge/tests-78%20passing-brightgreen)

> MCP server for Swiss energy data from the Federal Office of Energy (SFOE) via GeoAdmin REST API and opendata.swiss — no API key required.

[🇩🇪 Deutsche Version](README.de.md)

## Overview

`swiss-energy-mcp` gives AI assistants structured, location-based access to Switzerland's energy infrastructure. Built on open geodata from the Swiss Federal Office of Energy (SFOE/BFE) via the GeoAdmin REST API and the opendata.swiss catalogue — completely authentication-free.

The server is part of a growing portfolio of Swiss open data MCP servers. Think of it as the energy atlas counterpart to `swiss-road-mobility-mcp`: while the latter maps mobility, this server maps where Switzerland produces electricity, where solar potential exists, and which municipalities hold the "Energiestadt" label.

## Features

- 🔍 **10 ready-to-use tools** covering all major energy data layers from SFOE/BFE
- ⚡ **Power plants** — all types: photovoltaic, hydro, wind, biomass, nuclear, with optional category filter
- 💨 **Wind turbines** — detailed data incl. manufacturer, model, hub height, annual production
- 💧 **Hydropower plants** — type, status, turbine capacity, expected annual output
- ☀️ **PV large installations** — project name, capacity, annual/winter production, altitude
- 🌿 **Biogas plants** — plant name, output
- 🏙️ **Energiestädte** — municipalities with the Swiss "Energiestadt" label (score, year awarded, audits)
- 🏠 **Solar roof potential** — suitability category, area, orientation, and slope per roof segment
- 📊 **Location energy profile** — combines 5 layers into a single overview for any Swiss location
- 🗂️ **SFOE dataset search** — full-text search across SFOE publications on opendata.swiss
- ✅ **Status check** — verifies availability of both upstream APIs

## Prerequisites

- Python 3.11+
- [`uv`](https://github.com/astral-sh/uv) (recommended) or `pip`

## Installation

### Claude Desktop (stdio transport)

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "swiss-energy-mcp": {
      "command": "uvx",
      "args": ["swiss-energy-mcp"]
    }
  }
}
```

### Local development

```bash
git clone https://github.com/malkreide/swiss-energy-mcp.git
cd swiss-energy-mcp
uv sync
uv run swiss-energy-mcp
```

### Cloud / HTTP transport (Streamable HTTP)

```bash
SWISS_ENERGY_TRANSPORT=http uvx swiss-energy-mcp
```

## Usage / Quickstart

Once connected in Claude Desktop, try:

```
What power plants are within 20 km of Bern?
Show me all wind turbines in the Jura region.
Is Zürich an Energiestadt? What's their score?
What is the solar potential of rooftops near lat=47.37, lon=8.54?
Give me a full energy profile for the region around Lucerne.
Find SFOE datasets about hydropower.
```

## Tools

| Tool | Description |
|---|---|
| `energy_find_power_plants` | All electricity generation plants within a radius (optional category filter) |
| `energy_find_wind_turbines` | Wind turbines with manufacturer, model, hub height |
| `energy_find_hydro_plants` | Hydropower plants with capacity and expected output |
| `energy_find_pv_installations` | Large PV installations with annual/winter production |
| `energy_find_biogas_plants` | Biogas plants |
| `energy_find_energy_cities` | Municipalities with "Energiestadt" label |
| `energy_solar_potential` | Solar suitability of roof segments at a location |
| `energy_location_profile` | Combined energy profile (5 layers) for a location |
| `energy_search_bfe_datasets` | Full-text search over SFOE datasets on opendata.swiss |
| `energy_check_status` | Check availability of GeoAdmin and opendata.swiss APIs |

All tools accept WGS84 coordinates (lat/lon). Conversion to Swiss LV95 is handled internally.

## Data Sources

| Source | URL | Auth |
|---|---|---|
| GeoAdmin REST API (swisstopo) | `api3.geo.admin.ch` | None |
| opendata.swiss CKAN API | `opendata.swiss/api/3/action` | None |

**BFE Layers used:**
- `ch.bfe.elektrizitaetsproduktionsanlagen`
- `ch.bfe.windenergieanlagen`
- `ch.bfe.statistik-wasserkraftanlagen`
- `ch.bfe.photovoltaik-grossanlagen`
- `ch.bfe.biogasanlagen`
- `ch.bfe.energiestaedte`
- `ch.bfe.solarenergie-eignung-daecher`

## Configuration

| Environment variable | Default | Description |
|---|---|---|
| `SWISS_ENERGY_TRANSPORT` | `stdio` | Transport mode: `stdio` or `http` |
| `SWISS_ENERGY_PORT` | `8000` | Port for HTTP transport |
| `SWISS_ENERGY_HOST` | `0.0.0.0` | Host for HTTP transport |

## Project Structure

```
swiss-energy-mcp/
├── src/
│   └── swiss_energy_mcp/
│       ├── __init__.py
│       ├── server.py        # FastMCP server — 10 tools
│       └── api_client.py    # HTTP client, LV95 conversion, GeoAdmin queries
├── tests/
│   └── test_server.py       # 78 unit tests + 7 live tests
├── pyproject.toml
├── CHANGELOG.md
└── README.md
```

## Changelog

See [CHANGELOG.md](CHANGELOG.md)

## License

MIT License — see [LICENSE](LICENSE)

## Author

Hayal Oezkan · [malkreide](https://github.com/malkreide)

---
