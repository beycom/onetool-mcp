"""Persistent memory for AI agents with SQLite storage and optional OpenAI embeddings.

Provides topic-based memory storage with semantic search, content dedup,
secret redaction, and importance decay. Requires OPENAI_API_KEY in secrets.yaml
when embeddings are enabled.
"""

from __future__ import annotations

# Pack for dot notation: mem.write(), mem.search(), etc.
pack = "mem"


def register_services(registry: object) -> None:
    """Register deterministic embedding-client cleanup."""
    from otutil.tools._mem.embedding import reset_embedding_client

    registry.register_reload_hook(reset_embedding_client)  # type: ignore[attr-defined]

__ot_requires__ = {
    "lib": [
        ("yaml", "pip install pyyaml"),
        ("jmespath", "pip install jmespath"),
    ],
}

# Only public functions are exposed as MCP tools.
__all__ = [
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

from otutil.tools._mem import (
    append,
    ask,
    context,
    count,
    decay,
    delete,
    dump,
    flush,
    grep,
    history,
    inspect,
    list,
    load,
    query,
    read,
    read_batch,
    refresh,
    reindex,
    restore,
    rollback,
    search,
    slice,
    slice_batch,
    snapshot,
    stale,
    stats,
    toc,
    update,
    update_batch,
    write,
    write_batch,
)
