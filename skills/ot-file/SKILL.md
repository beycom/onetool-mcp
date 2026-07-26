---
name: ot-file
description: Use when file operations must run through a remote OneTool session or require OneTool path enforcement, batch reads, fuzzy resolution, Markdown navigation, backups, trash, or dry-run mutation. Do not replace faster native local tools without a OneTool-specific reason.
user-invocable: false
---

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

<!-- BEGIN GENERATED:CATALOG_COVERAGE -->
## Catalog coverage

**Role:** `capability-owner`

| Pack | Extra | Help topics | Docs |
|---|---|---|---|
| `file` | `[util]` | `overview`, `workflow`, `setup`, `config` | [reference](https://onetool.beycom.online/reference/tools/file/) |
| `ripgrep` | `[dev]` | `overview`, `workflow`, `setup`, `config` | [reference](https://onetool.beycom.online/reference/tools/ripgrep/) |

For a missing pack, dependency, secret, or config field, inspect `ot.help(query='<pack>', topic='setup')` and hand off to `ot-setup`. For outbound MCP server setup or lifecycle, hand off to `ot-mcp-proxy`.
<!-- END GENERATED:CATALOG_COVERAGE -->
