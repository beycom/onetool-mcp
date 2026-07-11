# localhist-pack Specification

## Purpose

Define the Dev extra `localhist` pack for project-local history snapshots, inspection, autosave watcher lifecycle, and restore through MCP tools.

## Requirements

### Requirement: Localhist Pack Exposure
The system SHALL expose a Dev extra `localhist` pack that provides project-local history tools through the OneTool execution namespace.

#### Scenario: Agent calls localhist tool
- **WHEN** the Dev extra is installed and an agent calls a `localhist` tool
- **THEN** the tool SHALL execute against the effective project cwd.

#### Scenario: Git CLI requirement
- **WHEN** a `localhist` tool shells out to Git
- **THEN** the system SHALL require `git` on `PATH` and SHALL NOT require a Python Git library.

#### Scenario: Agent calls localhist alias
- **WHEN** the Dev extra is installed and an agent calls an `lh` tool alias
- **THEN** the alias SHALL resolve to the `localhist` pack.

#### Scenario: Pack summary
- **WHEN** the `localhist` pack metadata is displayed
- **THEN** the pack summary SHALL be `OneTool Local History snapshots backed by Git.`

#### Scenario: No CLI contract
- **WHEN** local history is used in phase one
- **THEN** the system SHALL expose the behavior through MCP tools and SHALL NOT require a OneTool CLI command.

### Requirement: Independent Local History Repository
The system SHALL manage local history in an independent Git database that observes the project working tree without sharing repository state with the primary Git repository.

#### Scenario: Initialize local history
- **WHEN** `localhist.init()` is called for an uninitialized project
- **THEN** the system SHALL create the local-history Git database, configure required local-history settings, write `<git_dir>/.gitignore` to ignore generated localhist contents while allowing that ignore file, ensure `.localhist/info/exclude` contains `.git/`, `.onetool/state/localhist/`, and the configured local-history Git directory, ensure `.onetool/state/localhist/force-include` exists, and return structured initialization status.
- **AND** it SHALL NOT edit the project root `.gitignore`.

#### Scenario: Local history Git identity
- **WHEN** `localhist.init()` initializes or reinitializes the local-history Git database
- **THEN** the database-local Git config SHALL set `user.name` to `OneTool`
- **AND** `user.email` to `localhist@onetool`

#### Scenario: Reinitialize existing local history
- **GIVEN** a local-history Git database already exists
- **WHEN** `localhist.init()` is called
- **THEN** the system SHALL leave existing commits, refs, objects, and configured values intact, avoid duplicate exclude or ignore entries, and return that local history was already initialized.

#### Scenario: Status before initialization
- **WHEN** `localhist.status()` is called before initialization
- **THEN** the system SHALL return a structured not-initialized result and SHALL NOT fall back to running primary project Git status.

### Requirement: Localhist Configuration
The system SHALL load `localhist` settings from the `tools.localhist` configuration section with project-relative defaults.

#### Scenario: Default paths
- **WHEN** no custom `localhist` paths are configured
- **THEN** the system SHALL default `git_dir` to `.localhist/` and `work_tree` to `.` resolved from the effective project cwd.

#### Scenario: Supported configuration
- **WHEN** `localhist` configuration defines only supported keys
- **THEN** the system SHALL accept `git_dir`, `work_tree`, and `autosave` settings for polling interval, quiet period, minimum save interval, heartbeat timeout, and message prefix.

#### Scenario: Removed configuration keys
- **WHEN** `localhist` configuration defines removed filter, identity, or retention keys
- **THEN** the system SHALL reject those keys through normal configuration validation.

#### Scenario: Unsupported global project token
- **WHEN** `localhist` configuration defines an absolute `git_dir`
- **THEN** the system SHALL require a `{project_id}` token, replace it with a stable filesystem-safe id derived from the effective project cwd, and refuse the primary `.git/` directory.

