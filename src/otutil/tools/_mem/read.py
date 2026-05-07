"""Memory read functions."""
from __future__ import annotations

import builtins
from typing import Any

from otpack import LogSpan

from .content import _tags_filter_sql, _topic_filter
from .db import _deserialize_tags, _use_connection

_builtins_list = builtins.list

_READ_COLUMNS = "id, topic, content, category, tags, relevance, access_count, created_at, updated_at, meta"

_MODE_HINTS = {
    "toc": "Use mem.toc(topic=...) instead.",
    "meta": "Use mem.inspect(topic=...) instead.",
}


def _check_mode_removed(func: str, mode: str | None, all_hint: str) -> None:
    if mode is None:
        return
    hint = _MODE_HINTS.get(mode) or (all_hint if mode == "all" else "The mode parameter has been removed.")
    raise ValueError(f"{func}() no longer accepts mode='{mode}'. {hint}")


def read(
    *,
    topic: str,
    id: str | None = None,
    meta: bool = False,
    mode: str | None = None,
) -> str:
    """Read a memory by exact topic match or ID.

    Increments the access count on each read.

    Args:
        topic: Exact topic path to read
        id: Optional memory ID for direct lookup (overrides topic match)
        meta: If True, include metadata header (topic, category, tags, etc.)

    Returns:
        Memory content (with metadata header if meta=True), or error if not found.

    Example:
        mem.read(topic="projects/onetool/rules")
        mem.read(topic="projects/onetool/rules", meta=True)
        mem.read(id="abc-123-def")
    """
    _check_mode_removed("mem.read", mode, "Use mem.read(meta=True) instead.")

    with LogSpan(span="mem.read", topic=topic) as s:
        try:
            with _use_connection() as conn:
                if id:
                    row = conn.execute(
                        f"SELECT {_READ_COLUMNS} FROM memories WHERE id = ?",
                        [id],
                    ).fetchone()
                else:
                    topic_sql, topic_params = _topic_filter(topic)
                    row = conn.execute(
                        f"SELECT {_READ_COLUMNS} FROM memories WHERE 1=1{topic_sql} ORDER BY created_at DESC LIMIT 1",
                        topic_params,
                    ).fetchone()

                if not row:
                    s.add("found", False)
                    return f"No memory found for topic '{topic}'" if not id else f"No memory found with id '{id}'"

                # Increment access count
                conn.execute(
                    "UPDATE memories SET access_count = access_count + 1, last_accessed = datetime('now') WHERE id = ?",
                    [row[0]],
                )
                conn.commit()

                # Update row with incremented access_count for accurate display
                row = (*row[:6], row[6] + 1, *row[7:])

            s.add("found", True)
            s.add("memoryId", row[0])

            # row indices: 0=id, 1=topic, 2=content, 3=category, 4=tags,
            #              5=relevance, 6=access_count, 7=created_at, 8=updated_at, 9=meta
            return _format_read_row(row, meta=meta)

        except Exception as e:
            s.add("error", str(e))
            return f"Error reading memory: {e}"


def _format_read_row(row: Any, *, meta: bool) -> str:
    """Format a single memory row.

    Row indices: 0=id, 1=topic, 2=content, 3=category, 4=tags,
                 5=relevance, 6=access_count, 7=created_at, 8=updated_at, 9=meta
    """
    content = row[2]
    if not meta:
        return content

    tags = _deserialize_tags(row[4])
    header = (
        f"Topic: {row[1]}\n"
        f"Category: {row[3]}\n"
        f"Tags: {', '.join(tags) if tags else 'none'}\n"
        f"Relevance: {row[5]}\n"
        f"Accessed: {row[6]} times\n"
        f"Created: {row[7]}\n"
        f"Updated: {row[8]}\n"
        f"ID: {row[0]}"
    )
    return f"{header}\n\n{content}"


def read_batch(
    *,
    topic: str | None = None,
    ids: list[str] | None = None,
    category: str | None = None,
    tags: list[str] | None = None,
    meta: bool = False,
    mode: str | None = None,
    limit: int = 50,
) -> str:
    """Read multiple memories by topic prefix, IDs, category, or tags.

    Returns full content for each matching memory. At least one filter
    (topic, ids, category, or tags) must be provided.

    Args:
        topic: Topic prefix filter (e.g., "projects/" matches all under projects)
        ids: List of specific memory IDs to read
        category: Category filter
        tags: Tag filter (matches memories with any of these tags)
        meta: If True, include metadata header per memory
        limit: Maximum results (default: 50)

    Returns:
        Concatenated memory contents separated by dividers, or error.

    Example:
        mem.read_batch(topic="projects/onetool/agents/")
        mem.read_batch(ids=["abc-123", "def-456"], meta=True)
        mem.read_batch(category="rule", limit=10)
    """
    _check_mode_removed("mem.read_batch", mode, "Use mem.read_batch(meta=True) instead.")

    if not any([topic, ids, category, tags]):
        return "Error: At least one filter (topic, ids, category, or tags) is required"

    if ids and any([topic, category, tags]):
        return "Error: ids cannot be combined with other filters (topic, category, tags)"

    with LogSpan(span="mem.read_batch", topic=topic, limit=limit) as s:
        try:
            with _use_connection() as conn:
                if ids:
                    placeholders = ", ".join("?" for _ in ids)
                    sql = f"SELECT {_READ_COLUMNS} FROM memories WHERE id IN ({placeholders})"
                    params: _builtins_list[Any] = _builtins_list(ids)
                else:
                    sql = f"SELECT {_READ_COLUMNS} FROM memories WHERE 1=1"
                    params = []

                    topic_sql, topic_params = _topic_filter(topic)
                    sql += topic_sql
                    params.extend(topic_params)

                    if category:
                        sql += " AND category = ?"
                        params.append(category)

                    if tags:
                        tags_sql, tags_params = _tags_filter_sql(tags)
                        sql += tags_sql
                        params.extend(tags_params)

                sql += " ORDER BY topic ASC LIMIT ?"
                params.append(limit)

                rows = conn.execute(sql, params).fetchall()

                if not rows:
                    s.add("found", 0)
                    return "No memories found matching filters"

                # Increment access counts
                row_ids = [r[0] for r in rows]
                placeholders = ", ".join("?" for _ in row_ids)
                conn.execute(
                    f"UPDATE memories SET access_count = access_count + 1, last_accessed = datetime('now') WHERE id IN ({placeholders})",
                    row_ids,
                )
                conn.commit()

            s.add("found", len(rows))

            parts = []
            for row in rows:
                formatted = _format_read_row(row, meta=meta)
                if not meta:
                    parts.append(f"# {row[1]}\n\n{formatted}")
                else:
                    parts.append(formatted)

            noun = "memory" if len(rows) == 1 else "memories"
            return f"Read {len(rows)} {noun}\n\n---\n\n" + "\n\n---\n\n".join(parts)

        except Exception as e:
            s.add("error", str(e))
            return f"Error reading memories: {e}"


__all__ = [
    "_READ_COLUMNS",
    "_format_read_row",
    "read",
    "read_batch",
]
