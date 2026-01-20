"""Unified JSONL stats writer for run-level and tool-level records.

Records are buffered in memory and flushed to JSONL at configurable intervals.
Data loss is tolerable - stats are nice-to-have, not critical.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal

from loguru import logger

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

RecordType = Literal["run", "tool"]


def _create_run_record(
    client: str,
    chars_in: int,
    chars_out: int,
    duration_ms: int,
    success: bool,
    error_type: str | None = None,
) -> dict[str, Any]:
    """Create a run-level stats record.

    Args:
        client: MCP client name (e.g., "Claude Desktop")
        chars_in: Input character count
        chars_out: Output character count
        duration_ms: Execution time in milliseconds
        success: Whether the run succeeded
        error_type: Exception class name if failed

    Returns:
        Record dict ready for JSONL serialization
    """
    record: dict[str, Any] = {
        "ts": datetime.now(UTC).isoformat(),
        "type": "run",
        "client": client,
        "chars_in": chars_in,
        "chars_out": chars_out,
        "duration_ms": duration_ms,
        "success": success,
    }
    if error_type:
        record["error_type"] = error_type
    return record


def _create_tool_record(
    client: str,
    tool: str,
    duration_ms: int,
    success: bool,
    error_type: str | None = None,
) -> dict[str, Any]:
    """Create a tool-level stats record.

    Args:
        client: MCP client name (e.g., "Claude Desktop")
        tool: Fully qualified tool name (e.g., "brave.search")
        duration_ms: Execution time in milliseconds
        success: Whether the tool call succeeded
        error_type: Exception class name if failed

    Returns:
        Record dict ready for JSONL serialization
    """
    record: dict[str, Any] = {
        "ts": datetime.now(UTC).isoformat(),
        "type": "tool",
        "client": client,
        "tool": tool,
        "duration_ms": duration_ms,
        "success": success,
    }
    if error_type:
        record["error_type"] = error_type
    return record


class JsonlStatsWriter:
    """Unified async batched JSONL writer for statistics.

    Handles both run-level and tool-level records in a single file,
    discriminated by the 'type' field.

    Usage:
        writer = JsonlStatsWriter(path, flush_interval=30)
        await writer.start()

        # Record run stats
        writer.record_run(client="Claude", chars_in=500, ...)

        # Record tool stats
        writer.record_tool(client="Claude", tool="brave.search", ...)

        # On shutdown
        await writer.stop()
    """

    def __init__(self, path: Path, flush_interval: int = 30) -> None:
        """Initialize writer.

        Args:
            path: Path to JSONL file
            flush_interval: Seconds between flushes
        """
        self._path = path
        self._flush_interval = flush_interval
        self._buffer: list[dict[str, Any]] = []
        self._lock = asyncio.Lock()
        self._task: asyncio.Task[None] | None = None
        self._running = False

    @property
    def path(self) -> Path:
        """Get the JSONL file path."""
        return self._path

    def record_run(
        self,
        client: str,
        chars_in: int,
        chars_out: int,
        duration_ms: int,
        success: bool,
        error_type: str | None = None,
    ) -> None:
        """Record a run-level stats event (non-blocking)."""
        record = _create_run_record(
            client=client,
            chars_in=chars_in,
            chars_out=chars_out,
            duration_ms=duration_ms,
            success=success,
            error_type=error_type,
        )
        self._buffer.append(record)

    def record_tool(
        self,
        client: str,
        tool: str,
        duration_ms: int,
        success: bool,
        error_type: str | None = None,
    ) -> None:
        """Record a tool-level stats event (non-blocking)."""
        record = _create_tool_record(
            client=client,
            tool=tool,
            duration_ms=duration_ms,
            success=success,
            error_type=error_type,
        )
        self._buffer.append(record)

    async def start(self) -> None:
        """Start the background flush task."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._flush_loop())
        logger.debug(f"JSONL stats writer started: {self._path}")

    async def stop(self) -> None:
        """Stop the writer and flush remaining records."""
        self._running = False

        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

        # Final flush
        await self._flush()
        logger.debug("JSONL stats writer stopped")

    async def _flush_loop(self) -> None:
        """Background task that flushes buffer periodically."""
        while self._running:
            try:
                await asyncio.sleep(self._flush_interval)
                await self._flush()
            except asyncio.CancelledError:
                break
            except Exception as e:
                # Log but don't crash - stats are not critical
                logger.warning(f"JSONL stats flush error: {e}")

    async def _flush(self) -> None:
        """Flush buffer to JSONL file."""
        async with self._lock:
            if not self._buffer:
                return

            records = self._buffer.copy()
            self._buffer.clear()

        try:
            await self._write_records(records)
            logger.debug(f"Flushed {len(records)} JSONL stats records")
        except Exception as e:
            # Log but don't crash - stats are not critical
            logger.warning(f"Failed to write JSONL stats: {e}")

    async def _write_records(self, records: Sequence[dict[str, Any]]) -> None:
        """Write records to JSONL file."""
        # Ensure parent directory exists
        self._path.parent.mkdir(parents=True, exist_ok=True)

        # Run blocking I/O in thread pool
        await asyncio.to_thread(self._write_jsonl, records)

    def _write_jsonl(self, records: Sequence[dict[str, Any]]) -> None:
        """Sync JSONL write (called from thread pool)."""
        with self._path.open("a") as f:
            for record in records:
                f.write(json.dumps(record, separators=(",", ":")) + "\n")


# Global stats writer instance (set by server on startup)
_stats_writer: JsonlStatsWriter | None = None
_client_name: str = "unknown"


def get_stats_writer() -> JsonlStatsWriter | None:
    """Get the global stats writer instance."""
    return _stats_writer


def set_stats_writer(writer: JsonlStatsWriter | None) -> None:
    """Set the global stats writer instance."""
    global _stats_writer
    _stats_writer = writer


def get_client_name() -> str:
    """Get the current MCP client name."""
    return _client_name


def set_client_name(name: str) -> None:
    """Set the current MCP client name."""
    global _client_name
    _client_name = name


def record_tool_stats(
    tool: str,
    duration_ms: int,
    success: bool,
    error_type: str | None = None,
) -> None:
    """Record tool-level stats if writer is available.

    Convenience function for use from executor dispatch points.
    Uses the global client name set during MCP initialization.
    """
    writer = get_stats_writer()
    if writer is not None:
        writer.record_tool(
            client=get_client_name(),
            tool=tool,
            duration_ms=duration_ms,
            success=success,
            error_type=error_type,
        )
