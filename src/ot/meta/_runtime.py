"""Runtime metadata tools for the core ot pack."""

from __future__ import annotations

from typing import Any

from ot.runtime_meta import get_runtime_meta, set_runtime_meta


def set_meta(*, name: str | None = None, description: str | None = None) -> dict[str, Any]:
    """Set a human-readable name or description for the current MCP runtime.

    Args:
        name: Optional runtime display name. Use an empty string to clear it.
        description: Optional runtime description. Use an empty string to clear it.

    Returns:
        Current runtime metadata after the update.
    """
    return set_runtime_meta(name=name, description=description)


def meta() -> dict[str, Any]:
    """Return identity, paths, Direct API details, and mutable runtime metadata."""
    return get_runtime_meta()

