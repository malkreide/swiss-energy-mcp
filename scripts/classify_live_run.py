#!/usr/bin/env python3
"""Was hat der geplante Live-Lauf festgestellt — clear, finding, unreachable oder unknown?

WARUM DAS EIN SKRIPT IST UND KEIN YAML-BLOCK
--------------------------------------------
`if: failure()` kennt zwei Antworten: rot und nicht rot. Ein Live-Lauf hat
vier, und die vierte ist die, die zaehlt:

  clear        Die Suite ist gelaufen und war gruen.
  finding      Die Suite ist gelaufen und etwas ist gefallen.
  unreachable  Die Suite ist gelaufen, und JEDER Fehlschlag endete an einer
               Quelle, die nicht oder nicht rechtzeitig geantwortet hat.
  unknown      Die Suite ist NICHT gelaufen — und niemand weiss, ob der Vertrag
               mit der Quelle noch haelt.

Ein gescheitertes `pip install`, ein Timeout, eine umbenannte Marke: alles
`unknown`, alles sieht unter `if: failure()` aus wie ein gebrochener Vertrag.
Und ein Lauf, in dem jeder Test uebersprungen wurde, sieht unter jedem
Exit-Code-Check aus wie Erfolg.

Diese Einordnung entscheidet, ob ein Issue aufgeht oder zugeht. Sie in einen
`run:`-Block zu schreiben hiesse, den einzigen Teil des Workflows, der etwas
behauptet, an die einzige Stelle zu legen, an der ihn niemand testen kann.
Deshalb steht sie hier, neben ihrem Test.

DER UEBERSPRUNGENE LAUF
-----------------------
Gemessen am 7.8.2026 an `swiss-transport-mcp`: Ohne `TRANSPORT_API_KEY`
ueberspringt die Live-Suite alle sechs Tests, und pytest endet mit 0. Ein
woechentlicher Job haette gemeldet: gruen. Geprueft haette er nichts — und ein
offenes Issue haette er zugemacht, mit einem Vergleich, den es nie gab.

`tests - skipped == 0` ist deshalb `unknown` und nicht `clear`. Ein Secret, das
niemand gesetzt hat, ist kein gruener Vertrag mit der Quelle; es ist gar keiner.

DIE NICHT ERREICHBARE QUELLE
----------------------------
Am 20.10. und am 10.11.2026 fielen je drei Tests, weil `api3.geo.admin.ch`
einige Minuten lang nicht innerhalb von 25 s antwortete. Beide Male ging ein
Issue auf, das wie ein gebrochener Vertrag aussah, und beide Male war am
naechsten Tag alles gruen. Ein Ausfall gehoert gesehen, aber nicht
verwechselt: `unreachable` macht den Job weiter rot und das Issue weiter auf,
sagt aber im Titel, dass nichts zu fixen ist.

Die Einordnung liest dafuer die Meldung jedes Fehlschlags. Nur wenn JEDER
einzelne an einer Zeitueberschreitung, einem Netzwerkfehler oder HTTP 429/5xx
endet, ist es `unreachable`. Ein 404 zaehlt nicht dazu (ein umbenannter Layer
antwortet so), und ein einziger anderer Fehlschlag macht den ganzen Lauf zum
`finding`: Der koennte genau der Vertragsbruch sein, den diese Suite finden
soll.

DIE QUELLE IST DAS JUNIT-XML, NICHT DER EXIT-CODE
-------------------------------------------------
Der Exit-Code von pytest sagt 0 fuer «alles gruen» und fuer «alles
uebersprungen» dasselbe. Das XML zaehlt Tests, Fehler, Fehlschlaege und
Uebersprungene getrennt, also wird es gelesen. Fehlt es, ist pytest gar nicht
bis zum Schreiben gekommen — auch das ist `unknown`, und zwar mit Grund.

Aufruf:
    python scripts/classify_live_run.py live-report.xml
    python scripts/classify_live_run.py live-report.xml --pytest-exit 1

Gibt `state=...` und `reason=...` auf stdout aus und haengt beides an
`$GITHUB_OUTPUT` an, wenn die Variable gesetzt ist. Der Exit-Code ist immer 0:
Ueber rot oder gruen entscheidet der Workflow, nicht dieser Reporter.
"""

from __future__ import annotations

import argparse
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path

CLEAR = "clear"
FINDING = "finding"
UNKNOWN = "unknown"
UNREACHABLE = "unreachable"

