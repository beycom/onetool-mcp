"""Memory maintenance operations: delete, purge, stats, and batch update."""
from __future__ import annotations

import builtins
from typing import Any

from otpack import LogSpan

from .content import _topic_filter
from .db import _deserialize_meta, _use_connection
from .embedding import _embed_now, _enqueue_after_commit
from .mutations import _apply_memory_update

_builtins_list = builtins.list


def context(
    *,
    topic: str | None = None,
    limit: int = 5,
) -> str:
    """Load most-accessed memories for quick context injection.

    Returns the top-N memories by access count, useful for session startup.

    Args:
        topic: Optional topic prefix filter
        limit: Number of memories to return (default: 5)

    Returns:
        Formatted context block with most-accessed memories.

    Example:
        mem.context(topic="projects/onetool/")
        mem.context(limit=10)
    """
    with LogSpan(span="mem.context", topic=topic, limit=limit) as s:
        try:
            with _use_connection() as conn:
                sql = """
                    SELECT id, topic, content, category, tags, relevance, access_count
                    FROM memories
                    WHERE 1=1
                """
                params: list[Any] = []

                topic_sql, topic_params = _topic_filter(topic)
                sql += topic_sql
                params.extend(topic_params)

                sql += " ORDER BY access_count DESC, relevance DESC LIMIT ?"
                params.append(limit)

                rows = conn.execute(sql, params).fetchall()

                if not rows:
                    s.add("resultCount", 0)
                    return "No memories found for context"

                # Increment access counts (batch)
                ids = [r[0] for r in rows]
                placeholders = ", ".join("?" for _ in ids)
                conn.execute(
                    f"UPDATE memories SET access_count = access_count + 1, last_accessed = datetime('now') WHERE id IN ({placeholders})",
                    ids,
                )
                conn.commit()

            s.add("resultCount", len(rows))

            lines = [f"Context: {len(rows)} memories loaded\n"]
            for r in rows:
                lines.append(
                    f"## {r[1]} [{r[3]}]\n"
                    f"{r[2]}\n"
                )
            return "\n".join(lines)

        except Exception as e:
            s.add("error", str(e))
            return f"Error loading context: {e}"


def update_batch(
    *,
    search_text: str,
    replace_text: str,
    topic: str | None = None,
    dry_run: bool = True,
) -> str:
    """Search and replace text across matching memories.

    Args:
        search_text: Text to find in memory content
        replace_text: Text to replace with
        topic: Optional topic prefix to scope the operation
        dry_run: If True (default), only preview changes without applying

    Returns:
        Summary of changes (or preview in dry_run mode).

    Example:
        mem.update_batch(search_text="old_name", replace_text="new_name", topic="projects/", dry_run=True)
        mem.update_batch(search_text="old_name", replace_text="new_name", topic="projects/", dry_run=False)
    """
    with LogSpan(span="mem.update_batch", search=search_text, replace=replace_text, dryRun=dry_run) as s:
        try:
            with _use_connection() as conn:
                escaped = search_text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                sql = "SELECT id, topic, content, meta FROM memories WHERE content LIKE ? ESCAPE '\\'"
                params: list[Any] = [f"%{escaped}%"]

                topic_sql, topic_params = _topic_filter(topic)
                sql += topic_sql
                params.extend(topic_params)

                rows = conn.execute(sql, params).fetchall()

                if not rows:
                    s.add("matchCount", 0)
                    return f"No memories contain '{search_text}'"

                s.add("matchCount", len(rows))

                if dry_run:
                    lines = [f"Dry run: {len(rows)} memories would be updated:\n"]
                    for r in rows:
                        occurrences = r[2].count(search_text)
                        lines.append(f"  {r[1]} ({occurrences} occurrence{'s' if occurrences != 1 else ''}) id={r[0][:8]}...")
                    return "\n".join(lines)

            updated = 0
            for r in rows:
                memory_id, _topic, old_content = r[0], r[1], r[2]
                existing_meta: dict[str, str] = _deserialize_meta(r[3])

                new_content = old_content.replace(search_text, replace_text)
                # Embedding API call happens outside the DB lock;
                # commit per memory so one failure doesn't lose progress
                embedding = _embed_now(new_content)

                with _use_connection() as conn:
                    _apply_memory_update(
                        conn,
                        memory_id=memory_id,
                        old_content=old_content,
                        new_content=new_content,
                        meta=existing_meta,
                        embedding=embedding,
                    )
                    conn.commit()
                _enqueue_after_commit(memory_id)
                updated += 1

            s.add("updated", updated)
            return f"Updated {updated} memories: replaced '{search_text}' with '{replace_text}'"

        except Exception as e:
            s.add("error", str(e))
            return f"Error in batch update: {e}"


__all__ = ["context", "update_batch"]
