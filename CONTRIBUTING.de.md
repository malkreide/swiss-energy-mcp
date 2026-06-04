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

## Lizenz

Mit Ihrem Beitrag erklären Sie sich damit einverstanden, dass Ihre Beiträge
unter der [MIT-Lizenz](LICENSE) lizenziert werden.
