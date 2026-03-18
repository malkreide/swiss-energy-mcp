# Beitragen / Contributing

> 🇩🇪 [Deutsch](#deutsch) · 🇬🇧 [English](#english)

---

## Deutsch

Vielen Dank für Ihr Interesse an diesem Projekt! Beiträge sind willkommen.

### Wie kann ich beitragen?

**Fehler melden:** Erstellen Sie ein [Issue](../../issues) mit einer klaren Beschreibung des Problems, Schritten zur Reproduktion und der erwarteten vs. tatsächlichen Ausgabe.

**Feature vorschlagen:** Beschreiben Sie den Use Case, idealerweise mit einem Bezug zum Schweizer Energiekontext (Standortplanung, Solarkataster, Energiestädte, Netzinfrastruktur etc.).

**Code beitragen:**

1. Forken Sie das Repository
2. Erstellen Sie einen Feature-Branch: `git checkout -b feature/mein-feature`
3. Installieren Sie die Dev-Abhängigkeiten: `pip install -e ".[dev]"`
4. Schreiben Sie Tests für Ihre Änderungen
5. Lint prüfen: `ruff check src/ tests/`
6. Commit mit aussagekräftiger Nachricht: `git commit -m "feat: Windenergieanlagen-Details erweitern"`
7. Pull Request erstellen

### Code-Standards

- Python 3.11+, Ruff für Linting
- Docstrings auf Englisch (für internationale Kompatibilität)
- Kommentare und Fehlermeldungen dürfen Deutsch oder Englisch sein
- Alle MCP-Tools müssen `readOnlyHint: True` setzen (nur lesender Zugriff)
- Pydantic-Modelle für alle Tool-Inputs

### Datenquellen-Richtlinie

Dieses Projekt verwendet ausschliesslich offene, öffentlich zugängliche Datenquellen (OGD). Neue Tools dürfen nur Daten einbinden, die ohne Registrierung oder kostenpflichtige Lizenz zugänglich sind — entsprechend dem No-Auth-First-Prinzip des Portfolios.

### Tests

```bash
# Unit-Tests (kein API-Key erforderlich)
PYTHONPATH=src pytest tests/ -m "not live"

# Live-Tests (erfordern Netzwerkzugriff)
PYTHONPATH=src pytest tests/ -m "live"
```

Committen Sie **niemals** API-Keys oder persönliche Zugangsdaten.

---

## English

Thank you for your interest in this project! Contributions are welcome.

### How can I contribute?

**Report bugs:** Create an [Issue](../../issues) with a clear description, reproduction steps, and expected vs. actual output.

**Suggest features:** Describe the use case, ideally with a reference to the Swiss energy context (site planning, solar cadastre, Energiestadt label, grid infrastructure, etc.).

**Contribute code:**

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Install dev dependencies: `pip install -e ".[dev]"`
4. Write tests for your changes
5. Run linter: `ruff check src/ tests/`
6. Commit with clear message: `git commit -m "feat: extend wind turbine details"`
7. Create a Pull Request

### Code Standards

- Python 3.11+, Ruff for linting
- Docstrings in English (for international compatibility)
- Comments and error messages may be in German or English
- All MCP tools must set `readOnlyHint: True` (read-only access)
- Pydantic models for all tool inputs

### Data Source Policy

This project uses only open, publicly accessible data sources (OGD). New tools may only integrate data that is accessible without registration or paid licensing — in line with the portfolio's No-Auth-First principle.

### Tests

```bash
# Unit tests (no network access required)
PYTHONPATH=src pytest tests/ -m "not live"

# Live tests (require network access)
PYTHONPATH=src pytest tests/ -m "live"
```

**Never** commit API keys or personal credentials.

---

## Lizenz / License

MIT – see [LICENSE](LICENSE)
