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

__ot_requires__ = [
    {
        "kind": "lib",
        "name": "openai",
        "import_name": "openai",
        "install_extra": "core",
        "purpose": "Generate embeddings and grounded answers",
    },
    {
        "kind": "lib",
        "name": "sqlite-vec",
        "import_name": "sqlite_vec",
        "install_extra": "[util]",
        "purpose": "Store and search knowledge-base vectors in SQLite",
    },
    {
        "kind": "lib",
        "name": "python-frontmatter",
        "import_name": "frontmatter",
        "install_extra": "[util]",
        "purpose": "Parse Markdown document metadata",
    },
    {
        "kind": "lib",
        "name": "crawl4ai",
        "import_name": "crawl4ai",
        "install_extra": "[scrape]",
        "purpose": "Build knowledge sources by crawling websites",
        "optional": True,
    },
    {
        "kind": "secret",
        "name": "OPENAI_API_KEY",
        "purpose": "Authenticate embedding and answer-generation requests",
    },
]

config_model = "Config"

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
from otutil.tools._knowledge.config import Config as _Config

Config = _Config
