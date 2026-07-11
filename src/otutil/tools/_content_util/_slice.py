"""Shared line-range and section slice logic."""

from __future__ import annotations

import re
from typing import Any

# Line range regex: matches patterns like ":50", "400:", "151:200", "-50:"
# A leading "-" requires digits after it so "-:" is not treated as a range.
LINE_RANGE_RE = re.compile(r"^(-?\d+)?:\d*$")


def resolve_line_range(spec: str, lines: list[str], total: int) -> str | None:
    """Parse and resolve a line range spec like ':50', '400:', '151:200', '-50:'.

    Args:
        spec: Line range string (e.g., ":50", "400:", "151:200", "-50:")
        lines: List of content lines
        total: Total line count (len(lines))

    Returns:
        Extracted content string, or None if the spec is invalid/empty
    """
    parts = spec.split(":")
    start_str, end_str = parts[0], parts[1]

    if start_str == "" and end_str == "":
        return None  # ":" alone is invalid

    if start_str == "":
        start = 1
    else:
        start = int(start_str)
        if start < 0:
            start = max(1, total + start + 1)

    end = total if end_str == "" else int(end_str)

    if start < 1:
        start = 1
    if end > total:
        end = total
    if start > end:
        return None

    return "\n".join(lines[start - 1 : end])


def resolve_slice(
    sel: int | str,
    lines: list[str],
    sections: list[dict[str, Any]],
) -> str | None:
    """Resolve a single slice selector to content.

    Format detection (polymorphic):
    - int: section number (1-indexed)
    - str matching LINE_RANGE_RE: line range (e.g., ":50", "400:", "151:200", "-50:")
    - str otherwise: heading path lookup (case-insensitive substring match)

    Args:
        sel: Selector (int section number, line range string, or heading substring)
        lines: Content split into lines
        sections: Parsed section dicts (each with heading, start, end)

    Returns:
        Extracted content string, or None if selector doesn't match
    """
    total = len(lines)

    if isinstance(sel, int):
        if 1 <= sel <= len(sections):
            sec = sections[sel - 1]
            return "\n".join(lines[sec["start"] - 1 : sec["end"]])
        return None

    if LINE_RANGE_RE.match(sel):
        return resolve_line_range(sel, lines, total)

    sel_lower = sel.lower()
    for sec in sections:
        if sel_lower in sec["heading"].lower():
            return "\n".join(lines[sec["start"] - 1 : sec["end"]])
    return None


def selector_label(select: int | str | list[int | str]) -> str:
    """Build a human-readable label for a slice selector.

    Args:
        select: Single or list of selectors

    Returns:
        Human-readable label string
    """
    if isinstance(select, int):
        return f"Section {select}"
    if isinstance(select, str):
        return select
    parts = []
    for s in select:
        if isinstance(s, int):
            parts.append(f"Section {s}")
        else:
            parts.append(str(s))
    return ", ".join(parts)
