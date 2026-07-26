---
name: ot-mem
description: Use when persistently storing or retrieving agent rules, decisions, mistakes, discoveries, notes, or project context in OneTool memory, including search, history, rollback, snapshots, staleness checks, and controlled maintenance.
user-invocable: false
---

# OneTool Memory

Use `mem` for durable agent-oriented memory.

## Availability

Check `__ot ot.packs(pattern='mem', info='min')`. If `[util]`, storage, embedding support, or
credentials are missing, stop and offer installation or configuration guidance; do not install,
initialize storage, or add credentials without a separate request.

## Workflow

1. Store only durable information likely to change future work.
2. Use a stable topic and concise, self-contained content.
3. Search before writing to avoid duplication or contradiction.
4. Retrieve narrowly and verify remembered claims against current source state.
5. Inspect history and create a snapshot before destructive maintenance or rollback.

Do not store secrets or transient tool output indiscriminately. Use `ot_context` for temporary
results and `knowledge` for portable managed corpora.
