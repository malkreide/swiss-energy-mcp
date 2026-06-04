# Sicherheitsrichtlinie & Sicherheitslage

[🇬🇧 English Version](SECURITY.md)

`swiss-energy-mcp` wurde gegen den internen MCP-Best-Practice-Audit-Katalog
gehärtet. Dieses Dokument fasst die Sicherheitslage zusammen und dokumentiert
die **akzeptierten Risiken** für Kontrollen, die bewusst auf der
Portfolio-/Gateway-Ebene statt innerhalb dieses einzelnen Servers behandelt
werden.

Das vollständige technische Sicherheitsmodell befindet sich in
[`docs/security.md`](docs/security.md) (Egress-Allow-List, DNS-Pinning,
SSRF-Schutz, Lethal-Trifecta-Bewertung); die Audit-Berichte liegen unter
[`audits/`](audits/).

## Schwachstellen melden

Bitte eröffnen Sie ein privates Security Advisory im GitHub-Repository oder
kontaktieren Sie den in `README.md` genannten Maintainer. Erstellen Sie keine
öffentlichen Issues für ausnutzbare Schwachstellen.

## Zusammenfassung der Sicherheitslage

Dies ist ein **nur lesender**, **PII-freier** MCP-Server für **öffentliche
Open Data**. Alle 10 Tools senden ausschliesslich HTTP-GET-Anfragen an eine
feste Menge von zwei Schweizer Open-Data-Hosts (`api3.geo.admin.ch` und
`opendata.swiss`). Bereits vorhandene Härtung:

| Bereich | Kontrolle |
|---|---|
| Egress | HTTPS-erzwungene Allow-List nur auf die zwei konfigurierten Open-Data-Hosts (SEC-004/021) |
| SSRF | Resolved-IP-Guard, der Hosts mit privaten/internen IPs ablehnt, inkl. Redirects (SEC-005) |
| DNS-Pinning | Validierte IP ist die verbundene IP — schliesst die TOCTOU-Lücke zwischen Allow-List-Prüfung und TCP-Connect (SEC-005) |
| Binding | Netzwerk-Transport bindet standardmässig `127.0.0.1` (`0.0.0.0` nur im Container) (SEC-016) |
| Transport | Streamable HTTP mit CORS, das nur `Mcp-Session-Id` exponiert (SDK-004) |
| Input | Pydantic-v2-Strict-Validierung für alle Tool-Inputs (SEC-018) |
| Secrets | Keine Zugangsdaten nötig; nur Env-Vars, `.gitignore` schützt `.env` (ARCH-005/SEC-013) |
| Fehler | Upstream-Bodies werden nach stderr geloggt, nie an das Modell weitergegeben (OBS-002) |
| Stdout | Reserviert für den JSON-RPC-Stream; Logging fest auf stderr (OBS-004) |
| Container | Läuft als Non-Root mit Multi-Stage-Build (SEC-007) |
| Tool-Oberfläche | `energy_`-Namespacing; Tool-Definitionen versioniert, keine dynamische Registrierung (SEC-022/ARCH-002) |

Die vollständigen Berichte finden Sie unter [`audits/`](audits/) und die
Härtungs-Historie im [`CHANGELOG.md`](CHANGELOG.md).

## Akzeptierte Risiken (Kontrollen auf Portfolio-Ebene)

Die folgenden Audit-Prüfungen sind bewusst **nicht** innerhalb dieses Servers
umgesetzt. Es handelt sich um portfolioweite Belange, die am besten auf einer
MCP-Gateway-/Host-Ebene durchgesetzt werden; das Restrisiko ist hier gering, da
der Server nur lesend ist und nur zwei vertrauenswürdige Open-Data-Hosts
erreicht.

### SEC-014 — Tool-Allow-Listing via MCP-Gateway

**Status:** akzeptiertes Risiko (Portfolio-Ebene).
Eine Allow-List pro Tool gehört zum MCP-Host/-Gateway, das mehrere Server
aggregiert, nicht zu einem einzelnen Server mit fester, nur lesender
Tool-Menge. Sobald ein zentrales Gateway für das Portfolio eingeführt wird,
sollte das Tool-Allow-Listing dort konfiguriert werden. Bis dahin ist das
Risiko begrenzt: Jedes Tool ist nur lesend und durch die obige
Egress-Allow-List eingeschränkt.

### SEC-015 — Pre-Flight-Erkennung von Tool-Poisoning

**Status:** akzeptiertes Risiko (Portfolio-Ebene).
Tool-Poisoning (bösartige Tool-Beschreibungen / Rug-Pulls) ist ein Supply-Chain-
und Host-seitiges Anliegen. Die Tool-Definitionen dieses Servers sind versioniert
und werden aus diesem Repository ausgeliefert; es gibt keine dynamische/entfernte
Tool-Registrierung. Die serverübergreifende Poisoning-Erkennung bleibt eine
Gateway-/Host-Verantwortung auf Portfolio-Ebene.

## Auslöser für eine Neubewertung

Diese Akzeptanzen sollten überprüft werden, sobald der Server:

- **Schreib**-Fähigkeiten erhält oder **PII** verarbeitet, oder
- Tools **dynamisch** / aus entfernten Quellen registriert, oder
- hinter einem gemeinsamen MCP-Gateway aggregiert wird (dann SEC-014/015 dort umsetzen).
