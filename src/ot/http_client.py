"""Shared HTTP client utilities.

Provides a unified http_get() function for making HTTP GET requests with:
- Consistent error handling and message format
- Optional headers (for auth tokens)
- Optional timeout (defaults from config)
- Optional LogSpan integration for observability
- Content-type aware response parsing (JSON or text)
- Connection pooling via shared client singleton

Usage:
    from ot.http_client import http_get

    # Basic GET
    success, result = http_get("https://api.example.com/data")

    # With headers and params
    success, result = http_get(
        "https://api.example.com/search",
        params={"q": "test"},
        headers={"Authorization": "Bearer token"},
    )

    # With LogSpan for observability
    success, result = http_get(
        url,
        log_span="api.fetch",
        log_data={"query": query},
    )
"""

from __future__ import annotations

import atexit
import contextlib
import threading
from typing import Any

import httpx

# Global shared HTTP client with connection pooling
_client: httpx.Client | None = None
_client_lock = threading.Lock()


def _get_shared_client() -> httpx.Client:
    """Get or create the shared HTTP client with connection pooling."""
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                _client = httpx.Client(
                    timeout=30.0,
                    limits=httpx.Limits(
                        max_keepalive_connections=20,
                        max_connections=100,
                        keepalive_expiry=30.0,
                    ),
                )
                atexit.register(_shutdown_client)
    return _client


def _shutdown_client() -> None:
    """Close the shared client on exit."""
    global _client
    if _client is not None:
        with contextlib.suppress(Exception):
            _client.close()
        _client = None


def http_get(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float | None = None,
    log_span: str | None = None,
    log_data: dict[str, Any] | None = None,
) -> tuple[bool, dict[str, Any] | str]:
    """Make HTTP GET request with unified error handling.

    Args:
        url: Full URL to request
        params: Optional query parameters
        headers: Optional HTTP headers (e.g., auth tokens)
        timeout: Request timeout in seconds (defaults to 30.0)
        log_span: Optional LogSpan name for observability
        log_data: Optional data to include in LogSpan

    Returns:
        Tuple of (success, result). If success, result is parsed JSON dict
        or response text. If failure, result is error message string.
    """
    from ot.logging import LogSpan as LogSpanClass

    # Default timeout
    if timeout is None:
        timeout = 30.0

    # Optional LogSpan wrapper
    span: LogSpanClass | None = None
    if log_span:
        span = LogSpanClass(span=log_span, **(log_data or {}))
        span.__enter__()

    try:
        client = _get_shared_client()
        response = client.get(url, params=params, headers=headers, timeout=timeout)
        response.raise_for_status()

        # Parse based on content type
        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type:
            result = response.json()
        else:
            result = response.text

        if span:
            span.add("status", response.status_code)

        return True, result

    except httpx.HTTPStatusError as e:
        error_msg = f"HTTP error ({e.response.status_code}): {e.response.text[:200]}"
        if span:
            span.add("error", f"HTTP {e.response.status_code}")
        return False, error_msg

    except httpx.RequestError as e:
        error_msg = f"Request failed: {e}"
        if span:
            span.add("error", str(e))
        return False, error_msg

    except Exception as e:
        error_msg = f"Error: {e}"
        if span:
            span.add("error", str(e))
        return False, error_msg

    finally:
        if span:
            span.__exit__(None, None, None)
