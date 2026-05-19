# Security Notes

## Lethal Trifecta assessment (SEC-019)

The "lethal trifecta" combines three capabilities whose intersection is
dangerous: (1) access to private/sensitive data, (2) exposure to untrusted
content, (3) the ability to exfiltrate data to an external destination.

`swiss-energy-mcp` holds **at most one** of the three:

| Capability | Present? | Notes |
|---|---|---|
| Access to private/sensitive data | No | Only public BFE open data; no PII, no auth |
| Exposure to untrusted content | Partial | Upstream API responses are rendered into summaries |
| Exfiltration channel | No | Only HTTP GET to two fixed, allow-listed hosts; no write/send tools |

**Conclusion:** the trifecta is not present. No Architecture Decision Record or
data-protection sign-off is required. Re-assess if write/send tools are added.

## Egress allow-list (SEC-021 / SEC-004 / SEC-005)

Outbound traffic is restricted at the code layer:

- `ALLOWED_HOSTS` in `api_client.py` is a `frozenset` of the only two hosts the
  server may contact: `api3.geo.admin.ch` and `opendata.swiss`.
- `assert_url_allowed()` runs before **every** request. It rejects non-HTTPS
  targets, hosts outside the allow-list, and hosts that resolve to a private,
  loopback, link-local or otherwise reserved IP (incl. the cloud metadata
  address `169.254.169.254`).
- The HTTP client is configured with `follow_redirects=False`, so an upstream
  response cannot bounce the client onto an unvetted host.

**Updating the allow-list:** edit `ALLOWED_HOSTS` in `api_client.py` and the
table above in the same change; new hosts require a code review.

**Network-layer defence-in-depth:** when deployed in a cluster, additionally
restrict egress with a Kubernetes `NetworkPolicy` or a security group that
permits only HTTPS to the two hosts above plus DNS resolution.

## Error masking (OBS-002)

Tools surface upstream failures by raising `ValueError` with short,
user-facing messages (no stack traces, no internal URLs). FastMCP converts a
raised exception into a tool result with `isError: true` and exposes only the
message text — internals stay in the server log.

## HTTP transport: sessions & scaling (SCALE-002)

The HTTP transport uses FastMCP's Streamable HTTP session manager, which keeps
session state **in memory**. The reference deployment is a single instance
(stdio locally, or one HTTP container).

If the server is ever scaled to multiple replicas behind a load balancer,
sessions must not be split across instances. Use **either**:

- sticky sessions on the edge load balancer keyed on the `Mcp-Session-Id`
  header (HAProxy stick-table, Nginx, or Kubernetes Ingress), **or**
- a shared session store (e.g. Redis) via a FastMCP `EventStore`.

Until such a deployment exists, single-instance operation is the documented
and supported configuration.