### Requirement: Manual Snapshots
The system SHALL allow agents to create manual local-history snapshots without polluting the primary Git repository.

#### Scenario: Save with changes
- **WHEN** `localhist.save(message="before refactor", kind="manual")` is called and eligible changes exist
- **THEN** the system SHALL ensure localhist-owned exclude rules are present, stage changes with Git-native ignore behavior, force-add configured force-includes, create a commit with the provided message and `manual` kind metadata, and return structured commit details.

#### Scenario: Save scoped paths
- **WHEN** `localhist.save(message="save markdown docs", paths=["docs/**/*.md"])` is called and matching eligible changes exist
- **THEN** the system SHALL stage only matching project-relative Git pathspecs without relying on shell expansion, create a commit, and return the normalized requested `paths` alongside `changed_count`.

#### Scenario: Save scoped ignored force-includes
- **WHEN** `localhist.save(...)` is called with scoped paths that match configured force-include rules
- **THEN** the system SHALL run normal Git staging for the scoped paths and then force-add matching configured force-includes.

#### Scenario: Scoped directory matches force-include glob
- **WHEN** `localhist.save(message="save", paths="wip/requirements")` is called with force-include rule `wip/**`
- **THEN** the system SHALL treat that force-include rule as matching the scoped path and force-add ignored files under the requested subtree.

#### Scenario: Save scoped paths reject unsafe pathspecs
- **WHEN** `localhist.save(...)` is called with empty paths, absolute paths, parent traversal, protected localhist storage paths, or Git pathspec magic
- **THEN** the system SHALL reject the call before committing.

#### Scenario: Save without changes
- **WHEN** `localhist.save(...)` is called and no eligible changes exist
- **THEN** the system SHALL return `created: false` instead of failing.

#### Scenario: Save rejects empty message
- **WHEN** `localhist.save(message="")` or a whitespace-only message is called
- **THEN** the system SHALL reject the call before initializing, staging, or committing.

#### Scenario: Save with custom snapshot kind
- **WHEN** `localhist.save(message="generated artifact", kind="agent-custom")` is called and eligible changes exist
- **THEN** the system SHALL create a commit and preserve `agent-custom` as snapshot kind metadata in commit details and log entries.

#### Scenario: Snapshot kind usage
- **WHEN** an agent chooses `kind` for a snapshot
- **THEN** it SHALL treat `kind` as stable category metadata such as `manual`, `auto`, `restore`, `generated`, `refactor`, or `experiment`
- **AND** it SHALL put draft names, versions, recommendations, and save-specific rationale in `message`.

### Requirement: Git-Native Snapshot Inclusion
The system SHALL use Git-native ignore behavior for local-history staging, with localhist-only excludes and explicit force-includes stored in the local-history Git database.

#### Scenario: Project gitignore honored
- **WHEN** an untracked file matches the project `.gitignore`
- **THEN** snapshot operations SHALL leave Git responsible for excluding that file from normal staging.

#### Scenario: Localhist-only exclude rule
- **WHEN** `localhist.add_exclude(rule="tmp/")` is called
- **THEN** the system SHALL append the rule idempotently to `.localhist/info/exclude` and return the config file path, added rules, unchanged rules, effective rules, and before/after content.

#### Scenario: Force-include rule
- **WHEN** `localhist.add_force_include(rule="generated/report.json")` is called
- **THEN** the system SHALL append the rule idempotently to `.onetool/state/localhist/force-include` and return the config file path, added rules, unchanged rules, effective rules, and before/after content.

#### Scenario: Protected force-include rule
- **WHEN** `localhist.add_force_include(...)` targets the primary `.git/` directory, `.onetool/state/localhist/`, the configured local-history Git directory, or uses Git pathspec magic
- **THEN** the system SHALL reject the rule and SHALL NOT append it to `.onetool/state/localhist/force-include`.

#### Scenario: Snapshot force-adds configured includes
- **WHEN** force-include rules exist and `localhist.save(...)` stages a snapshot
- **THEN** the system SHALL run normal Git staging and then force-add those pathspecs.

