"""Hybrid search for the knowledge pack: FTS5 BM25 + sqlite-vec KNN + RRF."""
from __future__ import annotations

import re
import sqlite3
from typing import Any

from loguru import logger

from ot.logging import LogEntry

from .db import deserialize_meta, deserialize_tags
from .embedding import generate_embedding, vec_to_bytes

_RRF_K = 60

_STOPWORDS = frozenset({
    "how", "do", "i", "what", "is", "the", "a", "an", "to", "of",
    "in", "for", "on", "with", "can", "my", "me",
})


def _fts_query(text: str) -> str:
    """Preprocess a query for FTS5: strip operator chars and remove stopwords."""
    sanitized = re.sub(r'[?!":\^*()\-]', ' ', text).strip()
    tokens = [t for t in sanitized.split() if t.lower() not in _STOPWORDS]
    return " ".join(tokens) if tokens else sanitized


def _exec_fts(
    conn: sqlite3.Connection,
    fts_q: str,
    limit: int,
    category: str | None,
) -> list[Any]:
    """Execute a single FTS5 MATCH query and return raw rows."""
    sql = """
        SELECT c.id, c.topic, c.content, c.category, c.tags, c.meta, c.hit_count,
               bm25(chunks_fts) AS score
        FROM chunks_fts
        JOIN chunks c ON c.rowid = chunks_fts.rowid
        WHERE chunks_fts MATCH ?
    """
    params: list[Any] = [fts_q]
    if category:
        sql += " AND c.category = ?"
        params.append(category)
    sql += " ORDER BY score LIMIT ?"
    params.append(limit)
    try:
        return conn.execute(sql, params).fetchall()
    except sqlite3.OperationalError as e:
        # Benign FTS5 query-syntax errors return no rows; anything else
        # (missing/corrupt table) must surface instead of silently degrading.
        if "syntax error" in str(e).lower() or "malformed match" in str(e).lower():
            logger.warning(
                LogEntry(event="knowledge.search.fts_query_error", query=fts_q, error=str(e))
            )
            return []
        logger.warning(
            LogEntry(event="knowledge.search.fts_failed", errorType=type(e).__name__, error=str(e))
        )
        raise


def search_fts(
    conn: sqlite3.Connection,
    query: str,
    limit: int,
    *,
    category: str | None = None,
) -> list[dict[str, Any]]:
    """Keyword search via FTS5 BM25."""
    # FTS5 bm25() score is negative; lower = more relevant
    fts_q = _fts_query(query)
    if not fts_q:
        return []

    rows = _exec_fts(conn, fts_q, limit, category)
    if not rows:
        # Prefix fallback: suffix each term with * for partial matching
        prefix_q = " ".join(t + "*" for t in fts_q.split())
        if prefix_q != fts_q:
            rows = _exec_fts(conn, prefix_q, limit, category)

    return [_row_to_result(r, abs(r[7])) for r in rows]


def search_vec(
    conn: sqlite3.Connection,
    query: str,
    limit: int,
    *,
    category: str | None = None,
) -> list[dict[str, Any]]:
    """Vector KNN search via sqlite-vec."""
    from .db import _require_vec
    _require_vec()

    vec = generate_embedding(query)
    blob = vec_to_bytes(vec)

    sql = """
        SELECT c.id, c.topic, c.content, c.category, c.tags, c.meta, c.hit_count,
               v.distance AS score
        FROM chunks_vec v
        JOIN chunks c ON c.id = v.chunk_id
        WHERE v.embedding MATCH ? AND k = ?
    """
    params: list[Any] = [blob, limit]
    if category:
        sql += " AND c.category = ?"
        params.append(category)
    sql += " ORDER BY v.distance"

    try:
        rows = conn.execute(sql, params).fetchall()
    except Exception as e:
        # A failing vec table (missing, corrupt, or dimension mismatch) must
        # surface — swallowing it silently turns hybrid search into FTS-only.
        logger.warning(
            LogEntry(event="knowledge.search.vec_failed", errorType=type(e).__name__, error=str(e))
        )
        raise

    # Distance is 0..2 (L2) — invert so lower distance = higher score
    return [_row_to_result(r, 1.0 / (1.0 + r[7])) for r in rows]


def search_hybrid(
    conn: sqlite3.Connection,
    query: str,
    limit: int,
    *,
    category: str | None = None,
) -> list[dict[str, Any]]:
    """Hybrid search: FTS5 + vec fused via RRF (k=60)."""
    fetch = limit * 3
    fts_results = search_fts(conn, query, fetch, category=category)
    vec_results = search_vec(conn, query, fetch, category=category)
    return _rrf_merge(fts_results, vec_results, limit)


def _rrf_merge(
    list_a: list[dict[str, Any]],
    list_b: list[dict[str, Any]],
    limit: int,
) -> list[dict[str, Any]]:
    """Reciprocal Rank Fusion: score = sum(1 / (k + rank))."""
    rrf: dict[str, float] = {}
    result_map: dict[str, dict[str, Any]] = {}

    for rank, r in enumerate(list_a, 1):
        mid = r["id"]
        rrf[mid] = rrf.get(mid, 0.0) + 1.0 / (_RRF_K + rank)
        result_map[mid] = r

    for rank, r in enumerate(list_b, 1):
        mid = r["id"]
        rrf[mid] = rrf.get(mid, 0.0) + 1.0 / (_RRF_K + rank)
        if mid not in result_map:
            result_map[mid] = r

    # Apply hit_count boost: frequently accessed chunks get up to +0.1
    for mid, r in result_map.items():
        hit = r.get("hit_count", 0) or 0
        rrf[mid] += 0.1 * min(hit, 10) / 10

    sorted_ids = sorted(rrf, key=lambda x: rrf[x], reverse=True)[:limit]
    merged = []
    for mid in sorted_ids:
        r = dict(result_map[mid])
        r["score"] = round(rrf[mid], 4)
        merged.append(r)
    return merged


def apply_metadata_filters(
    results: list[dict[str, Any]],
    *,
    source: str | None = None,
    tag: str | None = None,
    after: str | None = None,
) -> list[dict[str, Any]]:
    """Python-side metadata filtering applied after RRF."""
    filtered = []
    for r in results:
        meta = r.get("meta_dict", {})
        if source and not meta.get("source", "").startswith(source):
            continue
        if tag and tag not in r.get("tags_list", []):
            continue
        if after and r.get("created_at", "") < after:
            continue
        filtered.append(r)
    return filtered


def _row_to_result(row: tuple[Any, ...], score: float) -> dict[str, Any]:
    """Convert a DB row tuple to a result dict."""
    meta = deserialize_meta(row[5])
    tags = deserialize_tags(row[4])
    return {
        "id": row[0],
        "topic": row[1],
        "content": row[2],
        "category": row[3],
        "tags": row[4],
        "meta": row[5],
        "hit_count": row[6],
        "score": round(score, 4),
        # Parsed versions for filtering
        "tags_list": tags,
        "meta_dict": meta,
    }


__all__ = [
    "_fts_query",
    "_rrf_merge",
    "apply_metadata_filters",
    "search_fts",
    "search_hybrid",
    "search_vec",
]
