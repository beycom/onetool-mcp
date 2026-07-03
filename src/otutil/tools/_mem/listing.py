"""Memory listing and counting."""
from __future__ import annotations

import json
from typing import Any, List  # noqa: UP035

from otpack import LogSpan

from .content import _topic_filter
from .db import _deserialize_tags, _get_connection
from .formatting import _format_as_tree, _format_entry_meta


def list(
    *,
    topic: str | None = None,
    category: str | None = None,
    limit: int = 50,
    format: str = "list",
    depth: int = 0,
) -> str:
    """List memories with optional topic prefix and category filtering.

    Args:
        topic: Topic prefix filter (e.g., "projects/" lists all under projects)
        category: Filter by category
        limit: Maximum results (default: 50)
        format: Output format — "list" (flat, default) or "tree" (hierarchy)
        depth: Tree depth limit (0 = unlimited). Only used when format="tree".

    Returns:
        Formatted list of memories.

    Example:
        mem.list()
        mem.list(topic="projects/onetool/")
        mem.list(category="rule")
        mem.list(format="tree", topic="proj/", depth=1)
    """
    with LogSpan(span="mem.list", topic=topic, category=category, limit=limit, format=format) as s:
        try:
            conn = _get_connection()

            sql = "SELECT id, topic, category, tags, relevance, access_count, created_at, length(content) as content_len, meta FROM memories WHERE 1=1"
            params: List[Any] = []

            topic_sql, topic_params = _topic_filter(topic)
            sql += topic_sql
            params.extend(topic_params)

            if category:
                sql += " AND category = ?"
                params.append(category)

            sql += " ORDER BY topic, updated_at DESC LIMIT ?"
            params.append(limit)

            rows = conn.execute(sql, params).fetchall()

            if not rows:
                s.add("resultCount", 0)
                if format == "tree":
                    return "No memories found" + (f" under '{topic}'" if topic else "")
                return "No memories found"

            s.add("resultCount", len(rows))

            if format == "tree":
                return _format_as_tree(rows, topic=topic, depth=depth)

            noun = "memory" if len(rows) == 1 else "memories"
            lines = [f"Found {len(rows)} {noun}:\n"]
            for r in rows:
                tags_list = _deserialize_tags(r[3])
                row_meta = json.loads(r[8]) if r[8] else {}
                section_count = int(row_meta.get("section_count", 0))
                meta_str = _format_entry_meta(
                    mem_id=r[0], content_len=r[7], section_count=section_count,
                    relevance=r[4], category=r[2], tags_list=tags_list,
                )
                lines.append(f"  {r[1]} {meta_str}")
            return "\n".join(lines)

        except Exception as e:
            s.add("error", str(e))
            return f"Error listing memories: {e}"


def count(
    *,
    topic: str | None = None,
    category: str | None = None,
) -> str:
    """Count memories with optional filtering.

    Args:
        topic: Topic prefix filter
        category: Category filter

    Returns:
        Count of matching memories.

    Example:
        mem.count()
        mem.count(topic="projects/")
        mem.count(category="rule")
    """
    with LogSpan(span="mem.count", topic=topic, category=category) as s:
        try:
            conn = _get_connection()

            sql = "SELECT COUNT(*) FROM memories WHERE 1=1"
            params: List[Any] = []

            topic_sql, topic_params = _topic_filter(topic)
            sql += topic_sql
            params.extend(topic_params)

            if category:
                sql += " AND category = ?"
                params.append(category)

            result = conn.execute(sql, params).fetchone()[0]
            s.add("count", result)
            return str(result)

        except Exception as e:
            s.add("error", str(e))
            return f"Error counting memories: {e}"


__all__ = ["count", "list"]
