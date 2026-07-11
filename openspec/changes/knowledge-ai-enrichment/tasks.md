# Tasks: knowledge-ai-enrichment

## 1. Config

- [x] 1.1 Add `enrich_prompt: str = ""`, `enrich_batch_size: int = 20 (ge=1, le=500)`, `enrich_min_chars: int = 400 (ge=0)`, `enrich_max_chars: int = 6000 (ge=200)` fields to `Config` in `src/otutil/tools/_knowledge/config.py` (next to existing `enrich_model`), with descriptions matching the delta spec
- [x] 1.2 Unit tests: defaults, bounds validation (`enrich_batch_size=0` rejected), `extra="forbid"` still rejects unknown keys (`tests/otutil/unit/tools/test_knowledge.py`)

## 2. Enrichment module

- [x] 2.1 Create `src/otutil/tools/_knowledge/enrichment.py` with `EnrichResult` dataclass (`enriched`, `skipped_short`, `failed`, `errors: list[str]`) and `_DEFAULT_ENRICH_PROMPT` constant (1–2 plain sentences, ~50 words, no markdown)
- [x] 2.2 Implement `enrich_db(*, db_name, limit=None, force=False, ids=None, on_progress=None) -> EnrichResult`: selection `WHERE (summary IS NULL OR summary = '')` (all rows when `force=True`), `AND topic != '_meta'`, optional `id IN (...)` chunked at 500 ids, `ORDER BY topic`, optional `LIMIT`
- [x] 2.3 Client/model resolution: import `_get_llm_client` from `retrieval.py`; raise `ValueError` naming `OPENAI_API_KEY` when client is `None`; model = `config.enrich_model or get_llm_config().model or "gpt-4o-mini"`
- [x] 2.4 Per-chunk call: system message = `_UNTRUSTED_CONTEXT_SYSTEM` + (config `enrich_prompt` or default); user message = topic + content truncated to `enrich_max_chars`; `max_tokens=120`; retry HTTP 429/500/503 up to 3 attempts with exponential backoff
- [x] 2.5 Skip logic: `len(content) < enrich_min_chars` (and `enrich_min_chars > 0`) → write `summary = ''`, count `skipped_short`, no LLM call
- [x] 2.6 Failure handling: empty/whitespace response or exhausted retries → record `"chunk {id}: {err}"`, leave summary `NULL`, continue; abort run after 5 consecutive failures, recording unprocessed count in `errors`
- [x] 2.7 Durability: `UPDATE chunks SET summary = ? WHERE id = ?` (no `updated_at` change), commit every `enrich_batch_size` summaries; `on_progress(done, total)` callback; wrap run in `LogSpan(span="kb.enrich", ...)`
- [x] 2.8 Unit tests with mocked OpenAI client: backfill selection, force, limit, ids filter, short-skip writes `''`, empty response = failure, consecutive-failure abort, per-batch commit survives simulated crash, `updated_at` unchanged, `_meta` excluded

## 3. Invalidation on content change

- [x] 3.1 `src/otutil/tools/_knowledge/indexer.py` `_upsert_chunk` update branch: add `summary = NULL` to the UPDATE SET list
- [x] 3.2 `src/otutil/tools/_knowledge/crud.py`: add `summary = NULL` to the UPDATE statements in `update()` and `append()`
- [x] 3.3 Unit tests: re-index changed content clears summary; `kb.update`/`kb.append` clear summary; FTS no longer matches old summary text after clearing

## 4. Summaries in search results

- [x] 4.1 `src/otutil/tools/_knowledge/search.py`: add `c.summary` to `_exec_fts` and `search_vec` SELECTs; carry `"summary"` through `_row_to_result` (adjust score column index)
- [x] 4.2 `src/otutil/tools/_knowledge/retrieval.py`: add `c.summary` to the `_graph_expand` SELECT and result dict; in `search()` formatting, show `r["summary"]` in place of the content extract when non-empty (extract fallback unchanged)
- [x] 4.3 Unit tests: FTS matches a term present only in summary; result line shows summary when present, extract otherwise; `kb.ask` synthesis context still uses raw content

## 5. CLI

- [x] 5.1 Add `enrich` command to `src/onetool/kb.py`: `onetool kb enrich <db> [--limit N] [--force]`, Rich progress (mirroring `cmd_reindex`), prints `Enriched N, skipped M short, F failed` + up to 5 error lines, non-zero exit on hard errors (e.g. missing API key)
- [x] 5.2 Extend `IndexResult` in `indexer.py` with `chunk_ids: list[str]` populated for every inserted/updated chunk (including when embeddings are disabled)
- [x] 5.3 Add `--enrich` flag to `cmd_index`: after indexing completes, call `enrich_db(db_name=db, ids=result.chunk_ids)` and print the enrichment summary; no flag → no LLM calls
- [x] 5.4 Unit tests: `--enrich` passes only this run's chunk ids; default index run makes no chat-completion calls (assert mocked client not called)

## 6. Docs and verification

- [x] 6.1 Update the knowledge pack docstring/config docs if they enumerate `tools.knowledge` keys (check `docs/` for a knowledge/kb page mentioning enrichment) and mention `onetool kb enrich` in the CLI help text
- [x] 6.2 Run `just lint` and `uv run pytest tests/otutil/unit/tools/test_knowledge.py`; fix findings
- [x] 6.3 Manual smoke: on a small test db, run `onetool kb enrich <db> --limit 2` with a real or stubbed key path and verify `kb.stats` coverage and `kb.search` summary display
