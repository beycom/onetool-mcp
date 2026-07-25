"""Knowledge pack — SQLite-backed knowledge base with hybrid FTS5+vector search."""

from __future__ import annotations

pack = "knowledge"

__all__ = [
    "append",
    "ask",
    "dbs",
    "delete",
    "grep",
    "info",
    "list",
    "read",
    "related",
    "search",
    "slice",
    "stats",
    "toc",
    "update",
    "write",
]

from .crud import append, delete, read, update, write
from .listing import dbs, grep, info, stats, toc
from .listing import list_entries as list
from .listing import slice_entry as slice
from .retrieval import ask, related, search
