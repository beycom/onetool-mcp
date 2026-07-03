"""Embedding generation for the knowledge pack."""
from __future__ import annotations

import struct
import time
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from collections.abc import Callable

from loguru import logger

from ot.config import get_llm_config
from ot.logging import LogEntry
from otpack import LogSpan, get_secret

from .config import _get_config

if TYPE_CHECKING:
    from openai import OpenAI


_TOKEN_SAFETY_MARGIN = 100
_RETRYABLE_HTTP_STATUS = {429, 500, 503}
_EMBED_MAX_ATTEMPTS = 3

# Query embedding cache: key=(text, model, dimensions) → (vector, timestamp)
_EMBED_CACHE: dict[tuple[str, str, int], tuple[list[float], float]] = {}
_EMBED_CACHE_TTL = 900.0  # 15 minutes


def _get_openai_client() -> OpenAI:
    """Get OpenAI client using knowledge pack config, falling back to top-level llm config."""
    try:
        from openai import OpenAI
    except ImportError as e:
        raise ImportError("openai is required for knowledge embeddings. Install with: pip install openai") from e

    api_key = get_secret("OPENAI_API_KEY") or ""
    if not api_key:
        raise ValueError("OPENAI_API_KEY not configured in secrets.yaml (required for knowledge embeddings)")
    config = _get_config()
    base_url = config.base_url or get_llm_config().base_url or None
    return OpenAI(api_key=api_key, base_url=base_url)


def _get_embedding_model(config: Any) -> str:
    """Resolve the embedding model, falling back to top-level llm config."""
    if config.model:
        return cast("str", config.model)
    return cast("str", get_llm_config().embedding_model or config.model)


def _get_tiktoken_encoding(model: str) -> Any:
    """Get tiktoken encoding for a model, with fallback."""
    try:
        import tiktoken
    except ImportError as e:
        raise ImportError("tiktoken is required for knowledge embedding truncation. Install with: pip install tiktoken") from e
    try:
        return tiktoken.encoding_for_model(model)
    except KeyError:
        return tiktoken.get_encoding("cl100k_base")


def _chunk_text_by_tokens(text: str, max_tokens: int, model: str) -> list[str]:
    """Split text into chunks that each fit within the token limit."""
    encoding = _get_tiktoken_encoding(model)
    tokens = encoding.encode(text)
    if len(tokens) <= max_tokens:
        return [text]
    chunks = []
    for i in range(0, len(tokens), max_tokens):
        chunk_tokens = tokens[i: i + max_tokens]
        chunks.append(encoding.decode(chunk_tokens))
    return chunks


def _prepare_safe_batch(texts: list[str], config: Any, model: str) -> list[str]:
    """Truncate texts to token limit and replace empty strings for the OpenAI API."""
    effective_limit = max(1, config.max_embedding_tokens - _TOKEN_SAFETY_MARGIN)
    safe: list[str] = []
    for text in texts:
        chunks = _chunk_text_by_tokens(text, effective_limit, model)
        safe.append(chunks[0] if chunks else text)
    # OpenAI rejects batches that contain empty strings
    return [t if t.strip() else " " for t in safe]


