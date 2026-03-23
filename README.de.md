[🇬🇧 English Version](README.md)

> 🇨🇭 **Teil des [Swiss Public Data MCP Portfolios](https://github.com/malkreide)**

# ⚡ swiss-energy-mcp

![Version](https://img.shields.io/badge/version-0.1.0-blue)
[![Lizenz: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-Model%20Context%20Protocol-purple)](https://modelcontextprotocol.io/)
[![Datenquelle](https://img.shields.io/badge/Daten-BFE%20%2F%20GeoAdmin-red)](https://www.geo.admin.ch/)
![Tests](https://img.shields.io/badge/Tests-78%20bestanden-brightgreen)
![CI](https://github.com/malkreide/swiss-energy-mcp/actions/workflows/ci.yml/badge.svg)

> MCP-Server für Schweizer Energiedaten des Bundesamts für Energie (BFE) via GeoAdmin REST API und opendata.swiss – kein API-Key erforderlich.

---

## Übersicht

`swiss-energy-mcp` gibt KI-Assistenten strukturierten, standortbasierten Zugriff auf die Energieinfrastruktur der Schweiz. Grundlage sind offene Geodaten des Bundesamts für Energie (BFE) via GeoAdmin REST API und dem opendata.swiss-Katalog – vollständig ohne Authentifizierung.

Der Server ist Teil eines wachsenden Portfolios von MCP-Servern für Schweizer Open Data. Metapher: Wenn der `swiss-road-mobility-mcp` die Mobilitätskarte der Schweiz ist, dann ist dieser Server das Energieatlas-Pendant – er zeigt, wo die Schweiz Strom produziert, wo Solarpotenzial besteht und welche Gemeinden das Label «Energiestadt» tragen.

**Anker-Demo-Abfrage:** *«Welche Kraftwerke gibt es im Umkreis von 20 km um die Schule in Wädenswil – und ist die Gemeinde eine Energiestadt?»*

---

## Funktionen

- 🔍 **10 einsatzbereite Tools** für alle wichtigen BFE-Datenlayer aus GeoAdmin
- ⚡ **Elektrizitätsproduktionsanlagen** – alle Typen: PV, Wasser, Wind, Biomasse, Kern, mit optionalem Kategorie-Filter
- 💨 **Windenergieanlagen** – detaillierte Angaben zu Hersteller, Modell, Nabenhöhe, Jahresproduktion
- 💧 **Wasserkraftwerke** – Typ, Betriebsstatus, Turbinenleistung, erwartete Jahresproduktion
- ☀️ **PV-Grossanlagen** – Projektname, Leistung, Jahres-/Winterproduktion, Höhenlage
- 🌿 **Biogasanlagen** – Anlagenname, Leistung
- 🏙️ **Energiestädte** – Gemeinden mit Schweizer Energiestadt-Label (Punkte, Jahr, Audits)
- 🏠 **Solareignung Dächer** – Eignungskategorie, Fläche, Ausrichtung und Neigung je Dachfläche
- 📊 **Standort-Energieprofil** – kombiniert 5 Layer in einer Übersicht für einen beliebigen Schweizer Standort
- 🗂️ **BFE-Datensatz-Suche** – Volltextsuche über BFE-Publikationen auf opendata.swiss
- ✅ **Statusprüfung** – prüft Verfügbarkeit beider vorgelagerter APIs
- ☁️ **Dual Transport** – stdio für Claude Desktop, Streamable HTTP für Cloud-Deployment

---

## Voraussetzungen

- Python 3.11+
- [`uv`](https://github.com/astral-sh/uv) (empfohlen) oder `pip`

---

## Installation

### Claude Desktop (stdio-Transport)

In `claude_desktop_config.json` eintragen:

```json
{
  "mcpServers": {
    "swiss-energy-mcp": {
      "command": "uvx",
      "args": ["swiss-energy-mcp"]
    }
  }
}
```

**Pfad zur Konfigurationsdatei:**
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

### Lokale Entwicklung

```bash
git clone https://github.com/malkreide/swiss-energy-mcp.git
cd swiss-energy-mcp
uv sync
uv run swiss-energy-mcp
```

### Cloud / HTTP-Transport (Streamable HTTP)

Für den Einsatz via **claude.ai im Browser** (z.B. auf verwalteten Arbeitsplätzen ohne lokale Software-Installation):

```bash
SWISS_ENERGY_TRANSPORT=http uvx swiss-energy-mcp
```

> 💡 *«stdio für den Entwickler-Laptop, HTTP für den Browser.»*

---

## Schnellstart

Nach der Verbindung in Claude Desktop lassen sich folgende Abfragen stellen:

```
Welche Kraftwerke gibt es im Umkreis von 20 km um Bern?
Zeig mir alle Windenergieanlagen im Jura.
Ist Zürich eine Energiestadt? Wie ist die Punktezahl?
Wie ist das Solarpotenzial der Dächer bei lat=47.37, lon=8.54?
Erstelle ein Energieprofil für die Region Luzern.
Suche BFE-Datensätze zum Thema Wasserkraft.
```

---

## Verfügbare Tools

| Tool | Beschreibung |
|---|---|
| `energy_find_power_plants` | Elektrizitätsproduktionsanlagen im Umkreis (optionaler Typ-Filter) |
| `energy_find_wind_turbines` | Windenergieanlagen mit Hersteller, Modell, Nabenhöhe |
| `energy_find_hydro_plants` | Wasserkraftwerke mit Leistung und Jahresproduktion |
| `energy_find_pv_installations` | PV-Grossanlagen mit Jahres-/Winterproduktion |
| `energy_find_biogas_plants` | Biogasanlagen |
| `energy_find_energy_cities` | Gemeinden mit Label «Energiestadt» |
| `energy_solar_potential` | Solareignung der Dachflächen an einem Standort |
| `energy_location_profile` | Kombiniertes Energieprofil (5 Layer) für einen Standort |
| `energy_search_bfe_datasets` | Volltextsuche über BFE-Datensätze auf opendata.swiss |
| `energy_check_status` | Verfügbarkeit von GeoAdmin und opendata.swiss prüfen |

Alle Tools akzeptieren WGS84-Koordinaten (Breiten-/Längengrad). Die Konvertierung ins Schweizer LV95-System erfolgt intern.

### Beispiel-Abfragen

| Abfrage | Tool |
|---|---|
| *«Kraftwerke in der Nähe von Bern (20 km)?»* | `energy_find_power_plants` |
| *«Windenergieanlagen im Jura?»* | `energy_find_wind_turbines` |
| *«Ist Zürich eine Energiestadt?»* | `energy_find_energy_cities` |
| *«Solareignung der Dächer bei lat=47.37, lon=8.54?»* | `energy_solar_potential` |
| *«Vollständiges Energieprofil für die Region Luzern?»* | `energy_location_profile` |
| *«BFE-Datensätze zum Thema Wasserkraft?»* | `energy_search_bfe_datasets` |

---

## Datenquellen

| Quelle | URL | Authentifizierung |
|---|---|---|
| GeoAdmin REST API (swisstopo) | `api3.geo.admin.ch` | Keine |
| opendata.swiss CKAN API | `opendata.swiss/api/3/action` | Keine |

**Verwendete BFE-Layer:**
- `ch.bfe.elektrizitaetsproduktionsanlagen`
- `ch.bfe.windenergieanlagen`
- `ch.bfe.statistik-wasserkraftanlagen`
- `ch.bfe.photovoltaik-grossanlagen`
- `ch.bfe.biogasanlagen`
- `ch.bfe.energiestaedte`
- `ch.bfe.solarenergie-eignung-daecher`

---

## Konfiguration

| Umgebungsvariable | Standard | Beschreibung |
|---|---|---|
| `SWISS_ENERGY_TRANSPORT` | `stdio` | Transportmodus: `stdio` oder `http` |
| `SWISS_ENERGY_PORT` | `8000` | Port für HTTP-Transport |
| `SWISS_ENERGY_HOST` | `0.0.0.0` | Host für HTTP-Transport |

---

## Architektur

```
┌─────────────────┐     ┌───────────────────────────┐     ┌──────────────────────────┐
│   Claude / KI   │────▶│   Swiss Energy MCP        │────▶│  BFE / Schweizer         │
│   (MCP Host)    │◀────│   (MCP Server)            │◀────│  Open Data               │
└─────────────────┘     │                           │     │                          │
                        │  10 Tools                 │     │  GeoAdmin REST API       │
                        │  Stdio | HTTP             │     │  (api3.geo.admin.ch)     │
                        │                           │     │                          │
                        │  server.py (FastMCP)      │     │  opendata.swiss CKAN     │
                        │  api_client.py            │     │  (opendata.swiss)        │
                        │   LV95-Konvertierung      │     └──────────────────────────┘
                        │   GeoAdmin-Abfragen       │
                        └───────────────────────────┘
```

### Infrastruktur-Komponenten

| Komponente | Metapher | Funktion |
|---|---|---|
| `api_client.py` | Telefonzentrale | HTTP-Anfragen, Koordinatenkonvertierung, Fehlerbehandlung |
| LV95-Konverter | Übersetzer | Wandelt WGS84 (Breite/Länge) ins Schweizer Koordinatensystem um |
| `server.py` | Schaufenster | Stellt alle 10 Tools via FastMCP bereit |

---

## Projektstruktur

```
swiss-energy-mcp/
├── src/
│   └── swiss_energy_mcp/
│       ├── __init__.py
│       ├── server.py        # FastMCP-Server – 10 Tools
│       └── api_client.py    # HTTP-Client, LV95-Konvertierung, GeoAdmin-Abfragen
├── tests/
│   └── test_server.py       # 78 Unit-Tests + 7 Live-Tests
├── pyproject.toml
├── CHANGELOG.md
├── CONTRIBUTING.md
├── LICENSE
├── README.md                # Englische Hauptversion
└── README.de.md             # Diese Datei (Deutsch)
```

---

## Bekannte Einschränkungen

- **GeoAdmin-Umkreissuche:** Der maximale Suchradius hängt von der Layer-Dichte ab; sehr grosse Radien können unvollständige Ergebnisse liefern
- **Solareignung:** Layer `ch.bfe.solarenergie-eignung-daecher` deckt Gebäudegrundflächen ab – nicht alle Dachtypen sind klassifiziert
- **Energiestadt:** Nur Gemeinden mit aktivem Label sind enthalten; historische Einträge können unvollständig sein
- **opendata.swiss CKAN:** Die Volltextsuche deckt nur Metadaten ab, nicht den Inhalt der Dokumente

---

## Tests

```bash
# Unit-Tests (kein API-Key erforderlich)
PYTHONPATH=src pytest tests/ -m "not live"

# Live-Integrationstests (Netzwerkzugang erforderlich)
PYTHONPATH=src pytest tests/ -m "live"
```

---

## Changelog

Siehe [CHANGELOG.md](CHANGELOG.md)

---

## Beitragen

Siehe [CONTRIBUTING.md](CONTRIBUTING.md)

---

## Lizenz

MIT-Lizenz – siehe [LICENSE](LICENSE)

---

## Autor

Hayal Oezkan · [malkreide](https://github.com/malkreide)

---

## Credits & Verwandte Projekte

- **Daten:** [BFE](https://www.bfe.admin.ch/) via [GeoAdmin](https://www.geo.admin.ch/) – Bundesamt für Energie
- **Daten:** [opendata.swiss](https://opendata.swiss/) – Schweizerisches Open-Government-Data-Portal
- **Protokoll:** [Model Context Protocol](https://modelcontextprotocol.io/) – Anthropic / Linux Foundation
- **Verwandt:** [swiss-road-mobility-mcp](https://github.com/malkreide/swiss-road-mobility-mcp) – MCP-Server für Schweizer Mobilitätsdaten
- **Verwandt:** [zurich-opendata-mcp](https://github.com/malkreide/zurich-opendata-mcp) – MCP-Server für Zürcher Stadtdaten
- **Portfolio:** [Swiss Public Data MCP Portfolio](https://github.com/malkreide)
