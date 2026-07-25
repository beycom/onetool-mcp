"""SQLite connection management, schema, and serialisation helpers."""

from __future__ import annotations

import builtins
import json
import math
import re
from typing import TYPE_CHECKING, cast

from loguru import logger

from ot.logging import LogEntry
from otpack import cosine_similarity_blobs, deserialize_embedding, serialize_embedding

from .config import _get_config

if TYPE_CHECKING:
    import sqlite3
    from contextlib import AbstractContextManager
    from pathlib import Path

from ot.utils.sqlite_pool import SqlitePool

_builtins_list = builtins.list
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# ── index availability (module-level caches) ────────────────────────────────
# FTS5 availability is a property of the SQLite build, discovered by trying to
# create the index; sqlite-vec is a property of the environment. mem degrades
# gracefully on both (unlike knowledge, which hard-fails without FTS5).
_FTS_AVAILABLE: bool | None = None  # None = not yet checked
_VEC_AVAILABLE: bool | None = None  # None = not yet checked


def _check_fts_available() -> bool:
    """Return True when the memories_fts FTS5 index is usable."""
    return bool(_FTS_AVAILABLE)


def _check_vec_available() -> bool:
    """Return True if sqlite-vec is importable."""
    global _VEC_AVAILABLE
    if _VEC_AVAILABLE is None:
        try:
            import sqlite_vec  # type: ignore[import-untyped]  # noqa: F401

            _VEC_AVAILABLE = True
        except ImportError:
            _VEC_AVAILABLE = False
    return _VEC_AVAILABLE


def _require_vec() -> None:
    """Raise ImportError with install instructions if sqlite-vec is absent."""
    if not _check_vec_available():
        raise ImportError(
            "sqlite-vec is required for vector search. "
            "Install with: pip install sqlite-vec  (or: pip install onetool-mcp[util])"
        )


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

    Registered as a SQLite UDF so it can be used in ORDER BY clauses. Delegates
    to otpack, keeping the mem-specific dimension-mismatch guidance.
    """
    if a_blob is not None and b_blob is not None and len(a_blob) != len(b_blob):
        raise ValueError(
            f"embedding dimension mismatch: {len(a_blob) // 4} vs {len(b_blob) // 4} dims. "
            "The stored embeddings were generated with a different model/dimensions; "
            "re-generate them with mem.reindex(dry_run=False)."
        )
    return cosine_similarity_blobs(a_blob, b_blob)


def _mem_setup(conn: sqlite3.Connection) -> None:
    """Setup function applied to every new mem connection."""
    conn.create_function("cosine_similarity", 2, _cosine_similarity)
    if _check_vec_available():
        try:
            import sqlite_vec

            conn.enable_load_extension(True)
            sqlite_vec.load(conn)
            conn.enable_load_extension(False)
        except Exception as exc:
            global _VEC_AVAILABLE
            _VEC_AVAILABLE = False
            logger.warning(
                LogEntry(
                    event="mem.db.vec_load_failed",
                    errorType=type(exc).__name__,
                    error=str(exc),
                )
            )
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


_FTS_SQL = """
CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
    topic,
    content,
    content='memories',
    content_rowid='rowid',
    tokenize = 'porter unicode61'
);
"""

_FTS_TRIGGERS_SQL = """
CREATE TRIGGER IF NOT EXISTS memories_fts_after_insert AFTER INSERT ON memories BEGIN
    INSERT INTO memories_fts(rowid, topic, content)
    VALUES (new.rowid, new.topic, new.content);
END;

CREATE TRIGGER IF NOT EXISTS memories_fts_after_delete AFTER DELETE ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, topic, content)
    VALUES ('delete', old.rowid, old.topic, old.content);
END;

CREATE TRIGGER IF NOT EXISTS memories_fts_after_update AFTER UPDATE ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, topic, content)
    VALUES ('delete', old.rowid, old.topic, old.content);
    INSERT INTO memories_fts(rowid, topic, content)
    VALUES (new.rowid, new.topic, new.content);
END;
"""

_VEC_TRIGGER_SQL = """
CREATE TRIGGER IF NOT EXISTS memories_vec_after_delete AFTER DELETE ON memories BEGIN
    DELETE FROM memories_vec WHERE memory_id = old.id;
