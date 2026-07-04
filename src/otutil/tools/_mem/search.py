"""Memory search: grep, semantic, keyword, and hybrid."""
from __future__ import annotations

import builtins
import re
from typing import Any

from otpack import LogSpan
from otutil.tools._content_util import grep_lines

from .config import _get_config
from .content import _tags_filter_sql, _topic_filter
from .db import _deserialize_tags, _get_connection, _serialize_embedding
from .embedding import _generate_embedding

_builtins_list = builtins.list


def grep(
    *,
    pattern: str,
    topic: str | None = None,
    category: str | None = None,
    tags: list[str] | None = None,
    context: int = 2,
    case_sensitive: bool = True,
    limit: int = 50,
    max_per_memory: int = 10,
    fixed_strings: bool = False,
) -> str:
    """Regex search across memory content with line-level results.

    Like ripgrep but for memory content stored in SQLite. Returns matching
    lines grouped by topic with line numbers, context lines, and slice hints.

    Args:
        pattern: Regex pattern (or literal string if fixed_strings=True)
        topic: Optional topic prefix filter (e.g., "docs/" matches all under docs)
        category: Optional category filter
        tags: Optional tag filter (matches memories with any of these tags)
        context: Number of context lines before and after each match (default 2)
        case_sensitive: Whether matching is case-sensitive (default True)
        limit: Maximum number of memories to search (default 50)
        max_per_memory: Maximum match groups per memory (default 10)
        fixed_strings: If True, treat pattern as a literal string (default False)

    Returns:
        Formatted results with match markers, line numbers, and slice hints.

    Example:
        mem.grep(pattern="def \\\\w+\\\\(")
        mem.grep(pattern="TODO", context=3, case_sensitive=False)
        mem.grep(pattern="foo.bar()", fixed_strings=True, topic="docs/")
    """
    with LogSpan(span="mem.grep", pattern=pattern, topic=topic, limit=limit) as s:
        try:
            # Validate / compile regex
            if fixed_strings:
                pattern = re.escape(pattern)

            flags = 0 if case_sensitive else re.IGNORECASE
            try:
                regex = re.compile(pattern, flags)
            except re.error as e:
                return f"Error: Invalid regex pattern: {e}"

            conn = _get_connection()

            sql = "SELECT id, topic, content FROM memories WHERE 1=1"
            params: _builtins_list[Any] = []

            topic_sql, topic_params = _topic_filter(topic)
            sql += topic_sql
            params.extend(topic_params)

            if category:
                sql += " AND category = ?"
                params.append(category)

            if tags:
                tags_sql, tags_params = _tags_filter_sql(tags)
                sql += tags_sql
                params.extend(tags_params)

            sql += " ORDER BY relevance DESC, updated_at DESC LIMIT ?"
            params.append(limit)

            rows = conn.execute(sql, params).fetchall()

            if not rows:
                s.add("resultCount", 0)
                return f"No matches found for: {pattern}"

            # Line-level matching
            output_parts: _builtins_list[str] = []
            total_matches = 0

            for _row_id, row_topic, content in rows:
                groups = grep_lines(content, regex, context=context, max_groups=max_per_memory)
                if not groups:
                    continue

                match_count = sum(1 for group in groups for _, _, is_match in group if is_match)
                total_matches += match_count
                blocks: _builtins_list[str] = []
                for group in groups:
                    block_lines: _builtins_list[str] = []
                    for ln, line, is_match in group:
                        marker = ">" if is_match else " "
                        block_lines.append(f"{marker} {ln:4d} | {line}")
                    blocks.append("\n".join(block_lines))

                # Slice hint: overall line range (lineno is already 1-based)
                first_line = groups[0][0][0]
                last_line = groups[-1][-1][0]
                slice_hint = f"[slice: {first_line}-{last_line}]"

                header = f"## {row_topic} ({match_count} match{'es' if match_count != 1 else ''}) {slice_hint}"
                output_parts.append(header + "\n" + "\n  ...\n".join(blocks))

            if not output_parts:
                s.add("resultCount", 0)
                return f"No matches found for: {pattern}"

            s.add("resultCount", total_matches)
            s.add("memoryCount", len(output_parts))
            summary = f"Found {total_matches} match{'es' if total_matches != 1 else ''} across {len(output_parts)} {'memory' if len(output_parts) == 1 else 'memories'}\n\n"
            return summary + "\n\n".join(output_parts)

        except Exception as e:
            s.add("error", str(e))
            return f"Error in grep: {e}"


