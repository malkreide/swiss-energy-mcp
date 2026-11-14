"""Die Einordnung `unreachable` gegen die Meldungen, die der Client wirklich erzeugt.

`scripts/classify_live_run.py` erkennt eine nicht erreichbare Quelle an der
Meldung jedes Fehlschlags. Die Tests dort fuettern handgeschriebene Meldungen
ein — und eine handgeschriebene Meldung kodiert nur die Annahme ihres Autors
(CLAUDE.md, Teil 1). Formuliert jemand im Client «Zeitüberschreitung» um,
blieben sie gruen, und `unreachable` griffe still nie mehr: jeder Ausfall
waere wieder ein `finding`.

Hier entstehen die Meldungen deshalb aus `EnergyHTTPClient.get` selbst, mit
einer per respx simulierten Quelle, und laufen dann durch die Einordnung.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import httpx
import pytest
import respx

from swiss_energy_mcp import api_client

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import classify_live_run as clr  # noqa: E402

URL = f"{api_client.GEOADMIN_BASE}/identify"


async def _haengt(_request: httpx.Request) -> httpx.Response:
    await asyncio.sleep(30)
    return httpx.Response(200, json={})


async def _meldung(**mock) -> str:
    """Die Meldung, so wie pytest sie ins JUnit-XML schreibt: `Typ: Text`."""
    client = api_client.EnergyHTTPClient()
    try:
        with respx.mock:
            respx.get(url__startswith=URL).mock(**mock)
            with pytest.raises(ValueError) as info:
                await client.get(URL)
    finally:
        await client.close()
    return f"ValueError: {info.value}"


AUSFALL = {
    "Netzwerkfehler": {"side_effect": httpx.ConnectError("weg")},
    "httpx-Timeout": {"side_effect": httpx.ReadTimeout("langsam")},
    "HTTP 429": {"return_value": httpx.Response(429)},
    "HTTP 500": {"return_value": httpx.Response(500)},
    "HTTP 502": {"return_value": httpx.Response(502)},
    "HTTP 503": {"return_value": httpx.Response(503)},
    "HTTP 504": {"return_value": httpx.Response(504)},
}

VERTRAG = {
    "HTTP 400": {"return_value": httpx.Response(400)},
    "HTTP 404": {"return_value": httpx.Response(404)},
}


@pytest.mark.parametrize("fall", sorted(AUSFALL))
async def test_ein_ausfall_der_quelle_wird_unreachable(fall, ohne_wartezeit):
    meldung = await _meldung(**AUSFALL[fall])
    assert clr.is_unreachable(meldung), meldung


@pytest.mark.parametrize("fall", sorted(VERTRAG))
async def test_eine_absage_der_quelle_bleibt_ein_befund(fall, ohne_wartezeit):
    """400 und 404 sind Antworten, kein Ausfall: so meldet sich ein umbenannter Layer."""
    meldung = await _meldung(**VERTRAG[fall])
    assert not clr.is_unreachable(meldung), meldung


async def test_das_abgelaufene_gesamtbudget_wird_unreachable(monkeypatch):
    """Die Meldung aus Lauf 177 — mit echter Uhr, das Budget auf 0.2 s verkuerzt."""
    monkeypatch.setattr(api_client, "RETRY_TOTAL_BUDGET", 0.2)
    meldung = await _meldung(side_effect=_haengt)
    assert "25 s" not in meldung  # das verkuerzte Budget steht in der Meldung
    assert clr.is_unreachable(meldung), meldung
