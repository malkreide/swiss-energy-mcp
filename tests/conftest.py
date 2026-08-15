"""Shared test fixtures for the Swiss Energy MCP test suite."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
import pytest_asyncio

from swiss_energy_mcp import api_client
from swiss_energy_mcp.api_client import AppContext, EnergyHTTPClient
from swiss_energy_mcp.server import build_server


class FakeContext:
    """Minimal stand-in for MCPServer's Context used in tool tests."""

    def __init__(self, client: EnergyHTTPClient) -> None:
        self.request_context = SimpleNamespace(lifespan_context=AppContext(client=client))
        self.progress: list[tuple] = []

    async def info(self, message: str, **extra: object) -> None:
        return None

    async def warning(self, message: str, **extra: object) -> None:
        return None

    async def error(self, message: str, **extra: object) -> None:
        return None

    async def report_progress(
        self, progress: float, total: float | None = None, message: str | None = None
    ) -> None:
        self.progress.append((progress, total, message))


@pytest.fixture(scope="session")
def server():
    """A fully built MCPServer server instance."""
    return build_server()


@pytest.fixture
def tool(server):
    """Return a callable that resolves a registered tool's function by name."""

    def _resolve(name: str):
        return server._tool_manager.get_tool(name).fn

    return _resolve


@pytest_asyncio.fixture
async def ctx():
    """A FakeContext backed by a real (closed afterwards) HTTP client."""
    client = EnergyHTTPClient()
    try:
        yield FakeContext(client)
    finally:
        await client.close()


# ---------------------------------------------------------------------------
# Canned upstream-response factories
# ---------------------------------------------------------------------------


def power_plant_feature(subcat: str = "Photovoltaik") -> dict:
    return {
        "attributes": {
            "sub_category_de": subcat,
            "main_category_de": "Erneuerbare Energien",
            "address": "Musterstrasse 1",
            "canton": "ZH",
            "initial_power": 18.81,
            "total_power": 18.81,
            "beginning_of_operation": 2021,
        }
    }


def wind_turbine_feature() -> dict:
    return {
        "attributes": {
            "fac_name": "Windpark Grenchenberg",
            "fac_operator": "Grenchenberg AG",
            "fac_power": 800.0,
            "fac_type_de": "Windkraftanlage",
            "turbines": (
                "<turbines><turbine><tur_manufacturer>Vestas</tur_manufacturer>"
                "<tur_model>V90</tur_model><tur_hubheight>100</tur_hubheight>"
                "</turbine></turbines>"
            ),
            "fac_website": "https://example.com",
        }
    }


def hydro_plant_feature() -> dict:
    return {
        "attributes": {
            "name": "KW Mühleberg",
            "location": "Mühleberg",
            "canton": "BE",
            "hydropowerplanttype_de": "Laufwasserkraftwerk",
            "hydropowerplantoperationalstatus_de": "In Betrieb",
            "beginningofoperation": 1960,
            "performanceturbinemaximum": 50.5,
            "productionexpected": 350.0,
        }
    }


def pv_feature() -> dict:
    return {
        "attributes": {
            "projectname": "Alpine PV Test",
            "projectmanagement": "Test AG",
            "statuscategory_de": "In Betrieb",
            "power": 2.0,
            "annualproduction": 3.1,
            "winterproduction": 1.4,
        }
    }


def biogas_feature() -> dict:
    return {"attributes": {"label": "Biogas Test", "leistung": "250 kW"}}


def energy_city_feature(name: str = "Zürich") -> dict:
    return {
        "attributes": {
            "name": name,
            "punktezahl": 90.0,
            "energiestadtseit": "2000-01-01",
            "einwohner": 420000,
            "anzahlaudits": 7,
            "linkenergiestadtweb": "https://energiestadt.ch/zuerich",
        }
    }


def solar_feature() -> dict:
    return {"attributes": {"klasse": 2, "flaeche": 120.5, "ausrichtung_de": "Süd"}}


def dataset() -> dict:
    return {
        "name": "solar-ch",
        "title": {"de": "Solarenergie Schweiz"},
        # `description`, nicht `notes` — so nennt opendata.swiss das Feld. Der
        # Stub hiess frueher wie der Code und bestaetigte damit nur dessen
        # Annahme; siehe tests/fixtures/PROVENANCE.md.
        "description": {"de": "Testbeschreibung."},
        "resources": [{"format": "CSV"}],
    }


@pytest.fixture
def ohne_wartezeit(monkeypatch):
    """Nullt den Backoff-Schlaf ueber den Modul-Alias `api_client._sleep`.

    Nicht ueber `monkeypatch.setattr(api_client.asyncio, "sleep", ...)`: das
    griffe ins Modul `asyncio` selbst und naehme httpx, respx und
    pytest-asyncio prozessweit dieselbe Mechanik weg. Portfolio-Konvention,
    siehe CLAUDE.md Teil 1.

    Gepatcht wird nur, wo eine Zusicherung ueber die *Form* einer Antwort
    laeuft. Wer die Wartezeit selbst prueft, nimmt die Fixture nicht — deshalb
    ist sie nicht `autouse`.
    """

    async def sofort(_delay: float) -> None:
        return None

    monkeypatch.setattr(api_client, "_sleep", sofort)
