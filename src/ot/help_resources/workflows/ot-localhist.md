<!-- Generated from skills/ot-localhist/SKILL.md; do not edit. -->
# OneTool Local History

Use `localhist` as an independent Git-backed safety net.

## Capability boundary

Check `__ot ot.packs(pattern='localhist', info='min')`, then inspect status. If `[dev]`, Git, or
the local history store is missing, stop and offer installation or initialization guidance; do
not install Git or initialize storage without a separate request.

Use `init`/`status` for repository state, excludes/force-includes for capture policy,
`save`/`log`/`history`/`show`/`diff` for snapshots, autosave operations for the opt-in watcher,
`restore` for selected paths, and `prune(older_than_days=..., dry_run=True)` for retention. This is
independent local Git storage, not the project's main Git repository or a remote backup.

## Workflow

1. Inspect status and initialize only for an explicitly selected project.
2. Save a checkpoint with a meaningful label before risky edits.
3. Review exclusions/force-includes; add narrowly scoped rules only when explicitly needed.
4. Use log/history/show/diff to identify the exact snapshot and paths.
5. Dry-run restore, save a safety snapshot, then restore only reviewed paths.
6. For prune, keep `dry_run=True`, inspect the cutoff/result, and approve history rewrite/GC.
7. Verify status/content after restore or retention changes.

## Safety and side effects

Initialization creates `.localhist` state. Autosave launches/reuses a watcher. Restore changes the
working tree. Prune rewrites snapshot history and optional GC can make removed objects
unrecoverable. Force-includes must not bypass protected internal paths; never use broad traversal or
pathspec magic to capture secrets.

## Verification and recovery

Confirm repository info/head, inspect post-operation status/diff, and verify restored file content.
After prune, compare dry-run and actual counts. On Git/config failure, preserve the store, inspect
setup and paths once, and avoid reinitialization as automatic recovery.

Autosave is opt-in. Local history is not a remote backup and must not be confused with the
project's main Git history.
