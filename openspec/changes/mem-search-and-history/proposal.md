# Proposal: mem-search-and-history

## Why

The mem pack's search quality and history story lag behind its storage features. Keyword search is a `LIKE '%…%'` substring match with a hardcoded score of 1.0 (fused via RRF against genuinely ranked semantic results), semantic search is a full-table scan through a pure-Python cosine UDF that degrades linearly with corpus size, and `memory_history` is write-only — `update()`'s docstring promises rollback that no tool provides. The knowledge pack already ships the proven fix for the first two (FTS5/BM25 + sqlite-vec vec0, both dependencies already installed), so mem can adopt the same patterns.

## What Changes

- Replace `LIKE`-based keyword search with an FTS5 external-content index over `memories(topic, content)`, ranked by BM25. Hybrid mode fuses two genuinely ranked lists via RRF. Existing databases are migrated in-place (index created and rebuilt on connection setup); builds without FTS5 fall back to the current LIKE behaviour with a logged warning.
- Add a vec0 virtual table (`memories_vec`) for indexed KNN semantic search when sqlite-vec is available, replacing the full-scan cosine UDF path. `memories.embedding` BLOB remains the source of truth (dump/snapshot round-trip unchanged); the vec index is dual-written on every embedding write and backfilled from stored BLOBs on migration. Dimension mismatches are skipped with a logged count instead of silently truncating or corrupting the index. Without sqlite-vec, the cosine UDF scan remains as fallback.
- Add two new tools: `mem.history()` (list stored versions of a memory with timestamps and previews) and `mem.rollback()` (restore a previous version as a normal update — the pre-rollback content is itself saved to history, so rollback is undoable). Fulfils the `update()` docstring promise.

Not in scope: the security/correctness bug fixes from the same issue (already landed in 240afa0a and d3f7168e), and the shared embedding-infra extraction tracked separately in `otpack-embedding-infra`.

## Capabilities

### New Capabilities

(none — all changes extend the existing mem pack spec)

### Modified Capabilities

- `ottools/tool-mem`:
  - "Memory Search" requirement changes: keyword mode is FTS5/BM25-ranked (with LIKE fallback), semantic mode uses the vec0 KNN index when available, hybrid fuses two ranked lists.
  - New requirements: "Keyword Search Index" (FTS5 schema, triggers, migration, query sanitisation), "Vector Search Index" (vec0 table, dual-write, backfill migration, dimension handling), "Memory History" (`mem.history()`), "Memory Rollback" (`mem.rollback()`).

## Impact

- **Code**: `src/otutil/tools/_mem/db.py` (schema, triggers, migration, vec/FTS availability checks), `src/otutil/tools/_mem/search.py` (keyword/semantic/hybrid paths), `src/otutil/tools/_mem/embedding.py` + `write.py` + `mutations.py` + `lifecycle.py` (embedding dual-write via shared helper), new `src/otutil/tools/_mem/history.py` (history/rollback tools), `src/otutil/tools/_mem/__init__.py` + `src/otutil/tools/mem.py` (exports), `src/otutil/tools/_mem/lifecycle.py` (`stats()` index status line).
- **Schema**: two new SQLite objects in existing mem databases (`memories_fts` FTS5 table + triggers, `memories_vec` vec0 table + delete trigger); `memories` and `memory_history` tables unchanged. Migration is idempotent and runs on connection setup.
- **Dependencies**: none new — `sqlite-vec>=0.1.9` is already a core dependency (pyproject.toml:63); FTS5 ships in CPython's bundled SQLite.
- **API surface**: two new MCP tools (`mem.history`, `mem.rollback`); `mem.search()` signature unchanged, result ordering improves.
- **Tests**: `tests/ottools/unit/tools/test_mem*.py` — new coverage for FTS ranking, vec index parity with fallback scan, migration of a pre-existing database, history listing, and rollback round-trip.
