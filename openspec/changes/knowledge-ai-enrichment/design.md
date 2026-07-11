# Design: knowledge-ai-enrichment

## Context

The `chunks` table has a nullable `summary` column (`src/otutil/tools/_knowledge/db.py:77`); `chunks_fts` indexes it (`db.py:110-119`) and the insert/delete/update triggers keep it in sync (`db.py:121-138`); `kb.stats()` reports summary coverage (`listing.py:371-380`). No code path ever writes `summary`, so coverage is always 0%.

Existing conventions this design follows:

- LLM client: `retrieval.py:_create_llm_client()` — `OPENAI_API_KEY` from secrets, `base_url = config.base_url or get_llm_config().base_url`, 60 s timeout, wrapped in `lazy_client` and reset via `reset_runtime_cache()` (registered as reload hook in `knowledge.py:register_services`).
- Model resolution: `config.enrich_model or get_llm_config().model or "gpt-4o-mini"` — already used by `_llm_rerank()` (`retrieval.py:396`) and `_synthesise()` (`retrieval.py:434`).
- Untrusted-context boundary: `_UNTRUSTED_CONTEXT_SYSTEM` (`retrieval.py:46-50`) is sent as a system message on every LLM call that carries indexed content.
- Batch resilience: `_store_embeddings_batch()` (`indexer.py:257-345`) — per-batch commit for durable progress, per-item fallback, abort after `_FALLBACK_ABORT_AFTER = 5` consecutive failures, error summary string.
- Maintenance ops are CLI-only: `kb index` / `kb reindex` live in `src/onetool/kb.py`, are not exported pack tools, and the main spec forbids advertising them as `kb.index()` / `kb.reindex()`.

## Goals / Non-Goals

**Goals:**

- Populate `chunks.summary` with short LLM-generated document summaries, on demand and optionally at index time.
- Backfill support for existing databases (select-missing semantics make every run a backfill).
- Keep stale summaries out of the index: clear on content change.
- Make summaries useful in retrieval: FTS matches them (already wired), and `kb.search()` displays them.
- Bounded cost: opt-in only, per-run limit, skip trivially short chunks.

**Non-Goals:**

