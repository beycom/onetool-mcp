<!-- Generated from skills/ot-knowledge/SKILL.md; do not edit. -->
# OneTool Knowledge

Use `knowledge` for configured SQLite knowledge bases.

## Capability boundary

Check `__ot ot.packs(pattern='knowledge', info='min')`, then list configured databases. If
`[util]`, a database, embedding support, or credentials are missing, stop and offer installation
or configuration guidance; do not create configuration or add credentials without a separate request.

Keep two workflows distinct. MCP `knowledge.*` owns query/use: database inventory, CRUD,
keyword/vector/hybrid retrieval, graph traversal, and cited synthesis. The `onetool kb` CLI owns
build/maintain: index/reindex, enrich, scrape, and statistics over configured projects. `[scrape]`
is separately opt-in and is not included by `[all]`.

## Workflow

1. Select the named project/database and inspect `knowledge.dbs()`/`info`.
2. For build work, validate `tools.knowledge.kb`, index a representative source, inspect stats, then
   scale; use scrape only for an approved configured source.
3. Prefer grep/keyword for exact terms, semantic for concepts, and hybrid when embeddings are ready.
4. Read source chunks and traverse `related` links before consequential claims.
5. Use `ask`/enrichment only when model cost adds value and preserve citations.
6. Confirm IDs/topics/source paths and backup expectations before CRUD or reindex maintenance.

## Safety and side effects

Index/reindex/enrich/scrape and CRUD mutate SQLite knowledge stores; scraping fetches untrusted
external content and can be costly. Embedding/model requests may disclose content remotely.
Keyword retrieval may remain useful when vector support is unavailable; report degraded mode
instead of presenting it as full hybrid search.

## Verification and recovery

Compare entry/chunk counts and source coverage, run an exact-term query plus a conceptual query,
read cited chunks, and verify graph/citation targets. On an embedding failure, preserve indexed
content, use keyword mode, inspect setup/config once, and retry only the failed stage.

Use `mem` for durable agent-specific decisions and `ot_context` for temporary session material.
Never present model synthesis as source text.
