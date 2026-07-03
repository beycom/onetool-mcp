"""SQLite connection management, schema, and serialisation helpers."""
from __future__ import annotations

import builtins
import json
import math
import re
import struct
from typing import TYPE_CHECKING, cast

from .config import _get_config

if TYPE_CHECKING:
    import sqlite3
    from contextlib import AbstractContextManager
    from pathlib import Path

from ot.utils.sqlite_pool import SqlitePool

_builtins_list = builtins.list
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _get_db_path() -> Path:
    """Get the memory database path, resolving relative to .onetool/ directory.

    Uses resolve_ot_path (not expand_path) so the default
    "data/mem/default.db" resolves against config._config_dir
    (config_path.parent).
    """
    from ot.meta import resolve_ot_path

    config = _get_config()
    db_path = resolve_ot_path(config.db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return db_path


def _cosine_similarity(a_blob: bytes | None, b_blob: bytes | None) -> float | None:
    """Cosine similarity between two packed float32 BLOB vectors.

    Registered as a SQLite UDF so it can be used in ORDER BY clauses.
    """
    if a_blob is None or b_blob is None:
        return None
    n = len(a_blob) // 4
    a = struct.unpack(f"<{n}f", a_blob)
    b = struct.unpack(f"<{n}f", b_blob)
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return float(dot / (norm_a * norm_b))


def _mem_setup(conn: sqlite3.Connection) -> None:
    """Setup function applied to every new mem connection."""
    conn.create_function("cosine_similarity", 2, _cosine_similarity)
    _ensure_tables(conn)


_pool = SqlitePool(_get_db_path, _mem_setup)


def _get_connection() -> sqlite3.Connection:
    """Get or create a read-write SQLite connection with WAL mode."""
    return _pool.get()


def _use_connection() -> AbstractContextManager[sqlite3.Connection]:
    """Context manager that holds the connection lock for the entire operation."""
    return _pool.use()


def _close_connection() -> None:
    """Close the module-level connection (for testing)."""
    _pool.close()


def _has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    """Check if a column exists in a SQLite table."""
    if not _IDENTIFIER_RE.fullmatch(table):
        raise ValueError(f"invalid table identifier: {table}")
    rows = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
    return any(r[1] == column for r in rows)


def _ensure_tables(conn: sqlite3.Connection) -> None:
    """Create memory tables if they don't exist, then apply migrations."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id             TEXT PRIMARY KEY,
            topic          TEXT NOT NULL,
            content        TEXT NOT NULL,
            content_hash   TEXT NOT NULL,
            category       TEXT DEFAULT 'note',
            tags           TEXT DEFAULT '[]',
            relevance      INTEGER DEFAULT 5,
            access_count   INTEGER DEFAULT 0,
            created_at     TEXT DEFAULT (datetime('now')),
            updated_at     TEXT DEFAULT (datetime('now')),
            last_accessed  TEXT DEFAULT (datetime('now')),
            embedding      BLOB,
            meta           TEXT DEFAULT '{}'
        )
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_memories_topic ON memories(topic)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_memories_content_hash ON memories(content_hash)
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS memory_history (
            id             TEXT PRIMARY KEY,
            memory_id      TEXT NOT NULL,
            content        TEXT NOT NULL,
            updated_at     TEXT DEFAULT (datetime('now'))
        )
    """)

    _migrate_tables(conn)


def _migrate_tables(conn: sqlite3.Connection) -> None:
    """Apply schema migrations to existing tables.

    Each migration checks before applying so it is safe to call repeatedly.
    """
    # v2: add meta column for extensible key-value metadata
    if not _has_column(conn, "memories", "meta"):
        conn.execute("ALTER TABLE memories ADD COLUMN meta TEXT DEFAULT '{}'")
    conn.commit()


# ---------------------------------------------------------------------------
# Serialisation helpers for SQLite columns
# ---------------------------------------------------------------------------


def _serialize_embedding(vec: list[float] | None) -> bytes | None:
    """Pack a float list into a BLOB for SQLite storage."""
    if vec is None:
        return None
    return struct.pack(f"<{len(vec)}f", *vec)


def _deserialize_embedding(blob: bytes | None) -> list[float] | None:
    """Unpack a BLOB back to a float list."""
    if blob is None:
        return None
    n = len(blob) // 4
    return _builtins_list(struct.unpack(f"<{n}f", blob))


def _serialize_tags(tags: list[str] | None) -> str:
    """Serialize tag list to JSON string."""
    return json.dumps(tags or [])


def _deserialize_tags(raw: str | None) -> list[str]:
    """Deserialize JSON string back to tag list."""
    if not raw:
        return []
    return cast("list[str]", json.loads(raw))


def _serialize_meta(meta: dict[str, str] | None) -> str:
    """Serialize meta dict to JSON string."""
    return json.dumps(meta or {})


def _deserialize_meta(raw: str | None) -> dict[str, str]:
    """Deserialize JSON string back to meta dict."""
    if not raw:
        return {}
    return cast("dict[str, str]", json.loads(raw))


__all__ = [
    "_close_connection",
    "_cosine_similarity",
    "_deserialize_embedding",
    "_deserialize_meta",
    "_deserialize_tags",
    "_ensure_tables",
    "_get_connection",
    "_get_db_path",
    "_has_column",
    "_migrate_tables",
    "_serialize_embedding",
    "_serialize_meta",
    "_serialize_tags",
    "_use_connection",
]
