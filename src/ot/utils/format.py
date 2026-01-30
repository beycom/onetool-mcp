"""Result serialization utilities for MCP responses."""

from __future__ import annotations

import json
from typing import Any, Literal

import yaml

__all__ = ["FormatMode", "serialize_result"]

FormatMode = Literal["json", "json_h", "yml", "yml_h", "raw"]


def serialize_result(result: Any, fmt: FormatMode = "json") -> str:
    """Serialize tool result to string for MCP response.

    Tools return native Python types (dict, list, str). This function
    serializes them to a string suitable for MCP text content.

    Format modes:
    - json: Compact JSON (default, no spaces)
    - json_h: Human-readable JSON (2-space indent)
    - yml: YAML flow style (compact)
    - yml_h: YAML block style (human-readable)
    - raw: str() conversion

    Args:
        result: Tool result (dict, list, str, or other)
        fmt: Output format mode (default: "json")

    Returns:
        String representation suitable for MCP response
    """
    # Strings pass through unchanged for all formats except raw
    if isinstance(result, str) and fmt != "raw":
        return result

    if fmt == "raw":
        return str(result)

    if fmt == "json":
        if isinstance(result, (dict, list)):
            return json.dumps(result, ensure_ascii=False, separators=(",", ":"))
        return str(result)

    if fmt == "json_h":
        if isinstance(result, (dict, list)):
            return json.dumps(result, ensure_ascii=False, indent=2)
        return str(result)

    if fmt == "yml":
        if isinstance(result, (dict, list)):
            return yaml.dump(result, default_flow_style=True, allow_unicode=True, sort_keys=False).rstrip()
        return str(result)

    if fmt == "yml_h":
        if isinstance(result, (dict, list)):
            return yaml.dump(result, default_flow_style=False, allow_unicode=True, sort_keys=False).rstrip()
        return str(result)

    # Unknown format, fall back to compact JSON
    if isinstance(result, (dict, list)):
        return json.dumps(result, ensure_ascii=False, separators=(",", ":"))
    return str(result)
