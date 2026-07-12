"""Directory indexer for the knowledge pack.

Walk a directory, chunk markdown files, insert into SQLite,
then run the link-graph second pass.
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urldefrag, urljoin

from loguru import logger

from ot.logging import LogEntry

if TYPE_CHECKING:
    from collections.abc import Callable

from .chunker import Chunk, chunk_file, strip_topic_roots
from .config import _get_config, _get_kb_project
from .db import (
    deserialize_meta,
    get_connection,
    serialize_embedding,
    serialize_meta,
    serialize_tags,
)

if TYPE_CHECKING:
    import sqlite3

_MD_LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")


@dataclass
class IndexResult:
    indexed: int = 0
    skipped: int = 0
    edges_added: int = 0
    errors: list[str] = field(default_factory=list)
    # Ids of every chunk inserted/updated this run (also when embeddings are
    # disabled) — consumed by `kb index --enrich`.
    chunk_ids: list[str] = field(default_factory=list)


def index_directory(
    *,
    path: str,
    db_name: str,
    overwrite: str = "skip",
    ignore: list[str] | None = None,
    on_start: Callable[[int], None] | None = None,
    on_file: Callable[[str, int], None] | None = None,
    on_embed_progress: Callable[[int, int], None] | None = None,
    on_link_progress: Callable[[int, int], None] | None = None,
) -> IndexResult:
    """Index all .md files under path into the named database.

    Args:
        path: Directory to index (absolute or relative to cwd).
        db_name: Target database name.
        overwrite: "skip" (default) — skip unchanged files; "update" — re-index changed files.
        ignore: Extra gitignore-style patterns to skip.
        on_start: Called once with total file count before the loop starts.
        on_file: Called after each file with (rel_path, chunks_indexed).
        on_embed_progress: Called after each embedding batch with (done, total).
        on_link_progress: Called after each chunk in the link-graph pass with (done, total).

    Returns:
        IndexResult with counts.
    """
    result = IndexResult()
    root = Path(path).expanduser().resolve()
    if not root.is_dir():
        result.errors.append(f"Directory not found: {root}")
        return result

    config = _get_config()
    kb_project = _get_kb_project(db_name)
    project_patterns = kb_project.index.ignore_patterns if kb_project else []
    topic_roots = kb_project.index.topic_roots if kb_project else []
    all_patterns = list(project_patterns) + (ignore or [])
    spec = _build_pathspec(all_patterns)
    from .db import _check_vec_available
    embeddings_enabled = _db_embeddings_enabled(db_name) and _check_vec_available()

    conn = get_connection(db_name)
    pending: list[tuple[str, str]] = []  # (chunk_id, content) needing embeddings

    all_files = sorted(root.rglob("*.md"))
    if on_start:
        on_start(len(all_files))

    for md_path in all_files:
        rel = md_path.relative_to(root)
        if spec and spec.match_file(str(rel)):
            result.skipped += 1
            if on_file:
                on_file(str(rel), 0)
            continue

        try:
            chunks = chunk_file(md_path, rel, min_chunk_chars=config.min_chunk_chars)
        except Exception as e:
            result.errors.append(f"{rel}: chunking failed — {e}")
            if on_file:
                on_file(str(rel), 0)
            continue

        if not chunks:
            result.skipped += 1
            if on_file:
                on_file(str(rel), 0)
            continue

        # Apply topic_roots stripping and compute depth
        for chunk in chunks:
            _apply_topic_roots(chunk, topic_roots)

        file_pending = 0
        for chunk in chunks:
            try:
                pair = _upsert_chunk(conn, chunk, overwrite, embeddings_enabled, result)
            except Exception as e:
                result.errors.append(f"{rel}: insert failed — {e}")
                continue
            if pair is not None:
                pending.append(pair)
                file_pending += 1

        if on_file:
            on_file(str(rel), file_pending)

    conn.commit()

    # Batch embed all new/updated chunks in one pass
    if pending:
        embed_err = _store_embeddings_batch(conn, pending, on_progress=on_embed_progress)
        if embed_err:
            result.errors.append(embed_err)
        conn.commit()

    # Second pass: build link graph
    result.edges_added = _build_link_graph(conn, root, on_progress=on_link_progress)
    conn.commit()

    return result


def _apply_topic_roots(chunk: Chunk, topic_roots: list[str]) -> None:
    """Strip topic_roots prefix, compute depth, and update chunk in-place."""
    canonical = chunk.topic  # before stripping (same as source_path)
    stripped = strip_topic_roots(canonical, topic_roots)
    chunk.topic = stripped
    depth = len(stripped.split("/")) if stripped else 1
    depth_tag = f"depth:{depth}"
    if depth_tag not in chunk.tags:
        chunk.tags.append(depth_tag)
    chunk.meta["depth"] = depth


def _db_embeddings_enabled(db_name: str) -> bool:
    """Check if embeddings are enabled for this database."""
    kb_project = _get_kb_project(db_name)
    if kb_project is not None:
        return kb_project.db.embeddings_enabled
    # Default: enabled
    return True


def _build_pathspec(patterns: list[str]) -> Any:
    """Build a pathspec matcher, or None if no patterns."""
    if not patterns:
        return None
    try:
        import pathspec
        return pathspec.PathSpec.from_lines("gitwildmatch", patterns)
    except ImportError:
        logger.warning(
            LogEntry(
                event="knowledge.indexer.pathspec_missing",
                patternCount=len(patterns),
                action="ignore_patterns_skipped",
            )
        )
        return None


def _upsert_chunk(
    conn: sqlite3.Connection,
    chunk: Chunk,
    overwrite: str,
    embeddings_enabled: bool,
    result: IndexResult,
) -> tuple[str, str] | None:
    """Insert or update a single chunk row using (source_path, anchor) as the dedup key.

    Returns (chunk_id, content) if the chunk needs embedding, else None.
    """
    existing = conn.execute(
        "SELECT id, content_hash FROM chunks WHERE source_path = ? AND anchor = ?",
        [chunk.source_path, chunk.anchor],
    ).fetchone()

    if existing:
        existing_id, existing_hash = existing
        if existing_hash == chunk.content_hash and overwrite == "skip":
            result.skipped += 1
            return None
        # Update — content changed, so any stored summary is stale (design D7).
        conn.execute(
            """
            UPDATE chunks
            SET topic = ?, content = ?, content_hash = ?, tags = ?, meta = ?,
                summary = NULL,
                updated_at = datetime('now')
            WHERE id = ?
            """,
            [
                chunk.topic,
                chunk.content,
                chunk.content_hash,
                serialize_tags(chunk.tags),
                serialize_meta(chunk.meta),
                existing_id,
            ],
        )
        result.indexed += 1
        result.chunk_ids.append(existing_id)
        return (existing_id, chunk.content) if embeddings_enabled else None
    else:
        chunk_id = str(uuid.uuid4())
        conn.execute(
            """
            INSERT INTO chunks (id, topic, content, content_hash, category, tags, meta, source, source_path, anchor)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                chunk_id,
                chunk.topic,
                chunk.content,
                chunk.content_hash,
                chunk.category,
                serialize_tags(chunk.tags),
                serialize_meta(chunk.meta),
                chunk.meta.get("source", ""),
                chunk.source_path,
                chunk.anchor,
            ],
        )
        result.indexed += 1
        result.chunk_ids.append(chunk_id)
        return (chunk_id, chunk.content) if embeddings_enabled else None


