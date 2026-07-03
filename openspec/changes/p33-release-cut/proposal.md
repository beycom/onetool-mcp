## Why

OneTool has accumulated a version's worth of breaking renames and removals since `2.2.2`
was tagged (last entry in `CHANGELOG.md:3`, still no `Unreleased`/`3.0.0` section). Cutting
`3.0.0` is currently blocked by two verified defects found in the release audit — a shell
injection risk on the publish path and a stale spec reference to an endpoint that no longer
exists — plus the mechanical work of bumping versions, writing the changelog, and running
the release gates in the right order. This is Wave 3 of the release plan and the terminal
change: it runs only after every other change in the plan has landed, and nothing merges
after `release::prep` except the changelog entry itself.

## What Changes

- Fix `scripts/release_publish.py:45` — `subprocess.run(cmd, shell=True, cwd=PROJECT_ROOT, check=check)`
  is the top security-consult finding on the `just release::publish` path. Replace the
  string-command `run()` helper and every call site with argv-list `subprocess.run(list[str], ...)`
  calls (no `shell=True` anywhere in `scripts/`).
- **BREAKING**: fix stale `/status` endpoint references in
  `openspec/specs/direct-run/spec.md:76,93` to `/health` — the real Direct API endpoints are
  `/run`, `/health`, `/ready` (`src/ot/direct_auth.py:20-22`); `/status` was never a real
  endpoint. This is a documentation/spec correction only; no client or server code changes.
- **BREAKING**: bump the release version `2.2.2` → `3.0.0` in `pyproject.toml:3`,
  `server.json:4`, and `packages/onetool-pack/pyproject.toml:3` via
  `just release::prep 3.0.0` (bumps all three files and drafts a changelog via git-cliff).
- Write the `CHANGELOG.md` `## [3.0.0]` entry by hand from the verified features inventory,
  breaking changes and migration notes first: `__run`→`__onetool` trigger rename,
  `mem.export`→`mem.dump`/`mem.snap`→`mem.snapshot`, `direct.*`→`direct.host.*` config
  nesting, `file.read` raw-lines-by-default, and the removed surfaces (`onetool-bench`, AWS
  pack, the entire handoff pack, public proxy reference pages, `output.compact`/`__compact__`,
  plus this release cycle's own removals: `ot.skills`/`install_skills`, the `[whiteboard]`
  extra, and the pack API param renames). Tool improvements are grouped under "New tools and
  improvements" without raw commit lists. Net-zero added-and-removed churn (caveman
  compaction, IDE bridge, handoff Codex delegation) is omitted entirely.
- Add the direct-run sanity recipe (`tests/explore/test-cli.md:122-128`, the seven
  `onetool direct run` probe commands) as an explicit, permanently recorded release gate in
  `dev/practices/release.md`, run before `just release::publish`.
- Run the release gates in order: `just release::check`; the direct-run sanity gate; then
  `just release::publish 3.0.0` dry-run, then `just release::publish 3.0.0 --force` (PyPI
  must succeed before the MCP Registry step, per the existing step ordering in
  `release.just:147-162`).

## Capabilities

### New Capabilities
- `release-cut`: verifiable, docs/process-only outcomes for cutting the 3.0.0 release — the
  publish script's argv-only subprocess contract, version-file consistency, 3.0.0 changelog
  content, and the recorded direct-run release gate. No runtime/tool behavior changes; this
  capability exists per the project's "docs-only changes still get a spec" rule, so its
  requirements are the verifiable documentation/process outcomes (rg checks, file content
  checks) rather than new tool behavior.

### Modified Capabilities
- `direct-run`: the "authenticated direct API client" requirement's pre-`/run` check
  description and the "Protocol mismatch" scenario currently reference a `/status` endpoint
  that does not exist; both are corrected to `/health` to match the real endpoints
  (`/run`, `/health`, `/ready`) implemented in `src/ot/direct_auth.py:20-22`.

## Impact

- `scripts/release_publish.py` — `run()` helper and all ~11 call sites (build, git add/commit/tag/push
  ×2, GitHub release ×2, PyPI publish, MCP Registry login/publish, docs deploy).
- `openspec/specs/direct-run/spec.md` — two-line (plus one adjacent wording) spec fix.
- `pyproject.toml`, `server.json`, `packages/onetool-pack/pyproject.toml` — version bump.
- `CHANGELOG.md` — new `## [3.0.0]` top entry.
- `dev/practices/release.md` — new documented gate step.
- Depends on all Wave 1 and Wave 2 changes (`p11`–`p18`, `p21`–`p23`) and the other Wave 3
  changes (`p31-demos-and-positioning`, `p32-dependency-refresh`) having already landed —
  `just release::check` (lint, typecheck, full test suite, secrets scan, docs build, sanity)
  is the mechanism that would surface any incomplete sibling change; this change does not
  re-implement or re-verify any sibling change's scope.
