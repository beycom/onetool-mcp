"""Result serialization utilities for MCP responses."""

from __future__ import annotations

import json
import math
from typing import Any, Literal

import yaml

__all__ = ["FormatMode", "serialize_result"]

FormatMode = Literal["json", "json_h", "yml", "yml_h", "raw"]


# D-b1: register a catch-all representer on SafeDumper so ``yaml.safe_dump`` degrades
# any value it cannot otherwise represent (set, Decimal, Path, custom objects) to its
# str() form instead of raising RepresenterError — mirroring the JSON path's
# ``default=str`` degrade. SafeDumper never emits unsafe ``!!python/object`` tags, and
# this catch-all also prevents ``!!set``-style tags. Registered process-wide on the
# shared SafeDumper (safe_dump hardcodes it); it only affects otherwise-unrepresentable
# types, making every safe_dump call strictly more lenient.
def _represent_as_str(dumper: yaml.SafeDumper, data: object) -> yaml.Node:
    return dumper.represent_str(str(data))


yaml.SafeDumper.add_multi_representer(object, _represent_as_str)
# SafeDumper ships an exact `set` representer that emits a `!!set` tag; override it (and
# frozenset) to the same str() degrade so YAML output stays tag-free and consistent with
# the JSON path (D-b1).
yaml.SafeDumper.add_representer(set, _represent_as_str)
yaml.SafeDumper.add_representer(frozenset, _represent_as_str)


def _degrade_non_finite(obj: Any) -> Any:
    """Recursively replace NaN/Infinity floats with informative string sentinels.

    Chosen sentinel: a string marker ("NaN"/"Infinity"/"-Infinity") rather than
    ``null`` — it preserves the fact that the value was non-finite while keeping the
    output valid, ``json.loads``-parseable JSON (D9). Only invoked on the rare
    ``allow_nan=False`` ValueError path, so the common case pays nothing.
    """
    if isinstance(obj, float) and not math.isfinite(obj):
        if math.isnan(obj):
            return "NaN"
        return "Infinity" if obj > 0 else "-Infinity"
    if isinstance(obj, dict):
        return {k: _degrade_non_finite(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_degrade_non_finite(v) for v in obj]
    return obj


def _json_dumps_safe(result: Any, *, indent: int | None, separators: tuple[str, str] | None) -> str:
    """json.dumps that degrades non-JSON-native values instead of raising.

    - ``default=str`` degrades datetime/Decimal/set/bytes/Path/custom objects to a
      string representation instead of raising TypeError (D8), and makes top-level
      and nested values behave identically (D10).
    - ``allow_nan=False`` makes NaN/Infinity raise ValueError (invalid JSON) rather
      than emitting bare ``NaN``/``Infinity`` tokens; on that ValueError the value is
      retried with non-finite floats replaced by string sentinels (D9).
    """
    try:
        return json.dumps(
            result,
            ensure_ascii=False,
            default=str,
            allow_nan=False,
            indent=indent,
            separators=separators,
        )
    except ValueError:
        return json.dumps(
            _degrade_non_finite(result),
            ensure_ascii=False,
            default=str,
            allow_nan=False,
            indent=indent,
            separators=separators,
        )


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

    # D10: serialize top-level scalars/containers through the same degrading path so
    # behavior no longer depends on nesting depth (a top-level set degrades exactly
    # like a nested one, instead of falling through to a mislabeled str()).
    if fmt == "json":
        return _json_dumps_safe(result, indent=None, separators=(",", ":"))

    if fmt == "json_h":
        return _json_dumps_safe(result, indent=2, separators=None)

    if fmt == "yml":
        if isinstance(result, (dict, list)):
            return yaml.safe_dump(
                result, default_flow_style=True, allow_unicode=True, sort_keys=False
            ).rstrip()
        return str(result)

    if fmt == "yml_h":
        if isinstance(result, (dict, list)):
            return yaml.safe_dump(
                result, default_flow_style=False, allow_unicode=True, sort_keys=False
            ).rstrip()
        return str(result)

    # Unknown format, fall back to compact JSON
    return _json_dumps_safe(result, indent=None, separators=(",", ":"))
