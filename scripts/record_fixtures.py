#!/usr/bin/env python3
"""Zeichnet je eine echte Antwort pro Abfrageform auf.

Warum nicht von Hand geschrieben: eine handgeschriebene Erfolgs-Antwort stimmt
mit dem ueberein, was ihr Autor annahm, und kann die Quelle deshalb nicht
widerlegen. Genau daran ist es hier gescheitert — `tests/conftest.py` baute
CKAN-Zeilen mit `notes`, weil der Code sie so las; opendata.swiss nennt das Feld
`description`, und jede Datensatz-Beschreibung war produktiv leer.

Aufgezeichnet wird an demselben Ort, an dem der Server die Antwort
entgegennimmt: ueber einen httpx-Response-Hook auf dem echten
`EnergyHTTPClient`. Damit tragen Aufzeichnung und Betrieb denselben
User-Agent, dasselbe Timeout und dieselbe DNS-Pinning-Transportschicht; eine
nachgebaute Anfrage taete das nicht.

Zwei Hosts, aber zehn Abfrageformen: `identify` je Layer, `find` je Layer,
`package_search` je Suche. Die Portfolio-Regel «eine Antwort je externem
Endpunkt» waere mit zwei Dateien erfuellt und truege fast nichts — der Name
einer Aufzeichnung ist deshalb aus der *Abfrage* gebildet und nicht aus dem
Werkzeug, das sie ausloest. Zwei Werkzeuge, die dieselbe Abfrage schicken,
teilen sich eine Datei; `energy_location_profile` schickt seine fuenf per
`asyncio.gather` und damit in unbestimmter Reihenfolge, was so keine Rolle
spielt.

Gekuerzt wird nur die **Zahl** der Eintraege, nie ein Feld. Wie stark, steht je
Datei in PROVENANCE.md.

Aufruf:

    python scripts/record_fixtures.py

Schreibt nach `tests/fixtures/` und erzeugt `tests/fixtures/PROVENANCE.md` neu.
Dateien, die kein Plan-Eintrag mehr erzeugt, werden geloescht — sonst waechst
der Ordner und der Nachweis bleibt zurueck.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import sys
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL / "src"))

from swiss_energy_mcp import models  # noqa: E402
from swiss_energy_mcp.api_client import AppContext, EnergyHTTPClient  # noqa: E402
from swiss_energy_mcp.server import build_server  # noqa: E402

FIXTURES = WURZEL / "tests" / "fixtures"

# Mont Crosin im Berner Jura: der einzige Punkt im Land, an dem alle sieben
# BFE-Layer im 10-km-Umkreis etwas liefern — Windpark, Wasserkraft, eine
# PV-Grossanlage, Energiestaedte und Biogas. Ein Fixture-Satz, in dem ein Layer
# leer ist, belegt dessen Form nicht.
MONT_CROSIN = {"lat": 47.1800, "lon": 7.0300, "radius_m": 10000}

VERSUCHE = 4

# Wie viele Trefferzeilen je Antwort bleiben. `identify` liefert bis zu 201
# Features; die Form einer Zeile belegen fuenf genauso gut wie zweihundert.
ZEILEN = 5


@dataclass(frozen=True)
class Aufruf:
    """Ein Werkzeugaufruf, der Anfragen ausloesen soll."""

    werkzeug: str
    eingabe: dict[str, Any]
    # Der Name der Eingabeklasse. Aus `fn.__annotations__` waere er nur eine
    # Zeichenkette — die Werkzeugmodule stehen unter `from __future__ import
    # annotations`, und ein Aufloesen zur Laufzeit brauchte deren Namensraum.
    klasse: str = ""


PLAN: list[Aufruf] = [
    Aufruf("energy_find_power_plants", dict(MONT_CROSIN), "PowerPlantInput"),
    Aufruf("energy_find_wind_turbines", dict(MONT_CROSIN), "LocationInput"),
    Aufruf("energy_find_hydro_plants", dict(MONT_CROSIN), "LocationInput"),
    Aufruf("energy_find_pv_installations", dict(MONT_CROSIN), "LocationInput"),
    Aufruf("energy_find_biogas_plants", dict(MONT_CROSIN), "LocationInput"),
    Aufruf("energy_solar_potential", dict(MONT_CROSIN), "LocationInput"),
    # Zwei Formen desselben Werkzeugs: mit `name` geht es an `find`, mit
    # Koordinaten an `identify`. Eine Aufzeichnung belegte nur die halbe Sache.
    Aufruf("energy_find_energy_cities", {"name": "Zürich"}, "EnergyCityInput"),
    Aufruf("energy_find_energy_cities", dict(MONT_CROSIN), "EnergyCityInput"),
    # Fuenf Layer per asyncio.gather — vier davon ueberschneiden sich mit den
    # Einzelwerkzeugen oben und landen deshalb in denselben Dateien.
    Aufruf("energy_location_profile", dict(MONT_CROSIN), "LocationInput"),
    Aufruf("energy_search_bfe_datasets", {"query": "wasserkraft", "limit": 10}, "SearchInput"),
    # `energy_check_status` schickt eine eigene `find`-Abfrage (ohne
    # `returnGeometry`) und eine eigene Suche mit `rows=1`.
    Aufruf("energy_check_status", {}),
]


@dataclass
class Antwort:
    """Eine gesehene Antwort samt der Anfrage, die sie ausgeloest hat."""

    url: httpx.URL
    text: str
    werkzeuge: list[str] = field(default_factory=list)
    original_bytes: int = 0
    gekuerzt_von: int = 0
    behalten: int = 0
    sha256: str = ""
    bytes: int = 0
    # Der endgueltige Dateiname. Kommt aus `name` und traegt bei einer Kollision
    # einen Zaehler; er wird beim Schreiben gesetzt.
    dateiname: str = ""

    @property
    def name(self) -> str:
        """Der Dateiname, aus der Abfrage gebildet — nicht aus dem Werkzeug."""
        pfad = self.url.path.rsplit("/", 1)[-1]
        if pfad == "identify":
            layer = self.url.params.get("layers", "").removeprefix("all:")
            return f"identify_{_kurz(layer)}.json"
        if pfad == "find":
            layer = self.url.params.get("layer", "")
            feld = self.url.params.get("searchField", "")
            return f"find_{_kurz(layer)}_{feld}.json"
        if pfad == "package_search":
            rows = self.url.params.get("rows", "")
            return f"package_search_rows{rows}.json"
        raise RuntimeError(f"unbekannte Abfrageform: {self.url}")


def _kurz(layer: str) -> str:
    """`ch.bfe.windenergieanlagen` → `windenergieanlagen`."""
    return layer.removeprefix("ch.bfe.").replace("-", "_")


def _hook_fuer(gesehen: list[Antwort]) -> Callable[[httpx.Response], Awaitable[None]]:
    """Baut den Response-Hook fuer einen Versuch.

    Eigene Funktion, damit die Liste als Argument gebunden ist und nicht als
    Schleifenvariable aus dem umgebenden Namensraum (ruff B023).
    """

    async def hook(response: httpx.Response) -> None:
        await response.aread()
        gesehen.append(Antwort(url=response.request.url, text=response.text))

    return hook


class _Kontext:
    """Der Context, den MCPServer sonst reicht — mit dem echten Client."""

    def __init__(self, client: EnergyHTTPClient) -> None:
        self.request_context = SimpleNamespace(lifespan_context=AppContext(client=client))

    async def info(self, message: str, **extra: object) -> None: ...

    async def warning(self, message: str, **extra: object) -> None: ...

    async def error(self, message: str, **extra: object) -> None: ...

    async def report_progress(self, *a: object, **kw: object) -> None: ...


async def _fahre(a: Aufruf, server: Any, client: EnergyHTTPClient) -> list[Antwort]:
    """Ruft ein Werkzeug und gibt die dabei gesehenen Antworten zurueck."""
    fn = server._tool_manager.get_tool(a.werkzeug).fn
    letzter: Exception | None = None

    for versuch in range(VERSUCHE):
        if versuch:
            await asyncio.sleep(2**versuch)
        gesehen: list[Antwort] = []
        hook = _hook_fuer(gesehen)
        hooks = client._client.event_hooks
        hooks.setdefault("response", []).append(hook)
        try:
            # `energy_check_status` nimmt nur den Context, alle anderen ein
            # Eingabemodell davor.
            if a.klasse:
                modell = getattr(models, a.klasse)
                await fn(modell(**a.eingabe), _Kontext(client))
            else:
                await fn(_Kontext(client))
        except Exception as e:  # noqa: BLE001 — jeder Fehler ist hier ein Retry-Grund
            letzter = e
            continue
        finally:
            hooks["response"].remove(hook)

        if not gesehen:
            letzter = RuntimeError(f"{a.werkzeug} hat keine Anfrage abgeschickt")
            continue
        for antwort in gesehen:
            antwort.werkzeuge.append(a.werkzeug)
        return gesehen

    raise RuntimeError(f"{a.werkzeug} nach {VERSUCHE} Versuchen nicht aufgezeichnet: {letzter}")


def _kuerze(daten: Any) -> tuple[int, int]:
    """Kuerzt die Trefferliste auf `ZEILEN`; gibt (vorher, nachher).

    `count` bleibt stehen: CKAN meldet dort die Gesamtzahl der Treffer und
    nicht die Zahl der gelieferten Zeilen, und genau die liest der Server aus.
    """
    if isinstance(daten.get("results"), list):  # GeoAdmin identify / find
        ziel, schluessel = daten, "results"
    elif isinstance(daten.get("result"), dict):  # CKAN package_search
        ziel, schluessel = daten["result"], "results"
    else:
        return 0, 0
    vorher = len(ziel[schluessel])
    ziel[schluessel] = ziel[schluessel][:ZEILEN]
    return vorher, len(ziel[schluessel])


async def main() -> int:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    heute = datetime.now(UTC).date().isoformat()
    server = build_server()
    nach_url: dict[str, Antwort] = {}

    client = EnergyHTTPClient()
    try:
        for a in PLAN:
            print(f"… {a.werkzeug} {a.eingabe}", file=sys.stderr)
            for antwort in await _fahre(a, server, client):
                schluessel = str(antwort.url)
                if schluessel in nach_url:
                    # Dieselbe Abfrage aus einem zweiten Werkzeug — eine Datei
                    # genuegt, aber der Nachweis nennt beide Werkzeuge.
                    vorhanden = nach_url[schluessel]
                    if a.werkzeug not in vorhanden.werkzeuge:
                        vorhanden.werkzeuge.append(a.werkzeug)
                    continue
                nach_url[schluessel] = antwort
    finally:
        await client.close()

    belegt: dict[str, str] = {}
    for antwort in nach_url.values():
        name = antwort.name
        if name in belegt:
            # Gleicher Endpunkt und Layer, andere Parameter — also doch zwei
            # Abfrageformen. Der Fall ist real: `energy_check_status` baut seine
            # `find`-Anfrage von Hand und laesst dabei `returnGeometry=false`
            # weg, das `find_geoadmin_by_name()` mitschickt. Beide werden
            # aufgezeichnet; welche zu wem gehoert, steht im Nachweis.
            zaehler = 2
            while f"{name[:-5]}_{zaehler}.json" in belegt:
                zaehler += 1
            name = f"{name[:-5]}_{zaehler}.json"
        antwort.dateiname = name
        belegt[name] = str(antwort.url)

        daten = json.loads(antwort.text)
        antwort.original_bytes = len(antwort.text.encode("utf-8"))
        antwort.gekuerzt_von, antwort.behalten = _kuerze(daten)
        # Neu eingerueckt geschrieben: eine Zeile JSON waere kleiner, aber im
        # Diff nicht lesbar, und ein Fixture will gelesen werden.
        (FIXTURES / name).write_text(
            json.dumps(daten, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        roh = (FIXTURES / name).read_bytes()
        antwort.sha256 = hashlib.sha256(roh).hexdigest()
        antwort.bytes = len(roh)

    _schreibe_provenance(sorted(nach_url.values(), key=lambda x: x.dateiname), heute)

    # Aufraeumen: was kein Plan-Eintrag mehr erzeugt, hat auch keinen Nachweis.
    geschrieben = set(belegt) | {"PROVENANCE.md"}
    for pfad in sorted(FIXTURES.iterdir()):
        if pfad.name not in geschrieben:
            print(f"– entferne veraltet: {pfad.name}", file=sys.stderr)
            pfad.unlink()

    print(f"{len(belegt)} Aufzeichnungen in {FIXTURES}", file=sys.stderr)
    return 0


def _schreibe_provenance(antworten: list[Antwort], heute: str) -> None:
    zeilen = [
        "# Herkunft der Fixtures",
        "",
        f"Aufgezeichnet am **{heute}** mit `python scripts/record_fixtures.py`.",
        "",
        "Eine Antwort je **Abfrageform**, nicht je Endpunkt: dieser Server spricht mit",
        "zwei Hosts, aber in zehn Abfrageformen (`identify` je Layer, `find` je Layer,",
        "`package_search` je Suche). Zwei Dateien wuerden die Portfolio-Regel erfuellen",
        "und fast nichts belegen.",
        "",
        "Die Antworten stammen aus dem echten `EnergyHTTPClient` (gleicher User-Agent,",
        "gleiches Timeout, gleiche DNS-Pinning-Transportschicht wie im Betrieb),",
        "abgegriffen ueber einen httpx-Response-Hook. Ausgeloest hat sie jeweils das",
        "Werkzeug selbst — so belegt die Aufzeichnung auch, dass das Werkzeug genau",
        "diese Abfrage schickt.",
        "",
        "Neu gesetzt ist die Einrueckung; gekuerzt ist allein die **Zahl** der",
        "Trefferzeilen. Kein Feld einer behaltenen Zeile ist angetastet, und `count`",
        "steht wie geliefert — CKAN meldet dort die Gesamtzahl der Treffer, nicht die",
        "Zahl der gelieferten Zeilen, und genau die liest der Server aus.",
        "",
        "Die Fehlerpfade — Timeout, 5xx, leere Trefferliste, `success: false` — bleiben",
        "handgeschrieben. Sie lassen sich nicht auf Zuruf aufzeichnen und sind als",
        "Erfindung in Ordnung.",
        "",
        "Aufnahmeort ist Mont Crosin im Berner Jura (47.18 N, 7.03 E, 10 km): der",
        "einzige Punkt, an dem alle sieben BFE-Layer etwas liefern. Ein Satz, in dem",
        "ein Layer leer ist, belegt dessen Form nicht.",
        "",
    ]
    for a in antworten:
        zeilen += [
            f"## `{a.dateiname}`",
            "",
            f"- **Werkzeuge:** {', '.join(f'`{w}`' for w in sorted(a.werkzeuge))}",
            f"- **URL:** `{a.url}`",
        ]
        if a.gekuerzt_von > a.behalten:
            zeilen.append(
                f"- **Auswahl:** die ersten {a.behalten} von {a.gekuerzt_von} "
                f"Trefferzeilen, aus {a.original_bytes} Bytes Rohantwort"
            )
        else:
            zeilen.append(f"- **Auswahl:** ungekuerzt ({a.behalten} Trefferzeilen)")
        zeilen += [
            f"- **Groesse:** {a.bytes} Bytes",
            f"- **SHA-256:** `{a.sha256}`",
            "",
        ]
    (FIXTURES / "PROVENANCE.md").write_text("\n".join(zeilen), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
