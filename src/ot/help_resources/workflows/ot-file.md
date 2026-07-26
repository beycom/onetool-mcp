<!-- Generated from skills/ot-file/SKILL.md; do not edit. -->
# OneTool File

Use `file` for security-bounded file work in OneTool's effective project context.

## Capability boundary

Check `__ot ot.packs(pattern='file', info='min')`. If `[util]` is missing, stop and offer
installation guidance; do not install or change path configuration without a separate request.

Use `resolve` for exact/glob/fuzzy path selection, `list`/`tree`/`search` for names,
`read`/`read_batch` for bounded content, and `toc`/`slice`/`slice_batch` for structured documents.
Use `grep` for content search when pure-Python path enforcement matters; use `ripgrep` for high
performance, types, or advanced regex/glob search. Mutations are `write`, `edit`, `copy`, `move`,
and `delete`.

## Workflow

1. Resolve uncertain paths; use bounded reads, trees, searches, TOCs, and slices.
2. Confirm resolved source and destination before mutation.
3. Use dry-run for uncertain operations and precise edits over full rewrites.
4. Preserve backup and trash defaults.
5. Read or inspect the result after mutation.

## Safety and side effects

Respect allowed directories and exclusions; never work around a path denial. Review overwrite,
recursive scope, symlink following, backup, trash, encoding, and replace occurrence explicitly.
Use `dry_run` where available. Trash is recoverable only when host support/config permits; backup
files are not a substitute for version control.

## Verification and recovery

Resolve and inspect the final path, re-read changed content, and verify source/destination state
after copy/move/delete. If a path is ambiguous, stop and return candidates. On a failed mutation,
inspect whether any partial effect occurred before one bounded retry.

Treat delete, move, recursive work, symlink following, and replace-all as high impact. Never work
around an allowed-directory denial; inspect `ot.security(check='path')` and explain the boundary.
