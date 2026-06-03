# MCP-Server Audit-Report — `swiss-energy-mcp`

**Audit-Datum:** 2026-06-03
**Auditor:** mcp-audit-skill (automatisiert)
**Skill-Version:** mcp-audit v0.1.0
**Check-Katalog:** [malkreide/mcp-audit-skill](https://github.com/malkreide/mcp-audit-skill) — 68 Checks / 8 Kategorien
**Vorherige Audits:** `audits/2026-05-19-swiss-energy-mcp.md` (Erst-Audit, 25 Findings) · `audits/2026-05-19-swiss-energy-mcp-reaudit.md` (Re-Audit v0.2.0)
**Geprüfte Version:** `0.2.1` (inkl. Folge-Fixes bis Commit `811e9cf`)

---

## 1. Executive Summary

`swiss-energy-mcp` wurde in der aktuellen Version `0.2.1` erneut gegen die 36 anwendbaren Best-Practice-Checks geprüft: 34 bestehen, 2 verbleiben als dokumentierte `partial` (beide low, akzeptiertes Restrisiko) — unverändert gegenüber dem Re-Audit. Die Code-Änderungen seit `0.2.0` (manuelle, pro Hop revalidierte Redirect-Behandlung in `0.2.1`; expliziter `sr=2056`-Parameter gegen stille Null-Treffer; Härtung der Live-Tests) verbessern Sicherheit und Korrektheit, ohne eine der zuvor geschlossenen Garantien zu schwächen. **Production-Readiness ist weiterhin erreicht.**

**Production-Readiness:** ✅ ja
**Empfohlenes nächstes Release:** freigegeben — `0.2.1` ist release-fähig (kein offener Blocker).

---

## 2. Profil-Snapshot

| Feld | Wert |
|---|---|
| Server-Name | `swiss-energy-mcp` |
| Repo-URL | https://github.com/malkreide/swiss-energy-mcp |
| Cluster | Swiss Public Data MCP Portfolio |
| Transport | dual (stdio default + Streamable HTTP via uvicorn) |
| Auth-Modell | none (alle Upstream-APIs öffentlich/auth-frei) |
| Datenklasse | Public Open Data (BFE-Energiedaten, keine PII) |
| Schreibzugriff | read-only (alle 10 Tools `readOnlyHint: true`) |
| Deployment | local-stdio; Multi-Stage-Dockerfile (non-root, UID 10001) für HTTP-Container |
| SDK | Python (FastMCP, `mcp[cli]>=1.20.0`) |
| Externe Requests | ja — fixe Allow-List: `api3.geo.admin.ch`, `(www.)opendata.swiss` |
| Sampling / HITL | nein |
| Geprüfter Commit | `811e9cf` (`main`), `__version__ = 0.2.1` |

**Applicability unverändert:** 36 von 68 Checks anwendbar (53 %). Auslöser für ein erneutes Re-Audit (schreibende Tools, PII-Verarbeitung, Multi-Replica-Cloud-Deployment, Stadt-Zürich-Infrastruktur) sind weiterhin nicht eingetreten.

---

## 3. Ergebnis-Übersicht

| Status | Erst-Audit (init) | Re-Audit (0.2.0) | **Dieses Audit (0.2.1)** |
|---|---|---|---|
| ✅ pass | 11 | 34 | **34** |
| ⚠️ partial | 17 | 2 | **2** |
| ❌ fail | 8 | 0 | **0** |

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

Keine critical-, high- oder medium-Findings. Beide verbleibenden `partial` sind low-Severity und als bewusste Design-Entscheidung in `docs/security.md` dokumentiert.

---

## 4. Verifikation der zuvor geschlossenen Findings

Alle 23 im Re-Audit als geschlossen geführten Findings wurden in `0.2.1` stichprobenartig erneut verifiziert und sind weiterhin geschlossen. Auszug der wichtigsten Nachweise:

| ID | Check | Nachweis in `0.2.1` |
|---|---|---|
| SDK-001 | FastMCP-Lifespan | `server.py:42–63` — `@asynccontextmanager`-Lifespan, `await client.close()` im `finally` |
| SDK-003 | `Context`-Injection | alle 10 Tools nehmen `ctx: Context`; `report_progress` in `energy_location_profile` (`places.py`) |
| SDK-004 | CORS | `server.py:90–110` — `CORSMiddleware`, `expose_headers=["Mcp-Session-Id"]`, `allow_origins` aus Settings (keine Wildcard) |
| SEC-004 | SSRF | `api_client.py:74–104` — HTTPS-Zwang + IP-Blocklist (inkl. `169.254.169.254`) |
| SEC-016 | Host-Binding | `settings.py:30` Default `127.0.0.1`; `0.0.0.0` nur im Dockerfile; README-Tabelle deckungsgleich |
| SEC-021 | Egress-Allow-List | `api_client.py:54–56` `ALLOWED_HOSTS` (`frozenset`), Pre-Request-Check pro Request |
| OBS-001 | `isError` | Tool-/Client-Fehler werden als `ValueError` geworfen → FastMCP setzt `isError` (Tests in `test_tools.py`) |
| OBS-003 | Strukturiertes Logging | `logging_config.py` — `structlog`, JSON nach stderr; Per-Call-Logs via `ctx.info` |
| CH-004 | OGD-Attribution | `EnergyResponse.source`/`license`/`provenance` in jeder Antwort (`models.py`, `_common.py`) |
| ARCH-008 | Alle Primitive | `resources.py` — Resource `energy://layers` + Prompt `energy_site_assessment` |
| ARCH-011 | Tool-Struktur | `tools/`-Package: `installations.py` / `places.py` / `catalog.py` |
| ARCH-012 | Protokoll-Pinning | `server.py:23` `LATEST_PROTOCOL_VERSION` aus SDK, README-Sektion «MCP Protocol Version», Dependabot |
| OPS-001 | Test-Strategie | `respx`-gemockte Tool-Tests; `test_unit`/`test_tools`/`test_live`; Nightly-Live-Workflow |

**Runtime-Verifikation dieses Audits:** `pytest -m "not live"` → **90 passed, 10 deselected**; `ruff check` → *All checks passed*; `ruff format --check` → *18 files already formatted*; Import-Smoke-Test grün.

---

## 5. Bewertung der Änderungen seit `0.2.0`

Die seit dem Re-Audit gemergten Änderungen wurden gezielt gegen die betroffenen Checks geprüft:

### 5.1 Redirect-Revalidierung (`0.2.1`, SEC-021 / SEC-004) — ✅ pass

**Observed:** `0.2.0` hatte Redirects vollständig deaktiviert (`follow_redirects=False`), was legitime 3xx-Antworten (z. B. von opendata.swiss) brechen konnte. `0.2.1` folgt Redirects nun manuell (`api_client.py:208–222`): jeder Hop wird vor dem Senden erneut durch `assert_url_allowed()` geprüft, mit Hard-Limit `_MAX_REDIRECTS = 5`.
**Bewertung:** Die SEC-021-Garantie (kein Bounce auf einen nicht allow-gelisteten Host) bleibt vollständig erhalten, während die Funktionsfähigkeit gegenüber redirectenden Upstreams wiederhergestellt ist. Saubere Verbesserung, kein Regress.

### 5.2 `sr=2056` auf dem identify-Endpoint (Korrektheit) — ✅ pass

**Observed:** `query_geoadmin_layer` sendet jetzt explizit `sr=2056` (`api_client.py:286`). Der identify-Endpoint defaultet sonst auf LV03 (21781), unter dem die hier erzeugten LV95-Koordinaten aus dem Raster fallen und **jede** Layer-Abfrage still null Treffer liefert.
**Bewertung:** Behebt einen latenten Korrektheits-Bug ohne Sicherheits-/Architektur-Implikation. Stärkt indirekt ARCH-003 (echte vs. leere Treffer sind nun verlässlich unterscheidbar).

### 5.3 Live-Test-Härtung (OPS-001) — ✅ pass

**Observed:** Mehrere Folge-Commits stabilisieren die Live-Tests gegen Upstream-Schwankungen (opendata.swiss, Hydro-Layer). Die CI-Trennung (PR-CI ohne `live`, Nightly-`schedule` mit `live`) bleibt intakt.
**Bewertung:** Keine Auswirkung auf die gemockte PR-CI; verbessert die Aussagekraft des Nightly-Laufs.

---

## 6. Verbleibende Findings (2, low, akzeptiertes Restrisiko)

### 6.1 SEC-005 — DNS-Pinning (low, partial)

**Observed:** `assert_url_allowed()` (`api_client.py:74–104`) löst den Host vor jedem Request auf und prüft alle IPs gegen die Blocklist. Für die TCP-Verbindung führt `httpx` jedoch eine eigene Auflösung durch — die validierte IP wird nicht gepinnt. Das gilt auch für die manuell weiterverfolgten Redirect-Hops.
**Risk:** Theoretisches TOCTOU-Fenster zwischen Validierung und Verbindung. Praktisch vernachlässigbar: nur zwei fixe Behörden-Domains, Allow-List-Prüfung pro Request, automatische Redirects deaktiviert. Ein Angriff erforderte die Kompromittierung der Behörden-DNS-Zone.
**Remediation (optional):** Custom-`httpx`-Transport mit gepinnter Resolved-IP. Als akzeptiertes Restrisiko in `docs/security.md` geführt.
**Effort:** S

### 6.2 SCALE-002 — Stateful Load Balancing (low, partial)

**Observed:** Der Streamable-HTTP-Transport nutzt den In-Memory-Session-Manager von FastMCP. Sticky-Sessions / Shared-State sind nicht implementiert.
**Risk:** Nur bei einem Multi-Replica-Deployment relevant. Die unterstützte Betriebsform ist explizit Single-Instance (stdio bzw. ein HTTP-Container); `docs/security.md` beschreibt das Vorgehen (Sticky-Sessions auf `Mcp-Session-Id` oder Redis-`EventStore`) für eine spätere Skalierung.
**Remediation:** Vor einem etwaigen Multi-Replica-Deployment umsetzen (dann high). Aktuell dokumentierte Design-Entscheidung.
**Effort:** M

---

## 7. Informelle Beobachtungen (keine Check-Verletzung)

Diese Punkte verletzen keinen Katalog-Check und sind **keine** Findings, sondern Hinweise für die nächste reguläre Pflege:

- **Toter Konstanten-Eintrag:** `LAYER_SOLAR_FACADES` (`api_client.py:115`) ist definiert, wird aber nirgends verwendet (nicht im `LAYER_CATALOG`). Entweder entfernen oder einbinden.
- **Irreführende Signatur:** `compute_tolerance(radius_m, image_size=1000)` (`api_client.py:172`) ignoriert beide Parameter und gibt konstant `500` zurück. Funktional korrekt, aber die Parameter suggerieren eine Abhängigkeit, die nicht besteht.
- **Versions-Drift-Risiko:** Der `User-Agent`-String `swiss-energy-mcp/0.2.1` (`api_client.py:200`) dupliziert die Version aus `pyproject.toml`/`__init__.py` und muss beim nächsten Bump manuell nachgezogen werden. Erwägenswert: aus `importlib.metadata.version()` ableiten.

---

## 8. Remediation-Plan

Keine offenen Pflicht-Massnahmen — keine critical/high/medium-Findings.

| Priorität | Punkt | Effort |
|---|---|---|
| Optional | SEC-005 — echtes DNS-Pinning (nur bei Bedarf; geringer Nutzen bei fixen Behörden-Hosts) | S |
| Vor Multi-Replica | SCALE-002 — Sticky-Sessions / Shared Session-Store | M |
| Housekeeping | §7 — toter Konstanten-Eintrag, `compute_tolerance`-Signatur, UA-Versionsableitung | S |

---

## 9. Audit-Metadata

| Feld | Wert |
|---|---|
| Skill-Version | mcp-audit v0.1.0 |
| Check-Katalog | malkreide/mcp-audit-skill (68 Checks, 8 Kategorien) |
| Audit-Methodik | `SKILL.md` (7-Schritt-Prozess: Profile → Catalog → Applicability → Execution → Findings → Report → Release-Proposal) |
| Verifikations-Modi | Static Code Analysis (`grep`/Review), Config-Check (CI/Dockerfile/Dependabot), Test-Lauf (90 gemockte Tests grün, ruff sauber) |
| Nicht ausgeführt | Live-Runtime-Tests (Netzwerk-Policy der Audit-Umgebung blockiert die Behörden-APIs) — abgedeckt durch den Nightly-`live`-Workflow |
| Re-Audit empfohlen nach | Einführung schreibender Tools, PII-Verarbeitung, Multi-Replica-Cloud-Deployment oder Stadt-Zürich-Einbindung; spätestens 6 Monate |

---

## 10. Sign-Off

- [x] Auditor: alle 36 anwendbaren Checks erneut ausgeführt
- [x] Auditor: 34 pass, 2 partial (low, akzeptiertes Restrisiko), 0 fail
- [x] Production-Readiness bestätigt — `0.2.1` release-fähig
- [ ] Server-Maintainer: Audit-Ergebnis bestätigt

---

*Ende des Audit-Reports — generiert mit dem mcp-audit-skill am 2026-06-03.*
