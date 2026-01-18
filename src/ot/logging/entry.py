"""LogEntry class for structured logging.

A simple struct for building log entries with automatic timing.
Supports fluent API, dict-style access, and lazy duration calculation.

Example:
    # Inline - all fields in constructor
    logger.debug(LogEntry(event="command.received", command=command))

    # Fluent - chain adds
    logger.debug(LogEntry(event="tool.lookup")
        .add("function", func_name)
        .add("found", True))

    # Multiple logs show increasing duration (no caching)
    entry = LogEntry(event="multi_step")
    do_step_1()
    logger.debug(entry)  # duration: 0.1s
    do_step_2()
    logger.info(entry)   # duration: 0.3s
"""

from __future__ import annotations

import json
import time
from typing import Any


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

        Can be called with a single key-value pair or with keyword arguments.

        Args:
            key: Field name (optional if using kwargs)
            value: Field value (required if key is provided)
            **kwargs: Bulk field additions

        Returns:
            Self for method chaining

        Example:
            entry.add("function", func_name)
            entry.add(function=func_name, found=True)
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
        """Set a field using dict-style access.

        Args:
            key: Field name
            value: Field value
        """
        self._fields[key] = value

    def __getitem__(self, key: str) -> Any:
        """Get a field using dict-style access.

        Args:
            key: Field name

        Returns:
            Field value

        Raises:
            KeyError: If field doesn't exist
        """
        return self._fields[key]

    def __contains__(self, key: str) -> bool:
        """Check if a field exists.

        Args:
            key: Field name

        Returns:
            True if field exists
        """
        return key in self._fields

    @property
    def fields(self) -> dict[str, Any]:
        """Return a copy of the fields for testing access.

        Returns:
            Copy of internal fields dictionary
        """
        return dict(self._fields)

    @property
    def duration(self) -> float:
        """Return current duration since entry creation.

        Returns:
            Duration in seconds (not cached, calculated fresh each call)
        """
        return round(time.perf_counter() - self._start_time, 3)

    def to_dict(self) -> dict[str, Any]:
        """Return all fields with duration for output.

        Returns:
            Dict with all fields, duration, and status info
        """
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
        """Serialize to JSON with duration.

        Duration is calculated lazily (not cached) so multiple
        calls show increasing duration.

        Returns:
            JSON string with fields and duration
        """
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
        """Return a debug representation.

        Returns:
            String showing LogEntry fields
        """
        return f"LogEntry({self._fields!r})"
