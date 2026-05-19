"""Tool-level tests using respx to mock the upstream HTTP APIs."""

from __future__ import annotations

import httpx
import pydantic
import pytest
import respx

from swiss_energy_mcp.api_client import GEOADMIN_BASE, OPENDATA_SWISS_BASE
from swiss_energy_mcp.models import (
    EnergyCityInput,
    EnergyResponse,
    LocationInput,
    PowerPlantInput,
    SearchInput,
    StatusResponse,
)
from tests.conftest import (
    biogas_feature,
    dataset,
    energy_city_feature,
    hydro_plant_feature,
    power_plant_feature,
    pv_feature,
    solar_feature,
    wind_turbine_feature,
)

ZH = {"lat": 47.3769, "lon": 8.5417}


def _identify(features):
    return respx.get(url__startswith=f"{GEOADMIN_BASE}/identify").mock(
        return_value=httpx.Response(200, json={"results": features})
    )


def _find(features):
    return respx.get(url__startswith=f"{GEOADMIN_BASE}/find").mock(
        return_value=httpx.Response(200, json={"results": features})
    )


def _package_search(count, results):
    return respx.get(url__startswith=f"{OPENDATA_SWISS_BASE}/package_search").mock(
        return_value=httpx.Response(
            200, json={"success": True, "result": {"count": count, "results": results}}
        )
    )


# ---------------------------------------------------------------------------
# Input model validation
# ---------------------------------------------------------------------------


class TestInputModels:
    def test_location_defaults(self):
        assert LocationInput(**ZH).radius_m == 5000

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"lat": 44.0, "lon": 8.5},
            {"lat": 49.0, "lon": 8.5},
            {"lat": 47.0, "lon": 4.0},
            {"lat": 47.0, "lon": 8.0, "radius_m": 100},
            {"lat": 47.0, "lon": 8.0, "radius_m": 999999},
        ],
    )
    def test_location_out_of_range_rejected(self, kwargs):
        with pytest.raises(pydantic.ValidationError):
            LocationInput(**kwargs)

    def test_extra_field_forbidden(self):
        with pytest.raises(pydantic.ValidationError):
            LocationInput(**ZH, bogus=1)

    def test_search_limit_capped(self):
        with pytest.raises(pydantic.ValidationError):
            SearchInput(limit=100)

    def test_energy_city_name_only(self):
        assert EnergyCityInput(name="Zürich").lat is None


# ---------------------------------------------------------------------------
# energy_find_power_plants
# ---------------------------------------------------------------------------


class TestPowerPlants:
    @respx.mock
    async def test_exact_result(self, tool, ctx):
        _identify([power_plant_feature()])
        res = await tool("energy_find_power_plants")(PowerPlantInput(**ZH), ctx)
        assert isinstance(res, EnergyResponse)
        assert res.match_type == "exact" and res.count == 1

    @respx.mock
    async def test_envelope_has_source_and_license(self, tool, ctx):
        _identify([power_plant_feature()])
        res = await tool("energy_find_power_plants")(PowerPlantInput(**ZH), ctx)
        assert "BFE" in res.source and res.license
        assert res.provenance.layer == "ch.bfe.elektrizitaetsproduktionsanlagen"

    @respx.mock
    async def test_empty_result_has_match_type_none_and_note(self, tool, ctx):
        _identify([])
        res = await tool("energy_find_power_plants")(PowerPlantInput(**ZH), ctx)
        assert res.match_type == "none" and res.count == 0
        assert res.notes and "radius_m" in res.notes

    @respx.mock
    async def test_category_filter(self, tool, ctx):
        _identify([power_plant_feature("Photovoltaik"), power_plant_feature("Wasserkraft")])
        res = await tool("energy_find_power_plants")(
            PowerPlantInput(**ZH, category_filter="photovoltaik"), ctx
        )
        assert res.count == 1

    @respx.mock
    async def test_upstream_error_propagates(self, tool, ctx):
        respx.get(url__startswith=f"{GEOADMIN_BASE}/identify").mock(
            return_value=httpx.Response(503)
        )
        with pytest.raises(ValueError):
            await tool("energy_find_power_plants")(PowerPlantInput(**ZH), ctx)


# ---------------------------------------------------------------------------
# energy_find_wind_turbines
# ---------------------------------------------------------------------------


