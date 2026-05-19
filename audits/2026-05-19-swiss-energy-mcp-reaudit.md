# MCP-Server Re-Audit-Report — `swiss-energy-mcp`

**Audit-Datum:** 2026-05-19 (Re-Audit)
**Auditor:** mcp-audit-skill (automatisiert)
**Skill-Version:** mcp-audit v0.1.0
**Check-Katalog:** [malkreide/mcp-audit-skill](https://github.com/malkreide/mcp-audit-skill) — 68 Checks / 8 Kategorien
**Vorheriger Audit:** `audits/2026-05-19-swiss-energy-mcp.md` (25 Findings)
**Geprüfte Version:** `0.2.0`

---

## 1. Executive Summary

Nach der Remediation (v0.2.0) wurde `swiss-energy-mcp` erneut gegen die 36 anwendbaren Best-Practice-Checks geprüft: 34 bestanden, 2 verbleiben als `partial` — beide low-Severity und als dokumentierte Restrisiken akzeptiert. Alle 8 high- und 12 medium-Findings des Erst-Audits sind geschlossen; es bestehen keine critical-, high- oder medium-Findings mehr. **Production-Readiness ist erreicht.**

**Production-Readiness:** ✅ ja
**Empfohlenes nächstes Release:** freigegeben — `0.2.0` kann getaggt werden.

---

## 2. Profil-Snapshot

| Feld | Wert |
|---|---|
| Server-Name | `swiss-energy-mcp` |
| Repo-URL | https://github.com/malkreide/swiss-energy-mcp |
| Transport | dual (stdio default + Streamable HTTP) |
| Auth-Modell | none |
| Datenklasse | Public Open Data (BFE-Energiedaten, keine PII) |
| Schreibzugriff | read-only |
| Deployment | local-stdio; Dockerfile für HTTP-Container vorhanden |
| SDK | Python (FastMCP, `mcp[cli]>=1.20.0`) |
| Geprüfter Commit | Remediation-Merge (PR #2), Version `0.2.0` |

Applicability unverändert gegenüber dem Erst-Audit: 36 von 68 Checks anwendbar.

---

## 3. Ergebnis-Übersicht

| Status | Erst-Audit | Re-Audit |
|---|---|---|
| ✅ pass | 11 | **34** |
| ⚠️ partial | 17 | **2** |
| ❌ fail | 8 | **0** |

| Kategorie | anwendbar | pass | partial | fail |
|---|---|---|---|---|
| ARCH | 11 | 11 | 0 | 0 |
| SDK | 4 | 4 | 0 | 0 |
| SEC | 12 | 11 | 1 | 0 |
| SCALE | 1 | 0 | 1 | 0 |
| OBS | 4 | 4 | 0 | 0 |
| CH | 1 | 1 | 0 | 0 |
| OPS | 3 | 3 | 0 | 0 |
| **Total** | **36** | **34** | **2** | **0** |

---

## 4. Status der Erst-Audit-Findings

Alle 25 Findings des Erst-Audits wurden adressiert. 23 sind vollständig geschlossen, 2 auf `partial` mit dokumentiertem Restrisiko reduziert.

### Geschlossen (23)

| ID | Erst-Audit | Re-Audit | Nachweis |
|---|---|---|---|
| ARCH-002 | partial | ✅ pass | `<use_case>`/`<important_notes>`/`<example>`-Tags in allen 10 Tool-Beschreibungen |
| ARCH-003 | fail | ✅ pass | `EnergyResponse.match_type` ('exact'/'none') + actionable `notes` |
| ARCH-004 | partial | ✅ pass | `settings.py` (pydantic-settings), Lifespan, `ctx`-basierte Handler |
| ARCH-005 | partial | ✅ pass | `.gitignore`, `.env.example`, Gitleaks-CI-Job; `__pycache__` entfernt |
| ARCH-008 | fail | ✅ pass | Resource `energy://layers` + Prompt `energy_site_assessment` |
| ARCH-011 | partial | ✅ pass | `tools/`-Package (installations/places/catalog), src-Layout |
| ARCH-012 | fail | ✅ pass | Dependabot, README-«MCP Protocol Version», CHANGELOG-Protokollnotiz |
| SDK-001 | fail | ✅ pass | `@asynccontextmanager`-Lifespan, Client-`close()` im `finally` |
| SDK-002 | partial | ✅ pass | `EnergyResponse`/`StatusResponse`-Modelle, konsistenter Envelope |
| SDK-003 | fail | ✅ pass | `ctx: Context` in allen 10 Tools, `report_progress` im Profil-Tool |
| SDK-004 | fail | ✅ pass | `CORSMiddleware`, `expose_headers=["Mcp-Session-Id"]` |
| SEC-004 | partial | ✅ pass | `assert_url_allowed`: HTTPS-Zwang + IP-Blocklist; `follow_redirects=False` |
| SEC-007 | partial | ✅ pass | Multi-Stage-`Dockerfile`, `USER` mit UID 10001 |
| SEC-016 | partial | ✅ pass | Host-Default `127.0.0.1`; README-Config korrigiert; `0.0.0.0` nur im Container |
| SEC-019 | partial | ✅ pass | Lethal-Trifecta-Bewertung in `docs/security.md` |
| SEC-021 | partial | ✅ pass | `ALLOWED_HOSTS`-`frozenset`, Pre-Request-Check, `docs/security.md` |
| OBS-001 | fail | ✅ pass | Execution-Errors werden geworfen → FastMCP `isError`; Tests verifizieren |
| OBS-002 | partial | ✅ pass | Saubere Fehlermeldungen ohne Internals/URLs; in `docs/security.md` dokumentiert |
| OBS-003 | fail | ✅ pass | `structlog`, JSON-Logs nach stderr, Per-Call-Logging via `ctx` |
| CH-004 | partial | ✅ pass | `source`/`license`/`provenance` in jeder Antwort |
| OPS-001 | partial | ✅ pass | `respx`-Tests, `test_unit`/`test_tools`/`test_live`, Nightly-Workflow |
| OPS-002 | partial | ✅ pass | README-`Configuration` an den Code angeglichen |
| OPS-003 | partial | ✅ pass | README-«Development Phase», `docs/roadmap.md` mit Phasen-Voraussetzungen |

Zusätzlich behoben: Der HTTP-Transport-Aufruf war im Erst-Audit-Stand funktionsuntüchtig (`mcp.run(transport="streamable_http", port=…)`) und ist nun korrekt implementiert.

### Verbleibend als `partial` (2, low, akzeptiertes Restrisiko)

| ID | Severity | Status | Begründung |
|---|---|---|---|
| SEC-005 | low | partial | DNS wird pro Request aufgelöst und validiert, die Resolved-IP wird jedoch nicht für die TCP-Verbindung gepinnt (httpx löst erneut auf). Restrisiko vernachlässigbar: nur zwei fixe Behörden-Hosts, Allow-List-Prüfung pro Request, Redirects deaktiviert. In `docs/security.md` dokumentiert. |
| SCALE-002 | low | partial | Sticky-Sessions/Shared-State sind nicht implementiert. Die Referenz-Deployment-Form ist explizit Single-Instance (stdio bzw. ein HTTP-Container); `docs/security.md` dokumentiert das Vorgehen für eine künftige Multi-Replica-Skalierung. Wird erst bei einem solchen Deployment blockierend. |

---

## 5. Detail-Findings

### 5.1 SEC-005 — DNS-Pinning (low, partial)

**Observed:** `assert_url_allowed` (`api_client.py`) löst den Host vor jedem Request einmalig auf und prüft alle IPs gegen die Blocklist. Für die eigentliche TCP-Verbindung führt `httpx` jedoch eine separate Auflösung durch — die validierte IP wird nicht gepinnt.
**Expected (SEC-005 Kriterium 2):** Die resolved IP wird für die TCP-Connection verwendet (URL-Pinning oder Custom-Resolver).
**Risk:** Theoretisches TOCTOU-Fenster zwischen Validierung und Verbindung. Praktisch vernachlässigbar — die Ziel-Hosts sind zwei fixe Behörden-Domains; ein Angriff erforderte eine Kompromittierung der Behörden-DNS-Zone.
**Remediation (optional):** Custom-`httpx`-Transport mit gepinnter IP. Aufgrund des minimalen Risikos als akzeptiertes Restrisiko geführt.
**Effort:** S

### 5.2 SCALE-002 — Stateful Load Balancing (low, partial)

**Observed:** Der Streamable-HTTP-Transport nutzt den In-Memory-Session-Manager von FastMCP. Sticky-Sessions oder ein Shared-State-Store sind nicht implementiert.
**Expected:** Bei Multi-Replica-Betrieb sticky Sessions auf `Mcp-Session-Id` oder ein gemeinsamer Session-Store.
**Risk:** Nur bei einem Multi-Replica-Deployment relevant. Die unterstützte Betriebsform ist Single-Instance; `docs/security.md` beschreibt die notwendigen Schritte für eine spätere Skalierung.
**Remediation:** Vor einem Multi-Replica-Deployment umsetzen (dann high). Aktuell als dokumentierte Design-Entscheidung akzeptiert.
**Effort:** M

---

## 6. Remediation-Plan

Keine offenen Pflicht-Massnahmen. Die zwei verbleibenden `partial`-Punkte sind dokumentierte, akzeptierte Restrisiken ohne Production-Blocker-Charakter:

- **SEC-005** — nur umsetzen, falls echtes DNS-Pinning gewünscht wird (geringer Nutzen bei fixen Behörden-Hosts).
- **SCALE-002** — vor einem etwaigen Multi-Replica-Cloud-Deployment umsetzen.

---

## 7. Audit-Metadata

| Feld | Wert |
|---|---|
| Skill-Version | mcp-audit v0.1.0 |
| Check-Katalog | malkreide/mcp-audit-skill (68 Checks) |
| Verifikations-Modi | Static Code Analysis (`grep`), Code-Review, Test-Lauf (87 gemockte Tests grün) |
| Nicht ausgeführt | Live-Runtime-Tests (Netzwerk-Policy der Audit-Umgebung blockiert die Behörden-APIs) |
| Re-Audit empfohlen nach | Einführung schreibender Tools, PII-Verarbeitung oder Multi-Replica-Cloud-Deployment |

---

## 8. Sign-Off

- [x] Auditor: alle 36 anwendbaren Checks erneut ausgeführt
- [x] Auditor: 23 Findings geschlossen, 2 als akzeptiertes Restrisiko (low) geführt
- [x] Production-Readiness erreicht — Release `0.2.0` freigegeben
- [ ] Server-Maintainer: Re-Audit-Ergebnis und Release bestätigt

---

*Ende des Re-Audit-Reports — generiert mit dem mcp-audit-skill am 2026-05-19.*
