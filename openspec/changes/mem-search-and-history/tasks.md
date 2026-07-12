# Tasks: mem-search-and-history

## 1. Schema, migration, and availability plumbing (`_mem/db.py`)

- [x] 1.1 Add `_check_fts_available()` (module-level cached flag) and `_check_vec_available()` / `_require_vec()` following `src/otutil/tools/_knowledge/db.py:30-48`
- [x] 1.2 Add `memories_fts` FTS5 external-content DDL (`topic, content, content='memories', content_rowid='rowid', tokenize='porter unicode61'`) plus insert/update/delete triggers mirroring `_knowledge/db.py:_FTS_TRIGGERS_SQL`; create in `_ensure_tables` inside try/except, setting the fts flag on failure with one `logger.warning`
- [x] 1.3 Add `memories_vec` vec0 DDL (`memory_id TEXT PRIMARY KEY, embedding float[{config.dimensions}]`) and `memories_vec_after_delete` trigger, created in `_ensure_tables` only when sqlite-vec is available (load extension per `_knowledge/db.py:_kb_setup`)
- [x] 1.4 In `_migrate_tables`: detect a freshly created `memories_fts` (check `sqlite_master` before create) and run `INSERT INTO memories_fts(memories_fts) VALUES('rebuild')` once for pre-existing rows
- [x] 1.5 In `_migrate_tables`: vec backfill — anti-join `memories` (embedding NOT NULL) against `memories_vec`, insert L2-normalised vectors where dims match `config.dimensions`; count and log skips (`event="mem.migrate.vec_dim_skipped"`, pointer to `mem.reindex(dry_run=False)`)
- [x] 1.6 In `_migrate_tables`: parse `float[N]` from `sqlite_master.sql` for `memories_vec`; on mismatch with `config.dimensions`, drop, recreate, and backfill
- [x] 1.7 Add `_normalize_vec(vec) -> list[float]` and `_sync_vec_index(conn, memory_id, vec | None)` — delete existing row; insert normalised vector when dims match; delete-only when `vec is None`; silent no-op when sqlite-vec unavailable. Export both plus availability checks in `__all__`

## 2. Embedding dual-write at all write sites

- [x] 2.1 `_mem/write.py` (~line 127): call `_sync_vec_index` after the INSERT when a sync embedding was computed
- [x] 2.2 `_mem/mutations.py` `_apply_memory_update`: call `_sync_vec_index` on the embeddings-enabled branch only (disabled branch preserves BLOB and vec row untouched)
- [x] 2.3 `_mem/embedding.py` `_process_embedding_job`: call `_sync_vec_index` inside the write-back `_use_connection` block (still guarded on unchanged content)
- [x] 2.4 `_mem/lifecycle.py` `reindex`: call `_sync_vec_index` in the per-memory commit block
- [x] 2.5 `_mem/io.py` `load` (~line 237) and `_mem/snapshots.py` `restore` (~line 352): call `_sync_vec_index` after each INSERT with a non-None embedding
- [x] 2.6 Grep `src/otutil/tools/_mem/` for any remaining `embedding = ?` / `_serialize_embedding` write not paired with `_sync_vec_index`; confirm none remain

## 3. Search paths (`_mem/search.py`)

- [x] 3.1 Add `_fts_query(text)` sanitiser (strip FTS operator chars, drop stopwords) and prefix-fallback retry, adapted from `_knowledge/search.py:23-86`
- [x] 3.2 Rewrite `_search_keyword` to a BM25 query joining `memories_fts` to `memories` with existing `_topic_filter`/category/`_tags_filter_sql` filters, `ORDER BY bm25(memories_fts)`, score = `round(abs(bm25), 4)`; keep the current LIKE implementation as `_search_keyword_like` and fall back to it (one-time warning) when FTS5 is unavailable
- [x] 3.3 Rewrite `_search_semantic` to use vec0 KNN (`WHERE v.embedding MATCH ? AND k = ?` joined to `memories`, normalised query vector, `k = max(limit*4, 50)` when filters present, score = `round(1 - distance**2 / 2, 4)`) when sqlite-vec is available and `memories_vec` is non-empty; otherwise keep the existing cosine-UDF scan path unchanged
- [x] 3.4 Verify `_search_hybrid` needs no change beyond receiving two ranked lists; update its docstring

