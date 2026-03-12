"""Tests für den Swiss Energy MCP Server.

Tiered test suite:
- Unit-Tests: Koordinaten-Konvertierung, Formatierungs-Hilfsfunktionen, Validierung
- Integration-Tests (gemockt): API-Client-Logik, Tool-Output-Format
- Live-Tests (mit @pytest.mark.live): echte API-Aufrufe (benötigen Internet)

Ausführung:
    pytest tests/               # Nur Unit/Integration-Tests (kein Internet nötig)
    pytest tests/ -m live       # Nur Live-Tests
    pytest tests/ -v --tb=short # Alle Tests mit Details
"""

import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from swiss_energy_mcp.api_client import (
    wgs84_to_lv95,
    radius_to_map_extent,
    compute_tolerance,
    format_power_value,
    format_year,
    clean_label,
    EnergyHTTPClient,
    LAYER_POWER_PLANTS,
    LAYER_WIND_TURBINES,
    LAYER_HYDRO_PLANTS,
    LAYER_PV_LARGE,
    LAYER_ENERGY_CITIES,
    LAYER_BIOGAS,
    LAYER_SOLAR_ROOFS,
)


# ===========================================================================
# Fixtures / Helper-Factories
# ===========================================================================

def make_power_plant_feature(subcat="Photovoltaik", address="Musterstrasse 1", canton="ZH",
                              power_init=18.81, total_power=18.81, op_start=2021):
    return {"attributes": {
        "sub_category_de": subcat, "main_category_de": "Erneuerbare Energien",
        "address": address, "canton": canton,
        "initial_power": power_init, "total_power": total_power,
        "beginning_of_operation": op_start,
    }}


def make_wind_turbine_feature(name="Windpark Grenchenberg", operator="Grenchenberg AG",
                               power_kw=800.0, fac_type="Windkraftanlage"):
    return {"attributes": {
        "fac_name": name, "fac_operator": operator,
        "fac_power": power_kw, "fac_type_de": fac_type,
        "turbines": (
            "<turbines><turbine><tur_manufacturer>Vestas</tur_manufacturer>"
            "<tur_model>V90</tur_model><tur_hubheight>100</tur_hubheight></turbine></turbines>"
        ),
        "fac_website": "https://example.com",
    }}


def make_hydro_plant_feature(name="KW Mühleberg", location="Mühleberg", canton="BE"):
    return {"attributes": {
        "name": name, "location": location, "canton": canton,
        "hydropowerplanttype_de": "Laufwasserkraftwerk",
        "hydropowerplantoperationalstatus_de": "In Betrieb",
        "beginningofoperation": 1960,
        "performanceturbinemaximum": 50.5,
        "productionexpected": 350.0,
        "fallheight": 18.5,
    }}


def make_energy_city_feature(name="Zürich", score=90.0, since="2000-01-01",
                              residents=420000, audits=7):
    return {"attributes": {
        "name": name, "punktezahl": score, "energiestadtseit": since,
        "einwohner": residents, "anzahlaudits": audits,
        "berater": "Energieberatung AG",
        "linkenergiestadtweb": "https://energiestadt.ch/zuerich",
    }}


def make_solar_roof_feature():
    return {"attributes": {
        "eignungskategorie_de": "gut geeignet",
        "klasse": 4, "flaeche": 120.5, "gstrid": "1234567",
        "ausrichtung_de": "Süd", "neigung": 25,
    }}


# ===========================================================================
# 1. Koordinaten-Konvertierung
# ===========================================================================

