"""Structured logging for OneTool packs.

Provides LogEntry, LogSpan, and formatting utilities.

LogEntry is a simple struct for building log entries with automatic timing.
LogSpan is a context manager that wraps LogEntry and auto-logs on exit.

Example (sync):
    with LogSpan(span="tool.execute", tool="search") as s:
        result = execute_tool()
        s.add("resultCount", len(result))
    # Auto-logs with duration, status=SUCCESS at INFO level

Example (async with FastMCP Context):
    async with LogSpan.async_span(ctx, span="tool.execute", tool="search") as s:
        result = await execute_tool()
        await s.log_info("Tool completed", resultCount=len(result))
"""

# NOTE: This file shares logic with src/ot/logging/span.py in onetool-mcp-design.
# Any changes to LogSpan must be applied to both files.

from __future__ import annotations

import json
import re
import time
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse, urlunparse

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable
    from types import TracebackType

from loguru import logger

__all__ = ["LogEntry", "LogSpan"]

# FastMCP Context is Any since it's an optional dependency with dynamic methods
Context = Any  # FastMCP context with log_info, log_error, etc.

# ============================================================================
# LogEntry
# ============================================================================


class LogEntry:
    """Structured log entry with automatic timing.

    Timing starts automatically on creation. Duration is calculated
    lazily in __str__ without caching, so multiple logs show increasing
    duration.
    """

    def __init__(self, **initial_fields: Any) -> None:
        """Initialize a log entry with optional initial fields.

        Args:
            **initial_fields: Initial fields for the log entry
        """
        self._start_time = time.perf_counter()
        self._fields: dict[str, Any] = dict(initial_fields)
        self._status: str | None = None
        self._status_code: int | None = None
        self._error_type: str | None = None
        self._error_message: str | None = None

    def add(self, key: str | None = None, value: Any = None, **kwargs: Any) -> LogEntry:
        """Add one or more fields to the entry.

        Args:
            key: Field name (optional if using kwargs)
            value: Field value (required if key is provided)
            **kwargs: Bulk field additions

        Returns:
            Self for method chaining
        """
        if key is not None:
            self._fields[key] = value
        self._fields.update(kwargs)
        return self

    def success(self, status_code: int | None = None) -> LogEntry:
        """Mark the entry as successful.

        Args:
            status_code: Optional HTTP status code

        Returns:
            Self for method chaining
        """
        self._status = "SUCCESS"
        self._status_code = status_code
        return self

    def failure(
        self,
        error: Exception | None = None,
        error_type: str | None = None,
        error_message: str | None = None,
    ) -> LogEntry:
        """Mark the entry as failed.

        Args:
            error: Exception that caused the failure
            error_type: Type name of the error
            error_message: Error message

        Returns:
            Self for method chaining
        """
        self._status = "FAILED"
        if error is not None:
            self._error_type = type(error).__name__
            self._error_message = str(error)
        if error_type is not None:
            self._error_type = error_type
        if error_message is not None:
            self._error_message = error_message
        return self

    def __setitem__(self, key: str, value: Any) -> None:
        """Set a field using dict-style access."""
        self._fields[key] = value

    def __getitem__(self, key: str) -> Any:
        """Get a field using dict-style access."""
        return self._fields[key]

    def __contains__(self, key: str) -> bool:
        """Check if a field exists."""
        return key in self._fields

    @property
    def fields(self) -> dict[str, Any]:
        """Return a copy of the fields."""
        return dict(self._fields)

    @property
    def duration(self) -> float:
        """Return current duration since entry creation."""
        return round(time.perf_counter() - self._start_time, 3)

    def to_dict(self) -> dict[str, Any]:
        """Return all fields with duration for output."""
        output = dict(self._fields)
        output["duration"] = self.duration

        if self._status is not None:
            output["status"] = self._status
        if self._status_code is not None:
            output["statusCode"] = self._status_code
        if self._error_type is not None:
            output["errorType"] = self._error_type
        if self._error_message is not None:
            output["errorMessage"] = self._error_message

        return output

    def __str__(self) -> str:
        """Serialize to JSON with duration."""
        output = dict(self._fields)
        output["duration"] = round(time.perf_counter() - self._start_time, 3)

        if self._status is not None:
            output["status"] = self._status
        if self._status_code is not None:
            output["statusCode"] = self._status_code
        if self._error_type is not None:
            output["errorType"] = self._error_type
        if self._error_message is not None:
            output["errorMessage"] = self._error_message

        return json.dumps(output, separators=(",", ":"), default=str)

    def __repr__(self) -> str:
        """Return a debug representation."""
        return f"LogEntry({self._fields!r})"


