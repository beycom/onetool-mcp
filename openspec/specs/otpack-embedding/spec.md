# otpack-embedding Specification

## Purpose

Defines the shared embedding infrastructure in `otpack` (`otpack/embedding.py`):
the `EmbeddingClient` (retry, batching, opt-in query caching, `dimensions=`
handling), token-windowing helpers, canonical little-endian float32 vector
serialization, and the Reciprocal Rank Fusion helper — all free of `ot.*`
imports so the module ships in the standalone `onetool-pack` wheel with an
optional `embedding` extra. The `mem` and `knowledge` packs delegate to this
layer while keeping config/secret resolution and their intentional behavioral
differences (long-text strategy, RRF boost) in the packs.

## Requirements

### Requirement: Shared embedding client from resolved values

The otpack library SHALL provide an `EmbeddingClient` (in `otpack.embedding`, exported from `otpack`) that is constructed exclusively from already-resolved values — `api_key`, `model`, optional `base_url`, optional `dimensions`, `max_tokens`, `timeout`, `log_prefix` — and SHALL NOT read OneTool configuration itself. The module SHALL contain no imports from `ot.*`, `ottools.*`, `otutil.*`, or `otdev.*`, so it passes the otpack import-boundary check unchanged.

#### Scenario: Client construction requires no OneTool runtime
- **WHEN** `EmbeddingClient(api_key="sk-…", model="text-embedding-3-small")` is constructed in a process without any `ot.*` package importable
- **THEN** construction SHALL succeed and embedding calls SHALL work using only the provided values

#### Scenario: Import boundary holds
- **WHEN** `packages/onetool-pack/scripts/check_otpack_boundary.py` runs over the otpack sources including `embedding.py`
- **THEN** it SHALL report zero violations

### Requirement: Optional embedding dependencies

The otpack wheel SHALL declare `openai` and `tiktoken` as an optional-dependency extra named `embedding` (not as required dependencies). Imports of `openai` and `tiktoken` SHALL be lazy; when a symbol requiring a missing library is used, the module SHALL raise `ImportError` with an install hint naming `onetool-pack[embedding]`.

#### Scenario: Base wheel install stays lean
- **WHEN** `onetool-pack` is installed without extras
- **THEN** `import otpack` SHALL succeed without `openai` or `tiktoken` installed

#### Scenario: Missing library raises install hint
- **WHEN** an embedding call is made and `openai` (or `tiktoken`) is not importable
- **THEN** an `ImportError` SHALL be raised whose message includes `pip install 'onetool-pack[embedding]'`

### Requirement: Token windowing helpers

The module SHALL provide `get_tiktoken_encoding(model)` returning the model's tiktoken encoding with fallback to `cl100k_base` for unknown models, and `chunk_text_by_tokens(text, max_tokens, model)` splitting text into consecutive token windows of at most `max_tokens` tokens (returning `[text]` unchanged when it already fits).

#### Scenario: Unknown model falls back to cl100k_base
- **WHEN** `get_tiktoken_encoding("some-future-model")` is called for a model tiktoken does not know
- **THEN** the `cl100k_base` encoding SHALL be returned instead of raising

#### Scenario: Long text is windowed losslessly
- **WHEN** `chunk_text_by_tokens(text, max_tokens, model)` is called with text exceeding `max_tokens` tokens
- **THEN** it SHALL return more than one chunk, each within `max_tokens` tokens, whose concatenated token sequence equals the original encoding

### Requirement: Long-text strategies on single embed

`EmbeddingClient.embed(text, long_text=…)` SHALL support two strategies for text exceeding the effective token limit (`max_tokens` minus a safety margin of 100): `"truncate"` (default) embeds only the first token window; `"mean"` embeds every window in one batched API call and returns the element-wise average vector.

#### Scenario: Truncate strategy embeds first window only
- **WHEN** `embed(long_text="truncate")` is called with over-limit text
- **THEN** exactly one input (the first token window) SHALL be sent to the embeddings API

#### Scenario: Mean strategy averages all windows
- **WHEN** `embed(long_text="mean")` is called with text spanning N > 1 windows
- **THEN** all N windows SHALL be embedded in a single API call and the returned vector SHALL be their element-wise mean

### Requirement: Retrying batch embedding with count guard

`EmbeddingClient.embed_batch(texts, batch_size=…, on_batch=…, max_attempts=3)` SHALL split inputs into sub-batches, truncate each text to the effective token limit, replace empty/whitespace-only strings with a single space (the OpenAI API rejects empty inputs), order response vectors by response index, and retry a failed sub-batch only on HTTP status 429, 500, or 503 with exponential backoff (`2.0 ** attempt` seconds) up to `max_attempts`. A response containing fewer vectors than inputs SHALL raise `ValueError` immediately. When `dimensions` is configured and differs from the model's known native output size, `dimensions=` SHALL be passed to the API; otherwise it SHALL be omitted.

#### Scenario: Transient HTTP failure retried
- **WHEN** a sub-batch call fails with HTTP 429, 500, or 503
- **THEN** it SHALL be retried with exponential backoff up to `max_attempts` before the error propagates

#### Scenario: Non-retryable error propagates immediately
- **WHEN** a sub-batch call fails with a non-retryable error (e.g. HTTP 400)
- **THEN** the error SHALL propagate without retry

#### Scenario: Count mismatch raises
- **WHEN** the API returns fewer vectors than requested inputs
- **THEN** `ValueError` SHALL be raised naming expected and received counts

#### Scenario: Non-default dimensions forwarded
- **WHEN** the client is constructed with `dimensions` differing from the model's native output size
- **THEN** every `embeddings.create` call SHALL include `dimensions=`

### Requirement: Opt-in bounded LRU query cache

`EmbeddingClient.embed(…, use_cache=True)` SHALL serve repeated texts from a per-client in-memory LRU cache keyed on `(sha256(text), model, dimensions)` — never the raw text — with a 15-minute TTL and a 256-entry cap. `use_cache` SHALL default to False.

#### Scenario: Cache hit skips API call
- **WHEN** the same text is embedded twice with `use_cache=True` within the TTL
- **THEN** the embeddings API SHALL be called only once

#### Scenario: Cache is bounded
- **WHEN** more distinct texts than the cap are cached
- **THEN** least-recently-used entries SHALL be evicted and the cache SHALL never exceed its cap

### Requirement: Canonical little-endian float32 serialization

The module SHALL provide `serialize_embedding(vec)` packing a float list as explicit little-endian float32 (`struct` format `<{n}f`, `None` → `None`) and `deserialize_embedding(blob)` performing the inverse (`None` → `None`), raising `ValueError` when the blob length is not a multiple of 4. It SHALL also provide `cosine_similarity_blobs(a, b)` computing cosine similarity between two such blobs (returning `None` if either is `None`, `0.0` for zero-norm vectors, and raising `ValueError` on length mismatch). This is the single canonical vector serialization for OneTool packs.

#### Scenario: Round-trip preserves vector
- **WHEN** a vector is passed through `serialize_embedding` then `deserialize_embedding`
- **THEN** the result SHALL equal the original within float32 precision

#### Scenario: Byte order is explicit little-endian
- **WHEN** `serialize_embedding([1.0])` is called on any platform
- **THEN** the output SHALL equal `struct.pack("<1f", 1.0)`

#### Scenario: Truncated blob rejected
- **WHEN** `deserialize_embedding` receives a blob whose length is not a multiple of 4
- **THEN** `ValueError` SHALL be raised

### Requirement: Reciprocal Rank Fusion helper

The module SHALL provide `rrf_merge(list_a, list_b, limit, *, k=60, id_key="id", boost=None)` fusing two ranked result lists by `score = Σ 1/(k + rank)` (1-based ranks), keeping the first-seen result dict per id (list_a precedence), optionally adding `boost(result)` to each merged id's score, writing the fused score (rounded to 4 decimals) into each result's `"score"` key, and returning the top `limit` results by descending score.

#### Scenario: Item in both lists outranks single-list items
- **WHEN** an id appears in both input lists and another id appears at the same ranks in only one list
- **THEN** the id present in both SHALL receive the higher fused score

#### Scenario: Boost callback applied
- **WHEN** a `boost` callable is provided
- **THEN** each merged result's score SHALL include the callback's additive contribution
