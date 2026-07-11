"""Section slicing for the ctx pack."""
from __future__ import annotations

import re
from typing import Any

from ot.logging import LogSpan

from .store import HandleStore, _get_store, _resolve_handle, load_live_meta

log = LogSpan

_LINE_RANGE_RE = re.compile(r"^\d+:\d+$")
_SECTION_NUM_RE = re.compile(r"^#(\d+)$")


def ctx_slice(
    handle: str,
    select: str,
    *,
    store: HandleStore | None = None,
) -> dict[str, Any]:
    """Extract content by section number, heading name, or line range.

    Args:
        handle: Context store handle
        select:
            - "N:M": line range (1-indexed inclusive, any format)
            - "#N": Nth section by TOC index (markdown only)
            - "<text>": section by heading substring (markdown only, case-insensitive)
        store: HandleStore instance (uses session default if not provided)
    """
    with log(span="ctx.slice", handle=handle) as s:
        if store is None:
            store = _get_store()

        try:
            handle = _resolve_handle(handle)
        except TypeError as e:
            return {"error": str(e)}

        meta, err = load_live_meta(store, handle)
        if meta is None:
            return {"error": err}

        fmt = meta.get("format", "text")

        # Accept int for section numbers: 2 → "#2"
        if isinstance(select, int):
            select = f"#{select}"

        # Line range: "N:M" — works for any format
        if _LINE_RANGE_RE.match(select):
            try:
                content = store.read_content(handle)
            except OSError:
                return {"error": f"Content not found for handle: {handle}"}

            lines = content.splitlines()
            parts = select.split(":")
            start = max(1, int(parts[0]))
            end = min(len(lines), int(parts[1]))
            if start > end:
                return {"error": f"Invalid line range: {select}"}
            s.add("lines", end - start + 1)
            return {
                "handle": handle,
                "select": select,
                "content": "\n".join(lines[start - 1: end]),
                "start_line": start,
                "end_line": end,
            }

        # Guard: json/yaml with path-like select → redirect to ctx.query()
        if fmt in ("json", "yaml") and ("." in select or "[" in select):
            return {
                "error": (
                    f"Handle format is {fmt!r}. "
                    f"Use ctx.query('{handle}', expr='{select}') for structured data queries."
                )
            }

        # Section selectors require markdown
        if fmt != "markdown":
            return {
                "error": (
                    f"Section selection by name or number requires markdown format "
                    f"(handle format is {fmt!r}). Use ctx.slice('{handle}', select='N:M') "
                    f"for a line range."
                )
            }

        toc: list[dict[str, Any]] = meta.get("toc", [])

        try:
            content = store.read_content(handle)
        except OSError:
            return {"error": f"Content not found for handle: {handle}"}

        lines = content.splitlines()
        total_lines = len(lines)

        # Section by number: "#N"
        m = _SECTION_NUM_RE.match(select)
        if m:
            n = int(m.group(1))
            idx = n - 1  # 0-indexed
            if idx < 0 or idx >= len(toc):
                return {"error": f"Section {n} not found (handle has {len(toc)} sections)"}
            entry = toc[idx]
            start = entry["line"]
            end = _section_end_line(toc, idx, total_lines)
            s.add("lines", end - start + 1)
            return {
                "handle": handle,
                "section": n,
                "title": entry["title"],
                "content": "\n".join(lines[start - 1: end]),
                "start_line": start,
                "end_line": end,
            }

        # Section by heading substring (case-insensitive)
        select_lower = select.lower()
        for i, entry in enumerate(toc):
            if select_lower in entry["title"].lower():
                start = entry["line"]
                end = _section_end_line(toc, i, total_lines)
                s.add("lines", end - start + 1)
                return {
                    "handle": handle,
                    "section": i + 1,
                    "title": entry["title"],
                    "content": "\n".join(lines[start - 1: end]),
                    "start_line": start,
                    "end_line": end,
                }

        return {"error": f"Section not found matching: {select!r}"}


def _section_end_line(toc: list[dict[str, Any]], idx: int, total_lines: int) -> int:
    """Return the last line number (1-indexed inclusive) for section at toc[idx].

    The section ends just before the next heading at the same or higher level
    (lower level number = higher in hierarchy), or at EOF.
    """
    entry = toc[idx]
    level = entry["level"]
    for next_entry in toc[idx + 1:]:
        if next_entry["level"] <= level:
            return int(next_entry["line"]) - 1
    return total_lines


__all__ = ["ctx_slice"]
