"""Inbound Host/Origin validation on the HTTP transport (SEC-005, inbound half).

The SDK leaves DNS-rebinding protection off while ``transport_security`` is
unset. This server never set it, so there was no Host check at all. These tests
pin the new behaviour and fail if the protection is dropped again.
"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from swiss_energy_mcp.server import build_server, build_transport_security
from swiss_energy_mcp.settings import Settings

_INIT = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "test", "version": "1"},
    },
}
_HEADERS = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}


def test_loopback_bind_enables_protection():
    sec = build_transport_security(Settings(host="127.0.0.1", port=8000))
    assert sec is not None
    assert sec.enable_dns_rebinding_protection is True
    assert "127.0.0.1:8000" in sec.allowed_hosts


def test_non_local_bind_without_allowlist_stays_off():
    """0.0.0.0 with no allow-list: the reachable name is unknowable here, so
    guessing would reject every real request. Protection stays off; the caller
    warns."""
    assert build_transport_security(Settings(host="0.0.0.0", port=8000)) is None


def test_non_local_bind_with_allowlist_enables_protection():
    sec = build_transport_security(
        Settings(host="0.0.0.0", port=8000, allowed_hosts="mcp.example.ch,mcp.example.ch:443")
    )
    assert sec is not None
    assert "mcp.example.ch" in sec.allowed_hosts
    assert "127.0.0.1:8000" in sec.allowed_hosts  # health checks keep working


def test_configured_cors_origin_passes_transport_check():
    sec = build_transport_security(
        Settings(host="127.0.0.1", port=8000, cors_origins="https://claude.ai")
    )
    assert "https://claude.ai" in sec.allowed_origins


def test_wildcard_cors_is_not_copied():
    """ "*" is matched literally by the SDK, so copying it would look like a
    wildcard while doing nothing."""
    sec = build_transport_security(Settings(host="127.0.0.1", port=8000, cors_origins="*"))
    assert "*" not in sec.allowed_origins


def _post_with_host(host_header: str):
    settings = Settings(host="127.0.0.1", port=8000)
    server = build_server(settings)
    # mcp 2.x: transport_security is a per-app kwarg, not a setting.
    with TestClient(
        server.streamable_http_app(
            transport_security=build_transport_security(settings)
        )
    ) as client:
        return client.post("/mcp", headers={"Host": host_header, **_HEADERS}, json=_INIT)


def test_allowed_host_is_served():
    assert _post_with_host("127.0.0.1:8000").status_code == 200


def test_foreign_host_is_rejected():
    assert _post_with_host("evil.example.com").status_code == 421


def test_right_host_wrong_port_is_rejected():
    """The load-bearing case: a fallback localhost policy would also reject
    ``evil.example.com``, so only the port-precise case proves the allow-list
    is really installed."""
    assert _post_with_host("127.0.0.1:9999").status_code == 421


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "::1"])
def test_all_loopback_forms_are_local(host):
    assert build_transport_security(Settings(host=host, port=8000)) is not None
