---
name: ot-mem
description: Use when persistently storing or retrieving agent rules, decisions, mistakes, discoveries, notes, or project context in OneTool memory, including search, history, rollback, snapshots, staleness checks, and controlled maintenance.
user-invocable: false
---

# OneTool Memory

Use `mem` for durable agent-oriented memory.

## Capability boundary

Check `__ot ot.packs(pattern='mem', info='min')`. If `[util]`, storage, embedding support, or
credentials are missing, stop and offer installation or configuration guidance; do not install,
initialize storage, or add credentials without a separate request.

The pack supports single/batch CRUD, deterministic grep/query/slice/TOC, semantic/keyword/hybrid
search, question answering, history/rollback, file freshness, YAML dump/load, filesystem
snapshot/restore, decay, reindex, and async embedding flush. Embeddings are optional and activate
only when configured.

## Workflow

1. Store only durable information likely to change future work.
2. Use a stable topic and concise, self-contained content.
3. Search before writing to avoid duplication or contradiction.
4. Retrieve with the least expensive mode; use deterministic read/grep/query before model-backed
   ask or semantic search where possible.
5. For file-backed entries, inspect `stale` and use dry-run `refresh`.
6. Inspect history and create a snapshot before update-batch, rollback, decay, reindex, or restore.
7. Flush pending async embeddings before a result depends on semantic completeness.

## Safety and side effects

Memory is durable and changes future agent behavior. Do not store secrets, transient output, or
unverified claims. Distinguish `dump`/`load` (YAML interchange) from `snapshot`/`restore`
(file-based backup). Maintenance operations can rewrite many records; retain dry-run defaults and
explicit scopes.

## Verification and recovery

Read the exact stored entry, inspect history, compare counts/stats, and verify search mode.
After async writes call `flush` when necessary. On vector/API failure, preserve the text record,
fall back to deterministic retrieval, and retry embedding maintenance once after setup repair.

Do not store secrets or transient tool output indiscriminately. Use `ot_context` for temporary
results and `knowledge` for portable managed corpora.

<!-- BEGIN GENERATED:CATALOG_COVERAGE -->
## Catalog coverage

**Role:** `capability-owner`

| Pack | Extra | Help topics | Docs |
|---|---|---|---|
| `mem` | `[util]` | `overview`, `workflow`, `setup`, `config` | [reference](https://onetool.beycom.online/reference/tools/mem/) |

For a missing pack, dependency, secret, or config field, inspect `ot.help(query='<pack>', topic='setup')` and hand off to `ot-setup`. For outbound MCP server setup or lifecycle, hand off to `ot-mcp-proxy`.
<!-- END GENERATED:CATALOG_COVERAGE -->
