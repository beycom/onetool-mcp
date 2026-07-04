"""Retrieval and synthesis tools: kb.search, kb.ask, kb.related."""
from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING, Any, cast

from ot.utils.factory import lazy_client
from otpack import LogSpan

from .config import _get_config
from .db import deserialize_meta, deserialize_tags, get_connection, use_connection
from .search import apply_metadata_filters, search_fts, search_hybrid, search_vec

if TYPE_CHECKING:
    from openai import OpenAI


def _create_llm_client() -> OpenAI | None:
    """Create OpenAI client for LLM reranking and synthesis."""
    try:
        from openai import OpenAI

        from ot.config import get_llm_config
        from otpack import get_secret

        api_key = get_secret("OPENAI_API_KEY") or ""
        if not api_key:
            return None
        config = _get_config()
        base_url = config.base_url or get_llm_config().base_url or None
        return OpenAI(api_key=api_key, base_url=base_url)
    except Exception:
        return None


_get_llm_client = lazy_client(_create_llm_client)


def reset_runtime_cache() -> None:
    """Reset module-level runtime caches.

    Called by ot.reload() so rotated credentials/base URLs are picked up
    without requiring a process restart.
    """
    cast("Any", _get_llm_client).reset()


def search(
    *,
    query: str,
    db: str,
    mode: str = "hybrid",
    k: int | None = None,
    source: str | None = None,
    tag: str | None = None,
    category: str | None = None,
    after: str | None = None,
) -> str:
    """Search the knowledge base using hybrid FTS5 + vector retrieval.

    Args:
        query: Search query text
        db: Database name
        mode: Search mode — 'hybrid' (default), 'semantic' (vector-only), 'keyword' (FTS5-only)
        k: Maximum results (default: config search_limit)
        source: Filter by meta.source prefix
        tag: Filter by tag (exact match)
        category: Filter by category
        after: Filter by created_at >= this ISO date string

    Returns:
        Formatted search results.

    Example:
        kb.search(query='list comprehension', db='docs')
        kb.search(query='async await', db='docs', mode='keyword', k=5)
    """
    if mode not in ("hybrid", "semantic", "keyword"):
        return f"Error: Invalid mode '{mode}'. Must be 'hybrid', 'semantic', or 'keyword'"

    config = _get_config()
    limit = k if k is not None else config.search_limit

    with LogSpan(span="kb.search", query=query, db=db, mode=mode, k=limit) as s:
        try:
            conn = get_connection(db)

            if mode == "hybrid":
                results = search_hybrid(conn, query, limit * 3, category=category)
            elif mode == "semantic":
                results = search_vec(conn, query, limit * 3, category=category)
            else:
                results = search_fts(conn, query, limit * 3, category=category)

            # Python-side metadata filters
            if source or tag or after:
                results = apply_metadata_filters(results, source=source, tag=tag, after=after)

            results = results[:limit]

            # Increment hit_count asynchronously (fire-and-forget)
            if results:
                ids = [r["id"] for r in results]
                _increment_hit_counts(db, ids)

            s.add("resultCount", len(results))
            if not results:
                return f"No results found for: {query}"

            extract = config.search_extract
            lines = [f"Found {len(results)} results for: {query}\n"]
            for i, r in enumerate(results, 1):
                content = r["content"]
                if extract > 0 and len(content) > extract:
                    content = content[:extract] + "..."
                tags_str = ", ".join(r["tags_list"]) if r["tags_list"] else "none"
                meta = r["meta_dict"]
                url = meta.get("url", "")
                url_part = f"\n   URL: {url}" if url else ""
                lines.append(
                    f"{i}. [{r['category']}] {r['topic']} (score: {r['score']})\n"
                    f"   Tags: {tags_str}{url_part}\n"
                    f"   {content}\n"
                    f"   ID: {r['id']}"
                )
            return "\n".join(lines)

        except Exception as e:
            s.add("error", str(e))
            return f"Error searching '{db}': {e}"


