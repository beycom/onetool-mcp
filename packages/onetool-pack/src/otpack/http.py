"""HTTP request utilities for OneTool packs.

Provides standardized HTTP error handling and header construction
for API-based tools.

Example:
    from otpack import safe_request, api_headers

    # Build API headers with authentication
    headers = api_headers("MY_API_KEY", header_name="Authorization", prefix="Bearer")

    # Make a request with standardized error handling
    success, result = safe_request(
        lambda: client.get("/endpoint", headers=headers)
    )
    if success:
        data = result  # Parsed JSON dict
    else:
        error_msg = result  # Error message string
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeVar

import httpx

from otpack.config import get_secret
from otpack.text import truncate

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = [
    "_format_http_error",
    "api_headers",
    "check_api_key",
    "create_json_http_client",
    "require_api_key",
    "safe_request",
]

T = TypeVar("T")


def create_json_http_client(
    base_url: str,
    *,
    timeout: float | Any = 30.0,
    headers: dict[str, str] | None = None,
) -> httpx.Client:
    """Create an httpx.Client for a JSON API with gzip Accept-Encoding defaults."""
    default_headers = {"Accept": "application/json", "Accept-Encoding": "gzip"}
    if headers:
        default_headers.update(headers)
    return httpx.Client(base_url=base_url, timeout=timeout, headers=default_headers)


def _missing_secret_message(secret_name: str) -> str:
    """Missing-secret error naming both the secret AND where/how to set it."""
    return (
        f"{secret_name} secret not configured. Set it in secrets.yaml — e.g. "
        f"ot_secrets.set(key='{secret_name}', value='...'), or via the guided "
        "'onetool init' secrets step."
    )


def api_headers(
    secret_name: str,
    *,
    header_name: str = "Authorization",
    prefix: str = "Bearer",
    extra: dict[str, str] | None = None,
) -> dict[str, str]:
    """Build API request headers with authentication.

    Retrieves a secret and constructs the appropriate authorization header.

    Args:
        secret_name: Name of secret (e.g., "MY_API_KEY")
        header_name: Header name for the auth token (default: "Authorization")
        prefix: Prefix before the token value (default: "Bearer")
        extra: Additional headers to include

    Returns:
        Dict of headers ready for HTTP requests

    Raises:
        ValueError: If the secret is not configured
    """
    api_key = get_secret(secret_name)
    if not api_key:
        raise ValueError(_missing_secret_message(secret_name))

    headers: dict[str, str] = {}

    if prefix:
        headers[header_name] = f"{prefix} {api_key}"
    else:
        headers[header_name] = api_key

    if extra:
        headers.update(extra)

    return headers


def safe_request(
    request_fn: Callable[[], T],
    *,
    parse_json: bool = True,
) -> tuple[bool, T | dict[str, Any] | str]:
    """Execute an HTTP request with standardized error handling.

    Args:
        request_fn: Callable that makes the HTTP request and returns response
        parse_json: If True (default), parse response as JSON

    Returns:
        Tuple of (success: bool, result).
        On success: (True, parsed_json_dict or response)
        On failure: (False, error_message_string)
    """
    try:
        response = request_fn()

        if hasattr(response, "raise_for_status"):
            response.raise_for_status()

        if parse_json and hasattr(response, "json"):
            return True, response.json()

        if hasattr(response, "text"):
            return True, response.text

        return True, response

    except Exception as e:
        return False, _format_http_error(e)


def _format_http_error(error: Exception) -> str:
    """Format an HTTP error into a user-friendly message.

    Args:
        error: The exception from the HTTP request

    Returns:
        Formatted error message string
    """
    error_type = type(error).__name__

    if hasattr(error, "response"):
        response = error.response
        status = getattr(response, "status_code", "unknown")
        text = truncate(getattr(response, "text", ""), 200)
        return f"HTTP error ({status}): {text}" if text else f"HTTP error ({status})"

    error_str = str(error)
    if "timeout" in error_str.lower():
        return f"Request timeout: {error}"
    if "connection" in error_str.lower():
        return f"Connection error: {error}"

    return f"Request failed ({error_type}): {error}"


def require_api_key(secret_name: str) -> tuple[str, str | None]:
    """Return (key, None) on success or ("", error_msg) on missing.

    Args:
        secret_name: Name of secret

    Returns:
        Tuple of (key, None) on success or ("", error_message) on missing
    """
    key = get_secret(secret_name) or ""
    if not key:
        return "", f"Error: {_missing_secret_message(secret_name)}"
    return key, None


def check_api_key(secret_name: str) -> str | None:
    """Check if an API key is configured and return error message if not.

    Args:
        secret_name: Name of secret to check

    Returns:
        None if configured, error message string if not
    """
    api_key = get_secret(secret_name)
    if not api_key:
        return f"Error: {_missing_secret_message(secret_name)}"
    return None
