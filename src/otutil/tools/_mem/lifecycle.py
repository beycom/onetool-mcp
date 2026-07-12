"""Memory lifecycle: decay, stats, embed, flush."""
from __future__ import annotations

import math
import time
from datetime import UTC, datetime
from typing import Any

from otpack import LogSpan

from .config import _get_config
from .content import _topic_filter
from .db import (
    _check_fts_available,
    _check_vec_available,
    _get_connection,
    _serialize_embedding,
    _sync_vec_index,
    _use_connection,
)
from .embedding import _generate_embedding


def decay(
    *,
    dry_run: bool = True,
) -> str:
    """Apply importance decay to all memories based on age and access patterns.

    Formula: score = relevance * 0.5^(age_days/half_life) * (1 + log(access+1) * 0.1)

    Args:
        dry_run: If True (default), only show decay scores without modifying

    Returns:
        Decay analysis or update confirmation.

    Example:
        mem.decay(dry_run=True)
        mem.decay(dry_run=False)
    """
    with LogSpan(span="mem.decay", dryRun=dry_run) as s:
        try:
            config = _get_config()
            half_life = config.decay_half_life_days
            conn = _get_connection()

            rows = conn.execute(
                "SELECT id, topic, relevance, access_count, created_at FROM memories"
            ).fetchall()

            if not rows:
                return "No memories to decay"

            now = datetime.now(UTC)
            decay_results = []

            for r in rows:
                memory_id, topic, relevance, access_count, created_at_str = r
                # SQLite stores timestamps as ISO text strings
                created_at = datetime.fromisoformat(created_at_str)
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=UTC)
                age_days = (now - created_at).total_seconds() / 86400

                decay_factor = 0.5 ** (age_days / half_life)
                access_boost = 1 + math.log(access_count + 1) * 0.1
                decayed_score = relevance * decay_factor * access_boost
                new_relevance = max(1, min(relevance, round(decayed_score)))

                decay_results.append({
                    "id": memory_id,
                    "topic": topic,
                    "old_relevance": relevance,
                    "new_relevance": new_relevance,
                    "age_days": round(age_days, 1),
                    "access_count": access_count,
                })

            s.add("memoryCount", len(decay_results))

            if dry_run:
                lines = [f"Decay preview ({len(decay_results)} memories, half_life={half_life}d):\n"]
                changed = [d for d in decay_results if d["old_relevance"] != d["new_relevance"]]
                for d in changed[:20]:
                    lines.append(
                        f"  {d['topic']}: {d['old_relevance']} -> {d['new_relevance']} "
                        f"(age={d['age_days']}d, accessed={d['access_count']}x)"
                    )
                if not changed:
                    lines.append("  No changes needed")
                elif len(changed) > 20:
                    lines.append(f"  ... and {len(changed) - 20} more")
                return "\n".join(lines)

            updated = 0
            with _use_connection() as conn:
                for d in decay_results:
                    if d["old_relevance"] != d["new_relevance"]:
                        conn.execute(
                            "UPDATE memories SET relevance = ? WHERE id = ?",
                            [d["new_relevance"], d["id"]],
                        )
                        updated += 1

                conn.commit()
            s.add("updated", updated)
            return f"Applied decay to {updated} memories (half_life={half_life}d)"

        except Exception as e:
            s.add("error", str(e))
            return f"Error applying decay: {e}"


def _vec_index_status(conn: Any) -> str:
    """Vector index status line for stats(): row count or fallback marker."""
    if not _check_vec_available():
        return "scan-fallback"
    vec_rows = conn.execute("SELECT COUNT(*) FROM memories_vec").fetchone()[0]
    return f"sqlite-vec ({vec_rows} rows)"


def stats() -> str:
    """Show memory statistics - counts, sizes, category breakdown, topic tree.

    Returns:
        Formatted statistics.

    Example:
        mem.stats()
    """
    with LogSpan(span="mem.stats") as s:
        try:
            conn = _get_connection()

            total = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
            if total == 0:
                return "No memories stored"

            # Category breakdown
            categories = conn.execute(
                "SELECT category, COUNT(*) as cnt FROM memories GROUP BY category ORDER BY cnt DESC"
            ).fetchall()

            # Topic tree (top-level topics)
            topics = conn.execute(
                """
                SELECT
                    CASE WHEN instr(topic, '/') > 0
                         THEN substr(topic, 1, instr(topic, '/') - 1)
                         ELSE topic
                    END as root_topic,
                    COUNT(*) as cnt
                FROM memories
                GROUP BY root_topic
                ORDER BY cnt DESC
                """
            ).fetchall()

            # Size stats
            size_stats = conn.execute(
                "SELECT SUM(length(content)), AVG(length(content)), MAX(length(content)) FROM memories"
            ).fetchone()

            # History count
            history_count = conn.execute("SELECT COUNT(*) FROM memory_history").fetchone()[0]

            # Embedding stats
            without_embeddings = conn.execute(
                "SELECT COUNT(*) FROM memories WHERE embedding IS NULL"
            ).fetchone()[0]
            config = _get_config()

            s.add("total", total)

            # Access embedding module state via lazy import to get mutable references
            from . import embedding as _emb

            lines = [
                "Memory Statistics:\n",
                f"  Total memories: {total}",
                f"  History entries: {history_count}",
                f"  Total content: {size_stats[0]:,} chars",
                f"  Avg content: {int(size_stats[1]):,} chars",
                f"  Max content: {size_stats[2]:,} chars",
                f"\nEmbeddings: {'enabled' if config.embeddings_enabled else 'disabled'}",
                f"  With embeddings: {total - without_embeddings}",
                f"  Without embeddings: {without_embeddings}",
                f"  Pending in queue: {_emb._embedding_queue.qsize()}",
                f"  Embedding errors: {_emb._embedding_errors}",
                "\nSearch indexes:",
                f"  Keyword: {'fts5' if _check_fts_available() else 'like-fallback'}",
                f"  Vector: {_vec_index_status(conn)}",
                "\nCategories:",
            ]
            for cat, cnt in categories:
                lines.append(f"  {cat}: {cnt}")

            lines.append("\nTopics:")
            for topic, cnt in topics:
                lines.append(f"  {topic}/: {cnt}")

            return "\n".join(lines)

        except Exception as e:
            s.add("error", str(e))
            return f"Error getting stats: {e}"


