# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