# Die Meldungen, mit denen `EnergyHTTPClient.get` eine Quelle meldet, die
# nicht oder nicht rechtzeitig geantwortet hat. 400 und 404 stehen bewusst
# NICHT hier: Ein umbenannter Layer antwortet genau so, und das ist ein
# gebrochener Vertrag. tests/test_live_einordnung_meldungen.py haelt die
# Liste gegen die Meldungen, die der Client wirklich erzeugt.
_UNREACHABLE_MARKERS = (
    re.compile(r"Zeitüberschreitung bei der Anfrage"),
    re.compile(r"Netzwerkfehler bei der Anfrage"),
    re.compile(r"\(HTTP (?:429|5\d\d)\)"),
)


def is_unreachable(message: str) -> bool:
    """Endet dieser Fehlschlag an einer Quelle, die nicht erreichbar war?"""
    return any(marker.search(message) for marker in _UNREACHABLE_MARKERS)


def _failure_messages(suites: list[ET.Element]) -> list[str]:
    """Das `message`-Attribut jedes Fehlschlags und Fehlers.

    Nur die Meldung, nicht der Traceback: Der zeigt Quellzeilen des Clients,
    und dort stehen alle Meldungen woertlich — auch die eines 404.
    """
    return [
        child.get("message") or ""
        for suite in suites
        for case in suite.iter("testcase")
        for child in case
        if child.tag in ("failure", "error")
    ]


def classify(report: Path, pytest_exit: int | None = None) -> tuple[str, str]:
    """(state, reason) aus einem JUnit-XML und optional dem pytest-Exit-Code."""
    if not report.is_file():
        return (
            UNKNOWN,
            f"kein Report unter {report} — pytest ist nicht bis zum Schreiben "
            "gekommen" + (f" (Exit {pytest_exit})" if pytest_exit is not None else ""),
        )
    try:
        root = ET.parse(report).getroot()
    except (ET.ParseError, OSError) as exc:
        return UNKNOWN, f"{report} ist nicht lesbar: {exc}"

    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    if not suites:
        return UNKNOWN, f"{report} enthaelt keine testsuite"

    def total(attr: str) -> int:
        return sum(int(s.get(attr) or 0) for s in suites)

    tests, failures, errors, skipped = (
        total("tests"),
        total("failures"),
        total("errors"),
        total("skipped"),
    )

    if failures or errors:
        counted = f"{failures} Fehlschlag/Fehlschlaege und {errors} Fehler von {tests} Test(s)"
        messages = _failure_messages(suites)
        # `unreachable` nur, wenn sich JEDER gezaehlte Fehlschlag einer
        # Meldung zuordnen laesst und jede davon eine nicht erreichbare Quelle
        # meldet. Ein einziger anderer Fehlschlag kann der gebrochene Vertrag
        # sein, den diese Suite finden soll — dann bleibt es `finding`.
        if (
            messages
            and len(messages) == failures + errors
            and all(is_unreachable(m) for m in messages)
        ):
            return (
                UNREACHABLE,
                f"{counted}, alle an einer nicht erreichbaren Quelle "
                "(Zeitueberschreitung, Netzwerkfehler, HTTP 429/5xx) — kein "
                "Hinweis auf einen geaenderten Vertrag",
            )
        return FINDING, counted
    if tests == 0:
        return (
            UNKNOWN,
            "null Tests eingesammelt — die Marke oder die Dateien haben sich "
            "bewegt, und ein Erfolg ohne Test ist kein Erfolg",
        )
    if tests - skipped == 0:
        return (
            UNKNOWN,
            f"alle {tests} Test(s) uebersprungen — meist ein fehlendes Secret oder "
            "eine nicht erfuellte Vorbedingung. Geprueft wurde nichts",
        )
    return CLEAR, f"{tests - skipped} von {tests} Test(s) ausgefuehrt, alle gruen"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="classify_live_run")
    ap.add_argument("report", type=Path, help="Pfad zum JUnit-XML von pytest")
    ap.add_argument("--pytest-exit", type=int, default=None)
    args = ap.parse_args(argv)

    state, reason = classify(args.report, args.pytest_exit)
    print(f"state={state}")
    print(f"reason={reason}")

    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        # Zeilenumbruch raus, bevor der Grund in `$GITHUB_OUTPUT` geht: Die
        # `key=value`-Form endet an der ersten neuen Zeile, und was danach
        # steht, liest der Runner als naechstes Output. Ein Grund koennte so
        # ein `state=clear` nachschieben und den roten Lauf gruen faerben.
        flat = " ".join(reason.split())
        with open(out, "a", encoding="utf-8") as fh:
            fh.write(f"state={state}\n")
            fh.write(f"reason={flat}\n")
    # Immer 0: Ueber rot oder gruen entscheidet der Workflow.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