# Abort per-item fallback after this many consecutive failures (API outage, not content issue)
_FALLBACK_ABORT_AFTER = 5


def _store_embeddings_batch(
    conn: sqlite3.Connection,
    pending: list[tuple[str, str]],
    on_progress: Callable[[int, int], None] | None = None,
    batch_size: int | None = None,
) -> str | None:
    """Generate and store embeddings for a list of (chunk_id, content) pairs.

    Processes in sub-batches (default: config.embedding_batch_size) with retry.
    Each successful sub-batch is committed immediately so progress is durable
    even if a later batch fails. Failed sub-batches are collected as errors.

    Returns an error string summarising any failures, else None.
    """
    if not pending:
        return None
    from .db import _check_vec_available
    if not _check_vec_available():
        return "sqlite-vec not installed — embeddings skipped (install with: uv add sqlite-vec)"

    from .embedding import _get_embedding_client

    config = _get_config()
    if batch_size is None:
        batch_size = config.embedding_batch_size
    client = _get_embedding_client()
    total = len(pending)
    errors: list[str] = []
    total_failed = 0
    done = 0

    for i in range(0, total, batch_size):
        sub = pending[i : i + batch_size]
        chunk_ids = [p[0] for p in sub]
        contents = [p[1] for p in sub]

        try:
            vecs = client.embed_batch(contents, batch_size=len(sub))
            pairs: list[tuple[str, list[float]]] = list(zip(chunk_ids, vecs, strict=True))
        except Exception:
            # Batch failed — fall back to per-item embedding to isolate bad chunk(s).
            # Abort the fallback early if _FALLBACK_ABORT_AFTER consecutive items fail
            # (signals an API outage, not a content problem).
            pairs = []
            consecutive_failures = 0
            for j, (cid, text) in enumerate(zip(chunk_ids, contents, strict=True)):
                try:
                    single = client.embed_batch([text], max_attempts=1)
                    pairs.append((cid, single[0]))
                    consecutive_failures = 0
                except Exception as item_err:
                    errors.append(f"chunk {cid}: {item_err}")
                    total_failed += 1
                    consecutive_failures += 1
                    if consecutive_failures >= _FALLBACK_ABORT_AFTER:
                        # Remaining items in this sub-batch counted as failed
                        remaining = len(sub) - j - 1
                        if remaining:
                            errors.append(
                                f"{remaining} chunk(s) at offset {i + j + 1}: "
                                f"fallback aborted after {_FALLBACK_ABORT_AFTER} consecutive API failures"
                            )
                            total_failed += remaining
                        break
                if on_progress:
                    on_progress(min(done + j + 1, total), total)

        for chunk_id, vec in pairs:
            blob = serialize_embedding(vec)
            conn.execute("DELETE FROM chunks_vec WHERE chunk_id = ?", [chunk_id])
            conn.execute(
                "INSERT INTO chunks_vec(chunk_id, embedding) VALUES (?, ?)",
                [chunk_id, blob],
            )
        conn.commit()
        done += len(sub)
        if on_progress:
            on_progress(min(done, total), total)

    if errors:
        return f"Embedding storage failed for {total_failed} of {total} chunk(s): {'; '.join(errors)}"
    return None