## 4. History and rollback tools

- [x] 4.1 Create `src/otutil/tools/_mem/history.py` with `history(*, topic=None, id=None, limit=10)`: single-match resolution matching `update()` (id overrides; error on 0 or >1), rows from `memory_history` ordered `updated_at DESC, rowid DESC`, numbered v1..vN with history-id 8-char prefix, timestamp, content length, first-line preview; header with current length/updated_at; "No history" message when empty
- [x] 4.2 Add `rollback(*, topic=None, id=None, version=1, history_id=None)` to `history.py`: resolve target by version number or history-id prefix (prefix wins; error on ambiguous/unknown prefix or out-of-range version, naming the valid range); restore via `_redact()` → `_embed_now()` outside the lock → `_apply_memory_update()` + commit → `_enqueue_after_commit()`; docstring notes content-only restore and that rollback is undoable
- [x] 4.3 Export `history` and `rollback` from `_mem/__init__.py` and add to `src/otutil/tools/mem.py` `__all__` + imports

## 5. Observability

- [x] 5.1 `_mem/lifecycle.py` `stats()`: add keyword index line (`fts5` / `like-fallback`) and vector index line (`sqlite-vec (N rows)` / `scan-fallback`, N from `SELECT COUNT(*) FROM memories_vec`)

## 6. Tests (`tests/otutil/unit/tools/test_mem.py` or a new `test_mem_search.py`; markers `unit` + `tools`)

- [x] 6.1 FTS: keyword search ranks a strong BM25 match above a weak one; score is not 1.0; operator-laden query does not error; prefix fallback finds partial terms; topic/category/tags filters apply
- [x] 6.2 FTS fallback: with `_fts_available` forced False, keyword search returns LIKE results and logs a warning
- [x] 6.3 Migration: build a DB with rows before FTS exists (simulate by creating memories table manually), open a connection, assert `memories_fts` matches pre-existing rows
- [x] 6.4 Vec: with sqlite-vec, write memories with fake embeddings, assert `memories_vec` rows exist and are normalised; semantic search returns cosine-equivalent scores matching the UDF-scan results on the same data (parity test); filtered semantic search over-fetches and respects limit
- [x] 6.5 Vec lifecycle: delete removes the vec row (trigger); update replaces it; embeddings-disabled update preserves it; dimension-mismatch vector skips the vec upsert with a log entry
- [x] 6.6 Vec migration: DB with embedding BLOBs but no vec rows backfills on connect; mismatched-dims BLOB is skipped and counted; changing `config.dimensions` drops and recreates `memories_vec`
- [x] 6.7 Vec fallback: with sqlite-vec forced unavailable, semantic search uses the UDF scan and returns identical results
- [x] 6.8 History: update a memory twice, `mem.history()` lists v1/v2 newest-first with previews; zero-match and multi-match topics error; never-updated memory returns "No history"
- [x] 6.9 Rollback: `rollback()` restores v1 and saves pre-rollback content (rollback of rollback returns the original); `version=N+1` errors with valid range; `history_id` prefix selects the right version and ambiguous prefix errors; TOC sections recomputed when meta has `sections`
- [x] 6.10 Stats: output includes keyword and vector index status lines in both available and fallback modes

## 7. Wrap-up

- [x] 7.1 Run `uv run pytest -m "unit and tools" tests/otutil/unit/tools/test_mem.py` (plus any new test file) and the mem integration tests if OPENAI_API_KEY is configured
- [x] 7.2 Run `just check` (ruff + mypy) and fix findings
- [x] 7.3 Verify end-to-end on a scratch DB via `run`: write → search all three modes → update → history → rollback → stats
