"""LLM summary enrichment for the knowledge pack (CLI-only, like index/reindex).

Populates `chunks.summary` with short LLM-generated summaries. Select-missing
semantics make every run a backfill; `force=True` re-summarises everything.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from loguru import logger

from ot.logging import LogEntry
from otpack import LogSpan

from .config import _get_config
from .db import get_connection
from .retrieval import _UNTRUSTED_CONTEXT_SYSTEM, _get_llm_client

if TYPE_CHECKING:
    import sqlite3
    from collections.abc import Callable

_DEFAULT_ENRICH_PROMPT = (
    "Summarise the following documentation chunk in 1-2 plain sentences "
    "(max ~50 words). State what it covers and when a reader would need it. "
    "No markdown, no preamble."
)

# Same retryable statuses as embedding._RETRYABLE_HTTP_STATUS; small local
# helper because _embed_batch_with_retry is embeddings-specific (design D4).
_RETRYABLE_HTTP_STATUS = {429, 500, 503}
_ENRICH_MAX_ATTEMPTS = 3
# Abort after this many consecutive failures — an outage, not a content
# problem (same value as indexer._FALLBACK_ABORT_AFTER).
_CONSECUTIVE_ABORT_AFTER = 5
# SQLite host-parameter safety: chunk `id IN (...)` selections.
_IDS_CHUNK_SIZE = 500
_MAX_SUMMARY_TOKENS = 120


@dataclass
class EnrichResult:
    enriched: int = 0
    skipped_short: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)


def _select_chunks(
    conn: sqlite3.Connection,
    *,
    force: bool,
    ids: list[str] | None,
    limit: int | None,
) -> list[tuple[str, str, str]]:
    """Select (id, topic, content) rows eligible for enrichment."""
    base = "SELECT id, topic, content FROM chunks WHERE topic != '_meta'"
    if not force:
        base += " AND (summary IS NULL OR summary = '')"

    if ids is not None:
        rows: list[tuple[str, str, str]] = []
        for i in range(0, len(ids), _IDS_CHUNK_SIZE):
            sub = ids[i : i + _IDS_CHUNK_SIZE]
            placeholders = ", ".join("?" for _ in sub)
            rows.extend(conn.execute(f"{base} AND id IN ({placeholders})", sub).fetchall())
        rows.sort(key=lambda row: row[1])
        return rows[:limit] if limit is not None else rows

    sql = base + " ORDER BY topic"
    params: list[Any] = []
    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)
    return conn.execute(sql, params).fetchall()


def _summarise_with_retry(client: Any, *, model: str, system: str, user: str) -> str:
    """One chat completion with retry on transient HTTP errors (design D4)."""
    for attempt in range(_ENRICH_MAX_ATTEMPTS):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                max_tokens=_MAX_SUMMARY_TOKENS,
            )
            return (resp.choices[0].message.content or "").strip()
        except Exception as e:
            status = getattr(e, "status_code", None)
            if status not in _RETRYABLE_HTTP_STATUS or attempt == _ENRICH_MAX_ATTEMPTS - 1:
                raise
            wait = 2.0**attempt
            logger.warning(
                LogEntry(
                    event="knowledge.enrich.retry",
                    statusCode=status,
                    waitSeconds=wait,
                    attempt=attempt + 1,
                    maxAttempts=_ENRICH_MAX_ATTEMPTS,
                    errorType=type(e).__name__,
                    error=str(e),
                )
            )
            time.sleep(wait)
    raise RuntimeError("unreachable")  # pragma: no cover


def enrich_db(
    *,
    db_name: str,
    limit: int | None = None,
    force: bool = False,
    ids: list[str] | None = None,
    on_progress: Callable[[int, int], None] | None = None,
) -> EnrichResult:
    """Generate LLM summaries for chunks missing them.

    Args:
        db_name: Target database name.
        limit: Max chunks to process this run.
        force: Re-summarise all chunks, not just those with missing summaries.
        ids: Restrict to these chunk ids (used by `kb index --enrich`).
        on_progress: Optional callback called per chunk with (done, total).

    Returns:
        EnrichResult with counts and error details.

    Raises:
        ValueError: When no LLM client is available (missing OPENAI_API_KEY) —
            a maintenance command must fail loudly.
    """
    result = EnrichResult()
    config = _get_config()
    client = _get_llm_client()
    if client is None:
        raise ValueError("OPENAI_API_KEY not configured in secrets.yaml (required for kb enrich)")

    from ot.config import get_llm_config

    model = config.enrich_model or get_llm_config().model or "gpt-4o-mini"
    prompt = config.enrich_prompt or _DEFAULT_ENRICH_PROMPT
    # Indexed content is untrusted data: keep the boundary in the system message.
    system = f"{_UNTRUSTED_CONTEXT_SYSTEM}\n\n{prompt}"

    with LogSpan(span="kb.enrich", db=db_name, force=force, limit=limit or 0) as span:
        conn = get_connection(db_name)
        rows = _select_chunks(conn, force=force, ids=ids, limit=limit)
        total = len(rows)
        uncommitted = 0
        consecutive_failures = 0

        for done, (chunk_id, topic, content) in enumerate(rows, start=1):
            content = content or ""
            if config.enrich_min_chars > 0 and len(content) < config.enrich_min_chars:
                # Empty string ≠ NULL: marks "deliberately not summarised" so
                # re-runs don't reselect; --force re-evaluates.
                conn.execute("UPDATE chunks SET summary = '' WHERE id = ?", [chunk_id])
                result.skipped_short += 1
                uncommitted += 1
            else:
                user = f"Topic: {topic}\n\n{content[: config.enrich_max_chars]}"
                try:
                    summary = _summarise_with_retry(client, model=model, system=system, user=user)
                    if not summary:
                        raise ValueError("empty LLM response")
                    conn.execute("UPDATE chunks SET summary = ? WHERE id = ?", [summary, chunk_id])
                    result.enriched += 1
                    uncommitted += 1
                    consecutive_failures = 0
                except Exception as e:
                    result.failed += 1
                    result.errors.append(f"chunk {chunk_id}: {e}")
                    consecutive_failures += 1
                    if consecutive_failures >= _CONSECUTIVE_ABORT_AFTER:
                        remaining = total - done
                        if remaining:
                            result.errors.append(
                                f"aborted after {_CONSECUTIVE_ABORT_AFTER} consecutive "
                                f"failures — {remaining} chunk(s) left unprocessed"
                            )
                        if on_progress:
                            on_progress(done, total)
                        break

            if uncommitted >= config.enrich_batch_size:
                conn.commit()
                uncommitted = 0
            if on_progress:
                on_progress(done, total)

        conn.commit()
        span.add(
            enriched=result.enriched,
            skippedShort=result.skipped_short,
            failed=result.failed,
        )
    return result


__all__ = ["EnrichResult", "enrich_db"]