def _build_link_graph(
    conn: sqlite3.Connection,
    _root: Path,
    on_progress: Callable[[int, int], None] | None = None,
) -> int:
    """Extract markdown hyperlinks from chunk content and insert edge rows.

    Returns number of edges inserted.
    """
    # Build url → chunk_id index from meta.url and topic; deserialize meta once per row
    url_to_id: dict[str, str] = {}
    raw_rows = conn.execute("SELECT id, topic, content, meta FROM chunks").fetchall()
    rows = [(cid, topic, content, deserialize_meta(meta_raw)) for cid, topic, content, meta_raw in raw_rows]
    for chunk_id, topic, _, meta in rows:
        url = meta.get("url", "")
        if url:
            # Normalise: strip fragment
            base_url, _ = urldefrag(url)
            url_to_id[base_url] = chunk_id
        # Also index by topic
        url_to_id[topic] = chunk_id

    total = len(rows)
    edges_added = 0
    for i, (chunk_id, _, content, meta) in enumerate(rows, 1):
        if on_progress:
            on_progress(i, total)
        base_url = meta.get("url", "")

        for match in _MD_LINK_RE.finditer(content):
            anchor_text = match.group(1)
            href = match.group(2)

            # Skip external URLs and anchors-only
            if href.startswith(("http://", "https://", "mailto:", "#")):
                # For absolute URLs, try to match against the url index
                if href.startswith(("http://", "https://")):
                    norm, _ = urldefrag(href)
                    dst_id = url_to_id.get(norm)
                    if dst_id and dst_id != chunk_id:
                        _insert_edge(conn, chunk_id, dst_id, anchor_text, "link")
                        edges_added += 1
                continue

            # Resolve relative URL against the chunk's own url
            resolved = urljoin(base_url, href) if base_url else href
            norm, _ = urldefrag(resolved)
            dst_id = url_to_id.get(norm)
            if dst_id and dst_id != chunk_id:
                _insert_edge(conn, chunk_id, dst_id, anchor_text, "link")
                edges_added += 1

    return edges_added


def _insert_edge(
    conn: sqlite3.Connection,
    src_id: str,
    dst_id: str,
    anchor_text: str,
    edge_type: str,
) -> None:
    """Insert an edge row, ignoring duplicates."""
    conn.execute(
        "INSERT OR IGNORE INTO edges (id, src_id, dst_id, edge_type, anchor_text) VALUES (?, ?, ?, ?, ?)",
        [str(uuid.uuid4()), src_id, dst_id, edge_type, anchor_text],
    )


__all__ = ["IndexResult", "_apply_topic_roots", "_build_link_graph", "_store_embeddings_batch", "index_directory"]