class TestWindTurbines:
    @respx.mock
    async def test_exact_result(self, tool, ctx):
        _identify([wind_turbine_feature()])
        res = await tool("energy_find_wind_turbines")(LocationInput(**ZH), ctx)
        assert res.match_type == "exact" and "Grenchenberg" in res.summary

    @respx.mock
    async def test_turbine_details_in_summary(self, tool, ctx):
        _identify([wind_turbine_feature()])
        res = await tool("energy_find_wind_turbines")(LocationInput(**ZH), ctx)
        assert "Vestas" in res.summary

    @respx.mock
    async def test_empty_result(self, tool, ctx):
        _identify([])
        res = await tool("energy_find_wind_turbines")(LocationInput(**ZH), ctx)
        assert res.match_type == "none" and res.notes

    @respx.mock
    async def test_results_carry_attributes(self, tool, ctx):
        _identify([wind_turbine_feature()])
        res = await tool("energy_find_wind_turbines")(LocationInput(**ZH), ctx)
        assert res.results[0]["fac_name"] == "Windpark Grenchenberg"

    @respx.mock
    async def test_error_propagates(self, tool, ctx):
        respx.get(url__startswith=f"{GEOADMIN_BASE}/identify").mock(
            return_value=httpx.Response(429)
        )
        with pytest.raises(ValueError):
            await tool("energy_find_wind_turbines")(LocationInput(**ZH), ctx)


# ---------------------------------------------------------------------------
# energy_find_hydro_plants
# ---------------------------------------------------------------------------


class TestHydroPlants:
    @respx.mock
    async def test_exact_result(self, tool, ctx):
        _identify([hydro_plant_feature()])
        res = await tool("energy_find_hydro_plants")(LocationInput(**ZH), ctx)
        assert res.count == 1 and "KW Mühleberg" in res.summary

    @respx.mock
    async def test_plant_type_in_summary(self, tool, ctx):
        _identify([hydro_plant_feature()])
        res = await tool("energy_find_hydro_plants")(LocationInput(**ZH), ctx)
        assert "Laufwasserkraftwerk" in res.summary

    @respx.mock
    async def test_empty_result(self, tool, ctx):
        _identify([])
        res = await tool("energy_find_hydro_plants")(LocationInput(**ZH), ctx)
        assert res.match_type == "none"

    @respx.mock
    async def test_provenance_layer(self, tool, ctx):
        _identify([hydro_plant_feature()])
        res = await tool("energy_find_hydro_plants")(LocationInput(**ZH), ctx)
        assert res.provenance.layer == "ch.bfe.statistik-wasserkraftanlagen"

    @respx.mock
    async def test_error_propagates(self, tool, ctx):
        respx.get(url__startswith=f"{GEOADMIN_BASE}/identify").mock(
            return_value=httpx.Response(404)
        )
        with pytest.raises(ValueError):
            await tool("energy_find_hydro_plants")(LocationInput(**ZH), ctx)


# ---------------------------------------------------------------------------
# energy_find_pv_installations
# ---------------------------------------------------------------------------


class TestPvInstallations:
    @respx.mock
    async def test_exact_result(self, tool, ctx):
        _identify([pv_feature()])
        res = await tool("energy_find_pv_installations")(LocationInput(**ZH), ctx)
        assert res.count == 1 and "Alpine PV Test" in res.summary

    @respx.mock
    async def test_production_in_summary(self, tool, ctx):
        _identify([pv_feature()])
        res = await tool("energy_find_pv_installations")(LocationInput(**ZH), ctx)
        assert "MWp" in res.summary and "GWh" in res.summary

    @respx.mock
    async def test_empty_result(self, tool, ctx):
        _identify([])
        res = await tool("energy_find_pv_installations")(LocationInput(**ZH), ctx)
        assert res.match_type == "none" and res.notes

    @respx.mock
    async def test_envelope_type(self, tool, ctx):
        _identify([pv_feature()])
        res = await tool("energy_find_pv_installations")(LocationInput(**ZH), ctx)
        assert isinstance(res, EnergyResponse)

    @respx.mock
    async def test_error_propagates(self, tool, ctx):
        respx.get(url__startswith=f"{GEOADMIN_BASE}/identify").mock(
            return_value=httpx.Response(503)
        )
        with pytest.raises(ValueError):
            await tool("energy_find_pv_installations")(LocationInput(**ZH), ctx)


# ---------------------------------------------------------------------------
# energy_find_biogas_plants
# ---------------------------------------------------------------------------