### Requirement: History Inspection
The system SHALL allow agents to inspect local-history status, logs, diffs, and file contents using structured tool results.

#### Scenario: Status after initialization
- **WHEN** `localhist.status()` is called after initialization
- **THEN** the system SHALL return Git-like working-tree file status, dirty counts, initialization state, and commit availability.

#### Scenario: Filtered status
- **WHEN** `localhist.status(path="src", status="untracked", limit=50)` is called
- **THEN** the system SHALL return matching status entries, total file count, and whether the result was truncated.

#### Scenario: Info after initialization
- **WHEN** `localhist.info()` is called after initialization
- **THEN** the system SHALL return initialization state, resolved repository paths, effective config, head and branch information when available, ignore file paths, force-include file path, and an inspection Git command.

#### Scenario: Log with no commits
- **GIVEN** local history is initialized with no commits
- **WHEN** `localhist.log(limit=20)` is called
- **THEN** the system SHALL return an empty log with clear status instead of failing.

#### Scenario: Log entries include readable date and kind
- **WHEN** `localhist.log(limit=20, date_format="%Y-%m-%d %H:%M:%S %Z")` is called
- **THEN** each entry SHALL include full hash, short hash, Unix timestamp, formatted local date/time, subject, and snapshot kind.

#### Scenario: Log and history use configurable date format
- **WHEN** `localhist.log(...)` or `localhist.history(...)` is called without `date_format`
- **THEN** the system SHALL format dates with `%Y-%m-%d %H:%M:%S %Z`.
- **WHEN** either tool is called with a custom `date_format`
- **THEN** the system SHALL use that `strftime` format for returned entry dates.

#### Scenario: Log rejects invalid limit
- **WHEN** `localhist.log(limit=0)` or `localhist.log(limit=-1)` is called
- **THEN** the system SHALL reject the limit before invoking Git.

#### Scenario: Diff with valid ref
- **WHEN** `localhist.diff(ref="HEAD")` is called with a valid ref
- **THEN** the system SHALL return the local-history diff for that ref with truncation metadata.

#### Scenario: Diff comparison modes
- **WHEN** `localhist.diff(ref="HEAD~1", against="HEAD", path="src/foo.py")` or `localhist.diff(ref="HEAD", against="worktree")` is called
- **THEN** the system SHALL return the requested comparison diff and report the comparison mode.

#### Scenario: Diff with invalid ref
- **WHEN** `localhist.diff(ref="HEAD~1")` is called and the ref does not exist
- **THEN** the system SHALL return a clear ref validation error.

#### Scenario: Show file at ref
- **WHEN** `localhist.show(ref="HEAD~1", path="src/foo.py")` is called with a valid ref and project-relative path
- **THEN** the system SHALL return that file as it existed at the requested snapshot.

#### Scenario: Show partial file content
- **WHEN** `localhist.show(ref="HEAD", path="src/foo.py", offset=1, limit=90)` or `localhist.show(ref="HEAD", path="src/foo.py", tail=40)` is called
- **THEN** the system SHALL return content plus total lines, returned lines, offset, and has-more metadata.

#### Scenario: Large diff and show output is bounded
- **WHEN** `localhist.diff(...)` or `localhist.show(...)` would return content beyond the built-in byte cap
- **THEN** the system SHALL return bounded content and include `truncated`, `max_bytes`, and `bytes_returned` metadata.

#### Scenario: Show rejects unsafe path
- **WHEN** `localhist.show(...)` is called with a path outside the effective project cwd
- **THEN** the system SHALL reject the path.

#### Scenario: Show symlink path
- **WHEN** a project-relative symlink path is saved and later inspected
- **THEN** the system SHALL validate the symlink path itself without following a target outside the work tree.

