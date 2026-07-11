"""CRUD operations for the knowledge pack."""
from __future__ import annotations

import sqlite3
import uuid
from typing import Any

from loguru import logger

from ot.logging import LogEntry
from otpack import LogSpan

from .chunker import _content_hash
from .config import VALID_CATEGORIES
from .db import (
    deserialize_meta,
    deserialize_tags,
    get_connection,
    serialize_meta,
    serialize_tags,
    use_connection,
)
from .embedding import generate_embedding, vec_to_bytes


def write(
    *,
    topic: str,
    content: str,
    db: str,
    category: str = "note",
    tags: list[str] | None = None,
    meta: dict[str, Any] | None = None,
) -> str:
    """Write a personal annotation to the knowledge database.

    Args:
        topic: Unique topic identifier (e.g. 'rhino/tip/nudge')
        content: Content to store
        db: Target database name
        category: Entry category — 'rule', 'note', or 'mistake' (default: 'note')
        tags: Optional list of tags
        meta: Optional metadata dict

    Returns:
        Confirmation string.

    Example:
        kb.write(topic='python/tips/loops', content='Use enumerate() for index access', db='docs')
    """
    if category not in VALID_CATEGORIES:
        return f"Error: Invalid category '{category}'. Must be one of: {', '.join(sorted(VALID_CATEGORIES))}"

    with LogSpan(span="kb.write", topic=topic, db=db) as s:
        try:
            with use_connection(db) as conn:
                existing = conn.execute("SELECT id FROM chunks WHERE topic = ?", [topic]).fetchone()
                if existing:
                    return f"Error: Topic '{topic}' already exists. Use kb.update() to replace it."

                chunk_id = str(uuid.uuid4())
                hash_ = _content_hash(content)
                try:
                    conn.execute(
                        """
                        INSERT INTO chunks (id, topic, content, content_hash, category, tags, meta, source)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        [chunk_id, topic, content, hash_, category,
                         serialize_tags(tags), serialize_meta(meta),
                         (meta or {}).get("source", "")],
                    )
                except sqlite3.IntegrityError:
                    # Unique-index backstop for a concurrent writer that got in
                    # between the existence check and the insert.
                    conn.rollback()
                    return f"Error: Topic '{topic}' already exists. Use kb.update() to replace it."
                embed_err = _try_embed(conn, chunk_id, content)
                conn.commit()
            s.add("chunkId", chunk_id)
            if embed_err:
                return f"Written: {topic} (warning: embedding failed — semantic search unavailable: {embed_err})"
            return f"Written: {topic}"
        except Exception as e:
            s.add("error", str(e))
            return f"Error writing to '{db}': {e}"


def read(*, topic: str | None = None, source_path: str | None = None, id: str | None = None, db: str) -> str:
    """Read a single entry by topic or id, or all chunks for a source file.

    topic and id are read-one: returns the most recently created matching chunk.
    source_path returns all chunks (page-level and per-section) for a file, ordered by anchor.

    Args:
        topic: Topic identifier — returns the latest matching chunk
        source_path: Canonical source path — returns all chunks for that file
        id: Chunk UUID for direct lookup (overrides topic)
        db: Database name

    Returns:
        Formatted entry content or error message.

    Example:
        kb.read(topic='python/tips/loops', db='docs')
        kb.read(id='abc-123', db='docs')
        kb.read(source_path='guides/v1/en-us/commands/move', db='docs')
    """
    if topic is None and source_path is None and id is None:
        return "Error: Provide topic=, id=, or source_path="

    with LogSpan(span="kb.read", topic=topic, sourcePath=source_path, db=db):
        try:
            conn = get_connection(db)
            if source_path is not None:
                rows = conn.execute(
                    "SELECT topic, content, category, tags, meta, created_at, updated_at FROM chunks WHERE source_path = ? ORDER BY anchor",
                    [source_path],
                ).fetchall()
                if not rows:
                    return f"Error: No entries found for source_path '{source_path}'"
                return "\n\n---\n\n".join(_format_chunk_row(r) for r in rows)

            if id is not None:
                row = conn.execute(
                    "SELECT topic, content, category, tags, meta, created_at, updated_at FROM chunks WHERE id = ?",
                    [id],
                ).fetchone()
                if not row:
                    return f"Error: No entry found with id '{id}'"
            else:
                row = conn.execute(
                    "SELECT topic, content, category, tags, meta, created_at, updated_at FROM chunks WHERE topic = ? ORDER BY created_at DESC LIMIT 1",
                    [topic],
                ).fetchone()
                if not row:
                    return f"Error: No entry found for topic '{topic}'"

            return _format_chunk_row(row)
        except Exception as e:
            return f"Error reading from '{db}': {e}"


def _format_chunk_row(row: Any) -> str:
    tags = deserialize_tags(row[3])
    meta = deserialize_meta(row[4])
    tags_str = ", ".join(tags) if tags else "none"
    meta_str = f"\nMeta: {meta}" if meta else ""
    return (
        f"## {row[0]}\n"
        f"Category: {row[2]} | Tags: {tags_str}\n"
        f"Created: {row[5]} | Updated: {row[6]}{meta_str}\n\n"
        f"{row[1]}"
    )


def append(*, topic: str, content: str, db: str, id: str | None = None) -> str:
    """Append content to an existing entry.

    Args:
        topic: Topic identifier
        content: Content to append
        db: Database name
        id: Chunk UUID for direct lookup (overrides topic)

    Returns:
        Confirmation string.

    Example:
        kb.append(topic='python/tips/loops', content='\\n- new note', db='docs')
        kb.append(id='abc-123', content='\\n- new note', db='docs')
    """
    with LogSpan(span="kb.append", topic=topic, db=db):
        try:
            with use_connection(db) as conn:
                if id is not None:
                    row = conn.execute(
                        "SELECT id, content FROM chunks WHERE id = ? ORDER BY created_at DESC LIMIT 1",
                        [id],
                    ).fetchone()
                    if not row:
                        return f"Error: No entry found with id '{id}'"
                else:
                    row = conn.execute(
                        "SELECT id, content FROM chunks WHERE topic = ? ORDER BY created_at DESC LIMIT 1",
                        [topic],
                    ).fetchone()
                    if not row:
                        return f"Error: No entry found for topic '{topic}'"
                chunk_id, old_content = row
                new_content = old_content + content
                new_hash = _content_hash(new_content)
                conn.execute(
                    "UPDATE chunks SET content = ?, content_hash = ?, summary = NULL, updated_at = datetime('now') WHERE id = ?",
                    [new_content, new_hash, chunk_id],
                )
                embed_err = _try_embed(conn, chunk_id, new_content)
                conn.commit()
            if embed_err:
                return f"Appended to: {topic} (warning: embedding failed — semantic search unavailable: {embed_err})"
            return f"Appended to: {topic}"
        except Exception as e:
            return f"Error appending to '{db}': {e}"


def update(*, topic: str, content: str, db: str, id: str | None = None, source_path: str | None = None, anchor: str | None = None) -> str:
    """Replace the content of an existing entry.

    When id= is provided it targets that chunk directly. Otherwise topic= is used,
    with optional source_path= and anchor= to narrow to a specific chunk.

    Args:
        topic: Topic identifier to update
        content: New content to store
        db: Database name
        id: Chunk UUID for direct update (overrides topic)
        source_path: Optional — narrow to a specific source file
        anchor: Optional — narrow to a specific heading anchor

    Returns:
        Confirmation string.

    Example:
        kb.update(topic='python/tips/loops', content='Updated loop tips', db='docs')
        kb.update(id='abc-123', topic='ignored', content='Updated content', db='docs')
    """
    with LogSpan(span="kb.update", topic=topic, db=db):
        try:
            with use_connection(db) as conn:
                if id is not None:
                    rows = conn.execute("SELECT id FROM chunks WHERE id = ?", [id]).fetchall()
                    if not rows:
                        return f"Error: No entry found with id '{id}'"
                else:
                    sql = "SELECT id FROM chunks WHERE topic = ?"
                    params: list[object] = [topic]
                    if source_path is not None:
                        sql += " AND source_path = ?"
                        params.append(source_path)
                    if anchor is not None:
                        sql += " AND anchor = ?"
                        params.append(anchor)
                    rows = conn.execute(sql, params).fetchall()
                    if not rows:
                        return f"Error: No entry found for topic '{topic}'"
                new_hash = _content_hash(content)
                embed_err: str | None = None
                for (chunk_id,) in rows:
                    conn.execute(
                        "UPDATE chunks SET content = ?, content_hash = ?, summary = NULL, updated_at = datetime('now') WHERE id = ?",
                        [content, new_hash, chunk_id],
                    )
                    embed_err = _try_embed(conn, chunk_id, content) or embed_err
                conn.commit()
            count = len(rows)
            suffix = f" ({count} chunks)" if count > 1 else ""
            if embed_err:
                return f"Updated: {topic}{suffix} (warning: embedding failed — semantic search unavailable: {embed_err})"
            return f"Updated: {topic}{suffix}"
        except Exception as e:
            return f"Error updating in '{db}': {e}"


def delete(*, topic: str | None = None, source_path: str | None = None, id: str | None = None, db: str) -> str:
    """Remove an entry by topic, id, or all chunks for a source file.

    Args:
        topic: Topic identifier to delete
        source_path: Delete all chunks for a source file
        id: Chunk UUID for direct deletion (overrides topic)
        db: Database name

    Returns:
        Confirmation string.

    Example:
        kb.delete(topic='python/tips/loops', db='docs')
        kb.delete(id='abc-123', db='docs')
        kb.delete(source_path='guides/v1/en-us/commands/move', db='docs')
    """
    if topic is None and source_path is None and id is None:
        return "Error: Provide topic=, id=, or source_path="

    with LogSpan(span="kb.delete", topic=topic, sourcePath=source_path, db=db):
        try:
            with use_connection(db) as conn:
                if id is not None:
                    rows = conn.execute("SELECT id FROM chunks WHERE id = ?", [id]).fetchall()
                    label = f"id '{id}'"
                elif source_path is not None:
                    rows = conn.execute("SELECT id FROM chunks WHERE source_path = ?", [source_path]).fetchall()
                    label = f"source_path '{source_path}'"
                else:
                    rows = conn.execute("SELECT id FROM chunks WHERE topic = ?", [topic]).fetchall()
                    label = f"topic '{topic}'"
                if not rows:
                    return f"Error: No entries found for {label}"
                for (chunk_id,) in rows:
                    conn.execute("DELETE FROM chunks WHERE id = ?", [chunk_id])
                conn.commit()
            count = len(rows)
            suffix = f" ({count} chunks)" if count > 1 else ""
            label_short = id or source_path or topic
            return f"Deleted: {label_short}{suffix}"
        except Exception as e:
            return f"Error deleting from '{db}': {e}"


def _try_embed(conn: Any, chunk_id: str, content: str) -> str | None:
    """Try to generate and store embedding.

    Embeds first and only then swaps the stored vector, so a failed re-embed
    never deletes the existing one. Returns an error string if embedding
    failed (so callers can surface it), else None.
    """
    try:
        vec = generate_embedding(content)
        blob = vec_to_bytes(vec)
        conn.execute("DELETE FROM chunks_vec WHERE chunk_id = ?", [chunk_id])
        conn.execute(
            "INSERT INTO chunks_vec(chunk_id, embedding) VALUES (?, ?)",
            [chunk_id, blob],
        )
        return None
    except Exception as e:
        logger.warning(
            LogEntry(
                event="knowledge.embedding.chunk_failed",
                chunkId=chunk_id,
                errorType=type(e).__name__,
                error=str(e),
            )
        )
        return str(e)


__all__ = ["_format_chunk_row", "append", "delete", "read", "update", "write"]