class TestBiogasPlants:
    @respx.mock
    async def test_exact_result(self, tool, ctx):
        _identify([biogas_feature()])
        res = await tool("energy_find_biogas_plants")(LocationInput(**ZH), ctx)
        assert res.count == 1 and "Biogas Test" in res.summary

    @respx.mock
    async def test_empty_result(self, tool, ctx):
        _identify([])
        res = await tool("energy_find_biogas_plants")(LocationInput(**ZH), ctx)
        assert res.match_type == "none" and res.notes

    @respx.mock
    async def test_source_attribution(self, tool, ctx):
        _identify([biogas_feature()])
        res = await tool("energy_find_biogas_plants")(LocationInput(**ZH), ctx)
        assert "BFE" in res.source

    @respx.mock
    async def test_results_attributes(self, tool, ctx):
        _identify([biogas_feature()])
        res = await tool("energy_find_biogas_plants")(LocationInput(**ZH), ctx)
        assert res.results[0]["label"] == "Biogas Test"

    @respx.mock
    async def test_error_propagates(self, tool, ctx):
        respx.get(url__startswith=f"{GEOADMIN_BASE}/identify").mock(
            return_value=httpx.Response(400)
        )
        with pytest.raises(ValueError):
            await tool("energy_find_biogas_plants")(LocationInput(**ZH), ctx)


# ---------------------------------------------------------------------------
# energy_solar_potential
# ---------------------------------------------------------------------------


class TestSolarPotential:
    @respx.mock
    async def test_exact_result(self, tool, ctx):
        _identify([solar_feature()])
        res = await tool("energy_solar_potential")(LocationInput(**ZH), ctx)
        assert res.match_type == "exact" and "Solareignung" in res.summary

    @respx.mock
    async def test_class_table_in_summary(self, tool, ctx):
        _identify([solar_feature()])
        res = await tool("energy_solar_potential")(LocationInput(**ZH), ctx)
        assert "Klasse" in res.summary

    @respx.mock
    async def test_empty_result(self, tool, ctx):
        _identify([])
        res = await tool("energy_solar_potential")(LocationInput(**ZH), ctx)
        assert res.match_type == "none" and res.notes

    @respx.mock
    async def test_map_link_present(self, tool, ctx):
        _identify([solar_feature()])
        res = await tool("energy_solar_potential")(LocationInput(**ZH), ctx)
        assert "map.geo.admin.ch" in res.summary

    @respx.mock
    async def test_error_propagates(self, tool, ctx):
        respx.get(url__startswith=f"{GEOADMIN_BASE}/identify").mock(
            return_value=httpx.Response(503)
        )
        with pytest.raises(ValueError):
            await tool("energy_solar_potential")(LocationInput(**ZH), ctx)


# ---------------------------------------------------------------------------
# energy_find_energy_cities
# ---------------------------------------------------------------------------


class TestEnergyCities:
    @respx.mock
    async def test_name_search(self, tool, ctx):
        _find([energy_city_feature()])
        res = await tool("energy_find_energy_cities")(EnergyCityInput(name="Zürich"), ctx)
        assert res.match_type == "exact" and "Zürich" in res.summary

    @respx.mock
    async def test_location_search(self, tool, ctx):
        _identify([energy_city_feature()])
        res = await tool("energy_find_energy_cities")(EnergyCityInput(**ZH, radius_m=20000), ctx)
        assert res.count == 1

    @respx.mock
    async def test_name_not_found(self, tool, ctx):
        _find([])
        res = await tool("energy_find_energy_cities")(EnergyCityInput(name="Nirgendwo"), ctx)
        assert res.match_type == "none" and "Nirgendwo" in res.notes

    async def test_missing_params_raises(self, tool, ctx):
        with pytest.raises(ValueError, match="name"):
            await tool("energy_find_energy_cities")(EnergyCityInput(), ctx)

    @respx.mock
    async def test_score_in_summary(self, tool, ctx):
        _find([energy_city_feature()])
        res = await tool("energy_find_energy_cities")(EnergyCityInput(name="Zürich"), ctx)
        assert "90" in res.summary


# ---------------------------------------------------------------------------
# energy_location_profile
# ---------------------------------------------------------------------------


