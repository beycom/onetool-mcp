# Design: mem-search-and-history

## Context

The mem pack (`src/otutil/tools/mem.py` + `src/otutil/tools/_mem/`, ~4.4k lines) stores memories in a single SQLite database (`memories` + `memory_history` tables, `src/otutil/tools/_mem/db.py`). Current state after the 240afa0a/d3f7168e bug-fix commits:

- **Keyword search** (`_search_keyword`, `search.py:254`): `LIKE '%…%'` over content and topic, ordered by `relevance DESC, updated_at DESC` — not query relevance — with every hit given a hardcoded `score: 1.0`.
- **Semantic search** (`_search_semantic`, `search.py:207`): full-table scan through the `cosine_similarity` Python UDF registered in `db.py:65`. O(n) per query with per-row `struct.unpack` cost.
- **Hybrid** (`_search_hybrid`, `search.py:299`): RRF over the two lists; keyword rank is not relevance-ranked, so fusion is fusing noise on the keyword side.
- **History**: `memory_history(id, memory_id, content, updated_at)` is written by `_apply_memory_update` (`mutations.py:46`) and deleted alongside its memory, but there is no tool to list or restore versions, despite `update()`'s docstring saying "Stores previous content in history for rollback".

The knowledge pack (`src/otutil/tools/_knowledge/db.py`, `search.py`) already implements the target patterns in this repo: an FTS5 external-content table with sync triggers, a `vec0` virtual table gated on sqlite-vec availability, BM25 keyword search with query sanitisation and prefix fallback, KNN vector search, and RRF fusion. `sqlite-vec>=0.1.9` is already a core dependency (`pyproject.toml:63`).

Connection setup runs `_ensure_tables` → `_migrate_tables` on every new connection (`db.py:63-142` via `SqlitePool` setup fn), giving us an idempotent migration hook for existing databases.

## Goals / Non-Goals

**Goals:**

- BM25-ranked keyword search via an FTS5 index, migrated in-place for existing databases, with graceful LIKE fallback where FTS5 is unavailable.
- Indexed KNN semantic search via a `vec0` table when sqlite-vec is available, with the existing UDF scan as fallback; `memories.embedding` BLOB stays the source of truth.
- `mem.history()` and `mem.rollback()` tools over the existing `memory_history` table.
- Zero new dependencies; no change to `mem.search()`'s signature; dump/snapshot round-trip unchanged.

**Non-Goals:**

- Extracting shared embedding infrastructure into otpack (tracked as `otpack-embedding-infra`).
- Changing the `memories` or `memory_history` table schemas.
- History retention/pruning policies (history grows as today; `delete()` already cleans up per-memory).
- Re-ranking, chunk-level vector search, or any change to how embeddings are generated.

## Decisions

### D1: FTS5 external-content index, mirroring the knowledge pack

Add to `_mem/db.py`, following `_knowledge/db.py:110-138`:

```sql
CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
    topic, content,
    content='memories', content_rowid='rowid',
    tokenize = 'porter unicode61'
);
```

plus `AFTER INSERT` / `AFTER DELETE` / `AFTER UPDATE` triggers on `memories` keeping the index in sync (same shape as `chunks_fts_after_*`).

- **Migration**: in `_migrate_tables`, when `memories_fts` is newly created for a database that already has rows, run `INSERT INTO memories_fts(memories_fts) VALUES('rebuild')` once. Guard: only rebuild when the FTS table was just created (check `sqlite_master` before creating). Idempotent and safe on every connection.
- **Availability**: unlike knowledge (which hard-fails without FTS5, `_knowledge/db.py:160-163`), mem degrades: wrap FTS creation in try/except, cache a module-level `_fts_available` flag, and have `_search_keyword` fall back to the current LIKE implementation with a `logger.warning` once. Rationale: mem is a default-on pack that must keep working on exotic SQLite builds; search availability beats strictness here.
- **Query path**: `_search_keyword` becomes a BM25 query joining `memories_fts` to `memories` (reusing `_topic_filter` / `_tags_filter_sql` / category filters on the joined table), `ORDER BY bm25(memories_fts) LIMIT ?`. Reported score is `abs(bm25)` rounded to 4 places (higher = better, consistent with knowledge). Query text is sanitised with the knowledge `_fts_query` approach (strip FTS operator chars, drop stopwords) and retried with `term*` prefix suffixes when the exact query yields nothing — this preserves the substring-ish forgiveness users get from LIKE today.
- **Hybrid**: `_search_hybrid` is unchanged structurally (RRF, k=60) but now fuses two genuinely ranked lists.