END;
"""


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", [name]
        ).fetchone()
        is not None
    )


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

    # FTS5 keyword index — degrade gracefully on SQLite builds without FTS5.
    global _FTS_AVAILABLE
    fts_existed = _table_exists(conn, "memories_fts")
    try:
        conn.executescript(_FTS_SQL)
        conn.executescript(_FTS_TRIGGERS_SQL)
        _FTS_AVAILABLE = True
    except Exception as exc:
        if _FTS_AVAILABLE is None:
            logger.warning(
                LogEntry(
                    event="mem.db.fts_unavailable",
                    errorType=type(exc).__name__,
                    error=str(exc),
                    action="keyword search falls back to LIKE",
                )
            )
        _FTS_AVAILABLE = False

    # vec0 KNN index — derived from memories.embedding; only when sqlite-vec loaded.
    if _check_vec_available():
        dims = int(_get_config().dimensions)
        if dims <= 0:
            raise ValueError(f"mem dimensions must be > 0, got {dims}")
        conn.execute(f"""
            CREATE VIRTUAL TABLE IF NOT EXISTS memories_vec USING vec0(
                memory_id TEXT PRIMARY KEY,
                embedding float[{dims}]
            )
        """)
        conn.executescript(_VEC_TRIGGER_SQL)

    _migrate_tables(conn, fts_existed=fts_existed)


def _vec_table_dims(conn: sqlite3.Connection) -> int | None:
    """Parse `float[N]` out of the memories_vec DDL, or None when absent."""
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'memories_vec'"
    ).fetchone()
    if not row or not row[0]:
        return None
    match = re.search(r"float\[(\d+)\]", row[0])
    return int(match.group(1)) if match else None


def _backfill_vec_index(conn: sqlite3.Connection) -> None:
    """Insert missing memories_vec rows from stored embedding BLOBs.

    Cheap no-op when nothing is missing (single anti-join SELECT). Vectors
    whose dimensions do not match config are counted and logged with a
    mem.reindex pointer.
    """
    dims = int(_get_config().dimensions)
    missing = conn.execute(
        """
        SELECT m.id, m.embedding FROM memories m
        LEFT JOIN memories_vec v ON v.memory_id = m.id
        WHERE m.embedding IS NOT NULL AND v.memory_id IS NULL
        """
    ).fetchall()
    if not missing:
        return
    skipped = 0
    for memory_id, blob in missing:
        vec = _deserialize_embedding(blob)
        if vec is None or len(vec) != dims:
            skipped += 1
            continue
        conn.execute(
            "INSERT INTO memories_vec(memory_id, embedding) VALUES (?, ?)",
            [memory_id, _serialize_embedding(_normalize_vec(vec))],
        )
    if skipped:
        logger.warning(
            LogEntry(
                event="mem.migrate.vec_dim_skipped",
                skippedCount=skipped,
                expectedDims=dims,
                action="re-generate with mem.reindex(dry_run=False)",
            )
        )


def _migrate_tables(conn: sqlite3.Connection, *, fts_existed: bool = True) -> None:
    """Apply schema migrations to existing tables.

    Each migration checks before applying so it is safe to call repeatedly.
    """
    # v2: add meta column for extensible key-value metadata
    if not _has_column(conn, "memories", "meta"):
        conn.execute("ALTER TABLE memories ADD COLUMN meta TEXT DEFAULT '{}'")

    # v3: populate a freshly created FTS index for pre-existing rows
    if _check_fts_available() and not fts_existed:
        has_rows = conn.execute("SELECT 1 FROM memories LIMIT 1").fetchone()
        if has_rows:
            conn.execute("INSERT INTO memories_fts(memories_fts) VALUES('rebuild')")

    # v3: vec index — recreate on dimension change, then backfill missing rows
    if _check_vec_available():
        dims = int(_get_config().dimensions)
        existing_dims = _vec_table_dims(conn)
        if existing_dims is not None and existing_dims != dims:
            conn.execute("DROP TABLE memories_vec")
            conn.execute(f"""
                CREATE VIRTUAL TABLE memories_vec USING vec0(
                    memory_id TEXT PRIMARY KEY,
                    embedding float[{dims}]
                )
            """)
        _backfill_vec_index(conn)

    conn.commit()


def _normalize_vec(vec: list[float]) -> list[float]:
    """L2-normalise a vector so KNN L2 ordering equals cosine ordering.

    Zero vectors are returned unchanged (normalisation is undefined).
    """
    norm = math.sqrt(sum(x * x for x in vec))
    if norm == 0.0:
        return vec
    return [x / norm for x in vec]


def _sync_vec_index(
    conn: sqlite3.Connection, memory_id: str, vec: list[float] | None
) -> None:
    """Keep the derived memories_vec row in sync with an embedding write.

    Deletes any existing row, then inserts the L2-normalised vector when its
    dimensions match config. `vec=None` deletes only (e.g. content changed and
    the new embedding arrives asynchronously). Silent no-op when sqlite-vec is
    unavailable. The memories.embedding BLOB remains the source of truth.
    """
    if not _check_vec_available():
        return
    conn.execute("DELETE FROM memories_vec WHERE memory_id = ?", [memory_id])
    if vec is None:
        return
    dims = int(_get_config().dimensions)
    if len(vec) != dims:
        logger.debug(
            LogEntry(
                event="mem.db.vec_dim_skipped",
                memoryId=memory_id,
                vecDims=len(vec),
                expectedDims=dims,
            )
        )
        return
    conn.execute(
        "INSERT INTO memories_vec(memory_id, embedding) VALUES (?, ?)",
        [memory_id, _serialize_embedding(_normalize_vec(vec))],
    )


# ---------------------------------------------------------------------------
# Serialisation helpers for SQLite columns
# ---------------------------------------------------------------------------


# Canonical float32 serialization lives in otpack (little-endian <{n}f).
_serialize_embedding = serialize_embedding
_deserialize_embedding = deserialize_embedding


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
    "_check_fts_available",
    "_check_vec_available",
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
    "_normalize_vec",
    "_require_vec",
    "_serialize_embedding",
    "_serialize_meta",
    "_serialize_tags",
    "_sync_vec_index",
    "_use_connection",
]
