"""Die Server-Identitaet, wie Spec 2026-07-28 sie fuehrt — in beiden Aeren.

Die moderne Aera haengt den Identitaetsblock unter
`_meta["io.modelcontextprotocol/serverInfo"]` an **jede** Antwort; die
Handshake-Aera fuehrt ihn einmalig in `initialize.serverInfo`. Beide speisen
sich aus demselben `MCPServer`-Konstruktor, und genau deshalb wird hier beides
gemessen: eine Zusicherung nur gegen eine Aera bliebe gruen, waehrend die
andere etwas anderes erzaehlt.

**Der Fehler, gegen den diese Datei geschrieben ist.** Der SDK-Vorgabewert von
`MCPServer(version=...)` ist der LEERE String, kein Fehler und keine Warnung.
Ohne das Argument stellt sich der Server jedem Client als
`{"name": "swiss_energy_mcp", "version": ""}` vor — in der modernen Aera bei
jedem einzelnen Aufruf. Alle Gates blieben dabei gruen: eine leere Identitaet
ist eine formal gueltige Antwort. Aufgefallen ist es erst an
`server/discover`, der Identitaetsprobe der Spec.

Gemessen wird durch den zusammengebauten ASGI-Stack, nicht an
`build_server(...)` abgelesen. Ein Konstruktorargument kann richtig gesetzt
sein und trotzdem nicht in der Antwort landen — das ist derselbe Unterschied
wie bei der CORS-Schicht, die sich lange nur lesen und nicht ausprobieren
liess.

Die Version wird gegen die **Paket-Metadaten** geprueft, nicht gegen
`swiss_energy_mcp.__version__`. Beide aus derselben Quelle zu lesen waere eine
Tautologie: ein wieder eingefuegtes Literal in `server.py` bliebe damit
unbemerkt, und genau diese Drift ist der Grund, warum
`scripts/check_version_sync.py` ueberhaupt existiert.
"""

from __future__ import annotations

import json
from importlib.metadata import version as _distribution_version
from typing import Any

import httpx
import pytest
from mcp_types import SERVER_INFO_META_KEY

from swiss_energy_mcp.server import build_http_app

MODERN_VERSION = "2026-07-28"
PROTOCOL_VERSION_KEY = "io.modelcontextprotocol/protocolVersion"
CLIENT_CAPABILITIES_KEY = "io.modelcontextprotocol/clientCapabilities"

_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
    "Host": "127.0.0.1:8000",
}

# Die auflistenden Methoden der modernen Aera. Jede einzelne traegt den
# Identitaetsblock; die Liste steht hier, damit ein Server, der ihn nur an
# `server/discover` haengt, nicht durchkommt.
MODERN_METHODS = (
    "server/discover",
    "tools/list",
    "resources/list",
    "resources/templates/list",
    "prompts/list",
)


def _unwrap(response: httpx.Response) -> dict[str, Any]:
    """JSON-RPC-Antwort aus einer moeglicherweise SSE-gerahmten Antwort."""
    body = response.text
    for line in body.splitlines():
        if line.startswith("data: "):
            body = line[len("data: ") :]
    return json.loads(body)


async def _post(headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
    app = build_http_app()
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://127.0.0.1:8000"
        ) as client:
            response = await client.post("/mcp", headers={**_HEADERS, **headers}, json=payload)
    return _unwrap(response)


async def _modern_server_info(method: str) -> dict[str, Any]:
    """`_meta`-Identitaetsblock einer Antwort der modernen Aera."""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": {
            "_meta": {
                PROTOCOL_VERSION_KEY: MODERN_VERSION,
                CLIENT_CAPABILITIES_KEY: {},
            }
        },
    }
    headers = {"Mcp-Method": method, "Mcp-Protocol-Version": MODERN_VERSION}
    result = (await _post(headers, payload)).get("result", {})
    return result.get("_meta", {}).get(SERVER_INFO_META_KEY, {})


async def _handshake_server_info() -> dict[str, Any]:
    """`serverInfo` aus einem echten `initialize` der Handshake-Aera."""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-11-25",
            "capabilities": {},
            "clientInfo": {"name": "identity-probe", "version": "1"},
        },
    }
    return (await _post({}, payload)).get("result", {}).get("serverInfo", {})


@pytest.mark.parametrize("method", MODERN_METHODS)
async def test_jede_moderne_antwort_traegt_die_identitaet(method: str) -> None:
    """Der Block haengt an jeder Antwort, nicht nur an der Identitaetsprobe."""
    info = await _modern_server_info(method)
    assert info, f"{method} liefert keinen {SERVER_INFO_META_KEY}-Block"
    assert info.get("name") == "swiss_energy_mcp"


@pytest.mark.parametrize("method", MODERN_METHODS)
async def test_die_moderne_aera_meldet_eine_nichtleere_version(method: str) -> None:
    """Der lasttragende Fall — und der, der ohne Argument still leer blieb.

    Getrennt von der Metadaten-Gleichheit unten: «leer» ist der beobachtete
    Fehler, «falsch» waere ein anderer. Eine einzige Zusicherung ueber beides
    wuerde im Fehlerfall nicht sagen, welcher von beiden eingetreten ist.
    """
    info = await _modern_server_info(method)
    assert info.get("version"), (
        f"{method} meldet version={info.get('version')!r}. Der SDK-Vorgabewert "
        "von `MCPServer(version=...)` ist der leere String — fehlt das "
        "Argument in `build_server`, stellt sich der Server ohne Version vor, "
        "ohne dass irgendein Gate rot wird."
    )


async def test_die_gemeldete_version_ist_die_der_paket_metadaten() -> None:
    """Gegen die Distribution geprueft, nicht gegen `__version__`.

    Faellt dieser Test bei gruenem Test oben, steht in `server.py` wieder ein
    Literal statt des Metadaten-Werts.
    """
    info = await _modern_server_info("server/discover")
    assert info.get("version") == _distribution_version("swiss-energy-mcp")


async def test_die_identitaet_nennt_titel_und_projektadresse() -> None:
    """Die uebrigen Felder, die Spec 2026-07-28 im Identitaetsblock fuehrt."""
    info = await _modern_server_info("server/discover")
    assert info.get("title"), "kein `title` im Identitaetsblock"
    website = info.get("websiteUrl")
    assert website, "keine `websiteUrl` im Identitaetsblock"
    assert website.startswith("https://"), website


async def test_beide_aeren_melden_dieselbe_identitaet() -> None:
    """Eine Aera allein gemessen liesse die andere frei driften.

    Der Handshake fuehrt den Block an einer voellig anderen Stelle der Antwort
    (`result.serverInfo` statt `result._meta[...]`). Dass beide denselben
    Konstruktor speisen, ist eine Eigenschaft des SDK — und damit etwas, das
    ein Bump aendern kann, ohne dass es hier sonst auffiele.
    """
    assert await _handshake_server_info() == await _modern_server_info("server/discover")
