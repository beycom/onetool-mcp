---
name: ot-localhist
description: Use when creating private project checkpoints outside main Git history, inspecting local-history status, diffs, or versions, managing opt-in autosave, or safely restoring selected files from a snapshot.
user-invocable: false
---

# OneTool Local History

Use `localhist` as an independent Git-backed safety net.

## Availability

Check `__ot ot.packs(pattern='localhist', info='min')`, then inspect status. If `[dev]`, Git, or
the local history store is missing, stop and offer installation or initialization guidance; do
not install Git or initialize storage without a separate request.

## Workflow

1. Inspect status and initialize only for an explicitly selected project.
2. Save a checkpoint with a meaningful label before risky edits.
3. Use list, show, and diff to identify the exact version needed.
4. Restore selected files only after reviewing the diff.
5. Verify the working tree after restore.

Autosave is opt-in. Local history is not a remote backup and must not be confused with the
project's main Git history.
