"""Memory mutation functions: delete, update, append."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from otpack import LogSpan

from .config import _get_config
from .content import (
    _content_hash,
    _encode_sections,
    _parse_headings,
    _redact,
    _topic_filter,
)
from .db import (
    _deserialize_meta,
    _serialize_embedding,
    _serialize_meta,
    _sync_vec_index,
    _use_connection,
)
from .embedding import _embed_now, _enqueue_after_commit

if TYPE_CHECKING:
    import sqlite3

_APPEND_CAS_ATTEMPTS = 3


class _MemoryConflictError(RuntimeError):
    """Raised when a read-derived memory mutation loses its CAS."""


def _apply_memory_update(
    conn: sqlite3.Connection,
    *,
    memory_id: str,
    old_content: str,
    old_content_hash: str,
    new_content: str,
    meta: dict[str, str],
    embedding: list[float] | None,
) -> None:
    """Atomically save history and CAS-update a memory row.

    Shared by update(), append(), rollback(), update_batch(), and refresh().
    Must be called with the connection lock held; compute `embedding`
    beforehand via _embed_now() so the OpenAI round-trip happens outside the
    lock. The helper owns and commits the mutation transaction. When embeddings
    are disabled the stored embedding is preserved instead of being overwritten
    with NULL. A predecessor mismatch rolls back history, content, metadata,
    and vector changes together.
    """
    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute(
            "INSERT INTO memory_history (id, memory_id, content) VALUES (?, ?, ?)",
            [str(uuid.uuid4()), memory_id, old_content],
        )

        # Recompute toc if the memory already has sections
        if "sections" in meta:
            headings = _parse_headings(new_content)
            if headings:
                meta["sections"] = _encode_sections(headings)
                meta["section_count"] = str(len(headings))
            else:
                del meta["sections"]
                meta.pop("section_count", None)

        new_hash = _content_hash(new_content)
        if _get_config().embeddings_enabled:
            cursor = conn.execute(
                """
                UPDATE memories
                SET content = ?, content_hash = ?, embedding = ?, meta = ?, updated_at = datetime('now')
                WHERE id = ? AND content_hash = ? AND content = ?
                """,
                [
                    new_content,
                    new_hash,
                    _serialize_embedding(embedding),
                    _serialize_meta(meta),
                    memory_id,
                    old_content_hash,
                    old_content,
                ],
            )
            if cursor.rowcount != 1:
                raise _MemoryConflictError(
                    f"Memory {memory_id} changed concurrently; retry the mutation"
                )
            # embedding=None (async mode) removes the now-stale vec row; the
            # worker re-syncs it after the new embedding is generated.
            _sync_vec_index(conn, memory_id, embedding)
        else:
            # Preserve any stored embedding when embeddings are disabled
            cursor = conn.execute(
                """
                UPDATE memories
                SET content = ?, content_hash = ?, meta = ?, updated_at = datetime('now')
                WHERE id = ? AND content_hash = ? AND content = ?
                """,
                [
                    new_content,
                    new_hash,
                    _serialize_meta(meta),
                    memory_id,
                    old_content_hash,
                    old_content,
                ],
            )
            if cursor.rowcount != 1:
                raise _MemoryConflictError(
                    f"Memory {memory_id} changed concurrently; retry the mutation"
                )
        conn.commit()
    except BaseException:
        conn.rollback()
        raise


def delete(
    *,
    topic: str | None = None,
    id: str | None = None,
    confirm: bool = False,
) -> str:
    """Delete memories by topic prefix or ID.

    For safety, deleting multiple memories requires confirm=True.

    Args:
        topic: Topic prefix to delete (e.g., "projects/old/" deletes all under it)
        id: Specific memory ID to delete
        confirm: Required for multi-delete operations

    Returns:
        Deletion confirmation or error.

    Example:
        mem.delete(id="abc-123")
        mem.delete(topic="projects/old/", confirm=True)
    """
    if not topic and not id:
        return "Error: Must specify topic or id"

    with LogSpan(span="mem.delete", topic=topic) as s:
        try:
            with _use_connection() as conn:
                if id:
                    result = conn.execute(
                        "DELETE FROM memories WHERE id = ? RETURNING id", [id]
                    ).fetchone()
                    if result:
                        # Clean up history too
                        conn.execute(
                            "DELETE FROM memory_history WHERE memory_id = ?", [id]
                        )
                        conn.commit()
                        s.add("deleted", 1)
                        return f"Deleted memory {id}"
                    else:
                        s.add("deleted", 0)
                        return f"No memory found with id '{id}'"

                # Topic-based deletion
                sql = "SELECT COUNT(*) FROM memories WHERE 1=1"
                params: list[Any] = []
                topic_sql, topic_params = _topic_filter(topic)
                sql += topic_sql
                params.extend(topic_params)

                match_count = conn.execute(sql, params).fetchone()[0]

                if match_count == 0:
                    s.add("deleted", 0)
                    return f"No memories found matching topic '{topic}'"

                if match_count > 1 and not confirm:
                    s.add("error", "confirm_required")
                    return f"Would delete {match_count} memories. Set confirm=True to proceed."

                # Delete history for matching memories
                del_history_sql = (
                    "DELETE FROM memory_history WHERE memory_id IN (SELECT id FROM memories WHERE 1=1"
                    + topic_sql
                    + ")"
                )
                conn.execute(del_history_sql, topic_params)

                del_sql = "DELETE FROM memories WHERE 1=1" + topic_sql
                conn.execute(del_sql, topic_params)
                conn.commit()

                s.add("deleted", match_count)
                return f"Deleted {match_count} memories matching topic '{topic}'"

        except Exception as e:
            s.add("error", str(e))
            return f"Error deleting memories: {e}"


def update(
    *,
    topic: str,
    content: str,
    id: str | None = None,
) -> str:
    """Update a memory's content. Must match exactly one memory.

    Stores previous content in history for rollback.
    Re-generates the embedding for the new content when embeddings are
    enabled; when disabled, the stored embedding is preserved.

    Args:
        topic: Topic to find the memory (must match exactly one)
        content: New content to replace existing
        id: Optional memory ID for direct update (overrides topic match)

    Returns:
        Update confirmation or error.

    Example:
        mem.update(topic="projects/onetool/rules", content="Updated rule text")
        mem.update(id="abc-123", topic="ignored", content="New content")
    """
    with LogSpan(span="mem.update", topic=topic) as s:
        try:
            with _use_connection() as conn:
                if id:
                    rows = conn.execute(
                        "SELECT id, content, content_hash, meta FROM memories WHERE id = ?",
                        [id],
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT id, content, content_hash, meta FROM memories WHERE topic = ?",
                        [topic],
                    ).fetchall()

            if not rows:
                s.add("error", "not_found")
                return (
                    f"No memory found for topic '{topic}'"
                    if not id
                    else f"No memory found with id '{id}'"
                )

            if len(rows) > 1:
                s.add("error", "multiple_matches")
                return f"Multiple memories ({len(rows)}) match topic '{topic}'. Use id= for specific update."

            memory_id = rows[0][0]
            old_content = rows[0][1]
            old_content_hash = rows[0][2]
            existing_meta: dict[str, str] = _deserialize_meta(rows[0][3])

            content = _redact(content)
            # Embedding API call happens outside the DB lock
            embedding = _embed_now(content)

            with _use_connection() as conn:
                _apply_memory_update(
                    conn,
                    memory_id=memory_id,
                    old_content=old_content,
                    old_content_hash=old_content_hash,
                    new_content=content,
                    meta=existing_meta,
                    embedding=embedding,
                )
            _enqueue_after_commit(memory_id)

            s.add("memoryId", memory_id)
            return f"Updated memory {memory_id} in topic '{topic}'"

        except Exception as e:
            s.add("error", str(e))
            return f"Error updating memory: {e}"


def append(
    *,
    topic: str,
    content: str,
    id: str | None = None,
    separator: str = "\n\n",
) -> str:
    """Append content to an existing memory.

    Args:
        topic: Topic of the memory to append to
        content: Content to append
        id: Optional memory ID (overrides topic match)
        separator: Separator between existing and new content (default: double newline)

    Returns:
        Confirmation or error.

    Example:
        mem.append(topic="projects/onetool/rules", content="New rule to add")
    """
    with LogSpan(span="mem.append", topic=topic) as s:
        try:
            redacted_content = _redact(content)
            saw_conflict = False
            for attempt in range(_APPEND_CAS_ATTEMPTS):
                with _use_connection() as conn:
                    if id:
                        row = conn.execute(
                            """
                            SELECT id, content, content_hash, meta
                            FROM memories
                            WHERE id = ?
                            """,
                            [id],
                        ).fetchone()
                    else:
                        rows = conn.execute(
                            """
                            SELECT id, content, content_hash, meta
                            FROM memories
                            WHERE topic = ?
                            """,
                            [topic],
                        ).fetchall()
                        if len(rows) > 1:
                            s.add("error", "multiple_matches")
                            return f"Multiple memories ({len(rows)}) match topic '{topic}'. Use id= for specific append."
                        row = rows[0] if rows else None

                if not row:
                    s.add("error", "conflict" if saw_conflict else "not_found")
                    if saw_conflict:
                        return "Error appending to memory: memory changed concurrently"
                    return (
                        f"No memory found for topic '{topic}'"
                        if not id
                        else f"No memory found with id '{id}'"
                    )

                memory_id, old_content, old_content_hash, meta_raw = row
                existing_meta: dict[str, str] = _deserialize_meta(meta_raw)
                new_content = old_content + separator + redacted_content
                # Embedding API call happens outside the DB lock and is
                # recomputed after every failed CAS.
                embedding = _embed_now(new_content)

                try:
                    with _use_connection() as conn:
                        _apply_memory_update(
                            conn,
                            memory_id=memory_id,
                            old_content=old_content,
                            old_content_hash=old_content_hash,
                            new_content=new_content,
                            meta=existing_meta,
                            embedding=embedding,
                        )
                except _MemoryConflictError:
                    saw_conflict = True
                    if attempt + 1 == _APPEND_CAS_ATTEMPTS:
                        raise
                    continue

                _enqueue_after_commit(memory_id)
                s.add("memoryId", memory_id)
                s.add("newLen", len(new_content))
                return f"Appended to memory {memory_id} in topic '{topic}' (now {len(new_content)} chars)"

            raise AssertionError("append CAS loop exhausted without returning")

        except Exception as e:
            s.add("error", str(e))
            return f"Error appending to memory: {e}"


__all__ = ["_apply_memory_update", "append", "delete", "update"]
