"""HTTP request utilities for OneTool SDK.

Provides standardized HTTP error handling and header construction
for API-based tools.

Example:
    from ot_sdk import safe_request, api_headers

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

from typing import Any, Callable, TypeVar

from ot_sdk.config import get_secret

T = TypeVar("T")


def api_headers(
    secret_name: str,
    *,
    header_name: str = "Authorization",
    prefix: str = "Bearer",
    extra: dict[str, str] | None = None,
) -> dict[str, str]:
    """Build API request headers with authentication.

    Retrieves a secret and constructs the appropriate authorization header.
    Commonly used patterns:
    - Bearer token: prefix="Bearer" (default)
    - API key header: header_name="X-API-Key", prefix=""

    Args:
        secret_name: Name of secret in secrets.yaml (e.g., "MY_API_KEY")
        header_name: Header name for the auth token (default: "Authorization")
        prefix: Prefix before the token value (default: "Bearer")
        extra: Additional headers to include

    Returns:
        Dict of headers ready for HTTP requests

    Raises:
        ValueError: If the secret is not configured

    Example:
        # Bearer token auth
        headers = api_headers("OPENAI_API_KEY")
        # {"Authorization": "Bearer sk-..."}

        # Custom API key header
        headers = api_headers("BRAVE_API_KEY", header_name="X-Subscription-Token", prefix="")
        # {"X-Subscription-Token": "BSA..."}

        # With extra headers
        headers = api_headers("API_KEY", extra={"Accept": "application/json"})
    """
    api_key = get_secret(secret_name)
    if not api_key:
        raise ValueError(f"{secret_name} secret not configured in secrets.yaml")

    headers: dict[str, str] = {}

    # Build auth header
    if prefix:
        headers[header_name] = f"{prefix} {api_key}"
    else:
        headers[header_name] = api_key

    # Add extra headers
    if extra:
        headers.update(extra)

    return headers


def safe_request(
    request_fn: Callable[[], T],
    *,
    parse_json: bool = True,
) -> tuple[bool, T | dict[str, Any] | str]:
    """Execute an HTTP request with standardized error handling.

    Wraps an HTTP request call and handles common error patterns:
    - Connection errors
    - HTTP status errors
    - JSON parsing errors
    - Timeout errors

    Args:
        request_fn: Callable that makes the HTTP request and returns response
        parse_json: If True (default), parse response as JSON

    Returns:
        Tuple of (success: bool, result).
        On success: (True, parsed_json_dict or response)
        On failure: (False, error_message_string)

    Example:
        # With httpx client
        success, result = safe_request(
            lambda: client.get("/api/data", params={"q": "test"})
        )

        if success:
            data = result["data"]
        else:
            return f"Error: {result}"

        # Without JSON parsing
        success, result = safe_request(
            lambda: client.get("/raw/text"),
            parse_json=False,
        )
    """
    try:
        response = request_fn()

        # Check for raise_for_status method (httpx/requests response)
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

    Extracts status code and response text when available.

    Args:
        error: The exception from the HTTP request

    Returns:
        Formatted error message string
    """
    error_type = type(error).__name__

    # Check for response attribute (HTTPStatusError, etc.)
    if hasattr(error, "response"):
        response = error.response
        status = getattr(response, "status_code", "unknown")
        text = getattr(response, "text", "")[:200]
        return f"HTTP error ({status}): {text}" if text else f"HTTP error ({status})"

    # Check for common error types
    error_str = str(error)
    if "timeout" in error_str.lower():
        return f"Request timeout: {error}"
    if "connection" in error_str.lower():
        return f"Connection error: {error}"

    return f"Request failed ({error_type}): {error}"


def check_api_key(secret_name: str) -> str | None:
    """Check if an API key is configured and return error message if not.

    Convenience function for early validation in tools.

    Args:
        secret_name: Name of secret to check

    Returns:
        None if configured, error message string if not

    Example:
        if error := check_api_key("BRAVE_API_KEY"):
            return error
        # Proceed with API calls
    """
    api_key = get_secret(secret_name)
    if not api_key:
        return f"Error: {secret_name} secret not configured"
    return None