def search(
    *,
    query: str,
    mode: str = "semantic",
    topic: str | None = None,
    category: str | None = None,
    limit: int | None = None,
    tags: list[str] | None = None,
    extract: int | None = None,
) -> str:
    """Search memories by semantic similarity, keyword matching, or hybrid.

    Args:
        query: Search query text
        mode: Search mode - "semantic" (vector cosine), "keyword" (LIKE), or "hybrid" (RRF)
        topic: Optional topic prefix filter (e.g., "projects/" matches all under projects)
        category: Optional category filter
        limit: Maximum results (default: config search_limit)
        tags: Optional tag filter (matches memories with any of these tags)
        extract: Character limit for content extract (default: config search_extract, 0 = full content)

    Returns:
        Formatted search results with scores.

    Example:
        mem.search(query="authentication patterns")
        mem.search(query="database", mode="keyword", topic="projects/")
        mem.search(query="error handling", mode="hybrid", category="mistake")
        mem.search(query="rules", extract=500)
    """
    config = _get_config()
    if limit is None:
        limit = config.search_limit
    if extract is None:
        extract = config.search_extract

    if mode not in ("semantic", "keyword", "hybrid"):
        return f"Error: Invalid mode '{mode}'. Must be 'semantic', 'keyword', or 'hybrid'"

    with LogSpan(span="mem.search", query=query, mode=mode, topic=topic, limit=limit) as s:
        try:
            if mode in ("semantic", "hybrid") and not config.embeddings_enabled:
                return "Semantic search requires embeddings. Enable with: tools.mem.embeddings_enabled: true"

            conn = _get_connection()

            if mode in ("semantic", "hybrid"):
                has_embeddings = conn.execute(
                    "SELECT 1 FROM memories WHERE embedding IS NOT NULL LIMIT 1"
                ).fetchone()
                if not has_embeddings:
                    return "No embeddings found. Run mem.reindex(dry_run=False) to generate them."

            if mode == "semantic":
                results = _search_semantic(conn, query, topic, category, tags, limit)
            elif mode == "keyword":
                results = _search_keyword(conn, query, topic, category, tags, limit)
            else:
                results = _search_hybrid(conn, query, topic, category, tags, limit)

            if not results:
                s.add("resultCount", 0)
                return f"No memories found for: {query}"

            s.add("resultCount", len(results))
            return _format_search_results(results, query, extract)

        except Exception as e:
            s.add("error", str(e))
            return f"Error searching memories: {e}"


def _search_semantic(
    conn: Any,
    query: str,
    topic: str | None,
    category: str | None,
    tags: list[str] | None,
    limit: int,
) -> list[dict[str, Any]]:
    """Semantic search using vector cosine similarity."""
    embedding = _generate_embedding(query)
    query_blob = _serialize_embedding(embedding)

    sql = """
        SELECT id, topic, content, category, tags, relevance, access_count,
               cosine_similarity(embedding, ?) as score
        FROM memories
        WHERE embedding IS NOT NULL
    """
    params: list[Any] = [query_blob]

    topic_sql, topic_params = _topic_filter(topic)
    sql += topic_sql
    params.extend(topic_params)

    if category:
        sql += " AND category = ?"
        params.append(category)

    if tags:
        tags_sql, tags_params = _tags_filter_sql(tags)
        sql += tags_sql
        params.extend(tags_params)

    sql += " ORDER BY score DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(sql, params).fetchall()
    return [
        {
            "id": r[0], "topic": r[1], "content": r[2], "category": r[3],
            "tags": _deserialize_tags(r[4]), "relevance": r[5], "access_count": r[6],
            "score": round(r[7], 4) if r[7] is not None else 0.0,
        }
        for r in rows
    ]


