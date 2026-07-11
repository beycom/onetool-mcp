"""kb.index and kb.reindex tool implementations."""
from __future__ import annotations

from typing import TYPE_CHECKING

from otpack import LogSpan

from .db import get_connection
from .indexer import _store_embeddings_batch, index_directory

if TYPE_CHECKING:
    from collections.abc import Callable


def index(
    *,
    path: str,
    db: str,
    overwrite: str = "skip",
    ignore: list[str] | None = None,
) -> str:
    """Index a directory of Markdown files into the knowledge database.

    Files are chunked, embedded (if enabled), and stored. Indexing is resumable:
    unchanged files (matching SHA-256 hash) are skipped by default.

    Args:
        path: Directory path to index
        db: Target database name
        overwrite: 'skip' (default) — skip unchanged files; 'update' — re-index changed files
        ignore: Extra gitignore-style patterns to skip (merged with config ignore_patterns)

    Returns:
        Summary of indexing results: indexed, skipped, edges_added.

    Example:
        kb.index(path='scratch/docs', db='docs')
        kb.index(path='docs/', db='mydb', overwrite='update')
    """
    with LogSpan(span="kb.index", path=path, db=db, overwrite=overwrite) as s:
        try:
            result = index_directory(path=path, db_name=db, overwrite=overwrite, ignore=ignore or [])
            s.add("indexed", result.indexed)
            s.add("skipped", result.skipped)
            s.add("edgesAdded", result.edges_added)
            summary = f"Indexed {result.indexed} chunks, skipped {result.skipped}, {result.edges_added} link edges added"
            if result.errors:
                summary += f"\nErrors ({len(result.errors)}): {'; '.join(result.errors[:3])}"
            return summary
        except Exception as e:
            s.add("error", str(e))
            return f"Error indexing '{path}': {e}"


def reindex(
    *,
    db: str,
    on_progress: Callable[[int, int], None] | None = None,
) -> str:
    """Backfill embeddings for chunks missing them in the knowledge database.

    Safe to run multiple times; skips chunks that already have embeddings.

    Args:
        db: Database name

    Returns:
        Summary of embeddings generated.

    Example:
        kb.reindex(db='docs')
    """
    with LogSpan(span="kb.reindex", db=db) as s:
        try:
            conn = get_connection(db)
            missing = conn.execute(
                "SELECT id, content FROM chunks WHERE id NOT IN (SELECT chunk_id FROM chunks_vec)"
            ).fetchall()

            if not missing:
                s.add("generated", 0)
                return "No chunks missing embeddings"

            pending = [(row[0], row[1]) for row in missing]

            before = conn.execute("SELECT COUNT(*) FROM chunks_vec").fetchone()[0]
            embed_err = _store_embeddings_batch(conn, pending, on_progress=on_progress)
            after = conn.execute("SELECT COUNT(*) FROM chunks_vec").fetchone()[0]

            # Count only embeddings actually added by this run — pre-existing
            # ones must not be reported as reindexed.
            generated = after - before
            errors = max(0, len(missing) - generated)

            s.add("generated", generated)
            s.add("errors", errors)
            result = f"Reindexed {generated} chunks"
            if errors:
                result += f" ({errors} errors)"
            if embed_err:
                result += f"\n{embed_err}"
            return result
        except Exception as e:
            s.add("error", str(e))
            return f"Error reindexing '{db}': {e}"


__all__ = ["index", "reindex"]
