---
name: ot-file
description: Use when file operations must run through a remote OneTool session or require OneTool path enforcement, batch reads, fuzzy resolution, Markdown navigation, backups, trash, or dry-run mutation. Do not replace faster native local tools without a OneTool-specific reason.
user-invocable: false
---

# OneTool File

Use `file` for security-bounded file work in OneTool's effective project context.

## Availability

Check `__ot ot.packs(pattern='file', info='min')`. If `[util]` is missing, stop and offer
installation guidance; do not install or change path configuration without a separate request.

## Workflow

1. Resolve uncertain paths; use bounded reads, trees, searches, TOCs, and slices.
2. Confirm resolved source and destination before mutation.
3. Use dry-run for uncertain operations and precise edits over full rewrites.
4. Preserve backup and trash defaults.
5. Read or inspect the result after mutation.

Treat delete, move, recursive work, symlink following, and replace-all as high impact. Never work
around an allowed-directory denial; inspect `ot.security(check='path')` and explain the boundary.
