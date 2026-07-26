---
name: ot-context
description: Use when a OneTool result or long JSON, YAML, log, or document must be stored behind a temporary handle and searched, sliced, queried, or questioned selectively. Use for session context, not durable memory or a portable knowledge base.
user-invocable: false
---

# OneTool Context

Use `ot_context` (`ctx`) as temporary, TTL-expiring storage for large content.

## Availability

Check `__ot ot.packs(pattern='ot_context', info='min')`. If unavailable, use
`ot.result(handle=...)` for basic paging. Stop and offer OneTool installation guidance before
trying context operations; do not install or configure anything without a separate request.

## Workflow

1. Reuse an automatically returned handle or store content with `ot_context.write`.
2. Inspect structure with `toc`, `query`, or `grep`; read only targeted slices.
3. Use `ask` only when deterministic retrieval cannot answer.
4. Return the smallest useful material and delete disposable handles when requested.

Use `mem` for durable agent memory and `knowledge` for configured portable corpora. Pass the
handle string, never the containing result object, and expect configured TTL expiry.
