"""Live integration tests — real API calls.

Marked ``live`` and skipped by default. Run with ``pytest -m live``.
These hit public, auth-free APIs and need network access.
"""

from __future__ import annotations

import pytest

from swiss_energy_mcp.models import (
    EnergyCityInput,
    EnergyResponse,
    LocationInput,
    PowerPlantInput,
    SearchInput,
    StatusResponse,
)

pytestmark = pytest.mark.live

ZH = {"lat": 47.3769, "lon": 8.5417}
JURA = {"lat": 47.22, "lon": 7.05}
CENTRAL = {"lat": 47.05, "lon": 8.31}


async def test_live_power_plants(tool, ctx):
    res = await tool("energy_find_power_plants")(PowerPlantInput(**ZH, radius_m=20000), ctx)
    assert isinstance(res, EnergyResponse)


async def test_live_wind_turbines(tool, ctx):
    res = await tool("energy_find_wind_turbines")(LocationInput(**JURA, radius_m=30000), ctx)
    assert isinstance(res, EnergyResponse)


async def test_live_hydro_plants(tool, ctx):
    res = await tool("energy_find_hydro_plants")(LocationInput(**CENTRAL, radius_m=30000), ctx)
    assert res.count > 0


async def test_live_pv_installations(tool, ctx):
    res = await tool("energy_find_pv_installations")(LocationInput(**CENTRAL, radius_m=40000), ctx)
    assert isinstance(res, EnergyResponse)


async def test_live_biogas_plants(tool, ctx):
    res = await tool("energy_find_biogas_plants")(LocationInput(**ZH, radius_m=30000), ctx)
    assert isinstance(res, EnergyResponse)


async def test_live_solar_potential(tool, ctx):
    res = await tool("energy_solar_potential")(LocationInput(**ZH, radius_m=3000), ctx)
    assert isinstance(res, EnergyResponse)


async def test_live_energy_cities(tool, ctx):
    res = await tool("energy_find_energy_cities")(EnergyCityInput(name="Zürich"), ctx)
    assert res.count > 0
    assert "zürich" in res.results[0].get("name", "").lower()


async def test_live_location_profile(tool, ctx):
    res = await tool("energy_location_profile")(LocationInput(**CENTRAL, radius_m=20000), ctx)
    assert "Energieprofil" in res.summary


async def test_live_search_datasets(tool, ctx):
    res = await tool("energy_search_bfe_datasets")(SearchInput(query="solar"), ctx)
    assert res.count > 0


async def test_live_check_status(tool, ctx):
    res = await tool("energy_check_status")(ctx)
    assert isinstance(res, StatusResponse)
    assert all(api.available for api in res.apis)