class TestLocationProfile:
    @respx.mock
    async def test_aggregates_layers(self, tool, ctx):
        _identify([power_plant_feature()])
        res = await tool("energy_location_profile")(LocationInput(**ZH, radius_m=20000), ctx)
        assert isinstance(res, EnergyResponse)
        assert "Energieprofil" in res.summary

    @respx.mock
    async def test_progress_reported(self, tool, ctx):
        _identify([])
        await tool("energy_location_profile")(LocationInput(**ZH), ctx)
        assert len(ctx.progress) >= 2

    @respx.mock
    async def test_empty_profile(self, tool, ctx):
        _identify([])
        res = await tool("energy_location_profile")(LocationInput(**ZH), ctx)
        assert res.match_type == "none"

    @respx.mock
    async def test_results_categories(self, tool, ctx):
        _identify([])
        res = await tool("energy_location_profile")(LocationInput(**ZH), ctx)
        cats = {r["category"] for r in res.results}
        assert {"power_plants", "wind_turbines", "hydro_plants"} <= cats

    @respx.mock
    async def test_partial_failure_tolerated(self, tool, ctx):
        # All five layer queries fail; the tool must still return a response.
        respx.get(url__startswith=f"{GEOADMIN_BASE}/identify").mock(
            return_value=httpx.Response(503)
        )
        res = await tool("energy_location_profile")(LocationInput(**ZH), ctx)
        assert res.count == 0


# ---------------------------------------------------------------------------
# energy_search_bfe_datasets
# ---------------------------------------------------------------------------


class TestSearchDatasets:
    @respx.mock
    async def test_result(self, tool, ctx):
        _package_search(1, [dataset()])
        res = await tool("energy_search_bfe_datasets")(SearchInput(query="solar"), ctx)
        assert res.count == 1 and "Solarenergie" in res.summary

    @respx.mock
    async def test_empty_result(self, tool, ctx):
        _package_search(0, [])
        res = await tool("energy_search_bfe_datasets")(SearchInput(query="xyz"), ctx)
        assert res.match_type == "none" and res.notes

    @respx.mock
    async def test_result_fields(self, tool, ctx):
        _package_search(1, [dataset()])
        res = await tool("energy_search_bfe_datasets")(SearchInput(query="solar"), ctx)
        item = res.results[0]
        assert item["name"] == "solar-ch" and "CSV" in item["formats"]

    @respx.mock
    async def test_pagination_note(self, tool, ctx):
        _package_search(50, [dataset()])
        res = await tool("energy_search_bfe_datasets")(SearchInput(query="solar", limit=1), ctx)
        assert "offset" in res.summary

    @respx.mock
    async def test_error_propagates(self, tool, ctx):
        respx.get(url__startswith=f"{OPENDATA_SWISS_BASE}/package_search").mock(
            return_value=httpx.Response(503)
        )
        with pytest.raises(ValueError):
            await tool("energy_search_bfe_datasets")(SearchInput(query="solar"), ctx)


# ---------------------------------------------------------------------------
# energy_check_status
# ---------------------------------------------------------------------------


class TestCheckStatus:
    @respx.mock
    async def test_both_apis_available(self, tool, ctx):
        _find([energy_city_feature()])
        _package_search(5, [dataset()])
        res = await tool("energy_check_status")(ctx)
        assert isinstance(res, StatusResponse)
        assert all(api.available for api in res.apis)

    @respx.mock
    async def test_geoadmin_down_reported(self, tool, ctx):
        respx.get(url__startswith=f"{GEOADMIN_BASE}/find").mock(return_value=httpx.Response(503))
        _package_search(5, [dataset()])
        res = await tool("energy_check_status")(ctx)
        geoadmin = next(a for a in res.apis if "GeoAdmin" in a.name)
        assert geoadmin.available is False

    @respx.mock
    async def test_lists_layers(self, tool, ctx):
        _find([])
        _package_search(0, [])
        res = await tool("energy_check_status")(ctx)
        assert any("ch.bfe" in layer for layer in res.layers)

    @respx.mock
    async def test_summary_present(self, tool, ctx):
        _find([])
        _package_search(0, [])
        res = await tool("energy_check_status")(ctx)
        assert "API-Status" in res.summary

    @respx.mock
    async def test_no_raw_exception_in_detail(self, tool, ctx):
        respx.get(url__startswith=f"{GEOADMIN_BASE}/find").mock(return_value=httpx.Response(503))
        _package_search(0, [])
        res = await tool("energy_check_status")(ctx)
        geoadmin = next(a for a in res.apis if "GeoAdmin" in a.name)
        assert "Traceback" not in geoadmin.detail
