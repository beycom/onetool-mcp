# Localhist

Project-local history snapshots backed by an independent Git database.

## Highlights

- Private snapshots without committing to the primary Git repository
- Manual saves, global and path-scoped history, diff, and file inspection
- Opt-in background autosave watcher lifecycle
- Conservative path-scoped restore with dry-run default and audit snapshots

## Functions

| Function | Description |
|----------|-------------|
| `localhist.init()` | Initialize the independent local-history Git database |
| `localhist.status(path, status, limit)` | Inspect Git-like working-tree status and dirty counts |
| `localhist.info()` | Inspect initialization state, paths, config, head, and ignore files |
| `localhist.add_exclude(rule)` | Add localhist-only exclude rules to `.localhist/info/exclude` |
| `localhist.add_force_include(rule)` | Add force-include pathspecs to `.onetool/state/localhist/force-include` |
| `localhist.save(message, ...)` | Create a snapshot with optional free-form kind metadata |
| `localhist.autosave_start(path, ...)` | Start or reuse the shared autosave watcher |
| `localhist.autosave_list()` | Inspect shared autosave watcher state |
| `localhist.autosave_stop(path, ...)` | Stop the shared autosave watcher, optionally scoped to a project path |
| `localhist.log(limit, ...)` | List local-history snapshots |
| `localhist.history(path, ...)` | List snapshots that touched a project-relative path |
| `localhist.diff(ref, against, path)` | Return a patch for a snapshot, ref comparison, or worktree comparison |
| `localhist.show(ref, path, offset, limit, tail)` | Return full or partial file content from a snapshot |
| `localhist.restore(ref, paths, ...)` | Restore selected paths from a snapshot |

## Key Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `message` | str | Snapshot commit message |
| `kind` | str | Free-form snapshot kind metadata. Empty defaults to `manual`. |
| `rule` | str \| list[str] | Localhist exclude or force-include pathspec rule |
| `ref` | str | Local-history commit ref, such as `HEAD` or `HEAD~1` |
| `against` | str \| None | Optional comparison ref, or `worktree` to compare a snapshot to current files |
| `path` | str | Project-relative file path, or project directory for `autosave_start()` / `autosave_stop()` |
| `paths` | list[str] | Explicit project-relative paths for restore |
| `offset` | int | One-based first line for partial `show()` reads |
| `limit` | int \| None | Maximum status entries, log/history entries, or lines returned by `show()` |
| `tail` | int \| None | Return the last N lines from `show()` |
| `dry_run` | bool | Restore preview mode. Defaults to `true`. |

## Requires

- `git` available on `PATH`.

## Configuration

### Required

- None — no secrets required.

### Optional

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `tools.localhist.git_dir` | str | `.localhist` | Project-relative Git database directory, or an absolute path containing `{project_id}` for global storage. Cannot be `.git`. |
| `tools.localhist.work_tree` | str | `.` | Project-relative working tree. Must stay inside the effective project cwd. |
| `tools.localhist.autosave.poll_interval_seconds` | float | `30.0` | Watcher polling interval. |
| `tools.localhist.autosave.quiet_period_seconds` | float | `30.0` | Required quiet period after the last detected dirty worktree change before autosaving. |
| `tools.localhist.autosave.min_save_interval_seconds` | float | `120.0` | Minimum interval between autosave snapshots. |
| `tools.localhist.autosave.heartbeat_timeout_seconds` | float | `120.0` | Time after which missing watcher heartbeats are considered stale. |
| `tools.localhist.autosave.message_prefix` | str | `autosave` | Prefix for watcher-generated snapshot messages. |

```yaml
tools:
  localhist:
    git_dir: .localhist
    work_tree: .
    autosave:
      poll_interval_seconds: 30.0
      quiet_period_seconds: 30.0
      min_save_interval_seconds: 120.0
      heartbeat_timeout_seconds: 120.0
      message_prefix: autosave
```

### Defaults

- If `tools.localhist` is omitted, localhist stores its Git database in `.localhist/` and snapshots the effective project cwd.
- Absolute `git_dir` values must include `{project_id}` so global storage paths remain project-specific.
- Localhist uses the project `.gitignore` through Git's native ignore handling.
- `localhist.init()` ensures the primary `.gitignore` ignores `.localhist/`, ensures `.localhist/info/exclude` includes `.git/`, `.onetool/state/localhist/`, and the configured local-history Git directory, and creates `.onetool/state/localhist/force-include`.
- Snapshot staging ensures localhist-owned excludes exist, runs `git add -A -- .`, then force-adds pathspecs from `.onetool/state/localhist/force-include`.
- Force-includes must be literal project-relative paths and cannot target `.git/`, `.onetool/state/localhist/`, or the configured local-history Git directory.
- `status()` reports working-tree file status. Use `info()` for initialization metadata, paths, config, head, branch, and ignore-file locations.
- `diff()` and `show()` cap returned content at 1 MB and include `truncated`, `max_bytes`, and `bytes_returned` metadata.
- `autosave_start()` and `autosave_list()` return the effective `tools.localhist` config, including `autosave` scheduling values.
- Autosave watcher runtime state is stored under `.onetool/state/localhist/`.
- The short pack alias is `lh`.
- No public `localhist.autosave(reason=...)` tool is exposed; autosave snapshots are created only by an active watcher.

## Examples

```python
# Initialize local history for the current project
localhist.init()
localhist.info()

# Save a manual checkpoint before a risky edit
localhist.save(message="before parser rewrite")
localhist.save(message="before generated update", kind="generated")

# Add localhist-only ignore and force-include rules
localhist.add_exclude(rule="tmp/")
localhist.add_force_include(rule="important.generated")

# Start and inspect background autosave
localhist.autosave_start()
localhist.autosave_list()
localhist.autosave_stop()

# Inspect recent snapshots and review a diff
localhist.log(limit=5)
localhist.history(path="src/parser.py", limit=5)
localhist.diff(ref="HEAD")
localhist.diff(ref="HEAD~1", against="HEAD", path="src/parser.py")
localhist.show(ref="HEAD", path="src/parser.py", offset=1, limit=80)

# Preview and then apply a path-scoped restore
localhist.restore(ref="HEAD~1", paths=["src/parser.py"])
localhist.restore(ref="HEAD~1", paths=["src/parser.py"], dry_run=False)

# To remove local-history state, delete the configured localhist Git directory.
```
