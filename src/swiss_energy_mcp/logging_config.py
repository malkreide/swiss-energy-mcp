"""Structured logging setup.

Logs are emitted as JSON to ``stderr``. stdout is reserved exclusively for the
MCP protocol stream when running on the stdio transport.
"""

from __future__ import annotations

import logging
import sys

import structlog


def configure_logging(level: str = "INFO") -> None:
    """Configure structlog to write JSON log lines to stderr."""
    numeric_level = logging.getLevelNamesMapping().get(level.upper(), logging.INFO)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.WriteLoggerFactory(file=sys.stderr),
        wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = "swiss-energy-mcp") -> structlog.stdlib.BoundLogger:
    """Return a bound structured logger."""
    return structlog.get_logger(name)
