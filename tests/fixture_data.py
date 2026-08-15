"""Zugriff auf die aufgezeichneten Antworten in `tests/fixtures/`.

Ein Loader statt `open()` an jeder Stelle: so gibt es genau einen Ort, der weiss,
wo die Aufzeichnungen liegen, und die Tests koennen ueber sie iterieren, statt
eine Liste von Hand zu pflegen, die zurueckbleibt.

Der Recorder wird hier als Modul geladen — nicht ausgefuehrt. Das hat zwei
Gruende: seine Namensregel ist dieselbe, nach der der Test-Dispatcher eine
Anfrage ihrer Aufzeichnung zuordnet (zwei Kopien der Regel liefen
auseinander), und der Import prueft nebenbei, dass das Skript ueberhaupt laedt.
Im Betrieb ruft es niemand auf, und ruff kaeme einem Fehler darin nicht bei.

Neu aufzeichnen mit `python scripts/record_fixtures.py`; Herkunft, Datum,
Auswahlregel und SHA-256 je Datei stehen in `tests/fixtures/PROVENANCE.md`.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

import httpx

WURZEL = Path(__file__).resolve().parent.parent
FIXTURES = WURZEL / "tests" / "fixtures"


@lru_cache(maxsize=1)
def recorder() -> Any:
    """Laedt `scripts/record_fixtures.py` als Modul, ohne `main()` zu rufen."""
    pfad = WURZEL / "scripts" / "record_fixtures.py"
    name = "record_fixtures_probe"
    spec = importlib.util.spec_from_file_location(name, pfad)
    if spec is None or spec.loader is None:  # pragma: no cover
        raise RuntimeError(f"{pfad} laesst sich nicht als Modul laden")
    modul = importlib.util.module_from_spec(spec)
    # Vor dem Ausfuehren registrieren: `@dataclass` schlaegt das eigene Modul in
    # `sys.modules` nach, um Annotationen aufzuloesen, und faellt sonst um.
    sys.modules[name] = modul
    try:
        spec.loader.exec_module(modul)
    finally:
        del sys.modules[name]
    return modul


def name_fuer(url: httpx.URL | str) -> str:
    """Der Name der Aufzeichnung, die zu dieser Abfrage gehoert.

    Dieselbe Regel, nach der der Recorder benennt — buchstaeblich dieselbe
    Funktion, damit Aufzeichnen und Abspielen nicht auseinanderlaufen koennen.
    """
    return recorder().Antwort(url=httpx.URL(url), text="").name


def fixture_text(name: str) -> str:
    """Die Aufzeichnung als Text — so, wie sie ueber die Leitung kaeme."""
    pfad = FIXTURES / name
    if not pfad.is_file():
        raise FileNotFoundError(f"keine Aufzeichnung {name} in {FIXTURES}")
    return pfad.read_text(encoding="utf-8")


def fixture_json(name: str) -> Any:
    """Die Aufzeichnung geparst."""
    return json.loads(fixture_text(name))


@lru_cache(maxsize=1)
def recorded_names() -> tuple[str, ...]:
    """Alle Aufzeichnungen im Ordner — nicht die, die ein Test erwartet.

    Der Unterschied ist der Punkt: eine Datei, die niemand erwartet, faellt
    sonst niemandem auf.
    """
    return tuple(sorted(p.name for p in FIXTURES.glob("*.json")))


def provenance() -> str:
    return (FIXTURES / "PROVENANCE.md").read_text(encoding="utf-8")
