"""Tool registration for the Swiss Energy MCP server.

Tools are grouped by domain into one module per group (ARCH-011):
``installations`` (power/wind/hydro/PV/biogas), ``places`` (solar, Energiestadt,
profile) and ``catalog`` (dataset search, status).
"""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from . import catalog, installations, places


def register_tools(mcp: MCPServer) -> None:
    """Register every tool group on the server."""
    installations.register(mcp)
    places.register(mcp)
    catalog.register(mcp)
