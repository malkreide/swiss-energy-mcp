# Roadmap & Development Phases

The server follows a phased architecture: read-only capability first, write
capability only after a dedicated review, multi-agent scenarios last (OPS-003).

## Phase 1 — Read-only (current)

**Status: active.** All ten tools are read-only (`readOnlyHint: true`,
`destructiveHint: false`) and contact only public, auth-free APIs.

- [x] Spatial tools for power plants, wind, hydro, PV, biogas
- [x] Energiestadt lookup, solar roof potential, combined location profile
- [x] opendata.swiss dataset search, API status check
- [x] Egress allow-list, structured logging, lifespan-managed HTTP client
- [x] Tiered test suite (unit + mocked tool tests + live tests)

## Phase 2 — Write capability (not planned)

Introducing any write-capable tool requires, before the transition:

- Completed best-practice audit run (see `audits/`)
- ISDS classification (if operated within a Stadt Zürich context)
- A DSG processing record (if any non-public data is touched)
- Idempotency keys and compensating actions for every write tool (ARCH-010)
- Human-in-the-loop confirmation for destructive operations (HITL-005)

There is currently **no plan** to add write tools — the energy data sources are
read-only catalogues.

## Phase 3 — Multi-agent (not planned)

Would additionally require a semantic layer, identity resolution and sign-off
from management and the data-protection officer.

Phase transitions are recorded in `CHANGELOG.md`.
