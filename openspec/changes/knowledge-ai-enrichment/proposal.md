# Proposal: knowledge-ai-enrichment

## Why

The knowledge pack advertises "AI enrichment" (module docstring, `kb.stats()` output, `summary` column with full FTS/trigger/stats plumbing in `src/otutil/tools/_knowledge/db.py`), but nothing ever writes the `summary` column — enrichment coverage is permanently 0%. The schema, FTS index (`chunks_fts` includes `summary`), sync triggers, and stats reporting are all in place; only the generation pipeline is missing. This was the one deferred item from the knowledge-pack fixes issue (bug fixes landed in 3e796d42 / d3f7168e).

## What Changes

- New enrichment module `src/otutil/tools/_knowledge/enrichment.py` that generates 1–2 sentence document summaries via an OpenAI-compatible chat LLM and writes them to `chunks.summary`.
- New CLI command `onetool kb enrich <db>` (in `src/onetool/kb.py`) — backfills summaries for chunks missing them; resumable, batched commits, per-chunk failure isolation with consecutive-failure abort. `--limit` caps chunks per run; `--force` regenerates existing summaries. Enrichment stays CLI-only, matching `kb index` / `kb reindex` (not exported as pack tools).
- Opt-in `--enrich` flag on `onetool kb index` runs enrichment for newly indexed/updated chunks after the embedding phase.
- Summary invalidation: content changes (indexer update path, `kb.update()`, `kb.append()`) clear the stale summary so the next `kb enrich` regenerates it.
- Config additions under `tools.knowledge` following the existing ot_llm fallback convention: `enrich_prompt` (already promised by the main spec, currently missing from `Config`), `enrich_batch_size`, `enrich_min_chars`, `enrich_max_chars`. Existing `enrich_model` (falls back to top-level `llm.model`) is reused as the enrichment model.
- Summaries surface in retrieval: `kb.search()` result lines show the summary when present (content extract otherwise); FTS matching over summaries already works via the existing `chunks_fts` triggers, so enriched chunks become findable by summary terms in `keyword` and `hybrid` modes with no search-code change to the FTS lane.
- `kb.stats()` AI-enrichment coverage line becomes meaningful (no code change; verified by spec scenario).

## Capabilities

### New Capabilities

(none — enrichment is a new requirement group within the existing `knowledge-pack` capability)

### Modified Capabilities

- `knowledge-pack`:
  - New requirement: AI enrichment — summary generation (`kb enrich` CLI: selection, model/config resolution, prompt boundary, batching, failure handling, backfill).
  - New requirement: Summary invalidation on content change.
  - New requirement: Summaries participate in search (FTS lane + result display).
  - Modified requirement: Config schema — `tools.knowledge` gains `enrich_prompt`, `enrich_batch_size`, `enrich_min_chars`, `enrich_max_chars`; documents `enrich_model` fallback for enrichment.

## Impact

- Code: `src/otutil/tools/_knowledge/enrichment.py` (new), `src/otutil/tools/_knowledge/config.py`, `src/otutil/tools/_knowledge/indexer.py` (invalidation on update), `src/otutil/tools/_knowledge/crud.py` (invalidation in update/append), `src/otutil/tools/_knowledge/search.py` + `retrieval.py` (summary in result rows/formatting), `src/onetool/kb.py` (new `enrich` command, `--enrich` flag on `index`).
- Config: new optional keys under `tools.knowledge`; no breaking changes, all defaults preserve current behaviour (enrichment never runs unless invoked).
- Dependencies: none new — reuses `openai` client, `OPENAI_API_KEY` secret, and top-level `llm:` fallbacks already used by rerank/synthesis in `retrieval.py`.
- Cost: enrichment makes one chat-completion call per chunk; it is opt-in (explicit CLI invocation or `--enrich`), never triggered by pack tool calls.
- Tests: extend `tests/otutil/unit/tools/test_knowledge.py` (mocked LLM client), no integration-test requirement.