def _search_keyword(
    conn: Any,
    query: str,
    topic: str | None,
    category: str | None,
    tags: list[str] | None,
    limit: int,
) -> list[dict[str, Any]]:
    """Pattern search using LIKE matching (case-insensitive in SQLite by default)."""
    sql = """
        SELECT id, topic, content, category, tags, relevance, access_count
        FROM memories
        WHERE (content LIKE ? ESCAPE '\\' OR topic LIKE ? ESCAPE '\\')
    """
    # Escape LIKE special characters so they match literally
    escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    like_pattern = f"%{escaped}%"
    params: list[Any] = [like_pattern, like_pattern]

    topic_sql, topic_params = _topic_filter(topic)
    sql += topic_sql
    params.extend(topic_params)

    if category:
        sql += " AND category = ?"
        params.append(category)

    if tags:
        tags_sql, tags_params = _tags_filter_sql(tags)
        sql += tags_sql
        params.extend(tags_params)

    sql += " ORDER BY relevance DESC, updated_at DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(sql, params).fetchall()
    return [
        {
            "id": r[0], "topic": r[1], "content": r[2], "category": r[3],
            "tags": _deserialize_tags(r[4]), "relevance": r[5], "access_count": r[6], "score": 1.0,
        }
        for r in rows
    ]


def _search_hybrid(
    conn: Any,
    query: str,
    topic: str | None,
    category: str | None,
    tags: list[str] | None,
    limit: int,
) -> list[dict[str, Any]]:
    """Hybrid search combining semantic and pattern results via RRF.

    Uses Reciprocal Rank Fusion: rrf_score = sum(1 / (k + rank))
    """
    k = 60  # RRF constant

    # Get both result sets (fetch more than limit for better fusion)
    fetch_limit = limit * 3
    semantic_results = _search_semantic(conn, query, topic, category, tags, fetch_limit)
    pattern_results = _search_keyword(conn, query, topic, category, tags, fetch_limit)

    # Build RRF scores
    rrf_scores: dict[str, float] = {}
    result_map: dict[str, dict[str, Any]] = {}

    for rank, r in enumerate(semantic_results, 1):
        mid = r["id"]
        rrf_scores[mid] = rrf_scores.get(mid, 0) + 1.0 / (k + rank)
        result_map[mid] = r

    for rank, r in enumerate(pattern_results, 1):
        mid = r["id"]
        rrf_scores[mid] = rrf_scores.get(mid, 0) + 1.0 / (k + rank)
        if mid not in result_map:
            result_map[mid] = r

    # Sort by RRF score and return top N
    sorted_ids = sorted(rrf_scores, key=lambda x: rrf_scores[x], reverse=True)[:limit]
    results = []
    for mid in sorted_ids:
        r = result_map[mid]
        r["score"] = round(rrf_scores[mid], 4)
        results.append(r)

    return results


def _format_search_results(results: list[dict[str, Any]], query: str, extract: int) -> str:
    """Format search results for output."""
    lines = [f"Found {len(results)} memories for: {query}\n"]
    for i, r in enumerate(results, 1):
        if extract > 0:
            content_preview = r["content"][:extract]
            if len(r["content"]) > extract:
                content_preview += "..."
        else:
            content_preview = r["content"]
        tags_str = ", ".join(r["tags"]) if r["tags"] else "none"
        lines.append(
            f"{i}. [{r['category']}] {r['topic']} (score: {r['score']})\n"
            f"   Tags: {tags_str} | Relevance: {r['relevance']} | Accessed: {r['access_count']}x\n"
            f"   {content_preview}\n"
            f"   ID: {r['id']}\n"
        )
    return "\n".join(lines)


__all__ = [
    "_format_search_results",
    "_search_hybrid",
    "_search_keyword",
    "_search_semantic",
    "grep",
    "search",
]
