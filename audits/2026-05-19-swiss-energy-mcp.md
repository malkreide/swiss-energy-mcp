# MCP-Server Audit-Report — `swiss-energy-mcp`

**Audit-Datum:** 2026-05-19
**Auditor:** mcp-audit-skill (automatisiert)
**Skill-Version:** mcp-audit v0.1.0
**Check-Katalog:** [malkreide/mcp-audit-skill](https://github.com/malkreide/mcp-audit-skill) — 68 Checks / 8 Kategorien

---

## 1. Executive Summary

Der Server `swiss-energy-mcp` wurde gegen 36 anwendbare Best-Practice-Checks geprüft; 11 bestanden, 25 Findings (0 critical, 8 high, 12 medium, 5 low) wurden dokumentiert. Kein critical-Finding — der Server verarbeitet ausschliesslich öffentliche, auth-freie BFE-Energiedaten, weshalb die SSRF-/Secret-/Trifecta-Checks im Kontext entschärft sind. Production-Readiness ist für den **lokalen stdio-Betrieb gegeben mit Auflagen**, für den im README beworbenen **HTTP-/Cloud-Betrieb jedoch nicht erreicht** (CORS, Host-Binding-Doku, Load-Balancing offen).

**Production-Readiness:** ❌ nein (für HTTP/Cloud) · ⚠️ bedingt ja (für lokal/stdio)
**Empfohlenes nächstes Release:** freigegeben mit Auflage — die 8 high-Findings sollten vor einem `0.2.0`-Release abgearbeitet werden.

---

## 2. Profil-Snapshot

| Feld | Wert |
|---|---|
| Server-Name | `swiss-energy-mcp` |
| Repo-URL | https://github.com/malkreide/swiss-energy-mcp |
| Cluster | Swiss Public Data MCP Portfolio |
| Transport | dual (stdio default + Streamable HTTP) |
| Auth-Modell | none |
| Datenklasse | Public Open Data (BFE-Energiedaten, keine PII) |
| Schreibzugriff | read-only |
| Deployment | local-stdio (HTTP-Transport im Code vorhanden, aber kein Deployment-Artefakt) |
| SDK | Python (FastMCP, `mcp[cli]>=1.0.0`) |
| Externe Requests | ja (api3.geo.admin.ch, opendata.swiss) |
| Sampling / Sequential Thinking | nein / nein |
| Letzter Commit | 2026-04-28 |

**Profil-Hinweise zur Applicability:**
- `is_cloud_deployed = false`: Kein Dockerfile, keine Railway-/Render-Konfiguration im Repo → SCALE-001/003/004/006, OBS-005/006, SEC-014/015/022 nicht anwendbar.
- `stadt_zuerich_context = false`: Trotz Autor «Schulamt Stadt Zürich» (pyproject) verarbeitet der Server keine Verwaltungsdaten — ausschliesslich Public Open Data. CH-005/006 daher nicht anwendbar. **Re-Audit nötig**, falls der Server in eine Stadt-Zürich-Infrastruktur eingebunden wird.

---

## 3. Applicability

| Kategorie | anwendbar | gesamt | Anteil |
|---|---|---|---|
| ARCH | 11 | 12 | 92% |
| SDK | 4 | 5 | 80% |
| SEC | 12 | 23 | 52% |
| SCALE | 1 | 6 | 17% |
| OBS | 4 | 6 | 67% |
| HITL | 0 | 5 | 0% |
| CH | 1 | 8 | 13% |
| OPS | 3 | 3 | 100% |
| **Total** | **36** | **68** | **53%** |

### Severity-Breakdown der anwendbaren Checks

| Severity | Anzahl |
|---|---|
| critical | 6 |
| high | 16 |
| medium | 14 |
| **Total** | **36** |

### Ergebnis-Übersicht

| Status | Anzahl | Check-IDs |
|---|---|---|
| ✅ pass | 11 | ARCH-001, ARCH-006, ARCH-007, ARCH-009, SEC-006, SEC-008, SEC-009, SEC-013, SEC-018, SEC-020, OBS-004 |
| ⚠️ partial | 17 | ARCH-002, ARCH-004, ARCH-005, ARCH-011, SDK-002, SEC-004, SEC-005, SEC-007, SEC-016, SEC-019, SEC-021, SCALE-002, OBS-002, CH-004, OPS-001, OPS-002, OPS-003 |
| ❌ fail | 8 | ARCH-003, ARCH-008, ARCH-012, SDK-001, SDK-003, SDK-004, OBS-001, OBS-003 |

---

## 4. Findings-Übersicht

*Effektive Severity = Check-Severity, bei dokumentierter Begründung herab-/heraufgestuft (siehe Detail-Findings).*

| ID | Titel | Check-Sev. | Effektiv | Status | Effort |
|---|---|---|---|---|---|
| SDK-001 | Kein FastMCP-Lifespan / HTTP-Client wird nie geschlossen | high | high | open | M |
| SDK-004 | Keine CORS-Konfiguration bei HTTP-Transport | high | high | open | S |
| SEC-016 | README dokumentiert nicht-existente `SWISS_ENERGY_HOST=0.0.0.0`-Variable | critical | high | open | S |
| SEC-021 | Keine Egress-Allow-List + `follow_redirects=True` | high | high | open | M |
| ARCH-004 | IoC unvollständig: kein Settings-Objekt, kein Lifespan | high | high | open | M |
| OBS-001 | Execution-Errors als Plain-String statt `isError: true` | high | high | open | M |
| OBS-002 | `mask_error_details` nicht gesetzt | high | high | open | S |
| OPS-001 | Test-Suite: kein `respx`, <5 Tests/Tool, kein Live-Workflow | high | high | open | M |
| ARCH-002 | Keine `<use_case>`-Tags in Tool-Beschreibungen | medium | medium | open | S |
| ARCH-003 | «Not Found»-Anti-Pattern: leere Strings ohne `match_type` | medium | medium | open | M |
| ARCH-008 | Nur Tools — keine Resources/Prompts, keine Begründung | medium | medium | open | M |
| ARCH-011 | 10 Tools in einer `server.py`, kein `tools/`-Verzeichnis | medium | medium | open | M |
| ARCH-012 | `protocolVersion` nicht gepinnt, kein Dependabot | medium | medium | open | S |
| SDK-002 | Tool-Returns sind `str`, kein strukturierter Envelope | medium | medium | open | M |
| SDK-003 | Keine `ctx: Context`-Injection / kein Progress-Reporting | medium | medium | open | M |
| SCALE-002 | Kein Sticky-Session-/Shared-State-Konzept für HTTP | high | medium | open | M |
| OBS-003 | Stdlib-`logging` statt strukturiertem Logger | medium | medium | open | M |
| CH-004 | Quellen-/Lizenz-Attribution in Tool-Antworten inkonsistent | medium | medium | open | S |
| OPS-002 | README-`Configuration`-Tabelle nennt falsche Env-Variablen | medium | medium | open | S |
| OPS-003 | Phase nicht im README deklariert, keine Roadmap | high | medium | open | S |
| ARCH-005 | Keine `.gitignore`, kein CI-Secret-Scan (`__pycache__` committed) | critical | low | open | S |
| SEC-004 | SSRF: keine HTTPS-/IP-Validierung | critical | low | open | S |
| SEC-005 | DNS-Rebinding: kein DNS-Pinning | high | low | open | S |
| SEC-007 | Kein Container-Sandboxing / kein Dockerfile | high | low | open | S |
| SEC-019 | Lethal-Trifecta-Bewertung nicht dokumentiert | critical | low | open | S |

**Gesamt:** 25 Findings — 0 critical, 8 high, 12 medium, 5 low.

---

## 5. Detail-Findings

### 5.1 SDK-001 — Kein FastMCP-Lifespan (high, fail)

**Observed:** `server.py:60` erzeugt `FastMCP("swiss_energy_mcp", instructions=...)` **ohne** `lifespan=`. Der HTTP-Client wird über ein Lazy-Global `_client` (`server.py:86–93`) verwaltet. Es gibt keine `@asynccontextmanager`-Lifespan-Funktion (`grep` nach `lifespan`/`asynccontextmanager` in `src/`: 0 Treffer).
**Expected:** Lifespan via `@asynccontextmanager`, an FastMCP-Konstruktor übergeben; Cleanup im `finally`-Block.
**Risk:** `EnergyHTTPClient.close()` (`api_client.py:198`) wird nie aufgerufen → die `httpx.AsyncClient`-Connection-Pools werden beim Shutdown nicht sauber geschlossen (Resource-Leak, hängende Sockets bei Server-Neustart). Das Lazy-Singleton verhindert immerhin Clients pro Tool-Call (Teil-Kriterium erfüllt).
**Remediation:**
```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(server):
    client = EnergyHTTPClient()
    try:
        yield {"client": client}
    finally:
        await client.close()

mcp = FastMCP("swiss_energy_mcp", instructions=..., lifespan=lifespan)
```
Tools greifen via `ctx.request_context.lifespan_context["client"]` zu (Synergie zu SDK-003).
**Effort:** M

### 5.2 SDK-004 — Keine CORS-Konfiguration bei HTTP-Transport (high, fail)

**Observed:** `main()` startet bei `MCP_TRANSPORT=streamable_http` den HTTP-Transport (`server.py:1309–1312`), ohne CORS-Middleware. Kein `expose_headers`/`Mcp-Session-Id` im Code. Das README bewirbt explizit den Browser-Einsatz («For use via claude.ai in the browser»).
**Expected:** CORS-Middleware mit `expose_headers=["Mcp-Session-Id"]`, `allow_headers` inkl. `Mcp-Session-Id`, explizite `allow_origins` (keine Wildcard in Production).
**Risk:** Browser-basierte MCP-Clients können den `Mcp-Session-Id`-Header nicht lesen → Folge-Requests ohne Session-Kontext → der im README beworbene Browser-/Cloud-Use-Case ist faktisch nicht funktionsfähig.
**Remediation:** Starlette-`CORSMiddleware` mit `expose_headers=["Mcp-Session-Id"]` registrieren, oder den HTTP-Use-Case aus dem README streichen, bis er getestet ist.
**Effort:** S

### 5.3 SEC-016 — README dokumentiert nicht-existente `0.0.0.0`-Host-Variable (critical-Check → high, partial)

**Observed:** Die README-`Configuration`-Tabelle (`README.md:166–170`) listet `SWISS_ENERGY_HOST` mit Default **`0.0.0.0`** sowie `SWISS_ENERGY_TRANSPORT`/`SWISS_ENERGY_PORT`. Der Code liest jedoch **andere** Variablen: `MCP_TRANSPORT` und `PORT` (`server.py:1301`, `1310`). Eine Host-Variable wird vom Code **gar nicht** ausgewertet — der FastMCP-Default (`127.0.0.1`) greift.
**Expected:** Code bindet per Default `127.0.0.1`; `0.0.0.0` nur explizit (z. B. im Dockerfile). Doku stimmt mit dem Code überein.
**Risk:** Der Code selbst bindet **nicht** auf `0.0.0.0` (gut) — das Finding wird daher von critical auf **high** herabgestuft. Aber: Die Doku suggeriert ein unsicheres `0.0.0.0`-Default-Binding (NeighborJack-Risiko) und nennt drei Env-Variablen, die wirkungslos sind. Wer der Doku folgt, erreicht weder die gewünschte Konfiguration noch versteht er das tatsächliche Binding-Verhalten.
**Remediation:** README-Tabelle an den Code angleichen (`MCP_TRANSPORT`, `PORT`); Host-Zeile entfernen oder eine echte `MCP_HOST`-Variable mit Default `127.0.0.1` implementieren. Cross-Ref: OPS-002.
**Effort:** S

### 5.4 SEC-021 — Keine Egress-Allow-List + `follow_redirects=True` (high, partial)

**Observed:** Die Ziel-Hosts sind als Konstanten hardcodiert (`api_client.py:15–16`) — eine implizite Allow-List, aber **keine** `frozenset`-basierte Pre-Request-Prüfung (`assert_host_allowed`). Der `httpx.AsyncClient` ist mit `follow_redirects=True` konfiguriert (`api_client.py:142–148`). Keine `docs/network-egress.md`.
**Expected:** Code-Layer-Allow-List als `frozenset`, Pre-Request-Host-Check vor jedem Request, dokumentierte Hosts.
**Risk:** `follow_redirects=True` ohne IP-/Host-Prüfung: Eine kompromittierte oder fehlkonfigurierte Upstream-Antwort kann den Client auf einen beliebigen (auch internen) Host umleiten. Da die Eingangs-URLs nicht user-kontrolliert sind, ist das Restrisiko begrenzt, aber real.
**Remediation:** `follow_redirects=False` setzen (die BFE-/CKAN-APIs benötigen keine Redirects), oder eine `frozenset`-Allow-List mit Host-Check vor dem Request einführen.
**Effort:** M

### 5.5 ARCH-004 — Inversion of Control unvollständig (high, partial)

**Observed:** Tool-Handler sind transport-agnostisch — kein direkter `request`/`websocket`-Zugriff (gut). Aber: Konfiguration läuft über direkte `os.environ.get`-Aufrufe in `main()` (`server.py:1301`, `1310`) statt über ein Pydantic-`Settings`-Objekt; es gibt keinen gemeinsamen Lifespan-/Setup-Pfad.
**Expected:** `BaseSettings`-Objekt für Transport/Port/Host; gemeinsamer Lifespan für stdio + HTTP.
**Risk:** Konfigurations-Streuung erschwert Tests und führte bereits zur Doku-Drift in SEC-016/OPS-002. Kein Fail-Fast bei fehlender/falscher Konfiguration.
**Remediation:** `pydantic-settings`-`Settings`-Klasse einführen, zusammen mit dem Lifespan aus SDK-001.
**Effort:** M

### 5.6 OBS-001 — Execution-Errors als Plain-String statt `isError` (high, fail)

**Observed:** Tool-Handler fangen `ValueError` aus dem API-Client und geben sie als normalen String zurück, z. B. `return f"Fehler bei der Abfrage: {e}"` (`server.py:428`, analog in allen Tools). FastMCP wertet einen zurückgegebenen String als **erfolgreiches** Tool-Result — `isError: true` wird nie gesetzt.
**Expected:** Anwendungsfehler mit `isError: true` im `tool-result` (FastMCP: `ToolError` werfen bzw. strukturiertes Fehler-Result).
**Risk:** Das LLM kann Fehler nicht von gültigen Daten unterscheiden — eine Fehlermeldung sieht aus wie ein normales Resultat. Folge: Halluzination oder stilles Weiterarbeiten mit Nicht-Daten.
**Remediation:** In Tool-Handlern bei Fehler `raise ToolError(str(e))` statt String-Return; Protocol-Errors (falsches Tool/Args) FastMCP überlassen.
**Effort:** M

### 5.7 OBS-002 — `mask_error_details` nicht gesetzt (high, partial)

**Observed:** `FastMCP(...)` (`server.py:60`) ohne `mask_error_details=True`. `energy_check_status` interpoliert in einem generischen `except Exception as e` die rohe Exception (`server.py:1252`, `1265`: `f"❌ Fehler: {e}"`). API-Client-Fehlermeldungen hängen die interne URL an (`api_client.py`, `f"...URL: {url}"`).
**Expected:** `mask_error_details=True`; keine rohen Exceptions/Internals in Tool-Returns; Originalfehler nur ins Server-Log.
**Risk:** Unmaskierte Exceptions und interne URLs gelangen zum LLM/Client. Bei diesem Server gering sensibel (öffentliche Endpunkte), aber das Pattern leakt bei künftigen Erweiterungen Internals.
**Remediation:** `FastMCP(..., mask_error_details=True)`; generisches `except Exception` in `energy_check_status` durch eine generische Meldung ersetzen, Detail nur loggen.
**Effort:** S

### 5.8 OPS-001 — Test-Strategie (high, partial)

**Observed:** `tests/test_server.py` enthält ~60 Unit-Tests + 7 Live-Tests. Lücken:
- HTTP-Mocking via `unittest.mock.patch`/`AsyncMock`, **nicht** `respx` (das `pytest-httpx` aus den dev-deps wird nicht genutzt).
- Keine Trennung in `test_unit.py` / `test_live.py`.
- <5 Tests/Tool für mehrere Tools; `energy_find_pv_installations` und `energy_find_biogas_plants` haben **keine** dedizierten Tool-Tests.
- Kein separater nightly/manueller Live-Test-Workflow.

Erfüllt: `@pytest.mark.live`-Marker, Marker in `pyproject.toml` registriert, CI läuft `pytest -m "not live"`.
**Risk:** Ungetestete Tools (PV, Biogas) können bei Refactorings unbemerkt brechen; Mock-basierte Tests prüfen die echte HTTP-Parameter-Konstruktion nicht.
**Remediation:** `respx`-Fixtures einführen; PV-/Biogas-Tool-Tests ergänzen; Live-Tests in einen `schedule`-Workflow auslagern.
**Effort:** M

### 5.9–5.20 Medium-Findings (Kurzform)

- **ARCH-002 (partial):** Tool-Docstrings sind ausführlich (>100 Zeichen Median ✓), enthalten aber keine `<use_case>`/`<important_notes>`/`<example>`-Tags. → Tags ergänzen für bessere semantische Trennschärfe. Effort S.
- **ARCH-003 (fail):** Leere Suchresultate liefern Plain-Strings («Keine Anlagen … gefunden») ohne `match_type`-Feld und ohne actionable Hinweise/Fuzzy-Fallback. Da nicht-sensible Geodaten: heuristische Vorschläge bzw. ein `match_type`-Feld empfohlen. Effort M.
- **ARCH-008 (fail):** Server nutzt ausschliesslich Tools. Read-only-Tools (z. B. `energy_check_status`) wären Resources-Kandidaten. Mindestens eine README-Begründung «warum nur Tools» ergänzen. Effort M.
- **ARCH-011 (partial):** Alle 10 Tools liegen in einer 1320-Zeilen-`server.py`. Bei >5 Tools verlangt der Standard ein `tools/`-Verzeichnis mit Datei-pro-Gruppe — oder eine README-Begründung. Effort M.
- **ARCH-012 (fail):** `protocolVersion` nicht explizit gepinnt; kein Dependabot/Renovate (`.github/` enthält nur `workflows/`); keine README-Sektion «MCP Protocol Version»; keine Update-Policy. CHANGELOG-Format ✓. Effort S.
- **SDK-002 (partial):** Alle Tools haben explizite Return-Annotation `-> str`, liefern aber Strings (Markdown bzw. JSON-String) statt strukturierter Pydantic-Modelle. JSON-Outputs uneinheitlich, kein durchgängiger `source`/`provenance`-Envelope. Effort M.
- **SDK-003 (fail):** Kein Tool hat `ctx: Context` (`grep` nach `Context`: 0 Treffer). `energy_location_profile` führt 5 parallele API-Calls aus (potenziell >2 s) ohne `ctx.report_progress()`. Effort M.
- **SCALE-002 (high-Check → medium, partial):** Streamable-HTTP-Transport ist aktivierbar, aber ohne Sticky-Sessions/Shared-State. Da derzeit kein Multi-Replica-Cloud-Deployment existiert, herabgestuft auf medium — wird **blockierend**, sobald HTTP mehrfach repliziert deployt wird. Effort M.
- **OBS-003 (fail):** Stdlib-`logging` mit Plain-Format statt strukturiertem Logger (structlog/loguru); kein JSON/logfmt; nur 2 Startup-Log-Zeilen; kein Per-Tool-Call-Kontext/`correlation_id`. Keine `print()` ✓. Effort M.
- **CH-004 (partial):** Quellen-/Lizenz-Attribution inkonsistent: Markdown-Footer `*Quelle: BFE/swisstopo …*` nur in 4 von 10 Tools (`energy_solar_potential`, `energy_find_energy_cities`, `energy_location_profile`, `energy_search_bfe_datasets`); die übrigen Tools und **alle** JSON-Outputs haben kein `source`/Lizenz-Feld. swisstopo/BFE-Daten verlangen explizite Attribution. → Einheitliches `source`-Feld in allen Antworten. Effort S.
- **OPS-002 (partial):** README enthält alle 8 Pflicht-Sektionen, ASCII-Diagramm, ≥3 Limits, README.de.md parallel, CONTRIBUTING.md bilingual — sehr gut. **Aber:** Die `Configuration`-Tabelle nennt drei Env-Variablen (`SWISS_ENERGY_TRANSPORT/PORT/HOST`), die der Code nicht kennt (Cross-Ref SEC-016). Effort S.
- **OPS-003 (high-Check → medium, partial):** Der Server ist faktisch ein sauberer Phase-1-Server (read-only, alle `readOnlyHint: true`), aber die Phase ist nicht im README deklariert und es gibt kein Roadmap-File. Da Architektur und Annotations konsistent sind, herabgestuft auf medium. → Phase 1 deklarieren + `docs/roadmap.md`. Effort S.

### 5.21–5.25 Low-Findings (Kurzform, Severity herabgestuft)

- **ARCH-005 (critical-Check → low, partial):** Der Server verarbeitet **keine** Secrets (auth-frei) — Kernrisiko entfällt, daher Herabstufung. Aber: Es gibt **keine `.gitignore`**, weshalb `__pycache__/*.pyc`-Dateien bereits eingecheckt sind (`src/swiss_energy_mcp/__pycache__/`, `tests/__pycache__/`). Kein CI-Secret-Scan (Gitleaks/Trufflehog). → `.gitignore` anlegen (`.env`, `__pycache__/`, `*.pyc`), eingecheckte `.pyc` entfernen, optional Gitleaks-Workflow. Effort S.
- **SEC-004 (critical-Check → low, partial):** Keine explizite HTTPS-/IP-Blocklist-Validierung. Herabgestuft, weil die Ziel-Hosts hardcodiert und nicht user-kontrolliert sind. Reales Restrisiko siehe SEC-021 (`follow_redirects=True`). Effort S.
- **SEC-005 (high-Check → low, partial):** Kein DNS-Pinning gegen TOCTOU. Herabgestuft — fixe, vertrauenswürdige Behörden-Endpunkte ohne user-kontrollierte Hostnamen. Effort S.
- **SEC-007 (high-Check → low, partial):** Kein Dockerfile / kein Container-Sandboxing. Für die lokale stdio-Installation via `uvx` akzeptabel; wird relevant, sobald HTTP/Cloud deployt wird (dann high). → Bei Cloud-Deployment Multi-Stage-Dockerfile mit Non-Root-`USER`. Effort S (bzw. M bei Cloud).
- **SEC-019 (critical-Check → low, partial):** Lethal-Trifecta inhärent nicht gegeben (read-only, keine private Daten, kein Exfiltrations-Kanal — nur GETs an fixe Hosts). Einziges offenes Kriterium: Die Bewertung ist nicht dokumentiert. → Kurzer Trifecta-Abschnitt in `docs/` oder README. Effort S.

---

## 6. Remediation-Plan

### Empfohlene Reihenfolge

**Sofort-Wins (Effort S, hoher Nutzen):**
1. **SEC-016 / OPS-002** (high/medium) — README-`Configuration` an den Code angleichen; irreführendes `0.0.0.0`-Default entfernen.
2. **OBS-002** (high) — `mask_error_details=True` + generisches `except` in `energy_check_status` entschärfen.
3. **SDK-004** (high) — CORS-Middleware ergänzen *oder* HTTP-Use-Case aus README streichen, bis getestet.
4. **ARCH-005** (low) — `.gitignore` anlegen, eingecheckte `__pycache__`/`.pyc` entfernen.

**Architektur-Sprint (Effort M):**
5. **SDK-001 + ARCH-004** (high) — Lifespan + `pydantic-settings`-`Settings` gemeinsam einführen.
6. **OBS-001** (high) — Execution-Errors auf `ToolError`/`isError` umstellen.
7. **SEC-021** (high) — `follow_redirects=False` bzw. Egress-Allow-List.
8. **OPS-001** (high) — `respx`-Tests + PV-/Biogas-Tool-Tests + Live-Workflow.

**Backlog (medium/low):** ARCH-002, ARCH-003, ARCH-008, ARCH-011, ARCH-012, SDK-002, SDK-003, SCALE-002, OBS-003, CH-004, OPS-003, SEC-004/005/007/019.

### Effort-Aggregation

| Severity | Anzahl | Grob-Aufwand |
|---|---|---|
| high | 8 | 4×S + 4×M ≈ 2–3 Wochen |
| medium | 12 | ~6×S + 6×M ≈ 3–4 Wochen |
| low | 5 | 5×S ≈ 2–3 Tage |
| **Gesamt** | **25** | **~6–8 Wochen** (1 Entwickler) |

---

## 7. Audit-Metadata

| Feld | Wert |
|---|---|
| Skill-Version | mcp-audit v0.1.0 |
| Check-Katalog | malkreide/mcp-audit-skill (68 Checks, MANIFEST verifiziert) |
| Audit-Methodik | siehe `SKILL.md` (7-Schritt-Prozess) |
| Verifikations-Modi | Static Code Analysis (`grep`), Code-Review |
| Nicht ausgeführt | Runtime-Tests (Live-API-Calls, MCP Inspector) — Empfehlung für Re-Audit |
| Re-Audit empfohlen nach | Remediation der high-Findings, spätestens 6 Monate |

---

## 8. Nicht-anwendbare Kategorien

- **HITL** (5 Checks) — kein Sampling, kein Sequential Thinking, read-only (kein write_capable). Komplett nicht anwendbar.
- **CH** (7 von 8 Checks) — Datenklasse `Public Open Data` ohne PII; DSG/EDÖB-/ISDS-Checks nicht relevant. Nur CH-004 (OGD-Lizenz) anwendbar.
- **Teile von SEC/SCALE/OBS** — kein OAuth/API-Key (SEC-001/002/003/010/011/012), kein Filesystem-Tool (SEC-017), kein Enterprise-Gateway-Kontext (SEC-014/015/022), kein Cloud-Deployment-Artefakt (SCALE-001/003/004/006, OBS-005/006).

**Trigger für ein Re-Audit:** Einführung schreibender Tools, Verarbeitung von Personendaten, produktives Cloud-/HTTP-Deployment oder Einbindung in eine Stadt-Zürich-Infrastruktur.

---

## 9. Sign-Off

- [x] Auditor: alle 36 anwendbaren Checks ausgeführt
- [x] Auditor: 25 Findings dokumentiert (0 critical, 8 high, 12 medium, 5 low)
- [ ] Server-Maintainer: Findings akzeptiert / Remediation-Plan akzeptiert

---

*Ende des Audit-Reports — generiert mit dem mcp-audit-skill am 2026-05-19.*
