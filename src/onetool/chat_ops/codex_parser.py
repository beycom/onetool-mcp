"""Reference parser for Codex rollout JSONL events.

This file is intentionally simple so users can copy it and adapt to other
providers. Custom parser modules configured via tools.chat_ops.providers.*.parser_file
must expose `parse_line(...)` and return:

- dict: event payload to ingest
- None: line should be skipped as unparsable/unsupported
"""

from __future__ import annotations

import json
from typing import Any


def parse_line(
    line: str,
    source_file: str | None = None,
    line_no: int | None = None,
) -> dict[str, Any] | None:
    """Parse one JSONL line into a canonical payload dict.

    Notes for custom providers:
    - Keep this function tolerant: return None for unknown/bad lines.
    - Normalize provider-specific wrappers here before returning.
    - You can use `source_file` and `line_no` for debugging or conditional logic.
    """
    del source_file, line_no
    try:
        parsed = json.loads(line)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed
