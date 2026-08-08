"""Shared embedding infrastructure for OneTool packs.

Tokenization windows, float32 blob serialization, cosine similarity, RRF
fusion, and an OpenAI-compatible :class:`EmbeddingClient` with retry, batch,
and opt-in query caching. Packs resolve config/secrets themselves and pass
resolved values in — this module imports nothing from the host application.

``openai`` and ``tiktoken`` are optional: install with
``pip install 'onetool-pack[embedding]'``.
"""

from __future__ import annotations

import hashlib
import math
import struct
import time
from collections import OrderedDict
from typing import TYPE_CHECKING, Any, Literal

from otpack.logging import LogEntry, LogSpan

if TYPE_CHECKING:
    from collections.abc import Callable

from loguru import logger

# Safety margin subtracted from token limits to avoid edge-case overflows.
TOKEN_SAFETY_MARGIN = 100

# Native output dimensions per known OpenAI embedding model. ``dimensions=``
# is passed to the API only when the configured value differs from the native
# default, so stored vectors always match the index built from configuration.
MODEL_NATIVE_DIMS: dict[str, int] = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
}

_RETRYABLE_HTTP_STATUS = {429, 500, 503}


# ---------------------------------------------------------------------------
# Pure helpers (no client needed)
# ---------------------------------------------------------------------------


def get_tiktoken_encoding(model: str) -> Any:
    """Get the tiktoken encoding for a model, with ``cl100k_base`` fallback."""
    try:
        import tiktoken
    except ImportError as e:
        raise ImportError(
            "tiktoken is required for otpack embedding. "
            "Install with: pip install 'onetool-pack[embedding]'"
        ) from e
    try:
        return tiktoken.encoding_for_model(model)
    except KeyError:
        return tiktoken.get_encoding("cl100k_base")


def chunk_text_by_tokens(text: str, max_tokens: int, model: str) -> list[str]:
    """Split text into chunks that each fit within the token limit.

    Returns ``[text]`` when it already fits; otherwise lossless consecutive
    token windows.
    """
    encoding = get_tiktoken_encoding(model)
    tokens = encoding.encode(text)
    if len(tokens) <= max_tokens:
        return [text]
    chunks = []
    for i in range(0, len(tokens), max_tokens):
        chunk_tokens = tokens[i : i + max_tokens]
        chunks.append(encoding.decode(chunk_tokens))
    return chunks


def dimensions_param(model: str, configured: int | None) -> int | None:
    """Return ``configured`` only when it differs from the model's native default.

    Unknown models return None (the API's native output is used as-is).
    """
    if configured is None:
        return None
    native = MODEL_NATIVE_DIMS.get(model)
    if native is not None and int(configured) != native:
        return int(configured)
    return None


def serialize_embedding(vec: list[float] | None) -> bytes | None:
    """Pack a float list into the canonical little-endian float32 blob."""
    if vec is None:
        return None
    return struct.pack(f"<{len(vec)}f", *vec)


def deserialize_embedding(blob: bytes | None) -> list[float] | None:
    """Unpack a canonical float32 blob back to a float list.

    Raises:
        ValueError: When the blob length is not a multiple of 4.
    """
    if blob is None:
        return None
    if len(blob) % 4 != 0:
        raise ValueError(f"embedding blob length {len(blob)} is not a multiple of 4")
    n = len(blob) // 4
    return list(struct.unpack(f"<{n}f", blob))


def cosine_similarity_blobs(a: bytes | None, b: bytes | None) -> float | None:
    """Cosine similarity between two packed float32 blobs.

    Returns None when either input is None, 0.0 when either norm is zero.

    Raises:
        ValueError: When the blob lengths (dimensions) differ.
    """
    if a is None or b is None:
        return None
    if len(a) != len(b):
        raise ValueError(
            f"embedding dimension mismatch: {len(a) // 4} vs {len(b) // 4} dims"
        )
    n = len(a) // 4
    va = struct.unpack(f"<{n}f", a)
    vb = struct.unpack(f"<{n}f", b)
    dot = sum(x * y for x, y in zip(va, vb, strict=True))
    norm_a = math.sqrt(sum(x * x for x in va))
    norm_b = math.sqrt(sum(x * x for x in vb))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return float(dot / (norm_a * norm_b))