class TestCoordinateConversion:
    def test_zurich_center(self):
        e, n = wgs84_to_lv95(47.3769, 8.5417)
        assert 2680000 < e < 2690000
        assert 1245000 < n < 1252000

    def test_bern(self):
        e, n = wgs84_to_lv95(46.9480, 7.4474)
        assert 2597000 < e < 2603000
        assert 1199000 < n < 1205000

    def test_geneva(self):
        e, n = wgs84_to_lv95(46.2044, 6.1432)
        assert 2498000 < e < 2505000
        assert 1117000 < n < 1124000

    def test_lucerne(self):
        e, n = wgs84_to_lv95(47.0502, 8.3093)
        assert 2660000 < e < 2670000
        assert 1210000 < n < 1220000

    def test_basel(self):
        e, n = wgs84_to_lv95(47.5596, 7.5886)
        assert 2610000 < e < 2620000
        assert 1265000 < n < 1275000

    def test_output_types(self):
        e, n = wgs84_to_lv95(47.0, 8.0)
        assert isinstance(e, float)
        assert isinstance(n, float)

    def test_eastward_increases(self):
        e_west, _ = wgs84_to_lv95(47.0, 7.0)
        e_east, _ = wgs84_to_lv95(47.0, 9.0)
        assert e_east > e_west

    def test_northward_increases(self):
        _, n_south = wgs84_to_lv95(46.0, 8.0)
        _, n_north = wgs84_to_lv95(47.5, 8.0)
        assert n_north > n_south


# ===========================================================================
# 2. radius_to_map_extent
# ===========================================================================

class TestRadiusToMapExtent:
    def test_extent_contains_center(self):
        r = radius_to_map_extent(47.3769, 8.5417, 5000)
        assert r["xmin"] < r["e"] < r["xmax"]
        assert r["ymin"] < r["n"] < r["ymax"]

    def test_extent_size(self):
        r = radius_to_map_extent(47.0, 8.0, 10000)
        assert abs((r["xmax"] - r["xmin"]) - 20000) < 10
        assert abs((r["ymax"] - r["ymin"]) - 20000) < 10

    def test_all_keys_present(self):
        r = radius_to_map_extent(47.0, 8.0, 5000)
        for k in ("xmin", "ymin", "xmax", "ymax", "e", "n"):
            assert k in r

    def test_small_radius(self):
        r = radius_to_map_extent(47.0, 8.0, 500)
        assert abs((r["xmax"] - r["xmin"]) - 1000) < 5

    def test_large_radius(self):
        r = radius_to_map_extent(47.0, 8.0, 50000)
        assert abs((r["xmax"] - r["xmin"]) - 100000) < 50

    def test_center_matches_wgs84(self):
        lat, lon = 47.3769, 8.5417
        r = radius_to_map_extent(lat, lon, 5000)
        e, n = wgs84_to_lv95(lat, lon)
        assert abs(r["e"] - e) < 1
        assert abs(r["n"] - n) < 1


# ===========================================================================
# 3. compute_tolerance
# ===========================================================================

class TestComputeTolerance:
    def test_positive(self):
        assert compute_tolerance(5000) > 0

    def test_returns_500(self):
        assert compute_tolerance(5000) == 500
        assert compute_tolerance(1000) == 500
        assert compute_tolerance(50000) == 500

    def test_integer_return(self):
        assert isinstance(compute_tolerance(5000), int)


# ===========================================================================
# 4. format_power_value
# ===========================================================================

class TestFormatPowerValue:
    def test_kw_small(self):
        assert "18.81 kW" in format_power_value(18.81, "kW")

    def test_kw_to_mw_conversion(self):
        result = format_power_value(1500, "kW")
        assert "MW" in result and "1.50" in result

    def test_none_value(self):
        assert format_power_value(None) == "k.A."

    def test_empty_string(self):
        assert format_power_value("") == "k.A."

    def test_float_input(self):
        assert "100.00 kW" in format_power_value(100.0, "kW")

    def test_string_with_comma(self):
        assert "kW" in format_power_value("18,81", "kW")

    def test_exact_1000_kw_is_mw(self):
        assert "MW" in format_power_value(1000, "kW")

    def test_999_stays_kw(self):
        result = format_power_value(999, "kW")
        assert "kW" in result and "MW" not in result

    def test_zero_value(self):
        assert "0.00 kW" in format_power_value(0, "kW")

    def test_mw_unit_passthrough(self):
        assert "MW" in format_power_value(50.5, "MW")


# ===========================================================================
# 5. format_year
# ===========================================================================

class TestFormatYear:
    def test_integer_year(self):
        assert format_year(2021) == "2021"

    def test_string_year(self):
        assert format_year("2018") == "2018"

    def test_none_year(self):
        assert format_year(None) == "k.A."

    def test_empty_string(self):
        assert format_year("") == "k.A."

    def test_valid_1990(self):
        assert format_year("1990") == "1990"