*Alternative considered*: contentless FTS or a separate normalised keyword column — rejected; external-content FTS is the established repo pattern and costs no content duplication.

### D2: vec0 KNN index with normalised vectors; BLOB remains source of truth

Add to `_mem/db.py`, gated on a `_check_vec_available()` / `_require_vec()` pair copied from `_knowledge/db.py:30-48`:

```sql
CREATE VIRTUAL TABLE IF NOT EXISTS memories_vec USING vec0(
    memory_id TEXT PRIMARY KEY,
    embedding float[{dims}]           -- dims = config.dimensions (default 1536)
);
CREATE TRIGGER IF NOT EXISTS memories_vec_after_delete AFTER DELETE ON memories BEGIN
    DELETE FROM memories_vec WHERE memory_id = old.id;
END;
```

- **Source of truth**: `memories.embedding` BLOB is unchanged and remains authoritative — dump/snapshot round-trip, the fallback scan, and dimension-mismatch diagnostics all keep working. `memories_vec` is a derived index.
- **Dual-write helper**: new `_sync_vec_index(conn, memory_id, vec)` in `db.py`: deletes any existing vec row, then inserts the **L2-normalised** vector when `len(vec) == config.dimensions`; skips (debug log) on dimension mismatch; deletes only when `vec is None`. Called at all six embedding write sites: `write.py:127` (insert), `io.py:237` (load), `snapshots.py:352` (restore), `mutations.py` `_apply_memory_update` (only on the embeddings-enabled branch — the disabled branch preserves both BLOB and vec row), `embedding.py:_process_embedding_job` (worker write-back), `lifecycle.py:reindex`. No-ops silently when sqlite-vec is unavailable.
- **Normalisation**: vectors are L2-normalised before insertion into `memories_vec` and the query vector is normalised too. Why: chunked-and-averaged embeddings (`embedding.py:_generate_embedding`) are not unit-norm, so raw L2 distance would not preserve cosine ranking. With unit vectors, L2 KNN ordering equals cosine ordering exactly, and the reported score can be converted back losslessly: `score = 1 - distance²/2` — keeping the 0..1 cosine score semantics users see today. The BLOB keeps the raw un-normalised vector.
- **Query path**: `_search_semantic` uses the KNN form when sqlite-vec is available and `memories_vec` is non-empty: `WHERE v.embedding MATCH ? AND k = ?` joined to `memories` (pattern: `_knowledge/search.py:103-114`). Because KNN selects k nearest *before* join filters apply, over-fetch when topic/category/tags filters are present: `k = max(limit * 4, 50)`, then filter and `LIMIT` in the outer query. Otherwise (no sqlite-vec, or empty index) fall back to the existing cosine-UDF scan unchanged.
- **Backfill migration**: in `_migrate_tables`, when sqlite-vec is available, insert missing rows: for each `memories` row with `embedding IS NOT NULL` and no `memories_vec` row, normalise and insert if dims match `config.dimensions`; count and log skips (`mem.migrate.vec_dim_skipped`) pointing at `mem.reindex(dry_run=False)`. Cheap no-op when nothing is missing (single anti-join SELECT).
- **Dimension change**: if the existing `memories_vec` DDL (from `sqlite_master.sql`, parse `float[N]`) disagrees with `config.dimensions`, drop and recreate the vec table, then backfill. Stored BLOBs of the old dimension are skipped by the dims guard and reported via the skip log.

*Alternative considered*: `distance_metric=cosine` on the vec0 column — works, but normalisation keeps parity with the knowledge pack's L2 usage while additionally making the reported score an exact cosine; and normalising fixes the averaged-chunk-vector problem either way.

### D3: `mem.history()` and `mem.rollback()` in a new `_mem/history.py`

New module `src/otutil/tools/_mem/history.py`, exported via `_mem/__init__.py` and added to `mem.py` `__all__`/imports.

- **`history(*, topic=None, id=None, limit=10)`**: resolves the memory with the same single-match rule as `update()` (exact topic match; `id` overrides; error on 0 or >1 matches). Lists `memory_history` rows for that memory ordered newest-first (`updated_at DESC, rowid DESC`), numbered `v1..vN` where v1 is the most recent prior version. Each line: version number, history-row id prefix (8 chars), timestamp, content length, first-line preview. Header shows the current content's length and `updated_at` for orientation. Returns "No history for …" when empty.
- **`rollback(*, topic=None, id=None, version=1, history_id=None)`**: selects the target version by `version` number (default 1 = most recent prior version) or explicit `history_id` (full or unambiguous prefix; `history_id` overrides `version`). Restores by running the standard update flow: re-apply `_redact()` to the historical content (idempotent; picks up patterns added since), compute embedding via `_embed_now()` outside the DB lock, then `_apply_memory_update()` + commit + `_enqueue_after_commit()`. Because `_apply_memory_update` saves the pre-rollback content to history first, **rollback is itself undoable** and TOC sections/embeddings are recomputed by the shared path for free. Returns a confirmation naming the memory id and restored version.
- Version numbers are display-order conveniences (they shift as new history accrues); `history_id` is the stable selector — the `history()` output shows both.

*Alternative considered*: destructive "pop" rollback (delete the restored history row) — rejected: non-destructive restore-as-update is simpler, undoable, and matches user expectations from git-style `revert`.

### D4: observability

`stats()` (`lifecycle.py:108`) gains two lines: keyword index status (`fts5` / `like-fallback`) and vector index status (`sqlite-vec, N rows` / `scan-fallback`), so degraded modes are visible without log access.

## Risks / Trade-offs

- [FTS5 triggers add write overhead to every memory write/update] → Negligible at mem's scale (thousands of rows, interactive writes); the knowledge pack already carries the identical trigger set at larger scale.
- [KNN over-fetch (`limit*4`) can still under-fill heavily filtered semantic searches] → Documented behaviour; filters narrow the candidate pool by design. Users needing exhaustive filtered search have grep/keyword modes; the fallback scan path is exact.
- [vec index can silently lack rows whose stored dims mismatch config] → Skips are counted and logged at migration/write time with a `mem.reindex` pointer; `stats()` exposes vec row count vs total for drift spotting.
- [External-content FTS desync if any code path writes `memories` without triggers firing (e.g. future bulk imports using `executemany` still fire triggers — but a manual `DELETE` inside `snapshots.py` restore does fire them too)] → Triggers fire on all DML; only direct file-level manipulation could desync, and `'rebuild'` at migration is the recovery hatch.
- [Rollback restores content only — category/tags/relevance changes since the snapshot are kept] → Intentional: `memory_history` stores content only; documenting in the docstring avoids surprise.
- [Two search implementations per mode (indexed + fallback) doubles the test surface] → Unit tests run both paths explicitly (monkeypatching availability flags); fallback paths are the pre-existing implementations, minimising new code in them.

## Migration Plan

1. Schema objects are created/rebuilt idempotently in `_ensure_tables`/`_migrate_tables` on first connection after upgrade — no manual step, no data rewrite of existing tables.
2. Rollback strategy: dropping `memories_fts` (+ triggers) and `memories_vec` (+ trigger) restores the exact pre-change database; `memories`/`memory_history` are never altered.

## Open Questions

None — all decisions above are settled for implementation.
