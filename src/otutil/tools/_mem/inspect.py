"""Memory inspect — structured single-item metadata."""

from __future__ import annotations

from typing import Any

from otpack import LogSpan

from .content import _decode_sections
from .db import _deserialize_meta, _deserialize_tags, _get_connection


def inspect(
    *,
    topic: str,
    id: str | None = None,
) -> dict[str, Any]:
    """Return structured metadata for a single memory.

    Args:
        topic: Exact topic path to inspect
        id: Optional memory ID for direct lookup (overrides topic match)

    Returns:
        Dict with topic, category, tags, relevance, access_count, created_at,
        updated_at, id, and toc_entry_count.

    Example:
        mem.inspect(topic="projects/onetool/rules")
        mem.inspect(id="abc-123-def")
    """
    with LogSpan(span="mem.inspect", topic=topic) as s:
        try:
            conn = _get_connection()

            columns = "id, topic, category, tags, relevance, access_count, created_at, updated_at, meta"
            if id:
                row = conn.execute(
                    f"SELECT {columns} FROM memories WHERE id = ?",
                    [id],
                ).fetchone()
            else:
                row = conn.execute(
                    f"SELECT {columns} FROM memories WHERE topic = ?",
                    [topic],
                ).fetchone()

            if not row:
                s.add(found=False)
                label = f"id '{id}'" if id else f"topic '{topic}'"
                return {"error": f"No memory found for {label}"}

            s.add(found=True)
            s.add(memoryId=row[0])

            # row indices: 0=id, 1=topic, 2=category, 3=tags, 4=relevance,
            #              5=access_count, 6=created_at, 7=updated_at, 8=meta
            tags = _deserialize_tags(row[3])
            row_meta = _deserialize_meta(row[8])
            sections = _decode_sections(row_meta.get("sections", ""))

            return {
                "id": row[0],
                "topic": row[1],
                "category": row[2],
                "tags": tags,
                "relevance": row[4],
                "access_count": row[5],
                "created_at": row[6],
                "updated_at": row[7],
                "toc_entry_count": len(sections),
            }

        except Exception as e:
            s.add(error=str(e))
            return {"error": f"Error inspecting memory: {e}"}


__all__ = ["inspect"]
