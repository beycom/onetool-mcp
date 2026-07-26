---
name: ot-knowledge
description: Use when searching, reading, questioning, annotating, or traversing a configured portable OneTool knowledge base with keyword, semantic, or hybrid retrieval and source-cited synthesis. Use ot-mem for agent memory and ot-context for transient results.
user-invocable: false
---

# OneTool Knowledge

Use `knowledge` for configured SQLite knowledge bases.

## Availability

Check `__ot ot.packs(pattern='knowledge', info='min')`, then list configured databases. If
`[util]`, a database, embedding support, or credentials are missing, stop and offer installation
or configuration guidance; do not create configuration or add credentials without a separate request.

## Workflow

1. Select the intended knowledge base and inspect its status.
2. Prefer keyword retrieval for exact terms and hybrid retrieval for concepts.
3. Read source passages before making consequential claims.
4. Use synthesis only when its cost adds value; retain citations.
5. Confirm scope and backup before annotations or maintenance.

Use `mem` for durable agent-specific decisions and `ot_context` for temporary session material.
Never present model synthesis as source text.