- No embedding of summaries and no re-embedding of content+summary — the vector lane is untouched (re-embedding would invalidate every stored vector and duplicate the reindex pipeline).
- No automatic enrichment from pack tools (`kb.write`/`kb.update`/`kb.search` never call the enrichment LLM).
- No tag generation or other enrichment kinds — summaries only (stats' "tags" coverage is already fed by chunker/sidecar tags).
- No new pack tool export (`kb.enrich()` stays CLI-only, like index/reindex).
- No async/concurrent LLM calls — sequential with progress callback, matching the pack's synchronous style.

## Decisions

### D1: New module `src/otutil/tools/_knowledge/enrichment.py`

Public surface:

```python
@dataclass
class EnrichResult:
    enriched: int = 0
    skipped_short: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)

def enrich_db(
    *,
    db_name: str,
    limit: int | None = None,
    force: bool = False,
    ids: list[str] | None = None,
    on_progress: Callable[[int, int], None] | None = None,
) -> EnrichResult: ...
```

- Selection: `WHERE (summary IS NULL OR summary = '')` unless `force=True` (all rows), further narrowed to `id IN (...)` when `ids` is given (used by `kb index --enrich` for just-indexed chunks), `AND topic != '_meta'`, `ORDER BY topic`, `LIMIT ?` when `limit` is set.
- Chunks whose `length(content) < enrich_min_chars` are counted as `skipped_short` and get `summary = ''` written (empty string ≠ NULL: marks "deliberately not summarised" so re-runs don't reselect them; stats already counts only non-empty summaries as enriched — `listing.py:373`).
- Writes go through `UPDATE chunks SET summary = ? WHERE id = ?`; the existing `chunks_fts_after_update` trigger propagates to FTS. `updated_at` is NOT touched (enrichment is metadata, not a content edit).
- Rationale for a new module over extending `indexing.py`: enrichment has its own client, prompt, and failure policy; `indexing.py` is the thin tool-facing wrapper layer.

Alternative considered: reuse `ot_llm` pack's `transform()`. Rejected — packs don't call other packs' tools; knowledge already owns direct OpenAI client usage for rerank/synthesis.

### D2: LLM call shape — one chat completion per chunk

Each chunk gets its own call: system = untrusted-context boundary + summarisation instruction, user = `topic` + content truncated to `enrich_max_chars` characters, `max_tokens=120`.

- Alternative — batch N chunks per call with delimited/JSON output: fewer calls but fragile parsing (the comma-separated rerank parser is already the weakest spot in `retrieval.py`), partial-failure attribution is unclear, and a single oversized chunk poisons the whole call. Rejected.
- Per-chunk calls keep failure isolation trivial and retry semantics simple. Cost control comes from opt-in invocation, `--limit`, and `skipped_short`.

Default prompt (constant `_DEFAULT_ENRICH_PROMPT` in `enrichment.py`, overridable via `enrich_prompt` config):

> Summarise the following documentation chunk in 1-2 plain sentences (max ~50 words). State what it covers and when a reader would need it. No markdown, no preamble.

The system message concatenates `_UNTRUSTED_CONTEXT_SYSTEM` (imported from `retrieval.py`) with the prompt, so indexed content cannot inject instructions.

### D3: Client and model resolution — reuse `retrieval._get_llm_client`

`enrichment.py` imports `_get_llm_client` from `retrieval.py` (no import cycle: retrieval does not import enrichment). This keeps a single lazy client that `reset_runtime_cache()` already resets on `ot.reload()`. Model: `config.enrich_model or get_llm_config().model or "gpt-4o-mini"` — identical to rerank/synthesis.

Difference from `kb.ask`: when the client is `None` (no `OPENAI_API_KEY`), `kb.ask` degrades gracefully; `enrich_db` raises `ValueError("OPENAI_API_KEY not configured in secrets.yaml (required for kb enrich)")` — a maintenance command must fail loudly, mirroring `_get_openai_client()` in `embedding.py:61-63`.

### D4: Failure handling — mirror the embedding batch policy

- Per chunk: `try/except`; on failure append `f"chunk {id}: {err}"` to `errors`, increment `failed`, continue.
- Retry: transient HTTP 429/500/503 retried up to 3 attempts with exponential backoff (same statuses as `_RETRYABLE_HTTP_STATUS` in `embedding.py`; small local helper — `_embed_batch_with_retry` is embeddings-specific).
- Abort: after 5 consecutive failures (module constant, same value as `indexer._FALLBACK_ABORT_AFTER`) stop the run and record how many chunks were left unprocessed — an outage, not a content problem. Unprocessed chunks still have `summary IS NULL`, so the next run resumes them for free.
- Durability: commit every `enrich_batch_size` (default 20) summaries so an aborted run keeps its progress.
- Empty/whitespace LLM response: treated as a failure for that chunk (never write an accidental `''`, which would mark it skipped).

### D5: Config additions (`config.py::Config`)

| Key | Default | Meaning |
|---|---|---|
| `enrich_model` | `""` (existing) | Chat model; empty → `llm.model` |
| `enrich_prompt` | `""` | Custom summarisation instruction; empty → built-in default. (Main spec's config-schema requirement already lists this key; the field is currently missing from `Config` — this closes that gap.) |
| `enrich_batch_size` | `20` (ge=1, le=500) | Summaries per DB commit |
| `enrich_min_chars` | `400` (ge=0) | Content shorter than this is skipped (`summary=''`); 0 disables skipping |
| `enrich_max_chars` | `6000` (ge=200) | Content truncated to this many chars in the prompt |

Char-based truncation (not tokens): summaries don't need tiktoken precision, and 6000 chars is far below any chat-model context limit.

### D6: When enrichment runs

1. **On demand / backfill**: `onetool kb enrich <db> [--limit N] [--force]` — new Typer command in `src/onetool/kb.py`, Rich progress bar like `cmd_reindex`, prints `Enriched N chunks, skipped M short, F failed` plus up to 5 error lines.
2. **At index time (opt-in)**: `onetool kb index <project> --enrich` — after the embedding phase and link-graph pass, `cmd_index` calls `enrich_db(db_name=db, ids=<chunk ids inserted/updated this run>)`. `index_directory` already collects `pending: list[(chunk_id, content)]`; `IndexResult` gains `chunk_ids: list[str]` (populated from every `_upsert_chunk` return, including when embeddings are disabled) so the CLI can pass exactly the affected chunks. Default remains no enrichment.
3. **Never** from pack tool calls — interactive latency and silent cost are unacceptable; the pack surface is read/annotate, maintenance is CLI.

### D7: Invalidation on content change

Stale summaries describing old content are worse than none. Wherever content is rewritten, `summary` is reset to `NULL` in the same UPDATE statement:

- `indexer._upsert_chunk` update branch (`indexer.py:211-226`): add `summary = NULL` to the SET list.
- `crud.update` (`crud.py:249-252`): add `summary = NULL`.
- `crud.append` (`crud.py:193-196`): add `summary = NULL`.

`kb.write` inserts leave `summary` NULL already (eligible for the next enrich run). Deletion needs nothing (row + FTS cascade).

### D8: Summaries in search results

- `_exec_fts` and `search_vec` SELECTs (`search.py:37-49, 103-114`) add `c.summary`; `_row_to_result` (`search.py:199-215`) carries `"summary"` through; `_graph_expand` in `retrieval.py` adds `summary: None`-safe handling (its rows may omit it — select it there too for consistency).
- `retrieval.search()` formatting (`retrieval.py:160-175`): when `r["summary"]` is non-empty, the result line shows the summary in place of the truncated content extract; otherwise the current extract behaviour is unchanged. Full content remains available via `kb.read`.
- No change to FTS matching itself: the `chunks_fts` table already indexes `summary`, so BM25 matches summary terms as soon as the column is populated.
- `kb.ask` synthesis context keeps using raw content (summaries are lossy; synthesis wants detail).

## Risks / Trade-offs

- [LLM cost on large KBs (1 call/chunk)] → opt-in only; `--limit` for incremental backfill; `enrich_min_chars` skips stubs; consecutive-failure abort stops runaway retries.
- [Summary quality varies by model; hallucinated summaries pollute FTS] → prompt constrains to describing the chunk; summaries are display + FTS boost only, never fed to `kb.ask` synthesis as a substitute for content; `--force` allows regeneration after a model/prompt upgrade.
- [`summary=''` sentinel for "skipped short" conflates "no summary" and "deliberately none" in `chunks_fts`] → FTS treats `''` as no tokens (harmless); stats already distinguishes via `summary != ''`; `--force` re-evaluates skipped chunks.
- [Prompt injection from indexed content] → same `_UNTRUSTED_CONTEXT_SYSTEM` boundary as rerank/synthesis; output is stored as plain text, never executed.
- [Enrichment UPDATE fires the FTS delete+insert trigger per chunk — write amplification] → batched commits (default 20) keep transaction count low; enrichment is an offline CLI operation.
- [`ids=` list for `--enrich` could be large (SQLite host-parameter limit)] → chunk the `IN (...)` selection into batches of 500 ids.

## Migration Plan

No schema migration — `summary` column, FTS config, and triggers already exist in every database created by the current `_kb_setup`. Existing databases: run `onetool kb enrich <db>` once to backfill. Rollback: stop running the command; to clear generated data, `UPDATE chunks SET summary = NULL` (no tooling needed).

## Open Questions

None — all decisions above are settled for this change. Batch-per-call summarisation and summary-aware embeddings are explicitly deferred (see Non-Goals) and can be revisited if per-chunk cost proves problematic on very large KBs.
