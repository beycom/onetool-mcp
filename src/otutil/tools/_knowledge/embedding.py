"""Embedding generation for the knowledge pack.

Thin adapter over :class:`otpack.EmbeddingClient`: config/secret/model
resolution stays here; tokenization, retry, batching, caching, and
``dimensions=`` handling live in otpack.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Any

from ot.config import get_llm_config
from otpack import EmbeddingClient, get_secret

from .config import _get_config

if TYPE_CHECKING:
    from collections.abc import Callable

_CLIENT_TIMEOUT_S = 60.0

# Module-cached client keyed on the resolved inputs so config reloads rebuild it.
_client: EmbeddingClient | None = None
_client_key: tuple[str, str, str, int, int] | None = None
_client_lock = threading.Lock()


def _get_embedding_model(config: Any) -> str:
    """Resolve the embedding model, falling back to top-level llm config."""
    if config.model:
        return str(config.model)
    return get_llm_config().embedding_model or "text-embedding-3-small"


def _get_embedding_client() -> EmbeddingClient:
    """Get (or build) the shared EmbeddingClient from resolved config values."""
    global _client, _client_key
    api_key = get_secret("OPENAI_API_KEY") or ""
    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY not configured in secrets.yaml (required for knowledge embeddings)"
        )
    config = _get_config()
    model = _get_embedding_model(config)
    base_url = config.base_url or get_llm_config().base_url or ""
    key = (
        api_key,
        model,
        base_url,
        int(config.dimensions),
        int(config.max_embedding_tokens),
    )
    with _client_lock:
        if _client is None or _client_key != key:
            _client = EmbeddingClient(
                api_key=api_key,
                model=model,
                base_url=base_url or None,
                dimensions=int(config.dimensions),
                max_tokens=int(config.max_embedding_tokens),
                timeout=_CLIENT_TIMEOUT_S,
                log_prefix="kb",
            )
            _client_key = key
        return _client


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
        batch_size: Texts per API call. Defaults to config.embedding_batch_size (200).
        on_batch: Optional callback called after each batch with (done, total).

    Returns:
        List of embedding vectors, one per input text.
    """
    if not texts:
        return []
    if batch_size is None:
        batch_size = _get_config().embedding_batch_size
    return _get_embedding_client().embed_batch(
        texts, batch_size=batch_size, on_batch=on_batch
    )


__all__ = [
    "_get_embedding_client",
    "_get_embedding_model",
    "generate_embedding",
    "generate_embeddings_batch",
]
