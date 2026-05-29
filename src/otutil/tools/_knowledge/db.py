"""SQLite schema, connection management, and serialisation for the knowledge pack."""
from __future__ import annotations

import builtins
import json
import struct
import threading
from typing import TYPE_CHECKING, Any

from ot.utils.sqlite_pool import SqlitePool

from .config import _get_config, _get_kb_project

if TYPE_CHECKING:
    import sqlite3
    from pathlib import Path

_builtins_list = builtins.list

# Per-database pools — keyed by db_name
_pools: dict[str, SqlitePool] = {}
_pools_lock = threading.Lock()

# ── sqlite-vec availability ────────────────────────────────────────────────

_VEC_AVAILABLE: bool | None = None  # None = not yet checked


def _check_vec_available() -> bool:
    """Return True if sqlite-vec is importable."""
    global _VEC_AVAILABLE
    if _VEC_AVAILABLE is None:
        try:
            import sqlite_vec  # noqa: F401
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


# ── Path resolution ────────────────────────────────────────────────────────


def _resolve_db_path(db_name: str) -> Path:
    """Resolve the filesystem path for a named database."""
    from ot.meta import resolve_ot_path

    kb_project = _get_kb_project(db_name)
    if kb_project:
        path = resolve_ot_path(kb_project.db.path)
    else:
        path = resolve_ot_path(f"data/knowledge/{db_name}.db")
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


# ── Schema ─────────────────────────────────────────────────────────────────

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS chunks (
    id           TEXT PRIMARY KEY,
    topic        TEXT NOT NULL,
    content      TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    category     TEXT NOT NULL DEFAULT 'reference',
    tags         TEXT NOT NULL DEFAULT '[]',
    summary      TEXT,
    source       TEXT,
    source_path  TEXT,
    anchor       TEXT NOT NULL DEFAULT '',
    meta         TEXT NOT NULL DEFAULT '{}',
    hit_count    INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_chunks_topic ON chunks(topic);
CREATE INDEX IF NOT EXISTS idx_chunks_content_hash ON chunks(content_hash);
CREATE INDEX IF NOT EXISTS idx_chunks_category ON chunks(category);
CREATE UNIQUE INDEX IF NOT EXISTS idx_chunks_source ON chunks(source_path, anchor) WHERE source_path IS NOT NULL;

CREATE TABLE IF NOT EXISTS edges (
    id          TEXT PRIMARY KEY,
    src_id      TEXT NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
    dst_id      TEXT NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
    edge_type   TEXT NOT NULL,
    anchor_text TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_edges_src ON edges(src_id);
CREATE INDEX IF NOT EXISTS idx_edges_dst ON edges(dst_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_edges_unique ON edges(src_id, dst_id, edge_type);
"""

_FTS_SQL = """
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    topic,
    content,
    summary,
    content='chunks',
    content_rowid='rowid',
    tokenize = 'porter unicode61'
);
"""

_FTS_TRIGGERS_SQL = """
CREATE TRIGGER IF NOT EXISTS chunks_fts_after_insert AFTER INSERT ON chunks BEGIN
    INSERT INTO chunks_fts(rowid, topic, content, summary)
    VALUES (new.rowid, new.topic, new.content, new.summary);
END;

CREATE TRIGGER IF NOT EXISTS chunks_fts_after_delete AFTER DELETE ON chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, topic, content, summary)
    VALUES ('delete', old.rowid, old.topic, old.content, old.summary);
END;

CREATE TRIGGER IF NOT EXISTS chunks_fts_after_update AFTER UPDATE ON chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, topic, content, summary)
    VALUES ('delete', old.rowid, old.topic, old.content, old.summary);
    INSERT INTO chunks_fts(rowid, topic, content, summary)
    VALUES (new.rowid, new.topic, new.content, new.summary);
END;
"""

_VEC_TRIGGER_SQL = """
CREATE TRIGGER IF NOT EXISTS chunks_vec_after_delete AFTER DELETE ON chunks BEGIN
    DELETE FROM chunks_vec WHERE chunk_id = old.id;
END;
"""

_PRAGMA_SQL = """
PRAGMA mmap_size = 67108864;
PRAGMA cache_size = -65536;
"""


def _kb_setup(conn: sqlite3.Connection) -> None:
    """Setup function applied to every new KB connection."""
    conn.executescript(_PRAGMA_SQL)
    conn.executescript(_SCHEMA_SQL)
    # FTS5 — check availability
    try:
        conn.executescript(_FTS_SQL)
        conn.executescript(_FTS_TRIGGERS_SQL)
    except Exception as exc:
        raise RuntimeError(
            f"FTS5 is required for the knowledge pack but is not available in this SQLite build: {exc}"
        ) from exc

    # sqlite-vec — optional; only create if available
    if _check_vec_available():
        import sqlite_vec

        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
        config = _get_config()
        dims = int(config.dimensions)
        if dims <= 0:
            raise ValueError(f"knowledge dimensions must be > 0, got {dims}")
        conn.execute(f"""
            CREATE VIRTUAL TABLE IF NOT EXISTS chunks_vec USING vec0(
                chunk_id TEXT PRIMARY KEY,
                embedding float[{dims}]
            )
        """)
        conn.executescript(_VEC_TRIGGER_SQL)
    conn.commit()


def _get_pool(db_name: str) -> SqlitePool:
    """Get or create the SqlitePool for a named database."""
    with _pools_lock:
        if db_name not in _pools:
            # Capture db_name in a default arg to avoid late-binding issues
            def _path_fn(name: str = db_name) -> Path:
                return _resolve_db_path(name)

            _pools[db_name] = SqlitePool(_path_fn, _kb_setup)
        return _pools[db_name]


def get_connection(db_name: str) -> sqlite3.Connection:
    """Get a shared connection to the named knowledge database."""
    return _get_pool(db_name).get()


def use_connection(db_name: str):
    """Context manager that holds the pool lock for the named database."""
    return _get_pool(db_name).use()


def close_connection(db_name: str | None = None) -> None:
    """Close connection(s) (used in tests for cleanup)."""
    with _pools_lock:
        if db_name:
            pool = _pools.pop(db_name, None)
            if pool:
                pool.close()
        else:
            for pool in _pools.values():
                pool.close()
            _pools.clear()


# ── Serialisation helpers ──────────────────────────────────────────────────


def serialize_embedding(vec: list[float] | None) -> bytes | None:
    """Pack a float list into a BLOB for SQLite storage."""
    if vec is None:
        return None
    return struct.pack(f"<{len(vec)}f", *vec)


def deserialize_embedding(blob: bytes | None) -> list[float] | None:
    """Unpack a BLOB back to a float list."""
    if blob is None:
        return None
    n = len(blob) // 4
    return _builtins_list(struct.unpack(f"<{n}f", blob))


def serialize_tags(tags: list[str] | None) -> str:
    return json.dumps(tags or [])


def deserialize_tags(raw: str | None) -> list[str]:
    if not raw:
        return []
    return json.loads(raw)


def serialize_meta(meta: dict[str, Any] | None) -> str:
    return json.dumps(meta or {})


def deserialize_meta(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    return json.loads(raw)


__all__ = [
    "_FTS_SQL",
    "_FTS_TRIGGERS_SQL",
    "_SCHEMA_SQL",
    "_check_vec_available",
    "_require_vec",
    "_resolve_db_path",
    "close_connection",
    "deserialize_embedding",
    "deserialize_meta",
    "deserialize_tags",
    "get_connection",
    "serialize_embedding",
    "serialize_meta",
    "serialize_tags",
    "use_connection",
]
