"""Parameter validation helpers for OneTool packs.

Helpers return an ``"Error: ..."`` string on failure and ``None`` when valid,
matching the search packs' validation convention.

Example:
    from otpack import validate_choice, validate_int_range

    if error := validate_choice("topic", topic, {"general", "news"}):
        return error
    if error := validate_int_range("max_results", max_results, 1, 20):
        return error
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Collection

__all__ = ["validate_choice", "validate_int_range"]


def validate_choice(
    name: str,
    value: str | None,
    allowed: Collection[str],
    *,
    optional: bool = False,
) -> str | None:
    """Validate that value is one of the allowed choices.

    Args:
        name: Parameter name shown in the error message.
        value: Value to check.
        allowed: Allowed values.
        optional: If True, ``None`` passes validation.

    Returns:
        Error string, or None if valid.
    """
    if optional and value is None:
        return None
    if value in allowed:
        return None
    return f"Error: Invalid {name} '{value}'. Use {sorted(allowed)}"


def validate_int_range(name: str, value: int, lo: int, hi: int) -> str | None:
    """Validate that value is an int within [lo, hi] (bools rejected).

    Returns:
        Error string, or None if valid.
    """
    if not isinstance(value, int) or isinstance(value, bool) or not lo <= value <= hi:
        return f"Error: {name} must be between {lo} and {hi} (got {value})"
    return None
