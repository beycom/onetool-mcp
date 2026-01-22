"""LogSpan context manager for auto-logging operations.

Wraps LogEntry and auto-logs on context exit with duration and status.
Supports FastMCP Context for async MCP tool execution.

Example (sync):
    with LogSpan(span="tool.execute", tool="search") as s:
        result = execute_tool()
        s.add("resultCount", len(result))
    # Auto-logs with duration, status=SUCCESS at INFO level

Example (async with FastMCP Context):
    async with LogSpan.async_span(ctx, span="tool.execute", tool="search") as s:
        result = await execute_tool()
        await s.log_info("Tool completed", resultCount=len(result))
    # Logs via FastMCP Context if available, falls back to loguru
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from loguru import logger

from ot.logging.entry import LogEntry
from ot.logging.format import format_log_entry

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from types import TracebackType

# FastMCP Context is Any since it's an optional dependency with dynamic methods
Context = Any  # FastMCP context with log_info, log_error, etc.


def _format_for_output(entry: LogEntry) -> str:
    """Format a LogEntry for log output with truncation and sanitisation.

    Args:
        entry: LogEntry to format

    Returns:
        JSON string with formatted values
    """
    # Import here to avoid circular dependency
    from ot.config import is_log_verbose

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
        **initial_fields: Any,
    ) -> None:
        """Initialize a log span.

        Args:
            level: Default log level for successful completion (default: INFO)
            ctx: Optional FastMCP Context for async logging
            **initial_fields: Initial fields for the underlying LogEntry
        """
        self._level = level.upper()
        self._entry = LogEntry(**initial_fields)
        self._ctx = ctx

    def add(self, key: str | None = None, value: Any = None, **kwargs: Any) -> LogSpan:
        """Add one or more fields to the span.

        Delegates to the underlying LogEntry.

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
        """Set a field using dict-style access.

        Args:
            key: Field name
            value: Field value
        """
        self._entry[key] = value

    def __getitem__(self, key: str) -> Any:
        """Get a field using dict-style access.

        Args:
            key: Field name

        Returns:
            Field value
        """
        return self._entry[key]

    @property
    def entry(self) -> LogEntry:
        """Return the underlying LogEntry for direct access.

        Returns:
            The wrapped LogEntry instance
        """
        return self._entry

    @property
    def duration(self) -> float:
        """Return current duration since span creation.

        Returns:
            Duration in seconds
        """
        return self._entry.duration

    @property
    def context(self) -> Any:
        """Return the FastMCP Context if available.

        Returns:
            FastMCP Context or None
        """
        return self._ctx

    def to_dict(self) -> dict[str, Any]:
        """Return all fields with duration for output.

        Returns:
            Dict with all fields, duration, and status info
        """
        return self._entry.to_dict()

    # -------------------------------------------------------------------------
    # Sync context manager
    # -------------------------------------------------------------------------

    def __enter__(self) -> LogSpan:
        """Enter the span context.

        Returns:
            Self for use in with statement
        """
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit the span context and auto-log.

        On success (no exception), logs at the configured level with status=SUCCESS.
        On exception, logs at ERROR level with status=FAILED and error details.

        Args:
            exc_type: Exception type if an exception was raised
            exc_val: Exception value if an exception was raised
            exc_tb: Exception traceback if an exception was raised
        """
        if exc_val is not None:
            # Exception occurred - log as FAILED at ERROR level
            if isinstance(exc_val, Exception):
                self._entry.failure(error=exc_val)
            else:
                self._entry.failure(
                    error_type=type(exc_val).__name__, error_message=str(exc_val)
                )
            # depth=1 makes loguru report the caller's location, not span.py
            logger.opt(depth=1).error(_format_for_output(self._entry))
        else:
            # Success - log at configured level
            self._entry.success()
            # depth=1 makes loguru report the caller's location, not span.py
            logger.opt(depth=1).log(self._level, _format_for_output(self._entry))

    # -------------------------------------------------------------------------
    # Async logging methods
    # -------------------------------------------------------------------------

    async def log_debug(self, message: str, **kwargs: Any) -> None:
        """Log a debug message.

        Dispatches to FastMCP Context if available, otherwise uses loguru.

        Args:
            message: Log message
            **kwargs: Additional fields to include
        """
        await self._log_async("DEBUG", message, **kwargs)

    async def log_info(self, message: str, **kwargs: Any) -> None:
        """Log an info message.

        Dispatches to FastMCP Context if available, otherwise uses loguru.

        Args:
            message: Log message
            **kwargs: Additional fields to include
        """
        await self._log_async("INFO", message, **kwargs)

    async def log_warning(self, message: str, **kwargs: Any) -> None:
        """Log a warning message.

        Dispatches to FastMCP Context if available, otherwise uses loguru.

        Args:
            message: Log message
            **kwargs: Additional fields to include
        """
        await self._log_async("WARNING", message, **kwargs)

    async def log_error(self, message: str, **kwargs: Any) -> None:
        """Log an error message.

        Dispatches to FastMCP Context if available, otherwise uses loguru.

        Args:
            message: Log message
            **kwargs: Additional fields to include
        """
        await self._log_async("ERROR", message, **kwargs)

    async def _log_async(self, level: str, message: str, **kwargs: Any) -> None:
        """Internal async logging dispatcher.

        Args:
            level: Log level (DEBUG, INFO, WARNING, ERROR)
            message: Log message
            **kwargs: Additional fields
        """
        # Add fields to entry
        for key, value in kwargs.items():
            self._entry.add(key, value)

        # Try to use FastMCP Context if available
        if self._ctx is not None:
            try:
                # FastMCP Context has log_* methods
                log_method = getattr(self._ctx, f"log_{level.lower()}", None)
                if log_method is not None and callable(log_method):
                    await log_method(message)
                    return
            except Exception:
                pass  # Fall through to loguru

        # Fallback to loguru
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

        Use this for async code that needs to log via FastMCP Context.

        Args:
            ctx: Optional FastMCP Context for async logging
            level: Default log level for successful completion
            **initial_fields: Initial fields for the span

        Yields:
            LogSpan instance

        Example:
            async with LogSpan.async_span(ctx, span="tool.run") as span:
                result = await run_tool()
                span.add("result", result)
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
                # Exception occurred
                if isinstance(exc_val, Exception):
                    span._entry.failure(error=exc_val)
                else:
                    span._entry.failure(
                        error_type=type(exc_val).__name__,
                        error_message=str(exc_val),
                    )

                # Log via Context or loguru
                formatted = _format_for_output(span._entry)
                if ctx is not None:
                    try:
                        await ctx.log_error(formatted)
                    except Exception:
                        logger.error(formatted)
                else:
                    logger.error(formatted)
            else:
                # Success
                span._entry.success()

                # Log via Context or loguru
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