def ask(
    *,
    query: str,
    db: str,
    k: int = 10,
    rerank: bool = True,
    expand: bool = False,
) -> str:
    """Retrieve relevant chunks and synthesise an answer with citations.

    Retrieve → (optional rerank via LLM) → (optional graph expand) → synthesise.

    Args:
        query: Question to answer
        db: Database name
        k: Number of candidate chunks to retrieve (default 10)
        rerank: Re-rank candidates via batched LLM scoring (default True)
        expand: Include 1-hop graph neighbours of top chunks (default False)

    Returns:
        Synthesised answer with source citations.

    Example:
        kb.ask(query='How do I use list comprehensions?', db='docs')
    """
    with LogSpan(span="kb.ask", query=query, db=db, k=k) as s:
        try:
            conn = get_connection(db)

            # 1. Retrieve
            try:
                results = search_hybrid(conn, query, k * 2)
            except Exception:
                results = search_fts(conn, query, k * 2)
            results = results[:k]

            if not results:
                return f"No relevant entries found for: {query}"

            # 2. Optional: graph expand (add 1-hop neighbours)
            if expand and results:
                results = _graph_expand(conn, results, limit=k)

            # 3. Optional: rerank
            if rerank and results:
                results = _llm_rerank(query, results)

            # 4. Synthesise
            context_parts = []
            citations = []
            for i, r in enumerate(results[:k], 1):
                context_parts.append(f"[{i}] {r['topic']}\n{r['content'][:1000]}")
                meta = r["meta_dict"]
                url = meta.get("url", "")
                citations.append({"num": i, "topic": r["topic"], "url": url})

            context = "\n\n---\n\n".join(context_parts)
            answer = _synthesise(query, context)

            s.add("chunkCount", len(results))

            cite_lines = [f"  [{c['num']}] {c['topic']}" + (f" ({c['url']})" if c["url"] else "") for c in citations]
            return f"{answer}\n\n**Sources:**\n" + "\n".join(cite_lines)

        except Exception as e:
            s.add("error", str(e))
            return f"Error in kb.ask: {e}"


def related(
    *,
    topic: str,
    db: str,
    direction: str = "out",
    depth: int = 1,
) -> str:
    """Return chunks connected by link edges to the given topic.

    Args:
        topic: Topic identifier to start from
        db: Database name
        direction: 'out' (links from), 'in' (links to), or 'both'
        depth: Traversal depth — 1 or 2

    Returns:
        Formatted list of related chunks with anchor text.

    Example:
        kb.related(topic='guides/move', db='docs', direction='out', depth=1)
    """
    if direction not in ("out", "in", "both"):
        return f"Error: Invalid direction '{direction}'. Must be 'out', 'in', or 'both'"
    if depth not in (1, 2):
        return "Error: depth must be 1 or 2"

    with LogSpan(span="kb.related", topic=topic, db=db, direction=direction, depth=depth):
        try:
            conn = get_connection(db)
            row = conn.execute("SELECT id FROM chunks WHERE topic = ?", [topic]).fetchone()
            if not row:
                return f"Error: No entry found for topic '{topic}'"
            chunk_id = row[0]

            neighbours = _get_neighbours(conn, chunk_id, direction, depth)
            if not neighbours:
                return f"No related entries found for '{topic}'"

            lines = [f"Related entries for '{topic}' ({direction}, depth={depth}):\n"]
            for n in neighbours:
                anchor = f"  (via: {n['anchor_text']})" if n.get("anchor_text") else ""
                hop = f" [depth {n['depth']}]" if depth > 1 else ""
                lines.append(f"  {n['topic']}{hop}{anchor}")
            return "\n".join(lines)
        except Exception as e:
            return f"Error in kb.related: {e}"


def _get_neighbours(
    conn: Any,
    chunk_id: str,
    direction: str,
    depth: int,
) -> list[dict[str, Any]]:
    """Get 1- or 2-hop neighbours via edge traversal."""
    seen: set[str] = {chunk_id}
    results: list[dict[str, Any]] = []
    queue: deque[tuple[str, int]] = deque([(chunk_id, 1)])

    while queue:
        current_id, current_depth = queue.popleft()
        if current_depth > depth:
            break

        rows = _get_direct_neighbours(conn, current_id, direction)
        for nb_id, nb_topic, anchor_text in rows:
            if nb_id in seen:
                continue
            seen.add(nb_id)
            results.append({"id": nb_id, "topic": nb_topic, "anchor_text": anchor_text, "depth": current_depth})
            if current_depth < depth:
                queue.append((nb_id, current_depth + 1))

    return results


