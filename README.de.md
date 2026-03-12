# swiss-energy-mcp

![Version](https://img.shields.io/badge/version-0.1.0-blue)
![Lizenz](https://img.shields.io/badge/Lizenz-MIT-green)
![Python](https://img.shields.io/badge/python-3.11+-blue)
![Tests](https://img.shields.io/badge/Tests-78%20bestanden-brightgreen)

> MCP-Server für Schweizer Energiedaten des Bundesamts für Energie (BFE) via GeoAdmin REST API und opendata.swiss – kein API-Key erforderlich.

[🇬🇧 English Version](README.md)

## Übersicht

`swiss-energy-mcp` gibt KI-Assistenten strukturierten, standortbasierten Zugriff auf die Energieinfrastruktur der Schweiz. Grundlage sind offene Geodaten des Bundesamts für Energie (BFE) via der GeoAdmin REST API und dem opendata.swiss-Katalog – vollständig ohne Authentifizierung.

Der Server ist Teil eines wachsenden Portfolios von MCP-Servern für Schweizer Open Data. Metapher: Wenn der `swiss-road-mobility-mcp` die Mobilitätskarte der Schweiz ist, dann ist dieser Server das Energieatlas-Pendant – er zeigt, wo die Schweiz Strom produziert, wo Solarpotenzial besteht und welche Gemeinden das Label «Energiestadt» tragen.

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

## Voraussetzungen

- Python 3.11+
- [`uv`](https://github.com/astral-sh/uv) (empfohlen) oder `pip`

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

### Lokale Entwicklung

```bash
git clone https://github.com/malkreide/swiss-energy-mcp.git
cd swiss-energy-mcp
uv sync
uv run swiss-energy-mcp
```

### Cloud / HTTP-Transport (Streamable HTTP)

```bash
SWISS_ENERGY_TRANSPORT=http uvx swiss-energy-mcp
```

## Verwendung / Schnellstart

Nach der Verbindung in Claude Desktop lassen sich folgende Abfragen stellen:

```
Welche Kraftwerke gibt es im Umkreis von 20 km um Bern?
Zeig mir alle Windenergieanlagen im Jura.
Ist Zürich eine Energiestadt? Wie ist die Punktezahl?
Wie ist das Solarpotenzial der Dächer bei lat=47.37, lon=8.54?
Erstelle ein Energieprofil für die Region Luzern.
Suche BFE-Datensätze zum Thema Wasserkraft.
```

## Tools

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

## Konfiguration

| Umgebungsvariable | Standard | Beschreibung |
|---|---|---|
| `SWISS_ENERGY_TRANSPORT` | `stdio` | Transportmodus: `stdio` oder `http` |
| `SWISS_ENERGY_PORT` | `8000` | Port für HTTP-Transport |
| `SWISS_ENERGY_HOST` | `0.0.0.0` | Host für HTTP-Transport |

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
└── README.md
```

## Changelog

Siehe [CHANGELOG.md](CHANGELOG.md)

## Lizenz

MIT-Lizenz – siehe [LICENSE](LICENSE)

## Autor

Hayal Oezkan · [malkreide](https://github.com/malkreide)

---
