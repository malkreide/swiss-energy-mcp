"""Die CKAN-Hülle wird bestätigt, nicht angenommen (FID-006).

`search_opendata_swiss` schrieb:

    result = data.get("result", {})
    return {"count": result.get("count", 0), "results": result.get("results", [])}

Drei Defaults hintereinander, und zusammen ergeben sie den denkbar
irreführendsten Rückgabewert: Fällt `result` weg, kommt buchstäblich
`{"count": 0, "results": []}` heraus. Das ist nicht «etwas ist kaputt», das ist
«opendata.swiss hat null Treffer» — dieselbe Antwort, die eine korrekte, leere
Suche liefert, und für das Modell nicht davon zu unterscheiden.

Der Portfolio-Durchlauf am 2026-08-07 fand acht Server, die mit CKAN sprechen.
Alle acht prüfen das `success`-Envelope, sieben defaulteten `result` danach.
Dieser hier war der einzige, bei dem der Default bis auf die Zählung
durchschlug.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from swiss_energy_mcp.api_client import (
    OPENDATA_SWISS_BASE,
    EnergyHTTPClient,
    UpstreamSchemaError,
    search_opendata_swiss,
)


def _mock(payload):
    return respx.get(url__startswith=f"{OPENDATA_SWISS_BASE}/package_search").mock(
        return_value=httpx.Response(200, json=payload)
    )


async def _search(**kwargs):
    """Client bauen, suchen, schliessen — wie der Rest der Suite es tut.

    `EnergyHTTPClient` heisst `close()`, nicht `aclose()`; und die vorhandenen
    Tests in `test_tools.py` bauen den Client im Testkörper statt in einer
    Fixture. Beides hier übernommen, damit ein Leser nicht zwei Idiome für
    dieselbe Sache vor sich hat.

    Kein Test hier geht ins Netz: `respx.mock` patcht
    `httpx.AsyncHTTPTransport` auf Klassenebene, greift also auch für den
    `_PinningTransport` dieses Repos — nachgemessen, `route.called` ist wahr.
    Dass httpx auch für eine gemockte Antwort ein «HTTP Request … 200 OK» ins
    Log schreibt, sieht im Fehlerbericht wie ein echter Aufruf aus und ist
    keiner.
    """
    client = EnergyHTTPClient()
    try:
        return await search_opendata_swiss(client, **kwargs)
    finally:
        await client.close()


# --- Der Fund ----------------------------------------------------------------


@respx.mock
async def test_a_missing_result_is_not_a_search_with_no_hits():
    """Die Kernzusage, und ihr Name ist die ganze Begründung.

    Vorher: `{"count": 0, "results": []}` — ununterscheidbar von einer
    korrekten, leeren Suche.
    """
    _mock({"success": True, "help": "https://opendata.swiss/api/3/"})
    with pytest.raises(UpstreamSchemaError):
        await _search(query="solar")


@respx.mock
async def test_a_result_without_count_is_rejected():
    """Die Ebene darunter zählt genauso.

    `package_search` liefert `count` und `results` **immer**, auch bei null
    Treffern. Fehlt eines, ist das eine andere Antwort und keine leere Suche.
    """
    _mock({"success": True, "result": {"results": []}})
    with pytest.raises(UpstreamSchemaError) as excinfo:
        await _search(query="solar")
    assert "count" in str(excinfo.value)


@respx.mock
async def test_a_result_without_results_is_rejected():
    _mock({"success": True, "result": {"count": 0}})
    with pytest.raises(UpstreamSchemaError) as excinfo:
        await _search(query="solar")
    assert "results" in str(excinfo.value)


@respx.mock
async def test_the_message_names_the_keys_that_are_actually_there():
    """Ohne die vorhandenen Schlüssel ist der nächste Schritt Raten."""
    _mock({"success": True, "help": "…", "payload": {}})
    with pytest.raises(UpstreamSchemaError) as excinfo:
        await _search(query="solar")
    message = str(excinfo.value)
    assert "'help'" in message and "'payload'" in message, message
    assert "keine Leermenge" in message


@respx.mock
async def test_a_bare_list_instead_of_the_envelope_raises():
    """Vorher ein `AttributeError` aus `.get` — laut, aber unbenannt."""
    _mock([{"name": "irgendwas"}])
    with pytest.raises(UpstreamSchemaError) as excinfo:
        await _search(query="solar")
    assert "list" in str(excinfo.value)


# --- Die Gegenrichtung, und sie ist die wichtigere Hälfte --------------------


@respx.mock
async def test_a_genuinely_empty_search_still_passes():
    """Ein Wächter, der die echte Leermenge mitfängt, wird abgeschaltet.

    `count: 0` bei vorhandenem `results` ist eine **Aussage der Quelle**. Genau
    diese Antwort muss weiterhin durchgehen, sonst hat die Reparatur die
    Fehlerklasse nur verschoben.
    """
    _mock({"success": True, "result": {"count": 0, "results": []}})
    out = await _search(query="gibtesnicht")
    assert out == {"count": 0, "results": []}


@respx.mock
async def test_a_normal_search_still_passes():
    _mock({"success": True, "result": {"count": 1, "results": [{"title": "PV"}]}})
    out = await _search(query="solar")
    assert out["count"] == 1
    assert out["results"] == [{"title": "PV"}]


@respx.mock
async def test_a_real_ckan_error_stays_a_ckan_error():
    """Die Quelle hat geantwortet und Nein gesagt — keine Formänderung.

    Die beiden auseinanderzuhalten ist der Zweck des eigenen Typs.
    """
    _mock({"success": False, "error": {"message": "Not authorized"}})
    with pytest.raises(ValueError) as excinfo:
        await _search(query="solar")
    assert not isinstance(excinfo.value, UpstreamSchemaError)