def _get_direct_neighbours(
    conn: Any,
    chunk_id: str,
    direction: str,
) -> list[tuple[str, str, str]]:
    """Get direct (1-hop) neighbours."""
    if direction in ("out", "both"):
        out_rows = conn.execute(
            "SELECT c.id, c.topic, e.anchor_text FROM edges e JOIN chunks c ON c.id = e.dst_id WHERE e.src_id = ?",
            [chunk_id],
        ).fetchall()
    else:
        out_rows = []

    if direction in ("in", "both"):
        in_rows = conn.execute(
            "SELECT c.id, c.topic, e.anchor_text FROM edges e JOIN chunks c ON c.id = e.src_id WHERE e.dst_id = ?",
            [chunk_id],
        ).fetchall()
    else:
        in_rows = []

    return list(out_rows) + list(in_rows)


def _graph_expand(conn: Any, results: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    """Add 1-hop outbound neighbours of top-k chunks (deduplicated)."""
    seen_ids = {r["id"] for r in results}
    extra = []
    for r in results:
        rows = conn.execute(
            "SELECT c.id, c.topic, c.content, c.category, c.tags, c.meta, c.hit_count "
            "FROM edges e JOIN chunks c ON c.id = e.dst_id WHERE e.src_id = ?",
            [r["id"]],
        ).fetchall()
        for row in rows:
            if row[0] not in seen_ids:
                seen_ids.add(row[0])
                meta = deserialize_meta(row[5])
                tags = deserialize_tags(row[4])
                extra.append({
                    "id": row[0], "topic": row[1], "content": row[2],
                    "category": row[3], "tags": row[4], "meta": row[5],
                    "hit_count": row[6], "score": 0.0,
                    "tags_list": tags, "meta_dict": meta,
                })
    combined = results + extra
    return combined[:limit]


def _llm_rerank(query: str, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Re-rank results via a single batched LLM scoring call."""
    try:
        client = _get_llm_client()
        if client is None:
            return results

        config = _get_config()
        from ot.config import get_llm_config
        model = config.enrich_model or get_llm_config().model or "gpt-4o-mini"

        snippets = "\n\n".join(
            f"[{i}] {r['topic']}\n{r['content'][:500]}"
            for i, r in enumerate(results, 1)
        )
        prompt = (
            f"Query: {query}\n\n"
            f"Rate each passage for relevance to the query on a scale of 1-10.\n"
            f"Respond with only a comma-separated list of scores, one per passage.\n\n"
            f"{snippets}"
        )
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=100,
        )
        scores_str = resp.choices[0].message.content or ""
        scores = [float(x.strip()) for x in scores_str.split(",") if x.strip().replace(".", "").isdigit()]
        if len(scores) == len(results):
            return [r for _, r in sorted(zip(scores, results, strict=True), key=lambda x: x[0], reverse=True)]
    except Exception:
        pass
    return results


def _synthesise(query: str, context: str) -> str:
    """Synthesise an answer from retrieved context using an LLM."""
    try:
        client = _get_llm_client()
        if client is None:
            return "(LLM synthesis requires OPENAI_API_KEY — here are the retrieved chunks:)\n\n" + context[:2000]

        config = _get_config()
        from ot.config import get_llm_config
        model = config.enrich_model or get_llm_config().model or "gpt-4o-mini"
        prompt = (
            f"Answer the following question based on the provided context. "
            f"Be concise and cite sources by their [N] numbers.\n\n"
            f"Question: {query}\n\n"
            f"Context:\n{context}"
        )
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000,
        )
        return resp.choices[0].message.content or ""
    except Exception as e:
        return f"(Synthesis failed: {e})\n\nRetrieved context:\n{context[:2000]}"


def _increment_hit_counts(db_name: str, chunk_ids: list[str]) -> None:
    """Increment hit_count for retrieved chunks (fire-and-forget)."""
    try:
        if not chunk_ids:
            return
        placeholders = ", ".join("?" for _ in chunk_ids)
        with use_connection(db_name) as conn:
            conn.execute(
                f"UPDATE chunks SET hit_count = hit_count + 1 WHERE id IN ({placeholders})",
                chunk_ids,
            )
            conn.commit()
    except Exception:
        pass


__all__ = ["ask", "related", "reset_runtime_cache", "search"]