def reindex(
    *,
    topic: str | None = None,
    limit: int = 100,
    dry_run: bool = True,
) -> str:
    """Backfill or update vector embeddings for memories missing them.

    Use after enabling embeddings_enabled or after mem.load() to generate
    embeddings for imported records.

    Args:
        topic: Optional topic prefix filter
        limit: Maximum memories to process (default: 100)
        dry_run: If True, only report count without generating (default: True)

    Returns:
        Summary of backfill results.

    Example:
        mem.reindex(dry_run=True)           # Preview count
        mem.reindex(dry_run=False)           # Generate embeddings
        mem.reindex(topic="projects/", dry_run=False)  # Scoped backfill
    """
    config = _get_config()
    if not config.embeddings_enabled:
        return "Embeddings are disabled. Enable with: tools.mem.embeddings_enabled: true"

    with LogSpan(span="mem.reindex", topic=topic, limit=limit, dryRun=dry_run) as s:
        try:
            conn = _get_connection()

            sql = "SELECT id, content FROM memories WHERE embedding IS NULL"
            params: list[Any] = []
            if topic:
                topic_sql, topic_params = _topic_filter(topic)
                sql += topic_sql
                params.extend(topic_params)
            sql += " LIMIT ?"
            params.append(limit)

            rows = conn.execute(sql, params).fetchall()

            if not rows:
                return "All memories already have embeddings"

            if dry_run:
                s.add("count", len(rows))
                return f"Found {len(rows)} memories without embeddings. Run with dry_run=False to generate."

            generated = 0
            failed = 0
            first_error: str | None = None
            for memory_id, content in rows:
                try:
                    # Embedding API call happens outside the DB lock
                    embedding = _generate_embedding(content)
                except Exception as e:
                    failed += 1
                    if first_error is None:
                        first_error = str(e)
                    continue
                # Commit per memory so one failure doesn't lose earlier progress
                with _use_connection() as conn:
                    conn.execute(
                        "UPDATE memories SET embedding = ? WHERE id = ?",
                        [_serialize_embedding(embedding), memory_id],
                    )
                    _sync_vec_index(conn, memory_id, embedding)
                    conn.commit()
                generated += 1

            s.add("generated", generated)
            if failed:
                s.add("failed", failed)
                return (
                    f"Generated embeddings for {generated} memories "
                    f"({failed} failed; first error: {first_error})"
                )
            return f"Generated embeddings for {generated} memories"

        except Exception as e:
            s.add("error", str(e))
            return f"Error generating embeddings: {e}"


def flush(*, timeout: float = 60.0) -> str:
    """Wait for pending background embeddings to complete.

    Args:
        timeout: Maximum seconds to wait (default: 60)

    Returns:
        Completion status, or an error if the wait times out or the
        background worker has died.

    Example:
        mem.flush()
        mem.flush(timeout=10)
    """
    # Access embedding module state via lazy import to get mutable references
    from . import embedding as _emb

    if not _emb._embedding_worker_started:
        return "No background embeddings pending"
    try:
        deadline = time.monotonic() + timeout
        while _emb._embedding_queue.unfinished_tasks:
            worker = _emb._embedding_worker_thread
            if worker is None or not worker.is_alive():
                return (
                    "Error: embedding worker is not running "
                    f"({_emb._embedding_queue.qsize()} jobs pending)"
                )
            if time.monotonic() >= deadline:
                return (
                    f"Error: flush timed out after {timeout}s "
                    f"({_emb._embedding_queue.qsize()} jobs still pending)"
                )
            time.sleep(0.05)
        return "All pending embeddings completed"
    except Exception as e:
        return f"Error: {e}"


__all__ = ["decay", "flush", "reindex", "stats"]
