"""Knowledge pack — portable SQLite knowledge bases with hybrid search.

Indexes directories of Markdown files into SQLite with FTS5 BM25 keyword search,
sqlite-vec KNN vector search, link graph from markdown hyperlinks, and AI enrichment.

Requires OPENAI_API_KEY in secrets.yaml when embeddings are enabled.
Requires `pip install onetool-mcp[util]` for sqlite-vec and python-frontmatter.
"""

from __future__ import annotations

# Pack name for dot notation: kb.search(), kb.index(), etc.
pack = "knowledge"
pack_aliases = ("kb",)

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


def register_services(registry: object) -> None:
    """Register knowledge runtime cache reset hook."""
    from otutil.tools._knowledge.retrieval import reset_runtime_cache

    registry.register_reload_hook(reset_runtime_cache)  # type: ignore[attr-defined]


# Dependency declarations for CLI validation
__ot_requires__ = {
    "lib": [
        ("openai", "pip install openai"),
        ("sqlite_vec", "pip install sqlite-vec  (or: pip install onetool-mcp[util])"),
        (
            "frontmatter",
            "pip install python-frontmatter  (or: pip install onetool-mcp[util])",
        ),
    ],
}

from otutil.tools._knowledge import (
    append,
    ask,
    dbs,
    delete,
    grep,
    info,
    list,
    read,
    related,
    search,
    slice,
    stats,
    toc,
    update,
    write,
)
