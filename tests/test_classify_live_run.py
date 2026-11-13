#!/usr/bin/env python3
"""Tests fuer scripts/classify_live_run.py — die vier Antworten eines Live-Laufs.

Die Einordnung entscheidet, ob ein Issue aufgeht oder zugeht. Genau deshalb
steht sie in einem Skript und nicht in einem `run:`-Block: So kann jemand sie
gegen die Faelle halten, aus denen sie entstanden ist.

Der wichtigste Fall ist `test_alle_uebersprungen_ist_nicht_gruen`. Gemessen am
7.8.2026 an `swiss-transport-mcp`: Ohne `TRANSPORT_API_KEY` ueberspringt die
Live-Suite alle sechs Tests und pytest endet mit 0. Ein Job, der das als gruen
bucht, schliesst ein offenes Issue mit einem Vergleich, den es nie gab.

Nur Standardbibliothek, kein Netz.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import classify_live_run as clr  # noqa: E402


def write(tmp: Path, xml: str) -> Path:
    path = tmp / "live-report.xml"
    path.write_text(xml, encoding="utf-8")
    return path


def suite(tests: int, failures: int = 0, errors: int = 0, skipped: int = 0) -> str:
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        f'<testsuites><testsuite name="pytest" tests="{tests}" failures="{failures}" '
        f'errors="{errors}" skipped="{skipped}"></testsuite></testsuites>'
    )


class ClassifyTest(unittest.TestCase):
    def _state(self, xml: str) -> tuple[str, str]:
        with tempfile.TemporaryDirectory() as tmp:
            return clr.classify(write(Path(tmp), xml))

    def test_alles_gruen_ist_clear(self):
        state, reason = self._state(suite(tests=3))
        self.assertEqual(state, clr.CLEAR)
        self.assertIn("3 von 3", reason)

    def test_ein_fehlschlag_ist_ein_finding(self):
        state, _ = self._state(suite(tests=3, failures=1))
        self.assertEqual(state, clr.FINDING)

    def test_ein_fehler_ist_ein_finding(self):
        state, _ = self._state(suite(tests=3, errors=1))
        self.assertEqual(state, clr.FINDING)

    def test_alle_uebersprungen_ist_nicht_gruen(self):
        """swiss-transport-mcp ohne TRANSPORT_API_KEY: 6 von 6 uebersprungen."""
        state, reason = self._state(suite(tests=6, skipped=6))
        self.assertEqual(state, clr.UNKNOWN)
        self.assertIn("uebersprungen", reason)

    def test_teilweise_uebersprungen_ist_gruen(self):
        """Ein einzelner Skip ist eine Entscheidung im Test, kein Ausfall."""
        state, reason = self._state(suite(tests=6, skipped=5))
        self.assertEqual(state, clr.CLEAR)
        self.assertIn("1 von 6", reason)

    def test_null_tests_ist_kein_erfolg(self):
        """Die Marke umbenannt, die Dateien verschoben — pytest meldet trotzdem 0."""
        state, reason = self._state(suite(tests=0))
        self.assertEqual(state, clr.UNKNOWN)
        self.assertIn("null Tests", reason)

    def test_ein_fehlschlag_schlaegt_uebersprungene(self):
        state, _ = self._state(suite(tests=6, skipped=5, failures=1))
        self.assertEqual(state, clr.FINDING)

    def test_mehrere_testsuites_werden_summiert(self):
        xml = (
            "<testsuites>"
            '<testsuite tests="2" failures="0" errors="0" skipped="2"/>'
            '<testsuite tests="3" failures="0" errors="0" skipped="0"/>'
            "</testsuites>"
        )
        state, _ = self._state(xml)
        self.assertEqual(state, clr.CLEAR)

    def test_eine_einzelne_testsuite_ohne_huelle(self):
        xml = '<testsuite tests="2" failures="0" errors="0" skipped="0"/>'
        state, _ = self._state(xml)
        self.assertEqual(state, clr.CLEAR)


def cases(*failed: str, passed: int = 0, tag: str = "failure") -> str:
    """Eine Suite mit echten <testcase>-Elementen, so wie pytest sie schreibt.

    Jede Meldung in `failed` wird ein gescheiterter Testfall mit genau diesem
    `message`-Attribut; `passed` fuegt gruene Testfaelle hinzu.
    """
    from xml.sax.saxutils import quoteattr

    body = "".join(f'<testcase name="ok{i}"/>' for i in range(passed)) + "".join(
        f'<testcase name="t{i}"><{tag} message={quoteattr(m)}>Traceback</{tag}></testcase>'
        for i, m in enumerate(failed)
    )
    kind = "failures" if tag == "failure" else "errors"
    return (
        f'<testsuites><testsuite tests="{passed + len(failed)}" {kind}="{len(failed)}">'
        f"{body}</testsuite></testsuites>"
    )


# Woertlich aus Lauf 177 vom 10.11.2026 (drei Tests, GeoAdmin zu langsam).
BUDGET = (
    "ValueError: Zeitüberschreitung bei der Anfrage: keine vollständige Antwort "
    "innerhalb von 25 s, Wiederholungen eingeschlossen. Die Quelle antwortet "
    "gerade zu langsam."
)


class UnreachableTest(unittest.TestCase):
    """Ein Ausfall der Quelle ist rot, aber kein Befund ueber den Vertrag."""

    def _state(self, xml: str) -> tuple[str, str]:
        with tempfile.TemporaryDirectory() as tmp:
            return clr.classify(write(Path(tmp), xml))

    def test_lauf_177_ist_unreachable(self):
        state, reason = self._state(cases(BUDGET, BUDGET, BUDGET, passed=7))
        self.assertEqual(state, clr.UNREACHABLE)
        self.assertIn("3 Fehlschlag", reason)
        self.assertIn("nicht erreichbaren Quelle", reason)

    def test_status_assertion_mit_zeitueberschreitung(self):
        """test_live_check_status meldet den Ausfall als AssertionError-Detail."""
        msg = "AssertionError: Zeitüberschreitung bei der Anfrage: keine vollständige Antwort"
        state, _ = self._state(cases(msg + "\nassert False", passed=9))
        self.assertEqual(state, clr.UNREACHABLE)

    def test_netzwerk_429_und_5xx_sind_unreachable(self):
        for msg in (
            "ValueError: Netzwerkfehler bei der Anfrage. Bitte Verbindung prüfen.",
            "ValueError: Zu viele Anfragen (HTTP 429) — auch nach mehreren Wiederholungen.",
            "ValueError: Der Dienst ist vorübergehend nicht verfügbar (HTTP 503) — auch …",
            "ValueError: Die API hat einen Fehler gemeldet (HTTP 502).",
        ):
            with self.subTest(msg=msg):
                state, _ = self._state(cases(msg, passed=9))
                self.assertEqual(state, clr.UNREACHABLE)

    def test_404_und_400_bleiben_finding(self):
        """Ein umbenannter Layer antwortet mit 404 — das ist der Vertragsbruch."""
        for msg in (
            "ValueError: Ressource nicht gefunden (HTTP 404).",
            "ValueError: Fehlerhafte Anfrage (HTTP 400). Bitte Parameter prüfen.",
        ):
            with self.subTest(msg=msg):
                state, _ = self._state(cases(msg, passed=9))
                self.assertEqual(state, clr.FINDING)

    def test_ein_anderer_fehlschlag_macht_alles_zum_finding(self):
        state, _ = self._state(cases(BUDGET, BUDGET, "assert 0 > 0", passed=7))
        self.assertEqual(state, clr.FINDING)

    def test_ein_error_beim_setup_zaehlt_mit(self):
        state, _ = self._state(cases("failed on setup with RuntimeError", tag="error", passed=9))
        self.assertEqual(state, clr.FINDING)

    def test_nicht_zuordenbare_fehlschlaege_bleiben_finding(self):
        """Zwei gezaehlt, aber nur einer mit Meldung: der zweite koennte alles sein."""
        xml = (
            '<testsuites><testsuite tests="3" failures="2">'
            f'<testcase name="a"><failure message="{BUDGET}">x</failure></testcase>'
            '<testcase name="b"/><testcase name="c"/>'
            "</testsuite></testsuites>"
        )
        state, _ = self._state(xml)
        self.assertEqual(state, clr.FINDING)

    def test_die_meldung_zaehlt_nicht_der_traceback(self):
        """Der Traceback zeigt Quellzeilen des Clients, mit allen Meldungen darin."""
        xml = (
            '<testsuites><testsuite tests="1" failures="1"><testcase name="a">'
            '<failure message="ValueError: Ressource nicht gefunden (HTTP 404).">'
            'raise ValueError("Zeitüberschreitung bei der Anfrage. Bitte erneut versuchen.")'
            "</failure></testcase></testsuite></testsuites>"
        )
        state, _ = self._state(xml)
        self.assertEqual(state, clr.FINDING)


class MissingReportTest(unittest.TestCase):
    """Kein Report heisst: pytest kam nicht bis zum Schreiben. Nie clear."""

    def test_fehlender_report_ist_unknown(self):
        state, reason = clr.classify(Path("/nonexistent/live-report.xml"), pytest_exit=4)
        self.assertEqual(state, clr.UNKNOWN)
        self.assertIn("Exit 4", reason)

    def test_kaputtes_xml_ist_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(Path(tmp), "<testsuite tests=")
            state, _ = clr.classify(path)
        self.assertEqual(state, clr.UNKNOWN)

    def test_xml_ohne_testsuite_ist_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(Path(tmp), "<irgendwas/>")
            state, _ = clr.classify(path)
        self.assertEqual(state, clr.UNKNOWN)


class GithubOutputTest(unittest.TestCase):
    """Der Workflow liest state und reason ueber $GITHUB_OUTPUT."""

    def test_beide_werte_werden_angehaengt(self):
        import os

        with tempfile.TemporaryDirectory() as tmp:
            report = write(Path(tmp), suite(tests=2))
            out = Path(tmp) / "gh-output"
            out.write_text("", encoding="utf-8")
            os.environ["GITHUB_OUTPUT"] = str(out)
            try:
                rc = clr.main([str(report)])
            finally:
                del os.environ["GITHUB_OUTPUT"]
            written = out.read_text(encoding="utf-8")
        self.assertEqual(rc, 0)
        self.assertIn("state=clear", written)
        self.assertIn("reason=", written)


class GithubOutputZeilenTest(unittest.TestCase):
    """Ein Grund mit Zeilenumbruch darf kein zweites Output nachschieben.

    `key=value` endet in `$GITHUB_OUTPUT` an der ersten neuen Zeile; was
    danach steht, liest der Runner als eigenen Output. Der Reportpfad kommt
    vom Aufrufer und steht woertlich im Grund — ein Umbruch darin schoebe
    sonst ein `state=clear` nach und faerbte den roten Lauf gruen.
    """

    def test_umbruch_im_grund_schiebt_kein_zweites_output_nach(self):
        import os

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "gh-output"
            out.write_text("", encoding="utf-8")
            os.environ["GITHUB_OUTPUT"] = str(out)
            try:
                clr.main([str(Path(tmp) / "live-report.xml") + "\nstate=clear"])
            finally:
                del os.environ["GITHUB_OUTPUT"]
            zeilen = [z for z in out.read_text(encoding="utf-8").splitlines() if z]
        self.assertEqual([z for z in zeilen if z.startswith("state=")], ["state=unknown"])
        self.assertEqual(len(zeilen), 2)


if __name__ == "__main__":
    unittest.main()