def _embed_batch_with_retry(
    client: OpenAI,
    model: str,
    safe_batch: list[str],
    max_attempts: int = _EMBED_MAX_ATTEMPTS,
) -> list[list[float]]:
    """Call the embeddings API with retry and count guard.

    Retries on HTTP 429/500/503 and ValueError (e.g. "No embedding data received")
    using exponential backoff. Raises on the final failed attempt.

    Raises ValueError if the response contains fewer vectors than requested.
    """
    for attempt in range(max_attempts):
        try:
            response = client.embeddings.create(model=model, input=safe_batch)
            vecs = [item.embedding for item in sorted(response.data, key=lambda d: d.index)]
            if len(vecs) != len(safe_batch):
                raise ValueError(f"Expected {len(safe_batch)} embeddings, got {len(vecs)}")
            return vecs
        except Exception as e:
            status = getattr(e, "status_code", None)
            # Only retry on HTTP server/rate-limit errors — ValueError means the request
            # itself was rejected (e.g. batch too large), retrying immediately won't help.
            retryable = status in _RETRYABLE_HTTP_STATUS
            if not retryable or attempt == max_attempts - 1:
                raise
            wait = 2.0 ** attempt
            logger.warning(
                LogEntry(
                    event="knowledge.embedding.retry",
                    statusCode=status,
                    waitSeconds=wait,
                    attempt=attempt + 1,
                    maxAttempts=max_attempts,
                    errorType=type(e).__name__,
                    error=str(e),
                )
            )
            time.sleep(wait)
    raise RuntimeError("unreachable")  # pragma: no cover


def generate_embedding(text: str) -> list[float]:
    """Generate embedding vector for text using knowledge pack config.

    Query embeddings are cached for 15 minutes to avoid redundant API calls
    when the same query is issued multiple times in a session.
    """
    config = _get_config()
    model = _get_embedding_model(config)
    cache_key = (text, model, config.dimensions)
    now = time.monotonic()
    cached = _EMBED_CACHE.get(cache_key)
    if cached is not None:
        vec, ts = cached
        if now - ts < _EMBED_CACHE_TTL:
            return vec

    effective_limit = max(1, config.max_embedding_tokens - _TOKEN_SAFETY_MARGIN)
    text_chunks = _chunk_text_by_tokens(text, effective_limit, model)

    with LogSpan(span="kb.embedding", model=model, textLen=len(text), chunks=len(text_chunks)) as span:
        client = _get_openai_client()

        if len(text_chunks) == 1:
            response = client.embeddings.create(model=model, input=text_chunks[0])
            span.add("dimensions", len(response.data[0].embedding))
            result = response.data[0].embedding
        else:
            response = client.embeddings.create(model=model, input=text_chunks)
            vectors = [item.embedding for item in response.data]
            dims = len(vectors[0])
            span.add("dimensions", dims)
            averaged = [0.0] * dims
            for vec in vectors:
                for i in range(dims):
                    averaged[i] += vec[i]
            n = len(vectors)
            result = [v / n for v in averaged]

    _EMBED_CACHE[cache_key] = (result, now)
    return result


def generate_embeddings_batch(
    texts: list[str],
    batch_size: int | None = None,
    on_batch: Callable[[int, int], None] | None = None,
) -> list[list[float]]:
    """Generate embeddings for a list of texts using batched API calls.

    Args:
        texts: List of texts to embed.
        batch_size: Texts per API call. Defaults to config.embedding_batch_size (200).
        on_batch: Optional callback called after each batch with (done, total).

    Returns:
        List of embedding vectors, one per input text.
    """
    if not texts:
        return []

    config = _get_config()
    model = _get_embedding_model(config)
    if batch_size is None:
        batch_size = config.embedding_batch_size
    client = _get_openai_client()
    results: list[list[float]] = []
    total = len(texts)

    for i in range(0, total, batch_size):
        batch = texts[i : i + batch_size]
        safe_batch = _prepare_safe_batch(batch, config, model)

        with LogSpan(span="kb.embedding.batch", model=model, batchSize=len(safe_batch)):
            vecs = _embed_batch_with_retry(client, model, safe_batch)
            results.extend(vecs)

        if on_batch:
            on_batch(min(i + batch_size, total), total)

    return results


def vec_to_bytes(vec: list[float]) -> bytes:
    """Serialize embedding vector to bytes for sqlite-vec storage."""
    return struct.pack(f"{len(vec)}f", *vec)


__all__ = [
    "_embed_batch_with_retry",
    "_get_openai_client",
    "_prepare_safe_batch",
    "generate_embedding",
    "generate_embeddings_batch",
    "vec_to_bytes",
]
