"""Memory version history: list prior versions and roll back."""
from __future__ import annotations

from typing import Any

from otpack import LogSpan

from .content import _redact
from .db import _deserialize_meta, _use_connection
from .embedding import _embed_now, _enqueue_after_commit
from .mutations import _apply_memory_update


def _resolve_memory(
    conn: Any, *, topic: str | None, id: str | None
) -> tuple[str, str, str, str] | str:
    """Resolve exactly one memory by id or exact topic (same rule as update()).

    Returns (memory_id, content, meta_raw, updated_at) or an error string.
    """
    if not topic and not id:
        return "Error: Must specify topic or id"
    if id:
        rows = conn.execute(
            "SELECT id, content, meta, updated_at FROM memories WHERE id = ?", [id]
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, content, meta, updated_at FROM memories WHERE topic = ?", [topic]
        ).fetchall()
    if not rows:
        return f"No memory found with id '{id}'" if id else f"No memory found for topic '{topic}'"
    if len(rows) > 1:
        return f"Multiple memories ({len(rows)}) match topic '{topic}'. Use id= to disambiguate."
    return rows[0][0], rows[0][1], rows[0][2], rows[0][3]


def _history_rows(conn: Any, memory_id: str, limit: int | None = None) -> list[Any]:
    """History rows for a memory, newest first (v1 = most recent prior version)."""
    sql = (
        "SELECT id, content, updated_at FROM memory_history "
        "WHERE memory_id = ? ORDER BY updated_at DESC, rowid DESC"
    )
    params: list[Any] = [memory_id]
    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)
    return list(conn.execute(sql, params).fetchall())


def history(
    *,
    topic: str | None = None,
    id: str | None = None,
    limit: int = 10,
) -> str:
    """List prior versions of a memory, newest first.

    Versions are numbered v1..vN where v1 is the most recent prior version.
    Version numbers shift as new history accrues; the bracketed history-id
    prefix is the stable selector for mem.rollback(history_id=...).

    Args:
        topic: Topic to find the memory (must match exactly one)
        id: Optional memory ID for direct lookup (overrides topic match)
        limit: Maximum versions to list (default: 10)

    Returns:
        Numbered version list with previews, or an error message.

    Example:
        mem.history(topic="projects/onetool/rules")
        mem.history(id="abc-123", limit=5)
    """
    with LogSpan(span="mem.history", topic=topic, limit=limit) as s:
        try:
            with _use_connection() as conn:
                resolved = _resolve_memory(conn, topic=topic, id=id)
                if isinstance(resolved, str):
                    s.add("error", "not_resolved")
                    return resolved
                memory_id, content, _meta_raw, updated_at = resolved
                rows = _history_rows(conn, memory_id, limit)

            label = topic or memory_id
            if not rows:
                s.add("versionCount", 0)
                return f"No history for '{label}' ({memory_id})"

            s.add("versionCount", len(rows))
            lines = [
                f"History for '{label}' ({memory_id}) — "
                f"current: {len(content)} chars, updated {updated_at}\n"
            ]
            for n, (hist_id, hist_content, hist_updated_at) in enumerate(rows, start=1):
                preview = hist_content.splitlines()[0] if hist_content else ""
                if len(preview) > 80:
                    preview = preview[:80] + "..."
                lines.append(
                    f"  v{n} [{hist_id[:8]}] {hist_updated_at} — "
                    f"{len(hist_content)} chars: {preview}"
                )
            return "\n".join(lines)
        except Exception as e:
            s.add("error", str(e))
            return f"Error listing history: {e}"


def rollback(
    *,
    topic: str | None = None,
    id: str | None = None,
    version: int = 1,
    history_id: str | None = None,
) -> str:
    """Restore a memory to a prior version from mem.history().

    Restores content only — category, tags, and relevance changes since the
    snapshot are kept. The current content is saved to history first, so a
    rollback is itself undoable (rolling back a rollback returns the
    original). TOC sections and embeddings are recomputed from the restored
    content.

    Args:
        topic: Topic to find the memory (must match exactly one)
        id: Optional memory ID for direct lookup (overrides topic match)
        version: Version number from mem.history() to restore (default: 1 =
            most recent prior version). Ignored when history_id is given.
        history_id: Stable history-row id (full or unambiguous prefix);
            overrides version.

    Returns:
        Confirmation naming the memory and restored version, or an error.

    Example:
        mem.rollback(topic="projects/onetool/rules")
        mem.rollback(id="abc-123", version=2)
        mem.rollback(topic="notes/x", history_id="9f3c21ab")
    """
    with LogSpan(span="mem.rollback", topic=topic, version=version) as s:
        try:
            with _use_connection() as conn:
                resolved = _resolve_memory(conn, topic=topic, id=id)
                if isinstance(resolved, str):
                    s.add("error", "not_resolved")
                    return resolved
                memory_id, current_content, meta_raw, _updated_at = resolved
                rows = _history_rows(conn, memory_id)

            label = topic or memory_id
            if not rows:
                s.add("error", "no_history")
                return f"No history for '{label}' ({memory_id})"

            if history_id is not None:
                matches = [
                    (n, row) for n, row in enumerate(rows, start=1)
                    if str(row[0]).startswith(history_id)
                ]
                if not matches:
                    s.add("error", "unknown_history_id")
                    return f"Error: No history entry matches history_id '{history_id}'"
                if len(matches) > 1:
                    s.add("error", "ambiguous_history_id")
                    return (
                        f"Error: history_id '{history_id}' is ambiguous "
                        f"({len(matches)} matches). Use a longer prefix."
                    )
                target_version, target_row = matches[0]
            else:
                if not 1 <= version <= len(rows):
                    s.add("error", "version_out_of_range")
                    return (
                        f"Error: version {version} is out of range. "
                        f"Valid range: v1..v{len(rows)} (see mem.history())"
                    )
                target_version, target_row = version, rows[version - 1]

            existing_meta: dict[str, str] = _deserialize_meta(meta_raw)
            restored_content = _redact(str(target_row[1]))
            # Embedding API call happens outside the DB lock
            embedding = _embed_now(restored_content)

            with _use_connection() as conn:
                _apply_memory_update(
                    conn,
                    memory_id=memory_id,
                    old_content=current_content,
                    new_content=restored_content,
                    meta=existing_meta,
                    embedding=embedding,
                )
                conn.commit()
            _enqueue_after_commit(memory_id)

            s.add("memoryId", memory_id)
            s.add("restoredVersion", target_version)
            return (
                f"Rolled back memory {memory_id} ('{label}') to "
                f"v{target_version} [{str(target_row[0])[:8]}] "
                f"({len(restored_content)} chars)"
            )
        except Exception as e:
            s.add("error", str(e))
            return f"Error rolling back memory: {e}"


__all__ = ["history", "rollback"]
