"""Result serialization utilities for MCP responses."""

from __future__ import annotations

import json
from typing import Any

__all__ = ["serialize_result"]


def serialize_result(result: Any) -> str:
    """Serialize tool result to string for MCP response.

    Tools return native Python types (dict, list, str). This function
    serializes them to a string suitable for MCP text content.

    - Strings pass through unchanged
    - Dicts and lists are serialized to compact JSON
    - Other types use str()

    Args:
        result: Tool result (dict, list, str, or other)

    Returns:
        String representation suitable for MCP response
    """
    if isinstance(result, str):
        return result
    if isinstance(result, (dict, list)):
        return json.dumps(result, ensure_ascii=False, separators=(",", ":"))
    return str(result)