#### Scenario: Path-scoped history
- **WHEN** `localhist.history(path="src/foo.py", limit=20, follow=True)` is called
- **THEN** the system SHALL return structured entries for snapshots that touched the path, including hash, short hash, Unix timestamp, formatted local date/time, subject, path, and follow flag.

### Requirement: Path-Scoped Restore
The system SHALL support conservative path-scoped restore from a previous local-history snapshot.

#### Scenario: Restore dry-run default
- **WHEN** `localhist.restore(ref="HEAD~1", paths=["src/foo.py"])` is called without `dry_run=False`
- **THEN** the system SHALL report the files that would change and SHALL NOT modify the working tree.

#### Scenario: Restore requires explicit paths
- **WHEN** `localhist.restore(...)` is called without paths
- **THEN** the system SHALL reject the call and SHALL NOT perform whole-project restore.

#### Scenario: Restore applies selected paths
- **WHEN** `localhist.restore(ref="HEAD~1", paths=["src/foo.py"], dry_run=False)` is called with a valid ref and safe paths
- **THEN** the system SHALL restore only the requested paths from that snapshot.

#### Scenario: Restore resolves relative ref before safety snapshots
- **WHEN** `localhist.restore(ref="HEAD~1", paths=["src/foo.py"], dry_run=False)` creates a pre-restore safety snapshot
- **THEN** the system SHALL restore from the commit that `HEAD~1` resolved to before the safety snapshot changed `HEAD`.

#### Scenario: Restore snapshots current changes
- **GIVEN** requested restore paths contain current changes compared with the latest local-history snapshot
- **WHEN** a non-dry-run restore is applied
- **THEN** the system SHALL create a pre-restore safety snapshot before modifying files.

#### Scenario: Restore is auditable
- **WHEN** a non-dry-run restore is applied
- **THEN** the system SHALL create a `restore` snapshot after applying the restore and SHALL NOT delete later snapshots.

### Requirement: Localhist Autosave
The system SHALL expose opt-in background autosave watcher lifecycle tools while keeping autosave snapshots owned by the watcher process.

#### Scenario: Start autosave watcher
- **WHEN** `localhist.autosave_start()` is called
- **THEN** the system SHALL start or reuse a shared watcher for the effective project and return watcher state.

#### Scenario: List autosave watcher
- **WHEN** `localhist.autosave_list()` is called
- **THEN** the system SHALL return active, stale, heartbeat, and last-save information.

#### Scenario: Autosave waits for stable dirty state
- **WHEN** the autosave watcher observes a dirty worktree
- **THEN** the system SHALL measure the quiet period from the last observed dirty worktree change, not only from the first dirty observation.

#### Scenario: Stop autosave watcher
- **WHEN** `localhist.autosave_stop()` is called
- **THEN** the system SHALL request the active watcher to stop and return structured stop status.

#### Scenario: Stop request survives a watcher iteration
- **WHEN** `localhist.autosave_stop()` records a stop request while the watcher is mid-iteration
- **THEN** the watcher SHALL update the state file under the same lock as start and stop so the stop request is not overwritten.

#### Scenario: Corrupt watcher state file is recoverable
- **WHEN** the autosave watcher reads a corrupt or unreadable state file
- **THEN** the watcher SHALL keep running, record the failure in `recent_errors`, and rewrite a valid state file instead of terminating.

#### Scenario: No direct autosave snapshot tool
- **WHEN** users need autosave snapshots
- **THEN** the system SHALL NOT expose `localhist.autosave(reason=...)`; autosave snapshots SHALL be created only by an active watcher.

### Requirement: Deferred Localhist Capabilities
The system SHALL defer retention cleanup and whole-project restore.

#### Scenario: Deferred prune
- **WHEN** users need retention cleanup in phase one
- **THEN** the system SHALL NOT expose `localhist.prune()` as part of the phase-one API.

#### Scenario: Deferred whole-project restore
- **WHEN** users need whole-project restore in phase one
- **THEN** the system SHALL require path-scoped restore instead.
