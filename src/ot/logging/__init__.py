"""Structured logging for OneTool MCP server.

Provides JSON-structured logging with:
- LogEntry: Fluent API for building log entries with auto-timing
- LogSpan: Context manager for auto-logging operations
- File-only JSON output
"""

from loguru import logger

# Remove Loguru's default console handler immediately.
# This prevents logs from appearing on console before configure_logging() is called.
logger.remove()

from ot.logging.config import (  # noqa: E402
    configure_logging,
    configure_test_logging,
)
from ot.logging.entry import LogEntry  # noqa: E402
from ot.logging.span import LogSpan  # noqa: E402

__all__ = [
    "LogEntry",
    "LogSpan",
    "configure_logging",
    "configure_test_logging",
]
