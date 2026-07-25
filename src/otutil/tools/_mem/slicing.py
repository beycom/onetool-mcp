"""Memory slicing by section, heading, or line range."""

from __future__ import annotations

import builtins
from typing import Any

from otpack import LogSpan
from otutil.tools._content_util import LINE_RANGE_RE as _LINE_RANGE_RE
from otutil.tools._content_util import resolve_line_range as _resolve_line_range
from otutil.tools._content_util import resolve_slice as _resolve_slice
from otutil.tools._content_util import selector_label as _selector_label

from .content import _decode_sections
from .db import _deserialize_meta, _use_connection
from .read import _READ_COLUMNS

_builtins_list = builtins.list


def toc(
    *,
    topic: str,
    id: str | None = None,
) -> str:
    """Display a numbered section index for a memory with table of contents.

    Checks source file staleness when source metadata is available.

    Args:
        topic: Topic of the memory
        id: Optional memory ID (overrides topic)

    Returns:
        Numbered section index with line ranges, or error.

    Example:
        mem.toc(topic="spec")
        mem.toc(id="abc-123")
    """
    from .content import _build_toc, _check_staleness

    with LogSpan(span="mem.toc", topic=topic) as s:
        try:
            with _use_connection() as conn:
                if id:
                    row = conn.execute(
                        f"SELECT {_READ_COLUMNS} FROM memories WHERE id = ?", [id]
                    ).fetchone()
                else:
                    row = conn.execute(
                        f"SELECT {_READ_COLUMNS} FROM memories WHERE topic = ?", [topic]
                    ).fetchone()

                if not row:
                    s.add("found", False)
                    return (
                        f"No memory found for topic '{topic}'"
                        if not id
                        else f"No memory found with id '{id}'"
                    )

                row_meta = _deserialize_meta(row[9])
                sections = _decode_sections(row_meta.get("sections", ""))
                result = _build_toc(sections, row[2].count("\n") + 1)

                # Staleness detection
                status = _check_staleness(row_meta)
                if status == "stale":
                    result += "\n\nWarning: Source file has been modified since this memory was stored. Consider re-writing with mem.write()."
                elif status == "missing":
                    result += "\n\nWarning: Source file no longer exists."

                s.add("sections", len(sections))
                return result

        except Exception as e:
            s.add("error", str(e))
            return f"Error reading toc: {e}"


def slice(
    *,
    topic: str,
    select: int | str | list[int | str],
    id: str | None = None,
) -> str:
    """Extract content by section number, heading path, line range, or mixed list.

    Format detection (polymorphic):
    - int: section number (1-indexed)
    - str matching ``-?\\d*:\\d*``: line range (e.g., ":50", "400:", "151:200", "-50:")
    - str otherwise: heading path lookup (case-insensitive substring match)
    - list: apply the above rules to each element

    Args:
        topic: Topic of the memory
        select: Section selector - int, str, or list of mixed
        id: Optional memory ID (overrides topic)

    Returns:
        Extracted content, or error.

    Example:
        mem.slice(topic="spec", select=1)
        mem.slice(topic="spec", select="Requirements")
        mem.slice(topic="spec", select=":50")
        mem.slice(topic="spec", select=[1, "Requirements", "200:300"])
    """
    with LogSpan(span="mem.slice", topic=topic) as s:
        try:
            with _use_connection() as conn:
                if id:
                    row = conn.execute(
                        f"SELECT {_READ_COLUMNS} FROM memories WHERE id = ?", [id]
                    ).fetchone()
                else:
                    row = conn.execute(
                        f"SELECT {_READ_COLUMNS} FROM memories WHERE topic = ?", [topic]
                    ).fetchone()

                if not row:
                    s.add("found", False)
                    return (
                        f"No memory found for topic '{topic}'"
                        if not id
                        else f"No memory found with id '{id}'"
                    )

                content = row[2]
                lines = content.split("\n")
                row_meta = _deserialize_meta(row[9])
                sections = _decode_sections(row_meta.get("sections", ""))

                selectors = select if isinstance(select, _builtins_list) else [select]

                extracted_parts: list[str] = []
                for sel in selectors:
                    part = _resolve_slice(sel, lines, sections)
                    if part is not None:
                        extracted_parts.append(part)

                if not extracted_parts:
                    return "No matching content found for the given selector(s)"

                s.add("parts", len(extracted_parts))
                return "\n\n".join(extracted_parts)

        except Exception as e:
            s.add("error", str(e))
            return f"Error slicing memory: {e}"


