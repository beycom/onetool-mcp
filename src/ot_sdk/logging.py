"""Structured logging for worker tools.

Logs are written to stderr in JSON format for collection by ot-serve.
"""

from __future__ import annotations

import json
import sys
import time
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any


class LogSpan:
    """A structured logging span with timing and attributes."""

    def __init__(self, name: str, **attrs: Any) -> None:
        """Initialize a log span.

        Args:
            name: Span name (e.g., "brave.search")
            **attrs: Initial attributes to log
        """
        self.name = name
        self.attrs: dict[str, Any] = dict(attrs)
        self.start_time = time.time()
        self.error: str | None = None

    def add(self, **attrs: Any) -> None:
        """Add attributes to the span.

        Args:
            **attrs: Attributes to add (e.g., count=10, cached=True)
        """
        self.attrs.update(attrs)

    def _emit(self) -> None:
        """Emit the log entry to stderr."""
        elapsed_ms = (time.time() - self.start_time) * 1000

        entry = {
            "span": self.name,
            "elapsed_ms": round(elapsed_ms, 2),
            **self.attrs,
        }

        if self.error:
            entry["error"] = self.error

        print(json.dumps(entry), file=sys.stderr, flush=True)


@contextmanager
def log(name: str, **attrs: Any) -> Generator[LogSpan, None, None]:
    """Context manager for structured logging.

    Automatically captures timing and errors.

    Args:
        name: Span name (e.g., "brave.search")
        **attrs: Initial attributes to log

    Yields:
        LogSpan object for adding attributes

    Example:
        >>> with log("brave.search", query="test") as span:
        ...     result = do_search("test")
        ...     span.add(count=len(result), cached=False)
    """
    span = LogSpan(name, **attrs)
    try:
        yield span
    except Exception as e:
        span.error = f"{type(e).__name__}: {e}"
        raise
    finally:
        span._emit()
