"""Persistent memory for AI agents with SQLite storage and optional OpenAI embeddings.

Provides topic-based memory storage with semantic search, content dedup,
secret redaction, and importance decay. Requires OPENAI_API_KEY in secrets.yaml
when embeddings are enabled.

Thread safety: Uses a shared SQLite connection with WAL mode. Concurrent calls
from multiple threads should use _use_connection() to hold the lock for the
full operation. MCP tool dispatch is single-threaded so this is safe in normal
usage.
"""

from __future__ import annotations

# Pack for dot notation: mem.write(), mem.search(), etc.
pack = "mem"

__all__ = [
    "VALID_CATEGORIES",
    "Config",
    "append",
    "ask",
    "context",
    "count",
    "decay",
    "delete",
    "dump",
    "flush",
    "grep",
    "history",
    "inspect",
    "list",
    "load",
    "query",
    "read",
    "read_batch",
    "refresh",
    "reindex",
    "restore",
    "rollback",
    "search",
    "slice",
    "slice_batch",
    "snapshot",
    "stale",
    "stats",
    "toc",
    "update",
    "update_batch",
    "write",
    "write_batch",
]

# Dependency declarations for CLI validation
__ot_requires__ = {
    "lib": [
        ("openai", "pip install openai"),
        ("tiktoken", "pip install tiktoken"),
    ],
    # API key checked at runtime when embeddings enabled (not pack-level requirement)
}

from .ask import ask
from .config import VALID_CATEGORIES, Config
from .db import _close_connection, _get_connection  # noqa: F401
from .formatting import stale
from .history import history, rollback
from .inspect import inspect
from .io import dump, load
from .lifecycle import decay, flush, reindex, stats
from .listing import count, list
from .maintenance import context, update_batch
from .mutations import append, delete, update
from .query import query
from .read import read, read_batch
from .refresh import refresh
from .search import grep, search
from .slicing import slice, slice_batch, toc
from .snapshots import restore, snapshot
from .write import write, write_batch