def slice_batch(
    *,
    items: list[dict[str, Any]],
) -> str:
    """Extract sections from multiple memories in a single call.

    Each item specifies a memory (by topic or id) and a selector.
    Uses a batch DB query to minimise round-trips.

    Args:
        items: List of dicts, each with 'topic' or 'id' (str) and 'select'
               (int, str, or list). Max 20 items.

    Returns:
        Concatenated sliced content with topic headers and dividers.

    Example:
        mem.slice_batch(items=[
            {"topic": "docs/creating-tools.md", "select": "Checklist"},
            {"topic": "docs/testing.md", "select": "Required Markers"},
            {"topic": "docs/spec-format.md", "select": "Rules"},
        ])
        mem.slice_batch(items=[
            {"topic": "spec.md", "select": [1, "Requirements"]},
            {"id": "abc-123", "select": ":50"},
        ])
    """
    with LogSpan(span="mem.slice_batch", itemCount=len(items) if items else 0) as s:
        try:
            if not items:
                return "Error: items must be a non-empty list"
            if len(items) > 20:
                return f"Error: Maximum 20 items allowed, got {len(items)}"

            # Validate items and collect lookup keys (deduplicated)
            topic_keys_set: set[str] = set()
            id_keys_set: set[str] = set()
            validated: _builtins_list[
                tuple[dict[str, Any], str | None, str | None]
            ] = []

            for item in items:
                if not isinstance(item, dict):
                    validated.append((item, None, None))
                    continue
                sel = item.get("select")
                topic = item.get("topic")
                mid = item.get("id")
                if sel is None:
                    validated.append((item, None, None))
                    continue
                if not topic and not mid:
                    validated.append((item, None, None))
                    continue
                if topic and mid:
                    validated.append((item, None, None))
                    continue
                if topic:
                    topic_keys_set.add(topic)
                    validated.append((item, topic, None))
                else:
                    id_keys_set.add(mid)  # type: ignore[arg-type]
                    validated.append((item, None, mid))

            # Batch fetch all needed rows
            row_map: dict[str, Any] = {}  # keyed by topic or id
            topic_keys = sorted(topic_keys_set)
            id_keys = sorted(id_keys_set)

            with _use_connection() as conn:
                if topic_keys or id_keys:
                    conditions = []
                    params: _builtins_list[Any] = []
                    if topic_keys:
                        placeholders = ", ".join("?" for _ in topic_keys)
                        conditions.append(f"topic IN ({placeholders})")
                        params.extend(topic_keys)
                    if id_keys:
                        placeholders = ", ".join("?" for _ in id_keys)
                        conditions.append(f"id IN ({placeholders})")
                        params.extend(id_keys)

                    sql = f"SELECT {_READ_COLUMNS} FROM memories WHERE {' OR '.join(conditions)}"
                    rows = conn.execute(sql, params).fetchall()

                    # Index by topic and id
                    for row in rows:
                        row_map[f"topic:{row[1]}"] = row
                        row_map[f"id:{row[0]}"] = row

                    # Increment access counts
                    if rows:
                        row_ids = [r[0] for r in rows]
                        id_placeholders = ", ".join("?" for _ in row_ids)
                        conn.execute(
                            f"UPDATE memories SET access_count = access_count + 1, last_accessed = datetime('now') WHERE id IN ({id_placeholders})",
                            row_ids,
                        )
                        conn.commit()

            # Process each item
            result_parts: _builtins_list[str] = []
            sliced_count = 0

            for item, topic, mid in validated:
                # Items with topic=None and mid=None failed validation in the first pass
                sel = item.get("select") if isinstance(item, dict) else None

                if sel is None:
                    label = topic or mid or str(item)
                    result_parts.append(
                        f"# {label}\n\nError: 'select' is required for each item"
                    )
                    continue
                if not topic and not mid:
                    result_parts.append(
                        "# (invalid item)\n\nError: Each item must have 'topic' or 'id'"
                    )
                    continue

                # Look up row
                key = f"topic:{topic}" if topic else f"id:{mid}"
                row = row_map.get(key)
                if not row:
                    label = topic or mid or str(item)
                    result_parts.append(
                        f"# {label} [{_selector_label(sel)}]\n\nError: No memory found for {'topic' if topic else 'id'} '{label}'"
                    )
                    continue

                # Apply selector
                content = row[2]
                lines = content.split("\n")
                row_meta = _deserialize_meta(row[9])
                sections = _decode_sections(row_meta.get("sections", ""))

                selectors = sel if isinstance(sel, _builtins_list) else [sel]
                extracted: _builtins_list[str] = []
                for sel_item in selectors:
                    part = _resolve_slice(sel_item, lines, sections)
                    if part is not None:
                        extracted.append(part)

                display_topic = row[1]  # use actual topic from DB
                sel_label = _selector_label(sel)
                if extracted:
                    result_parts.append(
                        f"# {display_topic} [{sel_label}]\n\n" + "\n\n".join(extracted)
                    )
                    sliced_count += 1
                else:
                    result_parts.append(
                        f"# {display_topic} [{sel_label}]\n\nNo matching content found for selector(s)"
                    )

            s.add("sliced", sliced_count)
            s.add("total", len(items))
            noun = "memory" if sliced_count == 1 else "memories"
            return f"Sliced {sliced_count} {noun}\n\n---\n\n" + "\n\n---\n\n".join(
                result_parts
            )

        except Exception as e:
            s.add("error", str(e))
            return f"Error in slice_batch: {e}"


__all__ = [
    "_LINE_RANGE_RE",
    "_resolve_line_range",
    "_resolve_slice",
    "_selector_label",
    "slice",
    "slice_batch",
    "toc",
]
