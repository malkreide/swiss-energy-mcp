# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Die Pruefsummen im Fixture-Nachweis waren Zierde.** `PROVENANCE.md` fuehrt
  je Datei einen SHA-256 — um genau einen Fall zu fangen: eine Aufzeichnung,
  die nach dem Lauf von Hand nachgebessert wurde. Eine korrigierte Antwort ist
  wieder eine erfundene, und von aussen ist ihr das nicht anzusehen.
  Nachgerechnet hat sie kein Test. `test_die_pruefsumme_im_nachweis_stimmt`
  tut es jetzt, ueber die Bytes auf der Platte statt ueber den Loader — genau
  die hat der Recorder gehasht.

- **Aufgezeichnete Fixtures** in `tests/fixtures/` — 10 echte Antworten, eine je
  Abfrageform (nicht je Endpunkt: zwei Hosts, aber zehn Formen — `identify` je
  Layer, `find` je Layer, `package_search` je Suche). Herkunft, Datum,
  Auswahlregel und SHA-256 je Datei in `tests/fixtures/PROVENANCE.md`, neu
  aufzeichnen mit `scripts/record_fixtures.py`, geladen über
  `tests/fixture_data.py`. Aufnahmeort ist Mont Crosin: der einzige Punkt, an
  dem alle sieben BFE-Layer etwas liefern. Gekürzt ist nur die Zahl der
  Trefferzeilen, nie ein Feld. Portfolio-Konvention, gleich wie in
  `meteoswiss-mcp` und `swiss-statistics-mcp`.

- **`tests/test_recorded_fixtures.py`** — 27 Zusicherungen, die jedes Werkzeug
  aus seiner eigenen Aufzeichnung fahren. Der Dispatcher ordnet nach der
  *Anfrage* zu und nicht nach der Reihenfolge: `energy_location_profile`
  schickt seine fünf Abfragen per `asyncio.gather`, und eine Zuordnung nach
  Reihenfolge wäre im grünen Fall bloss zufällig richtig.

- **`_sleep = asyncio.sleep` im `api_client`** als Naht für Tests, plus die
  Fixture `ohne_wartezeit`. Acht Fehlerpfad-Tests fuhren bisher den echten
  Backoff-Ladder von 2+4+8 Sekunden ab; die Offline-Suite brauchte 135 s und
  braucht jetzt 5,6 s. `test_die_fixture_nullt_die_wartezeit_wirklich` misst
  die Uhr, nicht den Aufruf — eine Fixture, die den falschen Namen patcht,
  fällt sonst an keiner Zusicherung auf, sie macht den Lauf nur länger.

### Fixed

- **Jede Datensatz-Beschreibung war leer.** `energy_search_bfe_datasets` las
  sie aus `notes` — dem Feldnamen aus dem CKAN-Kern. opendata.swiss liefert das
  Feld unter `description`; in keiner aufgezeichneten Antwort kommt `notes` vor.
  Die Suite blieb dabei grün, weil `conftest.dataset()` das Feld genauso falsch
  nannte wie der Code und dessen Annahme damit nur bestätigte.

- **Die «leichtgewichtige» Statusabfrage war es nicht.** `energy_check_status`
  baut seine `find`-Anfrage von Hand und liess `returnGeometry=false` weg, das
  `find_geoadmin_by_name()` mitschickt. GeoAdmin legte deshalb die
  Gemeindegeometrie bei: 159 656 statt 574 Bytes für denselben einen Treffer,
  den das Tool nur zählt (gemessen am 15.08.2026). Damit ist die Anfrage jetzt
  zeichengleich mit der des Suchwerkzeugs, und beide teilen sich ein Fixture —
  laufen sie wieder auseinander, wird daraus sichtbar eine zweite Datei.

