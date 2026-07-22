# P13 — Publish architecture outputs transactionally

## Problem

Export and explorer generation stage individual content, but publish files one at a time. Export writes artifacts, deletes stale files, and writes the manifest last.

A filesystem failure during publication can leave new and old artifacts mixed together, stale files removed, and a manifest that no longer describes the directory.

## Expected

Stage and validate the complete output set before modifying the destination. Publish artifacts and their ownership manifest as one transaction, using a directory swap or an explicit rollback strategy.

`continue_on_error=true` may produce a deliberately partial staged result, but publication itself must still be coherent.

## Actual

`exporter.py` calls `_atomic` separately for each artifact and then removes stale outputs. `frontend.py` similarly replaces the report before replacing its manifest.

## Acceptance Criteria

- Validation or rendering failure leaves the prior destination unchanged.
- Injected failures at every publication phase leave either the complete old set or complete new set.
- The manifest always describes the visible artifact set.
- User-owned files remain untouched.
- Stale owned files are removed only as part of a successful transaction.
- Reuse and deterministic hash behaviour remain intact.

## Context

Review:

- `src/otdev/tools/_arch/v2/exporter.py::export_workspace`
- `src/otdev/tools/_arch/v2/frontend.py::generate_explorer`
- existing atomic-write helpers
- `tool-arch-multi-format-export` ownership and partial-failure requirements

Use `$p-fix` and update the existing capability specs if transaction mechanics need clarification.
