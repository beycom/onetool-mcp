"""Shared markdown heading parse and TOC build logic."""

from __future__ import annotations

import re
from typing import Any

# Matches ATX headings: # Heading, ## Heading, etc.
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")


def parse_headings(
    content: str,
    *,
    max_depth: int = 3,
    lines: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Parse markdown headings and compute line ranges for each section.

    Returns a list of dicts with keys: heading, level, start, end.
    Lines are 1-indexed. ``end`` is inclusive and points to the last line
    of the section (the line before the next heading or EOF).

    Args:
        content: Text content to parse (used only if lines is not provided)
        max_depth: Maximum heading depth to include (default: 3)
        lines: Pre-split lines (avoids re-splitting if caller already has them)

    Returns:
        List of section dicts with heading, level, start, end
    """
    _lines = lines if lines is not None else content.split("\n")
    headings: list[dict[str, Any]] = []

    in_fence = False
    for i, line in enumerate(_lines):
        stripped = line.lstrip()
        if stripped.startswith(("```", "~~~")):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = HEADING_RE.match(line)
        if m and len(m.group(1)) <= max_depth:
            headings.append({
                "heading": m.group(2).strip(),
                "level": len(m.group(1)),
                "start": i + 1,  # 1-indexed
                "end": len(_lines),  # adjusted below
            })

    for idx in range(len(headings) - 1):
        headings[idx]["end"] = headings[idx + 1]["start"] - 1

    return headings


def build_toc(sections: list[dict[str, Any]], total_lines: int) -> str:
    """Build a human-readable table of contents from section data.

    Args:
        sections: List of section dicts with heading, start, end
        total_lines: Total line count of the source content

    Returns:
        Formatted TOC string
    """
    if not sections:
        return "No sections found"
    lines = [f"Table of Contents ({len(sections)} sections, {total_lines} lines)\n"]
    for i, sec in enumerate(sections, 1):
        lines.append(f"  {i}. {sec['heading']} (lines {sec['start']}-{sec['end']})")
    return "\n".join(lines)
