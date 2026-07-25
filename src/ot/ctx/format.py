"""Format detection, normalisation, and TOC building for the ctx pack."""

from __future__ import annotations

import json
import re
from typing import Any

_HEADING_RE = re.compile(r"^(#{1,4})\s+(.*)")


def detect_format(content: str) -> str:
    """Detect content format: json → markdown → yaml → text.

    Detection order matters: YAML is a superset of many formats so it is
    checked last. A bare YAML scalar (string/number) is treated as text.

    Returns:
        One of "json", "markdown", "yaml", "text".
    """
    # 1. JSON — strict, fails fast
    try:
        json.loads(content)
        return "json"
    except (json.JSONDecodeError, ValueError):
        pass

    # 2. Markdown — any # heading in the first 50 lines
    lines = content.splitlines()
    for line in lines[:50]:
        if _HEADING_RE.match(line):
            return "markdown"

    # 3. YAML — must parse as dict or list (not a bare scalar)
    try:
        import yaml  # pyyaml is a core dep

        result = yaml.safe_load(content)
        if isinstance(result, (dict, list)):
            return "yaml"
    except Exception:
        pass

    return "text"


def normalize_content(content: str, fmt: str) -> str:
    """Normalise content for storage.

    JSON is pretty-printed (indent=2). Other formats are passed through
    unchanged.
    """
    if fmt == "json":
        try:
            parsed = json.loads(content)
            return json.dumps(parsed, indent=2)
        except (json.JSONDecodeError, ValueError):
            pass
    return content


def build_toc(content: str, fmt: str) -> list[dict[str, Any]]:
    """Build a table of contents for stored content.

    Returns:
        markdown: list of {"line": int, "level": int, "title": str}
        json/yaml: list of {"key": str, "type": str} with optional "size": int
        text: []
    """
    if fmt == "markdown":
        toc: list[dict[str, Any]] = []
        for i, line in enumerate(content.splitlines(), start=1):
            m = _HEADING_RE.match(line)
            if m:
                toc.append(
                    {"line": i, "level": len(m.group(1)), "title": m.group(2).strip()}
                )
        return toc

    if fmt in ("json", "yaml"):
        try:
            if fmt == "json":
                data: Any = json.loads(content)
            else:
                import yaml

                data = yaml.safe_load(content)

            if isinstance(data, list):
                return [{"key": "[array]", "type": "list", "size": len(data)}]
            if isinstance(data, dict):
                result: list[dict[str, Any]] = []
                for key, value in data.items():
                    entry: dict[str, Any] = {
                        "key": str(key),
                        "type": type(value).__name__,
                    }
                    if isinstance(value, (dict, list)):
                        entry["size"] = len(value)
                    result.append(entry)
                return result
        except Exception:
            pass
        return []

    # text
    return []


__all__ = ["build_toc", "detect_format", "normalize_content"]