- **Auch die GeoAdmin-Antworten wurden bei einer Strukturänderung zu null
  Features.** `identify_geoadmin` und `find_geoadmin_by_name` gaben
  `data.get("results", [])` zurück.

  Hier wiegt der Default schwerer als anderswo, denn dieser Server kennt null
  Features bereits als **echte** Antwort: Der Docstring von
  `identify_geoadmin` warnt ausdrücklich davor, dass ein falscher `sr`-Wert
  jede Ebene still leer laufen lässt. Der Default fügte eine zweite Ursache
  mit demselben Ergebnis hinzu — und danach waren sie nicht mehr
  auseinanderzuhalten.

  Beide laufen jetzt über `_geoadmin_results()`, das `results` bestätigt und
  sonst `UpstreamSchemaError` wirft — denselben Typ, den der CKAN-Pfad seit
  dem letzten Release nutzt. `results: []` bleibt eine Aussage der Quelle:
  Bestätigt wird die Anwesenheit des Schlüssels, nicht sein Inhalt.

  Nachtrag zum Portfolio-Durchlauf
  ([`FID-006`](https://github.com/malkreide/mcp-audit-skill/blob/main/checks/FID-006.md)):
  Der CKAN-Sweep reparierte den einen Pfad dieses Servers, GeoAdmin ist der
  andere. Eine Kohorte zu reparieren repariert einen Pfad, nicht einen Server.

### Fixed

- **Eine Strukturänderung von opendata.swiss wurde zu «null Treffer».**
  `search_opendata_swiss` schrieb drei Defaults hintereinander:

  ```python
  result = data.get("result", {})
  return {"count": result.get("count", 0), "results": result.get("results", [])}
  ```

  Fällt `result` weg — weil CKAN seine Antwort umbaut oder die Aktion nie
  richtig war —, kommt buchstäblich `{"count": 0, "results": []}` heraus. Das
  ist nicht «etwas ist kaputt», das ist **dieselbe Antwort, die eine korrekte,
  leere Suche liefert**, und für das Modell nicht davon zu unterscheiden.

  `result` wird jetzt bestätigt statt gedefaultet, und `count`/`results` mit
  ihm: `package_search` liefert beide **immer**, auch bei null Treffern, also
  ist ihr Fehlen keine leere Suche. Bei Abweichung fliegt `UpstreamSchemaError`
  mit den tatsächlich vorhandenen Schlüsseln in der Meldung.

  Ein echter CKAN-Fehler (`success: false`) bleibt ein `ValueError`: Dort hat
  die Quelle geantwortet und Nein gesagt, hier hat sie ihre Form geändert. Eine
  echte Leermenge (`count: 0` bei vorhandenem `results`) bleibt ein normales
  Ergebnis — ein Wächter, der die mitfängt, wird nach dem zweiten Fehlalarm
  abgeschaltet.

  Gefunden im Portfolio-Durchlauf zu
  [`FID-006`](https://github.com/malkreide/mcp-audit-skill/blob/main/checks/FID-006.md)
  am 2026-08-07: Acht Server im Portfolio sprechen mit CKAN, alle acht prüfen
  das `success`-Envelope, sieben defaulteten `result` danach. Dieser war der
  einzige, bei dem der Default bis auf die **Zählung** durchschlug.

### Added

- **`EnergyHTTPClient.get` hatte gar keinen Retry — jetzt hat es einen.**
  `reference/adoption.toml` in
  [mcp-data-source-probe-skill](https://github.com/malkreide/mcp-data-source-probe-skill)
  fuehrt diesen Client seit 2026-03-12 als Uebernahme der Retry-Vorlage. Beim
  Nachlesen am 2026-08-07: Uebernommen wurde die **Fehlerabbildung**, nicht die
  Schleife. Ein Grep ueber `src/` findet null Vorkommen von `asyncio.sleep`,
  `backoff`, `retry` oder `attempt`.

  Damit unterscheidet sich dieser Server von den zehn Schwester-Servern derselben
  Runde: Dort waren sechs Defekte an einem vorhandenen Retry zu **haerten**, hier
  fehlte er ganz. Ein 503 wurde direkt zu «Der Dienst ist voruebergehend nicht
  verfuegbar» — die Meldung, die der Skill als Defaitismus benennt: Sie sagt dem
  Menschen, er solle es nochmal versuchen, statt es selbst zu tun.

  Neu, in der Form der reparierten Vorlage:
  - 5xx, 429 und Netzwerkfehler werden bis zu vier Versuche wiederholt; 4xx
    ausser 429 wie bisher sofort durchgereicht.
  - **`Retry-After`** schlaegt die eigene Kurve, beide Formen nach RFC 9110
    §10.2.3; unlesbar ergibt `None` und faellt auf die Kurve zurueck — nie ein
    Absturz auf dem Fehlerpfad. Der Jitter darauf ist einseitig `[1.0x, 1.25x]`.
  - **Jitter** `[0.5x, 1.5x]` auf der exponentiellen Kurve, damit nicht alle
    Clients nach demselben Ausfall im Gleichschritt zurueckkommen.
  - **Deckel** von 20 s auf die einzelne Wartezeit, angewandt **nach** dem
    Jittern: `min(deckel, base) * jitter` waere keine Schranke.
  - **Gesamtbudget** von 25 s ueber den ganzen Aufruf, als
    `asyncio.timeout`-Wanduhr-Deadline. Nicht als httpx-Timeout: httpx begrenzt
    pro Operation, und sein Read-Timeout beginnt mit jedem Chunk von vorn.

  Die Fehlerabbildung selbst ist unveraendert — sie war nie das Problem. Zwei
  Meldungen wurden angepasst, weil sie sonst falsch geworden waeren: Bei 429 und
  503 stand «bitte kurz warten und erneut versuchen», und genau das ist jetzt
  bereits geschehen.

  Die Redirect-Kette samt Allow-List-Pruefung jedes Hops (SEC-021/SEC-004) ist in
  `_send_once` ausgelagert und inhaltlich unveraendert; sie laeuft in jedem
  Versuch vollstaendig.

  Neu `tests/test_retry_policy.py`: `Retry-After` in beiden Formen samt
  Ablehnungsfaellen, die Jitter-Streuung, die Deckel-Reihenfolge und die
  Einseitigkeit.


## [0.4.1] - 2026-08-02

### Fixed

- **`structlog` carried no upper bound, and the index already serves a major past
  the floor.** The declared range was `structlog>=24.1.0`; PyPI has been serving
  `26.1.0`. The artefact does not change — the resolver's answer to the next
  fresh install does, and that is exactly how `swiss-energy-mcp` 0.3.3 became
  uninstallable when `mcp` 2.0.0 removed the module it imported.

  Now `structlog>=24.1.0,<27`. The bound is measured rather than guessed: this package
  installs and imports against `structlog 26.1.0` today, so the cap admits what
  demonstrably works and stops only the next, unknown major.

A dependency range only reaches users through a new release, hence the
version bump. No code changed.

## [0.4.0] - 2026-08-01

This release exists mainly so that a repair reaches the people running the
server: **the published `0.3.3` could no longer be installed from scratch.** It
declares `mcp[cli]>=1.20.0` with no upper bound, and `mcp` 2.0.0 removed
`mcp.server.fastmcp` — so every fresh `pip install swiss-energy-mcp` resolved to
2.0.0 and died on startup with `ModuleNotFoundError`. The repository has carried
the fix since 29 July; it was simply never released, and `main` kept the same
version number as the broken artifact.

### Changed (breaking)

- **Migrated to the `mcp` Python SDK 2.x.** The server API moved from
  `mcp.server.fastmcp` to `mcp.server.mcpserver` with no compatibility shim.
  Visible to anyone embedding this server: `build_server()` now returns an
  `MCPServer` rather than a `FastMCP`; `host`/`port` are no longer constructor
  arguments (uvicorn receives the bind address directly anyway); and
  `transport_security` — the allow-list introduced in 0.3.x — moved from the
  settings object to a `streamable_http_app(transport_security=...)` keyword,
  where misuse now raises instead of being silently ignored.

  The dependency pin is `mcp[cli]>=2.0.0,<3` accordingly. Anyone who must stay
  on `mcp` 1.x should stay on 0.3.x — and pin an upper bound themselves, because
  the published 0.3.3 has none.

  Verified against a 1.x baseline captured before any edit: 106 passed,
  10 deselected — identical.

### Fixed

- `energy_search_bfe_datasets` (and the opendata.swiss part of `energy_check_status`)
  no longer fail with an egress-allow-list error. opendata.swiss now redirects the
  CKAN API (`www.opendata.swiss` → `opendata.swiss` → `ckan.opendata.swiss`), and
  the final host was not on the allow-list. The CKAN base URL now points directly
  at `ckan.opendata.swiss`, which is also added to the egress allow-list — avoiding
  the redirect hops entirely.

## [0.3.0] - 2026-06-03

This release follows the 2026-06-03 best-practice re-audit
(see `audits/2026-06-03-swiss-energy-mcp.md`), which confirmed
production-readiness, and resolves its remaining low-severity finding.

### Added
- DNS pinning (SEC-005): a custom `httpcore` network backend connects to the
  exact IP that was validated against the egress allow-list, closing the
  time-of-check/time-of-use gap between host validation and the TCP connect. TLS
  SNI and certificate verification still use the original hostname, so transport
  security is unchanged. See `docs/security.md`.

### Changed
- Internal housekeeping (no behaviour change): the `User-Agent` is derived from
  the installed package version instead of a hardcoded string; the constant
  `compute_tolerance()` helper became the `IDENTIFY_TOLERANCE` constant; the
  unused `LAYER_SOLAR_FACADES` layer constant was removed.

## [0.2.1] - 2026-05-19

### Fixed
- HTTP redirects are no longer dropped. `0.2.0` disabled redirects entirely,
  which could break upstream endpoints that issue a 3xx (e.g. opendata.swiss).
  Redirects are now followed manually, with every hop re-validated against the
  egress allow-list — keeping the SEC-021 guarantee without losing redirects.

## [0.2.0] - 2026-05-19

This release implements the remediation of the MCP best-practice audit
(see `audits/2026-05-19-swiss-energy-mcp.md`).

### Changed (breaking)
- Tools no longer take a `response_format` parameter. Every search tool now
  returns a structured `EnergyResponse` envelope (`source`, `license`,
  `provenance`, `match_type`, `count`, `results`, `summary`, `notes`) instead
  of a Markdown or JSON string. `energy_check_status` returns a `StatusResponse`.
- Configuration moved to a typed `Settings` object; all environment variables
  use the `SWISS_ENERGY_` prefix. The HTTP transport now binds `127.0.0.1` by
  default — bind `0.0.0.0` only inside a container.

### Added
- Egress allow-list with SSRF / DNS-rebinding protection; redirects disabled.
- FastMCP lifespan managing a shared, properly closed HTTP client.
- `Context` injection: per-call logging and progress reporting.
- CORS middleware for the HTTP transport (exposes `Mcp-Session-Id`).
- Structured JSON logging to stderr (`structlog`).
- `energy://layers` resource and `energy_site_assessment` prompt.
- `Dockerfile` (multi-stage, non-root user), `.dockerignore`, `.gitignore`,
  `.env.example`, Dependabot config and a nightly live-test workflow.
- `docs/roadmap.md` (phased architecture) and `docs/security.md`
  (egress policy, lethal-trifecta assessment).
- `tools/` package (one module per tool group); test suite split into
  `test_unit.py` / `test_tools.py` / `test_live.py` with `respx`-mocked APIs.

### Fixed
- HTTP transport was non-functional (`mcp.run(transport="streamable_http",
  port=...)` is not a valid call); the server now serves Streamable HTTP via
  uvicorn with the correct transport.
- Tool execution errors now surface as `isError` results instead of being
  returned as plain success strings.

### Protocol
- MCP SDK pinned to `mcp[cli] >= 1.20.0`; protocol version follows the SDK.

## [0.1.0] - 2026-03-11

### Added
- Initial release
- `energy_find_power_plants` — electricity production plants (all types) with optional category filter
- `energy_find_wind_turbines` — wind turbines with manufacturer, model, hub height, annual production
- `energy_find_hydro_plants` — hydropower plants with capacity and expected annual output
- `energy_find_pv_installations` — large photovoltaic installations with seasonal production data
- `energy_find_biogas_plants` — biogas plants
- `energy_find_energy_cities` — Swiss "Energiestadt"-labelled municipalities (by name or location)
- `energy_solar_potential` — solar roof suitability at a given location
- `energy_location_profile` — combined energy profile (5 layers) for any Swiss location
- `energy_search_bfe_datasets` — full-text search over SFOE/BFE datasets on opendata.swiss
- `energy_check_status` — API availability check for GeoAdmin and opendata.swiss
- WGS84 → LV95 coordinate conversion (swisstopo approximation formula, ±1 m accuracy)
- Dual transport: stdio (Claude Desktop) + Streamable HTTP (cloud deployment)
- 78 unit/integration tests + 7 live integration tests
- Bilingual documentation (English README + German README.de.md)
