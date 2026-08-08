"""Embedding generation for the knowledge pack.

Thin adapter over :class:`otpack.EmbeddingClient`: config/secret/model
resolution stays here; tokenization, retry, batching, caching, and
``dimensions=`` handling live in otpack.
"""
from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from ot.config import get_embeddings_config
from otpack import EmbeddingClient, get_secret

if TYPE_CHECKING:
    from collections.abc import Callable

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
            "Top-level embeddings configuration is required for knowledge embeddings"
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
            previous = _client
            replacement = EmbeddingClient(
                api_key=api_key,
                model=embedding.model,
                base_url=embedding.base_url,
                dimensions=embedding.dimensions,
                max_tokens=embedding.max_tokens,
                timeout=embedding.timeout,
                log_prefix="kb",
            )
            _client = replacement
            _client_key = key
            if previous is not None:
                previous.close()
        return _client


def reset_embedding_client() -> None:
    """Close and forget the process-cached embedding client."""
    global _client, _client_key
    with _client_lock:
        client = _client
        _client = None
        _client_key = None
        if client is not None:
            client.close()


def generate_embedding(text: str) -> list[float]:
    """Generate an embedding vector for text using knowledge pack config.

    Long texts are embedded from their first token window only — the same
    rule as the batch path — so a given text always embeds identically
    regardless of code path. Query embeddings are served from a bounded LRU
    cache (15 min TTL).
    """
    return _get_embedding_client().embed(text, long_text="truncate", use_cache=True)


def generate_embeddings_batch(
    texts: list[str],
    batch_size: int | None = None,
    on_batch: Callable[[int, int], None] | None = None,
) -> list[list[float]]:
    """Generate embeddings for a list of texts using batched API calls.

    Args:
        texts: List of texts to embed.
        batch_size: Texts per API call. Defaults to top-level
            ``embeddings.batch_size``.
        on_batch: Optional callback called after each batch with (done, total).

    Returns:
        List of embedding vectors, one per input text.
    """
    if not texts:
        return []
    if batch_size is None:
        embedding = get_embeddings_config()
        if embedding is None:
            raise ValueError(
                "Top-level embeddings configuration is required for knowledge embeddings"
            )
        batch_size = embedding.batch_size
    return _get_embedding_client().embed_batch(
        texts, batch_size=batch_size, on_batch=on_batch
    )


__all__ = [
    "_get_embedding_client",
    "generate_embedding",
    "generate_embeddings_batch",
    "reset_embedding_client",
]
