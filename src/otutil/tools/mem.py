"""Persistent memory for AI agents with SQLite storage and optional OpenAI embeddings.

Provides topic-based memory storage with semantic search, content dedup,
secret redaction, and importance decay. Requires OPENAI_API_KEY in secrets.yaml
when embeddings are enabled.
"""

from __future__ import annotations

# Pack for dot notation: mem.write(), mem.search(), etc.
pack = "mem"

__ot_requires__ = [
    {
        "kind": "lib",
        "name": "PyYAML",
        "import_name": "yaml",
        "install_extra": "core",
        "purpose": "Serialize and restore memory exports",
    },
    {
        "kind": "lib",
        "name": "jmespath",
        "import_name": "jmespath",
        "install_extra": "core",
        "purpose": "Run structured memory queries",
    },
    {
        "kind": "lib",
        "name": "openai",
        "import_name": "openai",
        "install_extra": "core",
        "purpose": "Generate optional semantic embeddings",
        "optional": True,
        "activation": {"field": "embeddings_enabled", "equals": True},
    },
    {
        "kind": "lib",
        "name": "tiktoken",
        "import_name": "tiktoken",
        "install_extra": "core",
        "purpose": "Bound optional embedding input by model token limits",
        "optional": True,
        "activation": {"field": "embeddings_enabled", "equals": True},
    },
    {
        "kind": "secret",
        "name": "OPENAI_API_KEY",
        "purpose": "Authenticate optional embedding requests",
        "optional": True,
        "activation": {"field": "embeddings_enabled", "equals": True},
    },
]

config_model = "Config"

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
from otutil.tools._mem.config import Config as _Config

Config = _Config
