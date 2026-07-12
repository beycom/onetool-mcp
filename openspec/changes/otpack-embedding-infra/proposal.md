# Proposal: otpack-embedding-infra

## Why

The mem and knowledge packs each carry their own embedding stack. After the 2026-07-11 fix passes (240afa0a mem, 3e796d42 knowledge) the original "~400 duplicated lines" survey is stale, but a fresh survey confirms substantial *current* duplication and — worse — divergence where the packs should agree:

- **Duplicated near-verbatim** (verified against current `src/otutil/tools/_mem/embedding.py` and `src/otutil/tools/_knowledge/embedding.py`): OpenAI client construction (`_get_openai_client`), embedding-model fallback resolution (`_get_embedding_model`), tiktoken encoding lookup with `cl100k_base` fallback (`_get_tiktoken_encoding`), token-window chunking (`_chunk_text_by_tokens`, identical bodies), the `_TOKEN_SAFETY_MARGIN = 100` constant, and RRF fusion (`_mem/search.py:_search_hybrid` inline vs `_knowledge/search.py:_rrf_merge` — same algorithm, k=60).
- **Divergent where they shouldn't be**: knowledge has API-level retry on HTTP 429/500/503 with exponential backoff (`_embed_batch_with_retry`), a bounded LRU query-embedding cache, a 60s client timeout, and `dimensions=` handling via a native-dims table; mem has none of these on its synchronous path (only a coarse job-level retry in the async worker).
- **float32 serialization exists in three copies with two byte orders**: `_mem/db.py:150` and `_knowledge/db.py:224` use explicit little-endian `<{n}f`, while `_knowledge/embedding.py:240` (`vec_to_bytes`, used for all sqlite-vec writes and query blobs) uses *native* byte order `{n}f`. On the little-endian platforms this project supports the bytes happen to be identical — but the split is a latent corruption bug and must be unified on one canonical order.

One extraction into `packages/onetool-pack/` (import name `otpack`) fixes both packs at once and gives future packs (and standalone pack authors, since otpack ships as a wheel) a single vetted embedding layer.

## What Changes

- New `otpack.embedding` module in `packages/onetool-pack/src/otpack/embedding.py` providing: `EmbeddingClient` (construction from *resolved* values — api_key, model, base_url, dimensions — never from `ot.config`), tiktoken windowing helpers, single-text embed with `truncate`/`mean` long-text strategies, retrying batch embed, canonical little-endian float32 `serialize_embedding`/`deserialize_embedding`, blob cosine similarity, `rrf_merge`, and an opt-in bounded LRU query cache.
- otpack gains an optional-dependency extra `embedding = ["openai", "tiktoken"]` (lazy imports with install-hint `ImportError`s); the otpack import boundary (no `ot.*` imports outside config/logging) is preserved — `otpack/embedding.py` imports no `ot.*` module.
- mem and knowledge embedding modules shrink to thin adapters: config/secret/model resolution (which legitimately needs `ot.config` / `otpack.get_secret`) stays in the packs; everything mechanical delegates to `otpack.embedding`. The mem background worker queue stays in `_mem/embedding.py`.
- All float32 vector serialization unifies on explicit little-endian `<{n}f`. Knowledge's native-order `vec_to_bytes` is deleted; existing stored vectors need **no data migration** on supported (little-endian) platforms because the byte encodings are identical there; `kb reindex` / `mem.reindex(dry_run=False)` remain the escape hatch for any store written on a big-endian host.
- Behavior upgrades from convergence: mem's synchronous embedding path gains API-level retry on transient errors, and mem's semantic-search query embeddings gain the bounded LRU cache (previously knowledge-only).
- No tool signatures, config schema keys, or on-disk formats change.

## Capabilities

### New Capabilities

- `otpack-embedding`: shared embedding infrastructure contract in the otpack library — resolved-values client construction, token windowing, long-text strategies, retrying batch embed, canonical little-endian float32 serialization, RRF fusion, query cache, optional-dependency behavior, and the import-boundary guarantee.

### Modified Capabilities

- `knowledge-pack`: adds a "canonical embedding vector serialization" requirement (explicit little-endian, compatibility guarantee for existing stores, reindex escape hatch). Existing retry/cache/dimensions requirements are unchanged in behavior (implementation moves to otpack).
- `ottools/tool-mem`: adds requirements for API-level retry on transient embedding failures (sync path included) and a bounded LRU query-embedding cache for semantic search, plus the same canonical-serialization requirement.

## Impact

- **New code**: `packages/onetool-pack/src/otpack/embedding.py`, exports in `packages/onetool-pack/src/otpack/__init__.py`, `embedding` extra in `packages/onetool-pack/pyproject.toml`, tests in `packages/onetool-pack/tests/test_embedding.py`.
- **Refactored**: `src/otutil/tools/_mem/embedding.py`, `src/otutil/tools/_mem/db.py` (serialization + cosine UDF delegate), `src/otutil/tools/_mem/search.py` (RRF delegates), `src/otutil/tools/_knowledge/embedding.py`, `src/otutil/tools/_knowledge/db.py` (serialization delegates), `src/otutil/tools/_knowledge/search.py` (RRF delegates), `src/otutil/tools/_knowledge/indexer.py` / `crud.py` (call `serialize_embedding` instead of `vec_to_bytes`).
- **Tests touched**: `tests/otutil/unit/tools/test_mem.py`, `tests/otutil/unit/tools/test_knowledge.py`, `tests/integration/tools/test_mem.py` (import paths for moved helpers), `packages/onetool-pack/tests/test_boundary.py` (must still pass with the new module).
- **Dependencies**: `openai` and `tiktoken` are already core deps of the main repo, so mem/knowledge behavior is unaffected; they become an *optional* extra of the standalone otpack wheel only.
- **Risk**: byte-order unification — mitigated because `<{n}f` and native `{n}f` produce identical bytes on all little-endian platforms (the only supported ones); reindex commands cover the theoretical remainder.
