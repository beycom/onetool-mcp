"""Unit tests for MCP logging/setLevel integration helpers."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from ot.logging.mcp_logging import (
    map_mcp_logging_level,
    register_set_logging_level_handler,
)


@pytest.mark.unit
@pytest.mark.serve
@pytest.mark.parametrize(
    ("mcp_level", "python_level"),
    [
        ("debug", "DEBUG"),
        ("info", "INFO"),
        ("notice", "INFO"),
        ("warning", "WARNING"),
        ("error", "ERROR"),
        ("critical", "CRITICAL"),
        ("alert", "CRITICAL"),
        ("emergency", "CRITICAL"),
        ("DEBUG", "DEBUG"),
        ("unknown", "INFO"),
    ],
)
def test_map_mcp_logging_level(mcp_level: str, python_level: str) -> None:
    """Maps MCP logging level values to Python logging levels."""
    assert map_mcp_logging_level(mcp_level) == python_level


@pytest.mark.unit
@pytest.mark.serve
def test_register_set_logging_level_handler_registers_handler() -> None:
    """Registers the callback via FastMCP low-level set_logging_level decorator."""
    mock_mcp = MagicMock()
    mock_decorator = MagicMock()
    mock_mcp._mcp_server.set_logging_level.return_value = mock_decorator

    async def handler(_level: str) -> None:
        return None

    register_set_logging_level_handler(mock_mcp, handler)

    mock_mcp._mcp_server.set_logging_level.assert_called_once_with()
    mock_decorator.assert_called_once_with(handler)


@pytest.mark.unit
@pytest.mark.serve
def test_register_set_logging_level_handler_raises_without_low_level_server() -> None:
    """Raises a clear error when FastMCP internals are unavailable."""
    mock_mcp = MagicMock()
    mock_mcp._mcp_server = None

    async def handler(_level: str) -> None:
        return None

    with pytest.raises(RuntimeError, match="low-level server unavailable"):
        register_set_logging_level_handler(mock_mcp, handler)
