# Security Policy & Posture

[🇩🇪 Deutsche Version](SECURITY.de.md)

`swiss-energy-mcp` was hardened against the internal MCP best-practice audit
catalogue. This document summarises the security posture and records the
**accepted-risk** decisions for controls that are deliberately handled at the
portfolio/gateway layer rather than inside this single server.

The full technical security model lives in [`docs/security.md`](docs/security.md)
(egress allow-list, DNS pinning, SSRF protection, lethal-trifecta assessment);
the audit reports are under [`audits/`](audits/).

## Reporting a vulnerability

Please open a private security advisory on the GitHub repository, or contact the
maintainer listed in `README.md`. Do not file public issues for exploitable
vulnerabilities.

## Posture summary

This is a **read-only**, **no-PII**, **public-open-data** MCP server. All 10
tools only issue HTTP GET requests to a fixed set of two Swiss open-data hosts
(`api3.geo.admin.ch` and `opendata.swiss`). Hardening already in place:

| Area | Control |
|---|---|
| Egress | HTTPS-enforced allow-list to the two configured open-data hosts only (SEC-004/021) |
| SSRF | Resolved-IP guard rejecting hosts that resolve to private/internal IPs, incl. redirects (SEC-005) |
| DNS pinning | Validated IP is the IP connected to — closes the TOCTOU gap between allow-list check and TCP connect (SEC-005) |
| Binding | Network transport defaults to `127.0.0.1` (`0.0.0.0` only in containers) (SEC-016) |
| Transport | Streamable HTTP with CORS exposing only `Mcp-Session-Id` (SDK-004) |
| Input | Pydantic v2 strict validation for all tool inputs (SEC-018) |
| Secrets | No credentials required; env-vars only, `.gitignore` guards `.env` (ARCH-005/SEC-013) |
| Errors | Upstream bodies logged to stderr, never forwarded to the model (OBS-002) |
| Stdout | Reserved for the JSON-RPC stream; logging pinned to stderr (OBS-004) |
| Container | Runs non-root with a multi-stage build (SEC-007) |
| Tool surface | `energy_` namespacing; tool definitions version-controlled, no dynamic registration (SEC-022/ARCH-002) |

See [`audits/`](audits/) for the full reports and [`CHANGELOG.md`](CHANGELOG.md)
for the hardening history.

## Accepted risks (portfolio-level controls)

The following audit checks are **not** implemented inside this server by design.
They are portfolio-wide concerns best enforced at an MCP gateway / host layer,
and the residual risk here is low because the server is read-only and only
reaches two trusted public-data hosts.

### SEC-014 — Tool allow-listing via an MCP gateway

**Status:** accepted risk (portfolio-level).
A per-tool allow-list belongs to the MCP host/gateway that aggregates multiple
servers, not to an individual server that exposes a fixed, read-only tool set.
If/when a central gateway is introduced for the portfolio, tool allow-listing
should be configured there. Until then, the risk is bounded: every tool is
read-only and constrained by the egress allow-list above.

### SEC-015 — Pre-flight tool-poisoning detection

**Status:** accepted risk (portfolio-level).
Tool-poisoning (malicious tool descriptions / rug-pulls) is a supply-chain and
host-side concern. This server's tool definitions are version-controlled and
shipped from this repository; there is no dynamic/remote tool registration.
Cross-server poisoning detection remains a gateway/host responsibility tracked
at the portfolio level.

## Re-evaluation triggers

These acceptances should be revisited if the server ever:

- gains **write** capability or starts processing **PII**, or
- registers tools **dynamically** / from remote sources, or
- is aggregated behind a shared MCP gateway (then implement SEC-014/015 there).
