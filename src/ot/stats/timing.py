"""Timing context manager for tool call statistics.

Provides a reusable context manager that handles timing, success/error
tracking, and stats recording for tool calls.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import TYPE_CHECKING

from ot.stats.jsonl_writer import get_client_name, record_tool_stats

if TYPE_CHECKING:
    from collections.abc import Iterator


@contextmanager
def timed_tool_call(tool_name: str, client: str | None = None) -> Iterator[None]:
    """Context manager for timing tool calls and recording stats.

    Measures execution time, tracks success/failure, and records stats
    to the global stats writer.

    Args:
        tool_name: Fully qualified tool name (e.g., "brave.search")
        client: MCP client name. If None, uses global client name.

    Yields:
        None

    Example:
        with timed_tool_call("brave.search"):
            result = brave.search(query="test")
    """
    if client is None:
        client = get_client_name()

    start_time = time.monotonic()
    error_type: str | None = None
    success = True

    try:
        yield
    except Exception as e:
        success = False
        error_type = type(e).__name__
        raise
    finally:
        duration_ms = int((time.monotonic() - start_time) * 1000)
        record_tool_stats(
            tool=tool_name,
            duration_ms=duration_ms,
            success=success,
            error_type=error_type,
        )
