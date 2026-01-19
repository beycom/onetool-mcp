"""JSON formatting utilities for tool output."""

from __future__ import annotations

import json
from typing import Any

__all__ = ["format_result"]


def format_result(data: Any, *, compact: bool = True) -> str:
    """Format data as JSON for tool output.

    Args:
        data: Data to format (dict, list, or primitive)
        compact: If True, output single-line JSON (default).
                 If False, output pretty-printed JSON with indentation.

    Returns:
        JSON string representation of data
    """
    if compact:
        return json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return json.dumps(data, ensure_ascii=False, indent=2)