def rrf_merge(
    list_a: list[dict[str, Any]],
    list_b: list[dict[str, Any]],
    limit: int,
    *,
    k: int = 60,
    id_key: str = "id",
    boost: Callable[[dict[str, Any]], float] | None = None,
) -> list[dict[str, Any]]:
    """Reciprocal Rank Fusion: ``score = sum(1 / (k + rank))`` with 1-based ranks.

    Results from ``list_a`` take precedence when an id appears in both lists.
    ``boost(result)`` is applied additively per merged id when provided. The
    fused score is rounded to 4 decimals and written into each returned result
    (results are shallow-copied).
    """
    rrf: dict[str, float] = {}
    result_map: dict[str, dict[str, Any]] = {}

    for rank, r in enumerate(list_a, 1):
        rid = r[id_key]
        rrf[rid] = rrf.get(rid, 0.0) + 1.0 / (k + rank)
        result_map[rid] = r

    for rank, r in enumerate(list_b, 1):
        rid = r[id_key]
        rrf[rid] = rrf.get(rid, 0.0) + 1.0 / (k + rank)
        if rid not in result_map:
            result_map[rid] = r

    if boost is not None:
        for rid, r in result_map.items():
            rrf[rid] += boost(r)

    sorted_ids = sorted(rrf, key=lambda x: rrf[x], reverse=True)[:limit]
    merged = []
    for rid in sorted_ids:
        r = dict(result_map[rid])
        r["score"] = round(rrf[rid], 4)
        merged.append(r)
    return merged


# ---------------------------------------------------------------------------
# EmbeddingClient
# ---------------------------------------------------------------------------


