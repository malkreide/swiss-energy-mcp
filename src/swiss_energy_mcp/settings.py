"""Typed configuration for the Swiss Energy MCP server.

All settings are loaded once at startup from environment variables (prefix
``SWISS_ENERGY_``) or an optional ``.env`` file. This keeps configuration out
of global module state and gives a single fail-fast validation point.
"""

from __future__ import annotations

import json
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration, validated at startup."""

    model_config = SettingsConfigDict(
        env_prefix="SWISS_ENERGY_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    transport: Literal["stdio", "http"] = "stdio"
    # Loopback by default — bind 0.0.0.0 only inside a container (see Dockerfile).
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["https://claude.ai"]
    )
    # Inbound Host allow-list for the HTTP transport (SEC-005, inbound half).
    # e.g. SWISS_ENERGY_ALLOWED_HOSTS="mcp.example.ch,mcp.example.ch:443".
    # Only needed for a non-loopback bind: the reachable name is then a service
    # or public DNS name this process cannot derive from the bind address.
    allowed_hosts: Annotated[list[str], NoDecode] = Field(default_factory=list)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    http_timeout: float = Field(default=20.0, gt=0, le=120)

    @field_validator("cors_origins", "allowed_hosts", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        """Accept a comma-separated string as well as a JSON list.

        Both fields carry ``NoDecode``, so this validator — not the settings
        source — owns the parsing. Without it the validator never saw a string
        at all: pydantic-settings JSON-decodes a complex field inside the
        source, before any validator runs, and
        ``SWISS_ENERGY_CORS_ORIGINS=https://claude.ai`` — the value README and
        ``.env.example`` document — died there as a ``SettingsError``. The
        process then refused to start, on either transport.

        ``NoDecode`` switches that decoding off for good, so the JSON form has
        to be handled here too. It is the form that worked before this fix,
        and a deployment may well be carrying it.
        """
        if not isinstance(value, str):
            return value
        text = value.strip()
        if text.startswith("["):
            # Malformed JSON is passed on unchanged: pydantic then rejects it
            # with its own field error instead of a comma-split of the braces.
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return value
        return [item.strip() for item in text.split(",") if item.strip()]