# ===========================================================================
# 6. clean_label
# ===========================================================================

class TestCleanLabel:
    def test_removes_bold_tags(self):
        assert clean_label("<b>Test</b>") == "Test"

    def test_no_tags(self):
        assert clean_label("Zürich") == "Zürich"

    def test_strips_whitespace(self):
        assert clean_label("  Bern  ") == "Bern"

    def test_nested_bold(self):
        result = clean_label("<b>Stadtwerk Zürich</b>")
        assert result == "Stadtwerk Zürich"
        assert "<b>" not in result


# ===========================================================================
# 7. Pydantic-Modell-Validierung
# ===========================================================================

class TestPydanticModels:
    def test_location_input_valid(self):
        from swiss_energy_mcp.server import LocationInput
        p = LocationInput(lat=47.3769, lon=8.5417)
        assert p.radius_m == 5000

    def test_location_input_lat_too_low(self):
        from swiss_energy_mcp.server import LocationInput
        import pydantic
        with pytest.raises(pydantic.ValidationError):
            LocationInput(lat=44.0, lon=8.5)

    def test_location_input_lat_too_high(self):
        from swiss_energy_mcp.server import LocationInput
        import pydantic
        with pytest.raises(pydantic.ValidationError):
            LocationInput(lat=49.0, lon=8.5)

    def test_location_input_lon_too_low(self):
        from swiss_energy_mcp.server import LocationInput
        import pydantic
        with pytest.raises(pydantic.ValidationError):
            LocationInput(lat=47.0, lon=4.0)

    def test_location_input_lon_too_high(self):
        from swiss_energy_mcp.server import LocationInput
        import pydantic
        with pytest.raises(pydantic.ValidationError):
            LocationInput(lat=47.0, lon=12.0)

    def test_location_input_radius_too_small(self):
        from swiss_energy_mcp.server import LocationInput
        import pydantic
        with pytest.raises(pydantic.ValidationError):
            LocationInput(lat=47.0, lon=8.0, radius_m=100)

    def test_location_input_radius_too_large(self):
        from swiss_energy_mcp.server import LocationInput
        import pydantic
        with pytest.raises(pydantic.ValidationError):
            LocationInput(lat=47.0, lon=8.0, radius_m=100000)

    def test_power_plant_category_filter(self):
        from swiss_energy_mcp.server import PowerPlantInput
        p = PowerPlantInput(lat=47.0, lon=8.0, category_filter="Photovoltaik")
        assert p.category_filter == "Photovoltaik"

    def test_power_plant_no_filter(self):
        from swiss_energy_mcp.server import PowerPlantInput
        p = PowerPlantInput(lat=47.0, lon=8.0)
        assert p.category_filter is None

    def test_search_input_defaults(self):
        from swiss_energy_mcp.server import SearchInput
        p = SearchInput()
        assert p.query == "" and p.limit == 10 and p.offset == 0

    def test_search_input_limit_max_exceeded(self):
        from swiss_energy_mcp.server import SearchInput
        import pydantic
        with pytest.raises(pydantic.ValidationError):
            SearchInput(limit=100)

    def test_energy_city_name_only(self):
        from swiss_energy_mcp.server import EnergyCityInput
        p = EnergyCityInput(name="Zürich")
        assert p.name == "Zürich" and p.lat is None

    def test_response_format_json(self):
        from swiss_energy_mcp.server import LocationInput, ResponseFormat
        p = LocationInput(lat=47.0, lon=8.0, response_format="json")
        assert p.response_format == ResponseFormat.JSON

    def test_response_format_default_markdown(self):
        from swiss_energy_mcp.server import LocationInput, ResponseFormat
        p = LocationInput(lat=47.0, lon=8.0)
        assert p.response_format == ResponseFormat.MARKDOWN


# ===========================================================================
# 8. HTTP-Client
# ===========================================================================

