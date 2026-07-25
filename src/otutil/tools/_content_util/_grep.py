"""Shared grep line-matching logic for OneTool tools."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import re


def grep_lines(
    content: str,
    regex: re.Pattern[str],
    context: int = 2,
    max_groups: int | None = None,
) -> list[list[tuple[int, str, bool]]]:
    """Find regex matches in content and return grouped context windows.

    Args:
        content: Text content to search
        regex: Compiled regex pattern
        context: Number of context lines before/after each match
        max_groups: Maximum number of match groups to return. None means no
            group cap.

    Returns:
        List of groups; each group is a list of (lineno_1based, line, is_match) tuples.
        Overlapping context windows are merged into a single group.
    """
    lines = content.split("\n")
    match_line_idxs: list[int] = []

    for i, line in enumerate(lines):
        if regex.search(line):
            match_line_idxs.append(i)

    if not match_line_idxs:
        return []

    # Build context ranges, merging overlapping windows
    ranges: list[tuple[int, int]] = []
    for m in match_line_idxs:
        start = max(0, m - context)
        end = min(len(lines) - 1, m + context)
        if ranges and start <= ranges[-1][1] + 1:
            ranges[-1] = (ranges[-1][0], end)
        else:
            ranges.append((start, end))

    if max_groups is not None and len(ranges) > max_groups:
        ranges = ranges[:max_groups]

    match_set = set(match_line_idxs)

    groups: list[list[tuple[int, str, bool]]] = []
    for r_start, r_end in ranges:
        group = [(i + 1, lines[i], i in match_set) for i in range(r_start, r_end + 1)]
        groups.append(group)

    return groups
