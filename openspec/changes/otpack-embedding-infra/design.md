# Design: otpack-embedding-infra

## Context

**Current state (re-surveyed 2026-07-11, post 240afa0a / 3e796d42 — the old ~400-line survey is stale):**

| Concern | mem (`src/otutil/tools/_mem/`) | knowledge (`src/otutil/tools/_knowledge/`) | Shared now? |
|---|---|---|---|
| OpenAI client construction | `embedding.py:_get_openai_client` (no timeout) | `embedding.py:_get_openai_client` (timeout=60s) | Yes — near-identical |
| Model resolution | `embedding.py:_get_embedding_model` (config.model → `get_llm_config().embedding_model` → `text-embedding-3-small`) | identical body | Yes — but needs `ot.config` |
| tiktoken encoding + fallback | `_get_tiktoken_encoding` (cl100k_base fallback) | identical | Yes |
| Token windowing | `_chunk_text_by_tokens` | identical body | Yes |
| Safety margin | `_TOKEN_SAFETY_MARGIN = 100` | identical | Yes |
| Long-text handling | chunk-mean (average all window vectors) | truncate to first window (single + batch paths agree) | Divergent by design — keep both |
| API retry | none on sync path; coarse 3× job retry in async worker | `_embed_batch_with_retry`: 429/500/503, 3 attempts, exp backoff, count guard | Divergent — converge |
| Query cache | none | bounded LRU, sha256 key, 15 min TTL, 256 entries | Divergent — converge |
| `dimensions=` handling | none (implicit native) | `_dimensions_param` + `_MODEL_NATIVE_DIMS` | knowledge-only — share |
| RRF fusion | `search.py:_search_hybrid` inline (k=60) | `search.py:_rrf_merge` (k=60 + hit_count boost) | Yes — same algorithm |
| float32 serialization | `db.py:150` `<{n}f` (+ `_cosine_similarity` unpacks `<{n}f`) | `db.py:224` `<{n}f` **and** `embedding.py:240 vec_to_bytes` **native** `{n}f` | Three copies, two byte orders |
| Background worker/queue | `embedding.py` (queue of memory IDs, DB write-back) | n/a | mem-only — stays |

**Constraints:**
- otpack has a strict, AST-enforced import boundary (`packages/onetool-pack/scripts/check_otpack_boundary.py`): no `ot.*`/`ottools`/`otutil`/`otdev` imports anywhere except try/except-wrapped imports in `config.py` and `logging.py`. The new module gets **no exemption**.
- otpack ships as a standalone wheel (`build-pack`); its `pyproject.toml` deps are only loguru/httpx/pydantic/pyyaml. `openai`/`tiktoken` are core deps of the main repo but NOT of the otpack wheel.
- Existing DBs contain stored float32 blobs written with both byte-order spellings; they must remain readable.

## Goals / Non-Goals

**Goals:**
- One shared embedding layer in `otpack` that both packs delegate to, with zero `ot.*` imports.
- Single canonical float32 byte order (explicit little-endian `<{n}f`) with an explicit compat/migration story.
- Converge retry, caching, and `dimensions=` behavior; preserve each pack's intentional differences (long-text strategy, worker queue, RRF boost).
- Preserve per-pack observability (log span names `mem.embedding*` / `kb.embedding*` stay attributable).

**Non-Goals:**
- No changes to tool signatures, `onetool.yaml` config schema, or DB schemas.
- No async/`httpx`-based embedding client rewrite; keep the sync `openai` SDK.
- Not moving mem's background worker or either pack's DB access into otpack.
- Not unifying long-text strategies (mem keeps chunk-mean; knowledge keeps first-window truncate — its spec pins "same text embeds identically on every code path").

## Decisions

### D1: One new module `otpack/embedding.py`, class + pure functions

`packages/onetool-pack/src/otpack/embedding.py`, exported from `otpack/__init__.py`:

```python
# module constants
TOKEN_SAFETY_MARGIN = 100
MODEL_NATIVE_DIMS = {"text-embedding-3-small": 1536,
                     "text-embedding-3-large": 3072,
                     "text-embedding-ada-002": 1536}

# pure helpers (no client needed)
def get_tiktoken_encoding(model: str) -> Any                     # cl100k_base fallback; lazy import
def chunk_text_by_tokens(text: str, max_tokens: int, model: str) -> list[str]
def dimensions_param(model: str, configured: int | None) -> int | None
def serialize_embedding(vec: list[float] | None) -> bytes | None        # canonical <{n}f
def deserialize_embedding(blob: bytes | None) -> list[float] | None     # validates len % 4 == 0
def cosine_similarity_blobs(a: bytes | None, b: bytes | None) -> float | None
def rrf_merge(list_a, list_b, limit, *, k=60, id_key="id",
              boost: Callable[[dict], float] | None = None) -> list[dict]

class EmbeddingClient:
    def __init__(self, *, api_key: str, model: str, base_url: str | None = None,
                 dimensions: int | None = None, max_tokens: int = 8191,
                 safety_margin: int = TOKEN_SAFETY_MARGIN, timeout: float = 60.0,
                 log_prefix: str = "otpack", cache_ttl: float = 900.0,
                 cache_max: int = 256): ...
    def embed(self, text: str, *, long_text: Literal["truncate", "mean"] = "truncate",
              use_cache: bool = False) -> list[float]
    def embed_batch(self, texts: list[str], *, batch_size: int = 200,
                    on_batch: Callable[[int, int], None] | None = None,
                    max_attempts: int = 3) -> list[list[float]]
```

- **Why a class**: client, model, dimensions, limits, and the per-instance LRU cache travel together; packs construct one lazily and reuse it. Pure helpers stay module-level so `db.py`/`search.py` call sites don't need a client.
- **Why not extend `otpack/factory.py` or `http.py`**: embedding is a cohesive domain (tokenization + API + fusion + serialization), matching how `batch.py`/`text.py` are organized. `EmbeddingClient` may use `otpack.factory.lazy_client` internally for the OpenAI handle.
- Internals folded in from knowledge: `_prepare_safe_batch` (truncate + empty-string → `" "` guard), `_embed_batch_with_retry` (retry only on HTTP 429/500/503; count-guard `ValueError` raised immediately; exponential backoff `2.0 ** attempt`), sorted-by-index response handling, `dimensions=` passed only when it differs from the model's native default.
- `embed(long_text="mean")` reproduces mem's chunk-mean: batch-embed all windows in one API call, average element-wise.
- Cache: per-instance `OrderedDict` LRU keyed `(sha256(text), model, dimensions)`, opt-in via `use_cache=True` (packs enable it only for query embeddings, never document writes).

### D2: Import boundary — resolution stays in packs, otpack takes resolved values

`otpack/embedding.py` imports nothing from `ot.*`. All config/secret/model resolution stays in the packs, which become thin adapters:

- `_mem/embedding.py` keeps: `_get_config()`, `_get_embedding_model()` (uses `ot.config.get_llm_config`), `get_secret("OPENAI_API_KEY")`, the worker queue/enqueue machinery, and a new `_get_embedding_client()` that builds a module-cached `EmbeddingClient(api_key=…, model=…, base_url=config.base_url or get_llm_config().base_url or None, dimensions=None, max_tokens=config.max_embedding_tokens, log_prefix="mem")`. `_generate_embedding(text)` becomes `client.embed(text, long_text="mean")`; the query path in `_mem/search.py` passes `use_cache=True`.
- `_knowledge/embedding.py` keeps: `_get_config()`, `_get_embedding_model()`, secret lookup, and builds `EmbeddingClient(…, dimensions=config.dimensions, timeout=60.0, log_prefix="kb")`. `generate_embedding` → `client.embed(text, use_cache=True)`; `generate_embeddings_batch` → `client.embed_batch(texts, batch_size=config.embedding_batch_size, on_batch=…)`.
- The client is rebuilt when resolved inputs change (cache key on `(api_key, model, base_url, dimensions, max_tokens)`), so config reloads in tests keep working.

**Alternative rejected**: exempting `embedding.py` from the boundary like `config.py`/`logging.py` — would leak `ot.config` into the wheel and grow the exemption list the boundary test exists to prevent.

### D3: otpack wheel dependency — optional extra, lazy imports

Add to `packages/onetool-pack/pyproject.toml`:

```toml
[project.optional-dependencies]
embedding = ["openai>=2.44.0", "tiktoken>=0.12.0"]
```

`openai` and `tiktoken` are imported lazily inside `EmbeddingClient`/`get_tiktoken_encoding` with install-hint errors (`"openai is required for otpack embedding. Install with: pip install 'onetool-pack[embedding]'"`). The main repo already carries both as core deps (`pyproject.toml:37-38`), so mem/knowledge never hit the ImportError path.

**Alternative rejected**: required deps of the wheel — would bloat every standalone pack that uses only logging/paths/batch.

### D4: Canonical byte order `<{n}f` — no data migration required

- Canonical serialization is **explicit little-endian** `struct.pack(f"<{len(vec)}f", *vec)`; deserialization `struct.unpack(f"<{n}f", blob)` after validating `len(blob) % 4 == 0` (raise `ValueError` otherwise).
- Compat analysis: the only native-order writer is knowledge's `vec_to_bytes` (`{n}f`). For a homogeneous `f` array, native (`@`) and `<` formats produce **byte-identical output on little-endian hosts**, and every supported platform (macOS arm64/x86-64, Linux x86-64/aarch64, Windows x86-64) is little-endian. Therefore existing sqlite-vec blobs and query vectors are already in canonical form — **no reindex, rewrite, or dual-read path is needed**.
- Escape hatch (documented, not automated): a store hypothetically written on a big-endian host would return garbage similarities, not errors; `kb reindex` and `mem.reindex(dry_run=False)` regenerate all vectors and are the recovery path. Both already exist.
- `vec_to_bytes` is deleted; `_knowledge/indexer.py:332`, `_knowledge/crud.py:318`, `_knowledge/search.py:101` switch to `otpack.serialize_embedding`. `_mem/db.py` and `_knowledge/db.py` keep their `_serialize_embedding`/`serialize_embedding` names as thin re-exports/delegates (call-site churn stays minimal: `snapshots.py`, `mutations.py`, `write.py`, `io.py`, `search.py`, `lifecycle.py` keep importing from `db`).
- mem's `_cosine_similarity` SQLite UDF body moves to `otpack.cosine_similarity_blobs`; `_mem/db.py` keeps the UDF registration and its dimension-mismatch error message (which references `mem.reindex`).

### D5: RRF — one function, boost via callback

`rrf_merge(list_a, list_b, limit, k=60, id_key="id", boost=None)` implements `score = Σ 1/(k + rank)` with first-seen result precedence (semantic/FTS list first, matching both current implementations), rounds scores to 4 decimals, and applies `boost(result)` additively per merged id when provided. Knowledge passes `boost=lambda r: 0.1 * min(r.get("hit_count", 0) or 0, 10) / 10`; mem passes none. `_mem/search.py:_search_hybrid` and `_knowledge/search.py:_rrf_merge` both delegate (knowledge keeps `_rrf_merge` as a thin wrapper since it is in its module `__all__`).

### D6: Observability — `log_prefix` preserves pack-attributable spans

`EmbeddingClient` emits `LogSpan(span=f"{log_prefix}.embedding", …)`, `f"{log_prefix}.embedding.batch"`, and retry warnings as `f"{log_prefix}.embedding.retry"` via `otpack.logging` (already boundary-clean). With `log_prefix="mem"` / `"kb"`, existing span names are preserved exactly.

### D7: Behavior deltas accepted (spec'd in deltas)

Convergence intentionally changes two mem behaviors (both upgrades, both spec'd in `specs/ottools/tool-mem/spec.md`):
1. mem's synchronous embed path gains API-level retry (429/500/503, 3 attempts, exponential backoff). The async worker keeps its job-level retry on top — worst case 3×3 attempts over ~½ minute, acceptable for a background daemon thread.
2. mem semantic-search query embeddings are served from the bounded LRU cache.

## Risks / Trade-offs

- [Byte-order assumption: a user's DB was created on a big-endian host] → No supported platform is big-endian; documented recovery is `kb reindex` / `mem.reindex(dry_run=False)`. Deserialize length-validation catches truncated blobs regardless.
- [otpack wheel users without the `embedding` extra get runtime ImportError] → Lazy imports raise with an exact `pip install 'onetool-pack[embedding]'` hint; main-repo users are unaffected (core deps).
- [Boundary regression: new module accidentally imports `ot.*`] → `packages/onetool-pack/tests/test_boundary.py` runs the AST scanner over all otpack modules including the new file; CI fails on violation.
- [mem chunk-mean vs knowledge truncate silently swapped during refactor] → distinct `long_text` argument at the two call sites + unit tests asserting mem averages multi-window text and knowledge embeds only the first window.
- [Doubled retries in mem async worker slow failure surfacing] → bounded (≤9 API attempts, ≤~56s worst case) in a daemon thread that already tolerated ~14s; `_embedding_errors` counter still increments per job failure.
- [Client caching in packs returns stale client after config change] → cache keyed on the resolved value tuple; changing model/base_url/dimensions/api_key rebuilds.

## Migration Plan

1. Land `otpack/embedding.py` + exports + extra + otpack tests (pure addition, no behavior change).
2. Switch knowledge to the shared layer (delete `vec_to_bytes`, delegate retry/cache/dimensions); knowledge unit tests updated in the same commit.
3. Switch mem (client, chunk-mean via `long_text="mean"`, serialization/cosine delegation, RRF delegation, query cache, sync retry); mem unit + integration tests updated.
4. No data migration step: stored vectors are byte-identical under the canonical order on all supported platforms.
5. Rollback: revert commits; on-disk data was never rewritten, so rollback is code-only.

## Open Questions

None — all decisions above are settled; the issue's three caveats (stale survey, import boundary, byte-order migration) are resolved by the re-survey table, D2, and D4 respectively.