class EmbeddingClient:
    """OpenAI-compatible embedding client with retry, batching, and caching.

    Packs construct one lazily from resolved config values and reuse it. The
    per-instance LRU cache is opt-in via ``embed(use_cache=True)`` — enable it
    only for query embeddings, never document writes.

    Args:
        api_key: Resolved API key.
        model: Embedding model name.
        base_url: OpenAI-compatible API base URL (None = provider default).
        dimensions: Configured output dimensions; passed to the API only when
            it differs from the model's native default.
        max_tokens: Max tokens per embedding input (safety margin applied).
        safety_margin: Tokens subtracted from ``max_tokens`` for windowing.
        timeout: HTTP timeout in seconds.
        log_prefix: Span/event prefix so packs keep attributable log names
            (``{log_prefix}.embedding``, ``.embedding.batch``, ``.embedding.retry``).
        cache_ttl: Cache entry lifetime in seconds.
        cache_max: Max cached entries (LRU eviction).
    """

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str | None = None,
        dimensions: int | None = None,
        max_tokens: int = 8191,
        safety_margin: int = TOKEN_SAFETY_MARGIN,
        timeout: float = 60.0,
        log_prefix: str = "otpack",
        cache_ttl: float = 900.0,
        cache_max: int = 256,
    ) -> None:
        self._api_key = api_key
        self.model = model
        self._base_url = base_url
        self.dimensions = dimensions
        self._max_tokens = max_tokens
        self._safety_margin = safety_margin
        self._timeout = timeout
        self._log_prefix = log_prefix
        self._cache_ttl = cache_ttl
        self._cache_max = cache_max
        self._client: Any = None
        # LRU keyed (sha256(text), model, dimensions) → (vector, monotonic ts)
        self._cache: OrderedDict[tuple[str, str, int | None], tuple[list[float], float]] = (
            OrderedDict()
        )

    # -- internals ----------------------------------------------------------

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError as e:
                raise ImportError(
                    "openai is required for otpack embedding. "
                    "Install with: pip install 'onetool-pack[embedding]'"
                ) from e
            self._client = OpenAI(
                api_key=self._api_key,
                base_url=self._base_url,
                timeout=self._timeout,
            )
        return self._client

    def close(self) -> None:
        """Close the underlying HTTP client and clear cached vectors."""
        client = self._client
        self._client = None
        self._cache.clear()
        if client is not None:
            client.close()

    def _effective_limit(self) -> int:
        return max(1, self._max_tokens - self._safety_margin)

    def _prepare_safe_batch(self, texts: list[str]) -> list[str]:
        """Truncate texts to the token limit; blank inputs become ``" "``.

        The OpenAI API rejects batches containing empty strings.
        """
        limit = self._effective_limit()
        safe: list[str] = []
        for text in texts:
            chunks = chunk_text_by_tokens(text, limit, self.model)
            safe.append(chunks[0] if chunks else text)
        return [t if t.strip() else " " for t in safe]

    def _dimensions_kwargs(self) -> dict[str, Any]:
        dims = dimensions_param(self.model, self.dimensions)
        return {"dimensions": dims} if dims is not None else {}

    def _embed_batch_with_retry(
        self, safe_batch: list[str], max_attempts: int = 3
    ) -> list[list[float]]:
        """Call the embeddings API with retry and count guard.

        Retries only transient HTTP 429/500/503 (via the exception's
        ``status_code`` attribute) with exponential backoff ``2.0 ** attempt``.
        Raises ValueError immediately when the response contains fewer vectors
        than requested.
        """
        client = self._get_client()
        extra = self._dimensions_kwargs()
        for attempt in range(max_attempts):
            try:
                response = client.embeddings.create(
                    model=self.model, input=safe_batch, **extra
                )
                vecs = [item.embedding for item in sorted(response.data, key=lambda d: d.index)]
                if len(vecs) != len(safe_batch):
                    raise ValueError(f"Expected {len(safe_batch)} embeddings, got {len(vecs)}")
                return vecs
            except Exception as e:
                status = getattr(e, "status_code", None)
                retryable = status in _RETRYABLE_HTTP_STATUS
                if not retryable or attempt == max_attempts - 1:
                    raise
                wait = 2.0**attempt
                logger.warning(
                    LogEntry(
                        event=f"{self._log_prefix}.embedding.retry",
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

    def _cache_key(self, text: str) -> tuple[str, str, int | None]:
        return (
            hashlib.sha256(text.encode("utf-8")).hexdigest(),
            self.model,
            self.dimensions,
        )

    def _cache_get(self, key: tuple[str, str, int | None]) -> list[float] | None:
        cached = self._cache.get(key)
        if cached is None:
            return None
        vec, ts = cached
        if time.monotonic() - ts >= self._cache_ttl:
            return None
        self._cache.move_to_end(key)
        return vec

    def _cache_put(self, key: tuple[str, str, int | None], vec: list[float]) -> None:
        self._cache[key] = (vec, time.monotonic())
        self._cache.move_to_end(key)
        while len(self._cache) > self._cache_max:
            self._cache.popitem(last=False)

    # -- public API ----------------------------------------------------------

    def embed(
        self,
        text: str,
        *,
        long_text: Literal["truncate", "mean"] = "truncate",
        use_cache: bool = False,
    ) -> list[float]:
        """Embed a single text.

        Args:
            text: Input text.
            long_text: Over-limit strategy — ``"truncate"`` embeds only the
                first token window (a given text embeds identically on every
                code path); ``"mean"`` batch-embeds all windows in one API
                call and returns the element-wise average.
            use_cache: Serve/populate the per-instance LRU cache. Enable only
                for query embeddings, never document writes.

        Returns:
            Embedding vector.
        """
        key = self._cache_key(text)
        if use_cache:
            cached = self._cache_get(key)
            if cached is not None:
                return cached

        chunks = chunk_text_by_tokens(text, self._effective_limit(), self.model)
        if long_text == "truncate" or len(chunks) <= 1:
            inputs = [chunks[0] if chunks else text]
        else:
            inputs = chunks

        with LogSpan(
            span=f"{self._log_prefix}.embedding",
            model=self.model,
            textLen=len(text),
            chunks=len(chunks),
        ) as span:
            safe_inputs = [t if t.strip() else " " for t in inputs]
            vecs = self._embed_batch_with_retry(safe_inputs)
            span.add(dimensions=len(vecs[0]))

            if len(vecs) == 1:
                result = vecs[0]
            else:
                dims = len(vecs[0])
                averaged = [0.0] * dims
                for vec in vecs:
                    for i in range(dims):
                        averaged[i] += vec[i]
                n = len(vecs)
                result = [v / n for v in averaged]

        if use_cache:
            self._cache_put(key, result)
        return result

    def embed_batch(
        self,
        texts: list[str],
        *,
        batch_size: int = 200,
        on_batch: Callable[[int, int], None] | None = None,
        max_attempts: int = 3,
    ) -> list[list[float]]:
        """Embed a list of texts using batched API calls.

        Long texts are truncated to their first token window — the same rule
        as ``embed(long_text="truncate")`` — so a given text always embeds
        identically regardless of code path.

        Args:
            texts: Texts to embed.
            batch_size: Texts per API call.
            on_batch: Optional callback called after each batch with (done, total).
            max_attempts: Retry attempts per batch for transient HTTP errors.

        Returns:
            One embedding vector per input text.
        """
        if not texts:
            return []

        results: list[list[float]] = []
        total = len(texts)
        for i in range(0, total, batch_size):
            batch = texts[i : i + batch_size]
            safe_batch = self._prepare_safe_batch(batch)
            with LogSpan(
                span=f"{self._log_prefix}.embedding.batch",
                model=self.model,
                batchSize=len(safe_batch),
            ):
                vecs = self._embed_batch_with_retry(safe_batch, max_attempts=max_attempts)
                results.extend(vecs)
            if on_batch:
                on_batch(min(i + batch_size, total), total)
        return results


__all__ = [
    "MODEL_NATIVE_DIMS",
    "TOKEN_SAFETY_MARGIN",
    "EmbeddingClient",
    "chunk_text_by_tokens",
    "cosine_similarity_blobs",
    "deserialize_embedding",
    "dimensions_param",
    "get_tiktoken_encoding",
    "rrf_merge",
    "serialize_embedding",
]
