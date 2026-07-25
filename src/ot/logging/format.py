"""Output formatting for log entries.

Provides truncation and credential sanitisation at OUTPUT time.
Full values are preserved in LogEntry for programmatic access.

Field-based truncation limits:
    | Pattern                                        | Limit |
    |------------------------------------------------|-------|
    | path, filepath, source, dest, directory        | 200   |
    | command                                        | 200   |
    | url                                            | 120   |
    | query, topic                                   | 100   |
    | pattern, prompt                                | 100   |
    | error                                          | 300   |
    | default                                        | 120   |

Credential sanitisation:
    - URLs with credentials: postgres://user:pass@host -> postgres://***:***@host
    - Applied to fields containing 'url' or values starting with http(s)://
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse, urlunparse

# Field name patterns mapped to truncation limits
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

# URL credential pattern: scheme://user:pass@host
URL_WITH_CREDS = re.compile(r"^([a-zA-Z][a-zA-Z0-9+.-]*://)([^:]+):([^@]+)@(.+)$")
_WHITESPACE_RE = re.compile(r"\s+")


def _get_field_limit(field_name: str) -> int:
    """Get truncation limit for a field based on name patterns.

    Args:
        field_name: Name of the field (case-insensitive matching)

    Returns:
        Truncation limit in characters
    """
    lower_name = field_name.lower()

    # Check for pattern matches in field name
    for pattern, limit in FIELD_LIMITS.items():
        if pattern in lower_name:
            return limit

    return DEFAULT_LIMIT


def sanitize_url(url: str) -> str:
    """Mask credentials in a URL.

    Args:
        url: URL string, potentially with embedded credentials

    Returns:
        URL with username:password masked as ***:***

    Example:
        postgres://user:password@host/db -> postgres://***:***@host/db
    """
    match = URL_WITH_CREDS.match(url)
    if match:
        scheme, _user, _password, rest = match.groups()
        return f"{scheme}***:***@{rest}"

    # Also handle parsed URLs without regex (for edge cases)
    try:
        parsed = urlparse(url)
        if parsed.username or parsed.password:
            # Reconstruct with masked credentials
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
        pass  # Return original if parsing fails

    return url


def format_value(
    value: Any, field_name: str = "", max_length: int | None = None
) -> Any:
    """Format a single value for output with truncation.

    Only string values are truncated. Other types pass through unchanged.

    Args:
        value: Value to format
        field_name: Field name for determining truncation limit
        max_length: Override truncation limit (None = use field-based limit)

    Returns:
        Formatted value (truncated string or original value)
    """
    if not isinstance(value, str):
        return value

    if max_length is None:
        max_length = _get_field_limit(field_name)

    if len(value) <= max_length:
        return value

    # Truncate with ellipsis
    return value[: max_length - 3] + "..."


def single_line_value(value: str) -> str:
    """Collapse embedded whitespace so a formatted log field stays one line."""
    return _WHITESPACE_RE.sub(" ", value).strip()


def sanitize_for_output(value: Any, field_name: str = "") -> Any:
    """Sanitize a value by masking credentials.

    Applies to:
    - Fields containing 'url' in name
    - String values starting with http:// or https://

    Args:
        value: Value to sanitize
        field_name: Field name for context

    Returns:
        Sanitized value
    """
    if not isinstance(value, str):
        return value

    from ot.logging.redact import redact_secrets

    lower_name = field_name.lower()
    lower_value = value.lower()

    # Apply URL sanitisation if field name contains 'url' or value is a URL
    if "url" in lower_name or lower_value.startswith(("http://", "https://")):
        value = sanitize_url(value)

    # Redact secret-shaped literals in ANY field (not just url-named fields).
    return redact_secrets(value)


def format_log_entry(
    entry_dict: dict[str, Any],
    verbose: bool = False,
) -> dict[str, Any]:
    """Format a log entry dict for output.

    Applies truncation and credential sanitisation to all fields.
    Full values are preserved in the original entry.

    Args:
        entry_dict: Log entry as dict (from LogEntry.to_dict())
        verbose: If True, skip truncation (still sanitizes credentials)

    Returns:
        New dict with formatted values
    """
    formatted: dict[str, Any] = {}

    for key, value in entry_dict.items():
        # Always sanitize credentials
        sanitized = sanitize_for_output(value, key)

        # Apply truncation unless verbose mode
        if verbose:
            formatted[key] = sanitized
        else:
            formatted[key] = format_value(sanitized, key)

    return formatted


def format_dev_value(value: Any, field_name: str = "", verbose: bool = False) -> str:
    """Format a value for the dev-friendly log sink.

    Preserves raw values in LogEntry while ensuring emitted values are scalar,
    sanitized, truncated, and single-line.
    """
    if isinstance(value, dict):
        items = [
            f"{single_line_value(str(key))}={format_dev_value(item, str(key), verbose)}"
            for key, item in list(value.items())[:10]
        ]
        if len(value) > 10:
            items.append("...")
        return "{" + ", ".join(items) + "}"

    if isinstance(value, list):
        items = [format_dev_value(item, field_name, verbose) for item in value[:10]]
        if len(value) > 10:
            items.append("...")
        return "[" + ", ".join(items) + "]"

    sanitized = sanitize_for_output(value, field_name)
    if not verbose:
        sanitized = format_value(sanitized, field_name)

    if isinstance(sanitized, str):
        return single_line_value(sanitized)

    return single_line_value(str(sanitized))