# ============================================================================
# Log formatting
# ============================================================================

FIELD_LIMITS: dict[str, int] = {
    "path": 200,
    "filepath": 200,
    "source": 200,
    "dest": 200,
    "directory": 200,
    "command": 200,
    "url": 120,
    "query": 100,
    "topic": 100,
    "pattern": 100,
    "prompt": 100,
    "error": 300,
}
DEFAULT_LIMIT = 120

URL_WITH_CREDS = re.compile(r"^([a-zA-Z][a-zA-Z0-9+.-]*://)([^:]+):([^@]+)@(.+)$")


def _get_field_limit(field_name: str) -> int:
    lower_name = field_name.lower()
    for pattern, limit in FIELD_LIMITS.items():
        if pattern in lower_name:
            return limit
    return DEFAULT_LIMIT


def _sanitize_url(url: str) -> str:
    match = URL_WITH_CREDS.match(url)
    if match:
        scheme, _user, _password, rest = match.groups()
        return f"{scheme}***:***@{rest}"

    try:
        parsed = urlparse(url)
        if parsed.username or parsed.password:
            netloc = "***:***@" if parsed.password else "***@"
            netloc += parsed.hostname or ""
            if parsed.port:
                netloc += f":{parsed.port}"
            return urlunparse(
                (
                    parsed.scheme,
                    netloc,
                    parsed.path,
                    parsed.params,
                    parsed.query,
                    parsed.fragment,
                )
            )
    except Exception:
        pass

    return url


def _format_value(
    value: Any, field_name: str = "", max_length: int | None = None
) -> Any:
    if not isinstance(value, str):
        return value
    if max_length is None:
        max_length = _get_field_limit(field_name)
    if len(value) <= max_length:
        return value
    return value[: max_length - 3] + "..."


def _sanitize_for_output(value: Any, field_name: str = "") -> Any:
    if not isinstance(value, str):
        return value
    lower_name = field_name.lower()
    lower_value = value.lower()
    if "url" in lower_name or lower_value.startswith(("http://", "https://")):
        return _sanitize_url(value)
    return value


def format_log_entry(
    entry_dict: dict[str, Any],
    verbose: bool = False,
) -> dict[str, Any]:
    """Format a log entry dict for output with truncation and sanitization.

    Args:
        entry_dict: Log entry as dict (from LogEntry.to_dict())
        verbose: If True, skip truncation (still sanitizes credentials)

    Returns:
        New dict with formatted values
    """
    formatted: dict[str, Any] = {}
    for key, value in entry_dict.items():
        sanitized = _sanitize_for_output(value, key)
        if verbose:
            formatted[key] = sanitized
        else:
            formatted[key] = _format_value(sanitized, key)
    return formatted


# ============================================================================
# LogSpan
# ============================================================================


def _format_for_output(entry: LogEntry) -> str:
    """Format a LogEntry for log output with truncation and sanitisation."""
    from otpack.config import is_log_verbose

    formatted = format_log_entry(entry.to_dict(), verbose=is_log_verbose())
    return json.dumps(formatted, separators=(",", ":"), default=str)