class TestEnergyHTTPClient:
    @pytest.mark.asyncio
    async def test_successful_get(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {"results": [{"id": 1}]}
        mock_response.raise_for_status = MagicMock()
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            client = EnergyHTTPClient()
            result = await client.get("https://test.example.com/api", {"param": "value"})
            assert result == {"results": [{"id": 1}]}
            await client.close()

    @pytest.mark.asyncio
    async def test_timeout_raises_valueerror(self):
        import httpx
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.TimeoutException("timeout")
            client = EnergyHTTPClient()
            with pytest.raises(ValueError, match="Zeitüberschreitung"):
                await client.get("https://test.example.com/api")
            await client.close()

    @pytest.mark.asyncio
    async def test_http_404_raises_valueerror(self):
        import httpx
        mock_response = MagicMock()
        mock_response.status_code = 404
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.HTTPStatusError(
                "not found", request=MagicMock(), response=mock_response
            )
            client = EnergyHTTPClient()
            with pytest.raises(ValueError, match="404"):
                await client.get("https://test.example.com/api")
            await client.close()

    @pytest.mark.asyncio
    async def test_http_429_raises_valueerror(self):
        import httpx
        mock_response = MagicMock()
        mock_response.status_code = 429
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.HTTPStatusError(
                "too many", request=MagicMock(), response=mock_response
            )
            client = EnergyHTTPClient()
            with pytest.raises(ValueError, match="429"):
                await client.get("https://test.example.com/api")
            await client.close()

    @pytest.mark.asyncio
    async def test_network_error_raises_valueerror(self):
        import httpx
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.RequestError("connection refused")
            client = EnergyHTTPClient()
            with pytest.raises(ValueError, match="Netzwerkfehler"):
                await client.get("https://test.example.com/api")
            await client.close()


# ===========================================================================
# 9. Tool: energy_find_power_plants (gemockt)
# ===========================================================================

class TestEnergyFindPowerPlantsMocked:
    @pytest.mark.asyncio
    async def test_markdown_format(self):
        from swiss_energy_mcp.server import energy_find_power_plants, PowerPlantInput
        with patch("swiss_energy_mcp.server.query_geoadmin_layer", new_callable=AsyncMock,
                   return_value=[make_power_plant_feature()]):
            result = await energy_find_power_plants(PowerPlantInput(lat=47.3769, lon=8.5417))
            assert "Elektrizitätsproduktionsanlagen" in result
            assert "Photovoltaik" in result
            assert "Musterstrasse" in result

    @pytest.mark.asyncio
    async def test_json_format(self):
        from swiss_energy_mcp.server import energy_find_power_plants, PowerPlantInput
        with patch("swiss_energy_mcp.server.query_geoadmin_layer", new_callable=AsyncMock,
                   return_value=[make_power_plant_feature()]):
            result = await energy_find_power_plants(
                PowerPlantInput(lat=47.3769, lon=8.5417, response_format="json")
            )
            data = json.loads(result)
            assert data["count"] == 1
            assert data["layer"] == LAYER_POWER_PLANTS

    @pytest.mark.asyncio
    async def test_empty_result(self):
        from swiss_energy_mcp.server import energy_find_power_plants, PowerPlantInput
        with patch("swiss_energy_mcp.server.query_geoadmin_layer", new_callable=AsyncMock,
                   return_value=[]):
            result = await energy_find_power_plants(PowerPlantInput(lat=47.3769, lon=8.5417))
            assert "Keine Anlagen" in result

    @pytest.mark.asyncio
    async def test_category_filter(self):
        from swiss_energy_mcp.server import energy_find_power_plants, PowerPlantInput
        features = [make_power_plant_feature("Photovoltaik"), make_power_plant_feature("Wasserkraft")]
        with patch("swiss_energy_mcp.server.query_geoadmin_layer", new_callable=AsyncMock,
                   return_value=features):
            result = await energy_find_power_plants(
                PowerPlantInput(lat=47.3769, lon=8.5417, category_filter="photovoltaik")
            )
            assert "1 Anlage" in result

    @pytest.mark.asyncio
    async def test_api_error_message(self):
        from swiss_energy_mcp.server import energy_find_power_plants, PowerPlantInput
        with patch("swiss_energy_mcp.server.query_geoadmin_layer", new_callable=AsyncMock,
                   side_effect=ValueError("API nicht erreichbar")):
            result = await energy_find_power_plants(PowerPlantInput(lat=47.3769, lon=8.5417))
            assert "Fehler" in result

    @pytest.mark.asyncio
    async def test_json_location_info(self):
        from swiss_energy_mcp.server import energy_find_power_plants, PowerPlantInput
        with patch("swiss_energy_mcp.server.query_geoadmin_layer", new_callable=AsyncMock,
                   return_value=[]):
            result = await energy_find_power_plants(
                PowerPlantInput(lat=47.3769, lon=8.5417, response_format="json")
            )
            data = json.loads(result)
            assert data["location"]["lat"] == 47.3769
            assert data["radius_m"] == 5000


# ===========================================================================
# 10. Tool: energy_find_wind_turbines (gemockt)
# ===========================================================================

class TestEnergyFindWindTurbinesMocked:
    @pytest.mark.asyncio
    async def test_markdown_contains_turbine(self):
        from swiss_energy_mcp.server import energy_find_wind_turbines, LocationInput
        with patch("swiss_energy_mcp.server.query_geoadmin_layer", new_callable=AsyncMock,
                   return_value=[make_wind_turbine_feature()]):
            result = await energy_find_wind_turbines(LocationInput(lat=47.22, lon=7.05))
            assert "Windenergieanlagen" in result
            assert "Grenchenberg" in result

    @pytest.mark.asyncio
    async def test_json_format(self):
        from swiss_energy_mcp.server import energy_find_wind_turbines, LocationInput
        with patch("swiss_energy_mcp.server.query_geoadmin_layer", new_callable=AsyncMock,
                   return_value=[make_wind_turbine_feature()]):
            result = await energy_find_wind_turbines(
                LocationInput(lat=47.22, lon=7.05, response_format="json")
            )
            data = json.loads(result)
            assert data["count"] == 1 and data["layer"] == LAYER_WIND_TURBINES

    @pytest.mark.asyncio
    async def test_no_turbines(self):
        from swiss_energy_mcp.server import energy_find_wind_turbines, LocationInput
        with patch("swiss_energy_mcp.server.query_geoadmin_layer", new_callable=AsyncMock,
                   return_value=[]):
            result = await energy_find_wind_turbines(LocationInput(lat=47.3769, lon=8.5417))
            assert "Keine Windenergieanlagen" in result


# ===========================================================================
# 11. Tool: energy_find_hydro_plants (gemockt)
# ===========================================================================

class TestEnergyFindHydroPlantsMocked:
    @pytest.mark.asyncio
    async def test_markdown_contains_hydro(self):
        from swiss_energy_mcp.server import energy_find_hydro_plants, LocationInput
        with patch("swiss_energy_mcp.server.query_geoadmin_layer", new_callable=AsyncMock,
                   return_value=[make_hydro_plant_feature()]):
            result = await energy_find_hydro_plants(LocationInput(lat=47.05, lon=8.31))
            assert "Wasserkraftwerke" in result
            assert "KW Mühleberg" in result
            assert "Laufwasserkraftwerk" in result

    @pytest.mark.asyncio
    async def test_json_format(self):
        from swiss_energy_mcp.server import energy_find_hydro_plants, LocationInput
        with patch("swiss_energy_mcp.server.query_geoadmin_layer", new_callable=AsyncMock,
                   return_value=[make_hydro_plant_feature()]):
            result = await energy_find_hydro_plants(
                LocationInput(lat=47.05, lon=8.31, response_format="json")
            )
            data = json.loads(result)
            assert data["count"] == 1 and data["layer"] == LAYER_HYDRO_PLANTS


# ===========================================================================
# 12. Tool: energy_find_energy_cities (gemockt)
# ===========================================================================

class TestEnergyFindEnergyCitiesMocked:
    @pytest.mark.asyncio
    async def test_name_search_markdown(self):
        from swiss_energy_mcp.server import energy_find_energy_cities, EnergyCityInput
        with patch("swiss_energy_mcp.server.find_geoadmin_by_name", new_callable=AsyncMock,
                   return_value=[make_energy_city_feature()]):
            result = await energy_find_energy_cities(EnergyCityInput(name="Zürich"))
            assert "Zürich" in result and "Energiestädte" in result and "90.0%" in result

    @pytest.mark.asyncio
    async def test_name_search_json(self):
        from swiss_energy_mcp.server import energy_find_energy_cities, EnergyCityInput
        with patch("swiss_energy_mcp.server.find_geoadmin_by_name", new_callable=AsyncMock,
                   return_value=[make_energy_city_feature()]):
            result = await energy_find_energy_cities(
                EnergyCityInput(name="Zürich", response_format="json")
            )
            data = json.loads(result)
            assert data["count"] == 1

    @pytest.mark.asyncio
    async def test_location_search(self):
        from swiss_energy_mcp.server import energy_find_energy_cities, EnergyCityInput
        with patch("swiss_energy_mcp.server.query_geoadmin_layer", new_callable=AsyncMock,
                   return_value=[make_energy_city_feature()]):
            result = await energy_find_energy_cities(
                EnergyCityInput(lat=47.3769, lon=8.5417, radius_m=20000)
            )
            assert "Energiestädte" in result

    @pytest.mark.asyncio
    async def test_no_name_no_location_error(self):
        from swiss_energy_mcp.server import energy_find_energy_cities, EnergyCityInput
        result = await energy_find_energy_cities(EnergyCityInput())
        assert any(kw in result for kw in ("Name", "Fehler", "Keine", "Koordinaten"))


# ===========================================================================
# 13. Tool: energy_solar_potential (gemockt)
# ===========================================================================

class TestEnergySolarPotentialMocked:
    @pytest.mark.asyncio
    async def test_markdown_solar_info(self):
        from swiss_energy_mcp.server import energy_solar_potential, LocationInput
        with patch("swiss_energy_mcp.server.query_geoadmin_layer", new_callable=AsyncMock,
                   return_value=[make_solar_roof_feature()]):
            result = await energy_solar_potential(LocationInput(lat=47.3769, lon=8.5417))
            assert "Solar" in result

    @pytest.mark.asyncio
    async def test_no_solar_results(self):
        from swiss_energy_mcp.server import energy_solar_potential, LocationInput
        with patch("swiss_energy_mcp.server.query_geoadmin_layer", new_callable=AsyncMock,
                   return_value=[]):
            result = await energy_solar_potential(LocationInput(lat=47.3769, lon=8.5417))
            assert "Keine" in result or "keine" in result


# ===========================================================================
# 14. Tool: energy_location_profile (gemockt)
# ===========================================================================

class TestEnergyLocationProfileMocked:
    @pytest.mark.asyncio
    async def test_profile_contains_summary(self):
        from swiss_energy_mcp.server import energy_location_profile, LocationInput
        with patch("swiss_energy_mcp.server.query_geoadmin_layer", new_callable=AsyncMock,
                   return_value=[]):
            result = await energy_location_profile(
                LocationInput(lat=47.3769, lon=8.5417, radius_m=20000)
            )
            assert "Energieprofil" in result

    @pytest.mark.asyncio
    async def test_profile_json_structure(self):
        from swiss_energy_mcp.server import energy_location_profile, LocationInput
        with patch("swiss_energy_mcp.server.query_geoadmin_layer", new_callable=AsyncMock,
                   return_value=[]):
            result = await energy_location_profile(
                LocationInput(lat=47.3769, lon=8.5417, response_format="json")
            )
            data = json.loads(result)
            assert "location" in data and "radius_m" in data


# ===========================================================================
# 15. Tool: energy_search_bfe_datasets (gemockt)
# ===========================================================================

class TestEnergySearchBfeMocked:
    @pytest.mark.asyncio
    async def test_markdown_output(self):
        from swiss_energy_mcp.server import energy_search_bfe_datasets, SearchInput
        mock_result = {
            "count": 2,
            "results": [
                {"title": {"de": "Solarenergie Schweiz"}, "name": "solar-ch",
                 "notes": {"de": "Daten."}, "metadata_modified": "2024-01-01",
                 "resources": [{"format": "CSV"}]},
            ],
        }
        with patch("swiss_energy_mcp.server.search_opendata_swiss", new_callable=AsyncMock,
                   return_value=mock_result):
            result = await energy_search_bfe_datasets(SearchInput(query="solar"))
            assert "Solarenergie" in result

    @pytest.mark.asyncio
    async def test_json_output(self):
        from swiss_energy_mcp.server import energy_search_bfe_datasets, SearchInput
        mock_result = {"count": 1, "results": [{"title": {"de": "Test"}, "name": "test",
                                                 "notes": {}, "metadata_modified": "2024-01-01",
                                                 "resources": []}]}
        with patch("swiss_energy_mcp.server.search_opendata_swiss", new_callable=AsyncMock,
                   return_value=mock_result):
            result = await energy_search_bfe_datasets(SearchInput(query="test", response_format="json"))
            data = json.loads(result)
            assert data["count"] == 1


# ===========================================================================
# 16. Tool: energy_check_status (gemockt)
# ===========================================================================

class TestEnergyCheckStatusMocked:
    @pytest.mark.asyncio
    async def test_status_returns_string(self):
        from swiss_energy_mcp.server import energy_check_status
        mock_response = MagicMock()
        mock_response.json.return_value = {"results": []}
        mock_response.raise_for_status = MagicMock()
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
            result = await energy_check_status()
            assert isinstance(result, str) and len(result) > 0

    @pytest.mark.asyncio
    async def test_status_mentions_geoadmin(self):
        from swiss_energy_mcp.server import energy_check_status
        mock_response = MagicMock()
        mock_response.json.return_value = {"results": []}
        mock_response.raise_for_status = MagicMock()
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
            result = await energy_check_status()
            assert "GeoAdmin" in result


# ===========================================================================
# Live-Tests
# ===========================================================================

@pytest.mark.live
class TestLiveGeoAdmin:
    @pytest.mark.asyncio
    async def test_energy_cities_zurich(self):
        from swiss_energy_mcp.api_client import find_geoadmin_by_name, LAYER_ENERGY_CITIES
        client = EnergyHTTPClient()
        results = await find_geoadmin_by_name(client, LAYER_ENERGY_CITIES, "Zürich", "name")
        await client.close()
        assert len(results) > 0
        attrs = results[0].get("attributes", {})
        assert "zürich" in attrs.get("name", "").lower()
        assert attrs.get("punktezahl", 0) > 0

    @pytest.mark.asyncio
    async def test_wind_turbines_jura(self):
        from swiss_energy_mcp.api_client import query_geoadmin_layer, LAYER_WIND_TURBINES
        client = EnergyHTTPClient()
        results = await query_geoadmin_layer(client, LAYER_WIND_TURBINES, 47.22, 7.05, 30000)
        await client.close()
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_opendata_swiss_bfe(self):
        from swiss_energy_mcp.api_client import search_opendata_swiss
        client = EnergyHTTPClient()
        result = await search_opendata_swiss(client, query="solar", rows=5)
        await client.close()
        assert result["count"] > 0 and len(result["results"]) > 0

    @pytest.mark.asyncio
    async def test_hydro_plants_central_switzerland(self):
        from swiss_energy_mcp.api_client import query_geoadmin_layer, LAYER_HYDRO_PLANTS
        client = EnergyHTTPClient()
        results = await query_geoadmin_layer(client, LAYER_HYDRO_PLANTS, 47.05, 8.31, 30000)
        await client.close()
        assert len(results) > 0


@pytest.mark.live
class TestLiveServerTools:
    @pytest.mark.asyncio
    async def test_energy_check_status(self):
        from swiss_energy_mcp.server import energy_check_status
        result = await energy_check_status()
        assert "✅" in result
        assert "GeoAdmin" in result
        assert "opendata.swiss" in result

    @pytest.mark.asyncio
    async def test_energy_find_energy_cities_zurich(self):
        from swiss_energy_mcp.server import energy_find_energy_cities, EnergyCityInput
        params = EnergyCityInput(name="Zürich")
        result = await energy_find_energy_cities(params)
        assert "Zürich" in result and "Energiestädte" in result

    @pytest.mark.asyncio
    async def test_energy_location_profile_zurich(self):
        from swiss_energy_mcp.server import energy_location_profile, LocationInput
        params = LocationInput(lat=47.3769, lon=8.5417, radius_m=20000)
        result = await energy_location_profile(params)
        assert "Energieprofil" in result and "Zusammenfassung" in result
