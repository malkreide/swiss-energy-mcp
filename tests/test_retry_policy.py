"""Retry-Policy: Retry-After, Jitter und der Deckel.

Zusammen mit dem NEUEN Retry aus der mcp-data-source-probe-Vorlage übernommen.
Anders als bei den Schwester-Servern war hier nichts zu härten: Dieser Client
hatte gar keinen Retry — ein Grep über `src/` fand null Vorkommen von
`asyncio.sleep`, `backoff` oder `attempt`.
"""

from __future__ import annotations

import re
import time
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from pathlib import Path

import httpx
import pytest
import respx

from swiss_energy_mcp import api_client

# --- Retry policy: Retry-After, jitter, and the cap --------------------------
# Adopted together with the hardened retry from the mcp-data-source-probe
# reference template. These assert the behaviour, not the constants: a
# deterministic ladder and an unread `Retry-After` are what a sweep across
# eleven servers found on 2026-08-03, and every one of them looked fine.


def _retry_after_error(value: str) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "https://example.invalid/")
    return httpx.HTTPStatusError(
        "",
        request=request,
        response=httpx.Response(429, headers={"Retry-After": value}, request=request),
    )


def test_retry_after_reads_both_rfc9110_forms() -> None:
    def resp(status: int, headers: dict[str, str]) -> httpx.Response:
        request = httpx.Request("GET", "https://example.invalid/")
        return httpx.Response(status, headers=headers, request=request)

    assert api_client.parse_retry_after(resp(429, {"Retry-After": "120"})) == 120.0

    later = format_datetime(datetime.now(UTC) + timedelta(seconds=90))
    seconds = api_client.parse_retry_after(resp(503, {"Retry-After": later}))
    assert seconds is not None and 80 < seconds <= 90

    # A date in the past means "now", never a negative wait.
    past = "Wed, 21 Oct 2020 07:28:00 GMT"
    assert api_client.parse_retry_after(resp(503, {"Retry-After": past})) == 0.0

    # Unparseable falls back to the curve. It must not crash on the error path,
    # which is the one path already going badly.
    assert api_client.parse_retry_after(resp(429, {"Retry-After": "bald"})) is None
    assert api_client.parse_retry_after(resp(429, {})) is None

    # 500 does not carry a meaningful Retry-After.
    assert api_client.parse_retry_after(resp(500, {"Retry-After": "120"})) is None
    assert api_client.parse_retry_after(None) is None


def test_backoff_is_jittered() -> None:
    delays = {api_client.compute_delay(3, None) for _ in range(300)}
    # attempt 3 -> 2 * 2**2 = 8s, spread into [0.5x, 1.5x]
    assert len(delays) > 1, "a deterministic ladder synchronises every client"
    assert min(delays) >= 4.0
    assert max(delays) <= 12.0


def test_cap_binds_after_the_jitter() -> None:
    # Capping first and then multiplying by up to 1.5 would land at 30s, and
    # the constant would claim a ceiling it does not hold.
    deep = {api_client.compute_delay(9, None) for _ in range(200)}
    assert max(deep) <= api_client.RETRY_MAX_DELAY

    hinted = _retry_after_error("600")
    assert {api_client.compute_delay(1, hinted) for _ in range(100)} == {api_client.RETRY_MAX_DELAY}


def test_retry_after_jitter_is_one_sided() -> None:
    """The source said when. Later is polite; earlier ignores the value read."""
    delays = {api_client.compute_delay(1, _retry_after_error("4")) for _ in range(300)}
    assert min(delays) >= 4.0, "never earlier than the source asked for"
    assert max(delays) <= 5.0  # 4 * 1.25


# --- Die Naht, an der Tests die Wartezeit ersetzen ---------------------------
# Zwei Zusicherungen, die zusammengehoeren: dass der Schlaf ueberhaupt eine
# eigene Naht hat, und dass niemand stattdessen ins fremde Modul greift.


async def test_die_fixture_nullt_die_wartezeit_wirklich(ohne_wartezeit) -> None:
    """Misst die Uhr, nicht den Aufruf.

    Eine Fixture, die den falschen Namen patcht, faellt an keiner der beiden
    Zusicherungen unten auf — sie laesst nur den Lauf laenger dauern, und eine
    laengere Laufzeit liest niemand. Diese hier wartet den vollen Ladder ab,
    wenn die Naht nicht greift: 2 + 4 + 8 Sekunden.
    """
    client = api_client.EnergyHTTPClient()
    start = time.monotonic()
    try:
        with respx.mock:
            respx.get(url__startswith=api_client.GEOADMIN_BASE).mock(
                return_value=httpx.Response(503)
            )
            with pytest.raises(ValueError):
                await client.get(f"{api_client.GEOADMIN_BASE}/identify")
    finally:
        await client.close()
    gebraucht = time.monotonic() - start
    assert gebraucht < 2.0, f"der Backoff hat wirklich geschlafen: {gebraucht:.1f}s"


def test_der_schlaf_haengt_an_einem_modul_alias() -> None:
    """`_sleep` ist die Naht — ohne sie muesste man `asyncio.sleep` ersetzen."""
    quelle = Path(api_client.__file__).read_text(encoding="utf-8")
    assert "_sleep = asyncio.sleep" in quelle
    assert "await _sleep(" in quelle
    assert "await asyncio.sleep(" not in quelle, "eine Wartestelle umgeht den Alias"


def test_kein_test_patcht_die_wartezeit_am_fremden_modul() -> None:
    """Ein `setattr` auf `sleep` im Modul `asyncio` entschaerft es prozessweit.

    Dann verlieren httpx, respx und pytest-asyncio dieselbe Mechanik, und was
    danach gruen ist, sagt nichts mehr. Gepatcht wird stattdessen der Alias
    `api_client._sleep`; dafuer gibt es die Fixture `ohne_wartezeit`.

    Der Ausdruck unten trifft die Aufrufform, nicht das blosse Wort. Dieser
    Text vermeidet sie deshalb — beim ersten Schreiben stand sie hier, und die
    Zusicherung zeigte korrekterweise die eigene Datei an.
    """
    verboten = re.compile(r"setattr\([^)]*asyncio[^)]*sleep")
    schuldig = [
        p.name
        for p in Path(__file__).parent.glob("test_*.py")
        if verboten.search(p.read_text(encoding="utf-8"))
    ]
    assert not schuldig, f"patcht asyncio.sleep am fremden Modul: {schuldig}"
