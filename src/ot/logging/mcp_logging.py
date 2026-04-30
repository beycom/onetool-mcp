"""Helpers for MCP logging/setLevel integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from fastmcp import FastMCP

MCP_TO_PYTHON_LOG_LEVEL = {
    "debug": "DEBUG",
    "info": "INFO",
    "notice": "INFO",  # MCP notice -> INFO
    "warning": "WARNING",
    "error": "ERROR",
    "critical": "CRITICAL",
    "alert": "CRITICAL",  # MCP alert -> CRITICAL
    "emergency": "CRITICAL",  # MCP emergency -> CRITICAL
}


def map_mcp_logging_level(level: str) -> str:
    """Map MCP logging levels to Python logging levels."""
    return MCP_TO_PYTHON_LOG_LEVEL.get(str(level).lower(), "INFO")


def register_set_logging_level_handler(
    mcp: FastMCP, handler: Callable[[str], Awaitable[None]]
) -> None:
    """Register a handler for MCP logging/setLevel on the low-level server."""
    low_level_server = getattr(mcp, "_mcp_server", None)
    if low_level_server is None:
        raise RuntimeError(
            "FastMCP low-level server unavailable; cannot register logging/setLevel handler."
        )

    decorator = low_level_server.set_logging_level()
    decorator(handler)
