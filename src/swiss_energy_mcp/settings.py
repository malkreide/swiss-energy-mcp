"""Typed configuration for the Swiss Energy MCP server.

All settings are loaded once at startup from environment variables (prefix
``SWISS_ENERGY_``) or an optional ``.env`` file. This keeps configuration out
of global module state and gives a single fail-fast validation point.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    cors_origins: list[str] = Field(default_factory=lambda: ["https://claude.ai"])
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    http_timeout: float = Field(default=20.0, gt=0, le=120)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        """Allow a comma-separated string in addition to a JSON list."""
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value
