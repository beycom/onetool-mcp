"""OpenAI embedding generation and background worker."""
from __future__ import annotations

import queue
import threading
import time
from typing import TYPE_CHECKING, Any, cast

from loguru import logger

from ot.config import get_llm_config
from ot.logging import LogEntry
from otpack import LogSpan, get_secret

from .config import _get_config
from .db import _serialize_embedding, _use_connection

if TYPE_CHECKING:
    from types import ModuleType

    from openai import OpenAI


# Safety margin subtracted from token limit to avoid edge-case overflows.
# Standard safety margin for embedding token limits.
_TOKEN_SAFETY_MARGIN = 100

# Bounded queue: stores only memory IDs (not content) to avoid memory bloat.
# maxsize=1000 bounds memory usage.
_embedding_queue: queue.Queue[str] = queue.Queue(maxsize=1000)
_embedding_worker_started = False
_embedding_worker_thread: threading.Thread | None = None
_embedding_worker_lock = threading.Lock()
_embedding_errors: int = 0  # Surfaced in mem.stats()
_embedding_dropped: int = 0  # Count dropped jobs when queue is saturated


def _get_openai_client() -> OpenAI:
    """Get OpenAI client for embedding generation."""
    try:
        from openai import OpenAI
    except ImportError as e:
        raise ImportError(
            "openai is required for mem. Install with: pip install openai"
        ) from e

    api_key = get_secret("OPENAI_API_KEY") or ""
    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY not configured in secrets.yaml (required for memory embeddings)"
        )
    config = _get_config()
    base_url = config.base_url or get_llm_config().base_url or None
    return OpenAI(api_key=api_key, base_url=base_url)


def _import_tiktoken() -> ModuleType:
    """Lazy import tiktoken module."""
    try:
        import tiktoken
    except ImportError as e:
        raise ImportError(
            "tiktoken is required for mem embedding truncation. Install with: pip install tiktoken"
        ) from e
    return tiktoken


def _get_tiktoken_encoding(model: str) -> Any:
    """Get tiktoken encoding for a model, with fallback."""
    tiktoken = _import_tiktoken()
    try:
        return tiktoken.encoding_for_model(model)
    except KeyError:
        return tiktoken.get_encoding("cl100k_base")


def _chunk_text_by_tokens(text: str, max_tokens: int, model: str) -> list[str]:
    """Split text into chunks that each fit within the token limit.

    Returns a list of text chunks. If the text fits in one chunk, returns [text].
    """
    encoding = _get_tiktoken_encoding(model)
    tokens = encoding.encode(text)

    if len(tokens) <= max_tokens:
        return [text]

    chunks = []
    for i in range(0, len(tokens), max_tokens):
        chunk_tokens = tokens[i : i + max_tokens]
        chunks.append(encoding.decode(chunk_tokens))
    return chunks


def _get_embedding_model(config: Any) -> str:
    """Resolve the embedding model, falling back to top-level llm config."""
    if config.model:
        return cast("str", config.model)
    return cast("str", get_llm_config().embedding_model or "text-embedding-3-small")


def _generate_embedding(text: str) -> list[float]:
    """Generate embedding vector for text.

    If text exceeds the token limit, splits into chunks, embeds each,
    and returns the averaged vector. This preserves semantic coverage
    of the full document rather than silently losing the tail.
    """
    config = _get_config()
    model = _get_embedding_model(config)
    effective_limit = max(1, config.max_embedding_tokens - _TOKEN_SAFETY_MARGIN)
    chunks = _chunk_text_by_tokens(text, effective_limit, model)

    with LogSpan(
        span="mem.embedding",
        model=model,
        textLen=len(text),
        chunks=len(chunks),
    ) as span:
        client = _get_openai_client()

        if len(chunks) == 1:
            response = client.embeddings.create(
                model=model,
                input=chunks[0],
            )
            span.add("dimensions", len(response.data[0].embedding))
            return response.data[0].embedding

        # Batch embed all chunks in one API call
        response = client.embeddings.create(
            model=model,
            input=chunks,
        )
        vectors = [item.embedding for item in response.data]
        dims = len(vectors[0])
        span.add("dimensions", dims)

        # Average the vectors
        averaged = [0.0] * dims
        for vec in vectors:
            for i in range(dims):
                averaged[i] += vec[i]
        n = len(vectors)
        averaged = [v / n for v in averaged]

        return averaged


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
    The OpenAI call runs without the DB lock held so embedding round-trips
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
                conn.execute(
                    "UPDATE memories SET embedding = ? WHERE id = ? AND content = ?",
                    [_serialize_embedding(embedding), memory_id, row[0]],
                )
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

    Call this BEFORE acquiring the DB lock: the OpenAI round-trip must not
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
    "_TOKEN_SAFETY_MARGIN",
    "_chunk_text_by_tokens",
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
    "_get_openai_client",
    "_get_tiktoken_encoding",
    "_import_tiktoken",
    "_process_embedding_job",
]
