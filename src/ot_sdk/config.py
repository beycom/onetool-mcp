"""Configuration and secrets access for worker tools.

Config and secrets are passed to workers via the JSON-RPC request, not read
directly from files. This ensures workers don't need filesystem access to
the main ot-serve configuration.
"""

from __future__ import annotations

from typing import Any

# Current config and secrets, updated by worker_main on each request
_current_config: dict[str, Any] = {}
_current_secrets: dict[str, str] = {}


def get_secret(name: str) -> str | None:
    """Get a secret value by name.

    Secrets are loaded from secrets.yaml by ot-serve and passed to workers.
    They are NOT available as environment variables for security.

    Args:
        name: Secret name (e.g., "BRAVE_API_KEY")

    Returns:
        Secret value, or None if not found
    """
    return _current_secrets.get(name)


def get_config(path: str) -> Any:
    """Get a configuration value by dotted path.

    Config is loaded from ot-serve.yaml and passed to workers.

    Args:
        path: Dotted path to config value (e.g., "tools.brave.timeout")

    Returns:
        Config value, or None if path not found

    Example:
        >>> get_config("tools.brave.timeout")
        60.0
        >>> get_config("tools.db.max_chars")
        4000
    """
    parts = path.split(".")
    value: Any = _current_config

    for part in parts:
        if isinstance(value, dict):
            value = value.get(part)
        else:
            return None
        if value is None:
            return None

    return value