class LogSpan:
    """Context manager that wraps LogEntry and auto-logs on exit.

    On successful exit, logs at INFO level with status=SUCCESS.
    On exception, logs at ERROR level with status=FAILED, errorType, errorMessage.

    Supports optional FastMCP Context for async logging in MCP tool execution.
    """

    def __init__(
        self,
        level: str = "INFO",
        ctx: Context | None = None,
        log_callback: Callable[[str, str], None] | None = None,
        **initial_fields: Any,
    ) -> None:
        """Initialize a log span.

        Args:
            level: Default log level for successful completion (default: INFO)
            ctx: Optional FastMCP Context for async logging
            log_callback: Optional callback called on span exit with (level, message).
            **initial_fields: Initial fields for the underlying LogEntry
        """
        self._level = level.upper()
        self._entry = LogEntry(**initial_fields)
        self._ctx = ctx
        self._log_callback = log_callback

    def add(self, key: str | None = None, value: Any = None, **kwargs: Any) -> LogSpan:
        """Add one or more fields to the span.

        Args:
            key: Field name (optional if using kwargs)
            value: Field value (required if key is provided)
            **kwargs: Bulk field additions

        Returns:
            Self for method chaining
        """
        self._entry.add(key, value, **kwargs)
        return self

    def __setitem__(self, key: str, value: Any) -> None:
        """Set a field using dict-style access."""
        self._entry[key] = value

    def __getitem__(self, key: str) -> Any:
        """Get a field using dict-style access."""
        return self._entry[key]

    @property
    def entry(self) -> LogEntry:
        """Return the underlying LogEntry."""
        return self._entry

    @property
    def duration(self) -> float:
        """Return current duration since span creation."""
        return self._entry.duration

    @property
    def context(self) -> Any:
        """Return the FastMCP Context if available."""
        return self._ctx

    def to_dict(self) -> dict[str, Any]:
        """Return all fields with duration for output."""
        return self._entry.to_dict()

    # -------------------------------------------------------------------------
    # Sync context manager
    # -------------------------------------------------------------------------

    def __enter__(self) -> LogSpan:
        """Enter the span context."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit the span context and auto-log."""
        if exc_val is not None:
            if isinstance(exc_val, Exception):
                self._entry.failure(error=exc_val)
            else:
                self._entry.failure(
                    error_type=type(exc_val).__name__, error_message=str(exc_val)
                )
            formatted = _format_for_output(self._entry)
            logger.opt(depth=1).error(formatted)
            if self._log_callback is not None:
                self._log_callback("ERROR", formatted)
        else:
            self._entry.success()
            formatted = _format_for_output(self._entry)
            logger.opt(depth=1).log(self._level, formatted)
            if self._log_callback is not None:
                self._log_callback(self._level, formatted)

    # -------------------------------------------------------------------------
    # Async logging methods
    # -------------------------------------------------------------------------

    async def log_debug(self, message: str, **kwargs: Any) -> None:
        """Log a debug message."""
        await self._log_async("DEBUG", message, **kwargs)

    async def log_info(self, message: str, **kwargs: Any) -> None:
        """Log an info message."""
        await self._log_async("INFO", message, **kwargs)

    async def log_warning(self, message: str, **kwargs: Any) -> None:
        """Log a warning message."""
        await self._log_async("WARNING", message, **kwargs)

    async def log_error(self, message: str, **kwargs: Any) -> None:
        """Log an error message."""
        await self._log_async("ERROR", message, **kwargs)

    async def _log_async(self, level: str, message: str, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            self._entry.add(key, value)

        if self._ctx is not None:
            try:
                log_method = getattr(self._ctx, f"log_{level.lower()}", None)
                if log_method is not None and callable(log_method):
                    await log_method(message)
                    return
            except Exception:
                pass

        log_message = f"{message} - {self._entry}"
        logger.opt(depth=2).log(level.upper(), log_message)

    # -------------------------------------------------------------------------
    # Async context manager
    # -------------------------------------------------------------------------

    @classmethod
    @asynccontextmanager
    async def async_span(
        cls,
        ctx: Context | None = None,
        level: str = "INFO",
        **initial_fields: Any,
    ) -> AsyncIterator[LogSpan]:
        """Create an async context manager span.

        Args:
            ctx: Optional FastMCP Context for async logging
            level: Default log level for successful completion
            **initial_fields: Initial fields for the span

        Yields:
            LogSpan instance
        """
        span = cls(level=level, ctx=ctx, **initial_fields)
        exc_info: tuple[type[BaseException] | None, BaseException | None, Any] = (
            None,
            None,
            None,
        )

        try:
            yield span
        except BaseException as e:
            exc_info = (type(e), e, e.__traceback__)
            raise
        finally:
            _exc_type, exc_val, _exc_tb = exc_info

            if exc_val is not None:
                if isinstance(exc_val, Exception):
                    span._entry.failure(error=exc_val)
                else:
                    span._entry.failure(
                        error_type=type(exc_val).__name__,
                        error_message=str(exc_val),
                    )

                formatted = _format_for_output(span._entry)
                if ctx is not None:
                    try:
                        await ctx.log_error(formatted)
                    except Exception:
                        logger.error(formatted)
                else:
                    logger.error(formatted)
            else:
                span._entry.success()

                formatted = _format_for_output(span._entry)
                if ctx is not None:
                    try:
                        log_method = getattr(ctx, f"log_{span._level.lower()}", None)
                        if log_method is not None and callable(log_method):
                            await log_method(formatted)
                        else:
                            await ctx.log_info(formatted)
                    except Exception:
                        logger.log(span._level, formatted)
                else:
                    logger.log(span._level, formatted)
