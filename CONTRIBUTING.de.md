# Beitragen

[🇬🇧 English Version](CONTRIBUTING.md)

Vielen Dank für Ihr Interesse an diesem Projekt! Beiträge sind willkommen.
Dieser Server ist Teil des [Swiss Public Data MCP Portfolios](https://github.com/malkreide).

## Wie kann ich beitragen?

**Fehler melden:** Erstellen Sie ein [Issue](../../issues) mit einer klaren
Beschreibung des Problems, Schritten zur Reproduktion und der erwarteten vs.
tatsächlichen Ausgabe. Bitte geben Sie Ihre Python-Version und Ihr
Betriebssystem an.

**Feature vorschlagen:** Beschreiben Sie den Use Case, idealerweise mit einem
Bezug zum Schweizer Energiekontext (Standortplanung, Solarkataster,
Energiestädte, Netzinfrastruktur etc.).

**Code beitragen:**

1. Forken Sie das Repository
2. Erstellen Sie einen Feature-Branch: `git checkout -b feat/mein-feature`
3. Installieren Sie die Dev-Abhängigkeiten: `pip install -e ".[dev]"`
4. Schreiben Sie Tests für Ihre Änderungen
5. Lint prüfen: `ruff check src/ tests/`
6. Stellen Sie sicher, dass alle Tests bestehen: `PYTHONPATH=src pytest tests/ -m "not live"`
7. Commit mit aussagekräftiger Nachricht (siehe [Conventional Commits](https://www.conventionalcommits.org/)): `git commit -m "feat: Windenergieanlagen-Details erweitern"`
8. Pull Request gegen `main` erstellen

## Code-Standards

- Python 3.11+, Ruff für Linting und Formatierung
- Type Hints für alle öffentlichen Funktionen erforderlich
- Docstrings auf Englisch (für internationale Kompatibilität)
- Kommentare und Fehlermeldungen dürfen Deutsch oder Englisch sein
- Alle MCP-Tools müssen `readOnlyHint: True` setzen (nur lesender Zugriff)
- Pydantic-v2-Modelle für alle Tool-Inputs
- Den bestehenden FastMCP-Mustern in den Quellmodulen folgen

## Datenquellen-Richtlinie

Dieses Projekt verwendet ausschliesslich offene, öffentlich zugängliche
Datenquellen (OGD). Neue Tools dürfen nur Daten einbinden, die ohne
Registrierung oder kostenpflichtige Lizenz zugänglich sind — entsprechend dem
**No-Auth-First**-Prinzip des Portfolios.

| Quelle | Dokumentation |
|--------|--------------|
| GeoAdmin REST API (swisstopo) | [api3.geo.admin.ch](https://api3.geo.admin.ch/) |
| opendata.swiss CKAN API | [opendata.swiss](https://opendata.swiss/) |
| BFE | [bfe.admin.ch](https://www.bfe.admin.ch/) |

## Tests

```bash
# Unit-Tests (kein Netzwerkzugriff erforderlich)
PYTHONPATH=src pytest tests/ -m "not live"

# Live-Tests (erfordern Netzwerkzugriff)
PYTHONPATH=src pytest tests/ -m "live"
```

Committen Sie **niemals** API-Keys oder persönliche Zugangsdaten.

## Die Live-Suite: wann sie läuft, und wer ein rotes Ergebnis sieht

**Kadenz:** täglich um 03:00 UTC, dazu jederzeit von Hand über *Actions → Live API Tests → Run
workflow*. Siehe [`.github/workflows/live-tests.yml`](.github/workflows/live-tests.yml).

**Wer es sieht:** Ein roter Lauf öffnet ein Issue mit dem Label `upstream` und dem stabilen Titel «Live-Tests gegen api3.geo.admin.ch / opendata.swiss rot (<Datum>)». Ein zweiter roter Lauf erkennt das offene Issue am Titelanfang und hängt sich an denselben Thread, statt ein zweites aufzumachen. Wird die Suite wieder grün, schliesst sich das Issue selbst.

**Drei Antworten, nicht zwei.** `scripts/classify_live_run.py` liest das JUnit-XML statt des
Exit-Codes und unterscheidet: `clear` (gelaufen, grün), `finding` (gelaufen,
etwas gefallen) und `unknown` (nicht gelaufen — Installation gescheitert, null
Tests eingesammelt, alle übersprungen). Ein `unknown` schliesst nie ein Issue:
Zuzumachen hiesse zu behaupten, der Vergleich sei gelaufen.

**Ein roter Live-Lauf heisst nicht zwingend «unser Fehler».** Er heisst: Der
Vertrag mit der Quelle hat sich geändert, oder die Quelle ist gerade aus. Beides
gehört gesehen, nur das Erste gehört gefixt. Bitte den Lauf lesen, bevor der Job
deaktiviert wird — so stirbt dieser Check, und er ist der einzige im Repo, der
einer falschen Grundannahme über api3.geo.admin.ch / opendata.swiss widersprechen kann. Jeder andere Test
prüft gegen eine Fixture, und die Fixture ist aus derselben Annahme geschrieben
wie der Code.

## Lizenz

Mit Ihrem Beitrag erklären Sie sich damit einverstanden, dass Ihre Beiträge
unter der [MIT-Lizenz](LICENSE) lizenziert werden.
