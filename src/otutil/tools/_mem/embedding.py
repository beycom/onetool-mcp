"""OpenAI-compatible embedding generation and background worker.

Generation is a thin adapter over :class:`otpack.EmbeddingClient`
(``long_text="mean"``: over-limit texts are window-embedded and averaged).
The background queue/worker machinery stays here.
"""
from __future__ import annotations

import queue
import threading
import time

from loguru import logger

from ot.config import get_embeddings_config
from ot.logging import LogEntry
from otpack import EmbeddingClient, get_secret

from .config import _get_config
from .db import _serialize_embedding, _sync_vec_index, _use_connection

# Bounded queue: stores only memory IDs (not content) to avoid memory bloat.
# maxsize=1000 bounds memory usage.
_embedding_queue: queue.Queue[str] = queue.Queue(maxsize=1000)
_embedding_worker_started = False
_embedding_worker_thread: threading.Thread | None = None
_embedding_worker_lock = threading.Lock()
_embedding_errors: int = 0  # Surfaced in mem.stats()
_embedding_dropped: int = 0  # Count dropped jobs when queue is saturated

# Module-cached client keyed on the resolved inputs so config reloads rebuild it.
_client: EmbeddingClient | None = None
_client_key: tuple[str, str, str, int, int, float] | None = None
_client_lock = threading.Lock()


def _get_embedding_client() -> EmbeddingClient:
    """Get (or build) the shared EmbeddingClient from resolved config values."""
    global _client, _client_key
    embedding = get_embeddings_config()
    if embedding is None:
        raise ValueError(
            "Top-level embeddings configuration is required for memory embeddings"
        )
    api_key = get_secret(embedding.secret_name) or ""
    if not api_key:
        raise ValueError(
            f"Named embedding secret {embedding.secret_name!r} is not configured"
        )
    key = (
        api_key,
        embedding.model,
        embedding.base_url,
        embedding.dimensions,
        embedding.max_tokens,
        embedding.timeout,
    )
    with _client_lock:
        if _client is None or _client_key != key:
            _client = EmbeddingClient(
                api_key=api_key,
                model=embedding.model,
                base_url=embedding.base_url,
                dimensions=embedding.dimensions,
                max_tokens=embedding.max_tokens,
                timeout=embedding.timeout,
                log_prefix="mem",
            )
            _client_key = key
        return _client


def _generate_embedding(text: str) -> list[float]:
    """Generate embedding vector for text.

    If text exceeds the token limit, windows are embedded in one batched API
    call and averaged (``long_text="mean"``) — preserving semantic coverage
    of the full document rather than silently losing the tail.
    """
    return _get_embedding_client().embed(text, long_text="mean")


def _generate_query_embedding(text: str) -> list[float]:
    """Embed a search query, served from the client's bounded LRU cache.

    Content writes and the background worker stay uncached — only the query
    path benefits from repeats.
    """
    return _get_embedding_client().embed(text, long_text="mean", use_cache=True)


def _enqueue_embedding(memory_id: str) -> None:
    """Queue a memory ID for background embedding generation."""
    global _embedding_dropped
    _ensure_embedding_worker()
    try:
        # Non-blocking to avoid stalling write paths under sustained load.
        _embedding_queue.put_nowait(memory_id)
    except queue.Full:
        _embedding_dropped += 1
        if _embedding_dropped in {1, 10, 100} or _embedding_dropped % 1000 == 0:
            logger.warning(
                LogEntry(
                    event="mem.embedding.queue_full",
                    droppedCount=_embedding_dropped,
                    queueSize=_embedding_queue.qsize(),
                    queueMaxSize=_embedding_queue.maxsize,
                )
            )


def _ensure_embedding_worker() -> None:
    """Start the background embedding worker if not already running."""
    global _embedding_worker_started, _embedding_worker_thread
    with _embedding_worker_lock:
        if _embedding_worker_started:
            return
        t = threading.Thread(target=_embedding_worker, daemon=True)
        t.start()
        _embedding_worker_thread = t
        _embedding_worker_started = True


def _embedding_worker() -> None:
    """Background worker: drains the queue, one embedding job at a time."""
    while True:
        memory_id = _embedding_queue.get()
        try:
            _process_embedding_job(memory_id)
        finally:
            _embedding_queue.task_done()


def _process_embedding_job(memory_id: str) -> None:
    """Read content from DB, generate embedding outside the lock, write back.

    Re-reads content from DB (not from queue) to avoid holding large strings
    in memory and to pick up any content changes between enqueue and processing.
    The provider call runs without the DB lock held so embedding round-trips
    never block other DB operations; the write-back is guarded on content so
    a concurrent update is never clobbered with a stale vector.
    Retries up to 3 times with exponential backoff on failure.
    """
    global _embedding_errors
    retries = 0
    max_retries = 3
    while retries < max_retries:
        try:
            with _use_connection() as conn:
                row = conn.execute(
                    "SELECT content FROM memories WHERE id = ?", [memory_id]
                ).fetchone()
            if not row:
                return  # Memory was deleted before we got to it
            # API round-trip happens outside the DB lock
            embedding = _generate_embedding(row[0])
            with _use_connection() as conn:
                cursor = conn.execute(
                    "UPDATE memories SET embedding = ? WHERE id = ? AND content = ?",
                    [_serialize_embedding(embedding), memory_id, row[0]],
                )
                if cursor.rowcount:
                    _sync_vec_index(conn, memory_id, embedding)
                conn.commit()
            return
        except Exception:
            retries += 1
            _embedding_errors += 1
            if retries < max_retries:
                time.sleep(2**retries)  # 2s, 4s, 8s
            else:
                logger.warning(
                    LogEntry(
                        event="mem.embedding.failed",
                        memoryId=memory_id,
                        retries=max_retries,
                        errorCount=_embedding_errors,
                    )
                )


def _embed_now(content: str) -> list[float] | None:
    """Generate an embedding synchronously if sync embeddings are enabled.

    Call this BEFORE acquiring the DB lock: the provider round-trip must not
    block other DB operations. Returns None when embeddings are disabled or
    async; async callers enqueue via _enqueue_after_commit once the row is
    committed.
    """
    config = _get_config()
    if not config.embeddings_enabled or config.embeddings_async:
        return None
    return _generate_embedding(content)


def _enqueue_after_commit(memory_id: str) -> None:
    """Queue background embedding for a committed row (async mode only).

    Must be called after the row is committed so the worker can find it.
    """
    config = _get_config()
    if config.embeddings_enabled and config.embeddings_async:
        _enqueue_embedding(memory_id)


__all__ = [
    "_embed_now",
    "_embedding_dropped",
    "_embedding_errors",
    "_embedding_queue",
    "_embedding_worker",
    "_embedding_worker_lock",
    "_embedding_worker_started",
    "_embedding_worker_thread",
    "_enqueue_after_commit",
    "_enqueue_embedding",
    "_ensure_embedding_worker",
    "_generate_embedding",
    "_generate_query_embedding",
    "_get_embedding_client",
    "_process_embedding_job",
]
