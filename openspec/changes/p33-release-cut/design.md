## Context

OneTool has been in a breaking-change development window since `2.2.2` was tagged
(`CHANGELOG.md:3` is still the top entry). This change is Wave 3, the terminal change in the
release plan: `p33-release-cut` runs only after Wave 1 (`p11`–`p18`), Wave 2
(`p21`–`p23`), and the other Wave 3 changes (`p31-demos-and-positioning`,
`p32-dependency-refresh`) have landed. Nothing merges after `just release::prep 3.0.0` except
the hand-written `CHANGELOG.md` entry itself.

Three parallel security/architecture/performance reviews (report R8) judged the codebase
foundation sound; the release-blocking exceptions specific to the release path are:

1. `scripts/release_publish.py:45` — `subprocess.run(cmd, shell=True, cwd=PROJECT_ROOT, check=check)`.
   The `run()` helper takes a formatted shell string (several call sites interpolate the
   version argument directly, e.g. `f'git tag -a "v{version}" -m "Release {version}"'`,
   `scripts/release_publish.py:116`), which is the top finding from the security consult.
2. `openspec/specs/direct-run/spec.md:76,93` reference a `/status` endpoint that was never
   real. The actual Direct API surface is `/run`, `/health`, `/ready`
   (`src/ot/direct_auth.py:20-22`, `RUN_PATH`/`HEALTH_PATH`/`READY_PATH` constants). This is a
   spec-only drift; no client or server code implements `/status`.
3. Direct API test coverage is unit-only (ASGI TestClient + mocks); the process-level path —
   an actual running root process serving a real Direct API port — exists only as a manual
   exploratory recipe (`tests/explore/test-cli.md:122-128`), never run as a recorded release
   gate.

## Goals / Non-Goals

**Goals:**
- Close the two verified release-blocking defects (shell=True publish path, stale `/status`
  spec reference) before cutting `3.0.0`.
- Bump the release version consistently across all three version-bearing files.
- Produce a `CHANGELOG.md` `3.0.0` entry that leads with breaking changes/migration notes,
  matches the verified features inventory, and omits net-zero churn.
- Make the direct-run process-level sanity check a permanent, documented release gate instead
  of an ad hoc manual step.
- Run the release gates in the mandated order and publish PyPI before the MCP Registry.

**Non-Goals:**
- Re-implementing or re-verifying any Wave 1/Wave 2/other-Wave-3 change's scope (skills
  layout, core-flow hardening, recovery seams, secrets, install flow, extras restructure,
  pack API consistency, docs sweep, run contract, technical foundation, console-outbox
  contract, demos/positioning, dependency refresh). `just release::check` (lint, typecheck,
  full test suite, secrets scan, docs build, sanity) is the mechanism that surfaces any gap
  left by a sibling change; this change does not carry tasks for that scope.
- Automating the direct-run sanity recipe into CI. It requires a live root process and manual
  invocation per the report's scoping ("run ... as a recorded release gate"); automating it is
  out of scope here.
- Any change to the Direct API's actual endpoints, auth, or protocol — the `/status`→`/health`
  fix is textual/spec-only.

## Decisions

### 1. Argv-based `subprocess.run`, not `shlex.quote()` + `shell=True`

Replace the `run(cmd: str, check: bool = True)` helper (`scripts/release_publish.py:39-45`)
with a signature that takes `cmd: list[str]` and calls
`subprocess.run(cmd, cwd=PROJECT_ROOT, check=check)` (no `shell=True`). Update every call
site to pass a list instead of an interpolated string:

- `run("uv build")` → `run(["uv", "build"])` (`:106`)
- `run("git add -A")` → `run(["git", "add", "-A"])` (`:114`)
- `run(f'git commit -m "Release {version}"', check=False)` →
  `run(["git", "commit", "-m", f"Release {version}"], check=False)` (`:115`)
- `run(f'git tag -a "v{version}" -m "Release {version}"')` →
  `run(["git", "tag", "-a", f"v{version}", "-m", f"Release {version}"])` (`:116`)
- `run("git push origin main")` → `run(["git", "push", "origin", "main"])` (`:117`)
- `run(f'git push origin "v{version}"')` → `run(["git", "push", "origin", f"v{version}"])` (`:118`)
- `run(f'gh release create "v{version}" dist/* --title "v{version}" --notes-file tmp/release-notes.md')`
  → `run(["gh", "release", "create", f"v{version}", *sorted(glob-expanded dist/*), "--title", f"v{version}", "--notes-file", "tmp/release-notes.md"])`
  (`:137-139`) — note: `dist/*` glob expansion was previously done by the shell; the argv
  version must expand it in Python (e.g. `list((PROJECT_ROOT / "dist").glob("*"))`) before
  building the argv list.
- `run(f'gh release create "v{version}" dist/* --title "v{version}" --generate-notes')` → same
  glob-expansion treatment (`:142-144`)
- `run("uv publish")` → `run(["uv", "publish"])` (`:152`)
- `run("mcp-publisher login github")` → `run(["mcp-publisher", "login", "github"])` (`:160`)
- `run("mcp-publisher publish")` → `run(["mcp-publisher", "publish"])` (`:161`)
- `run("uv run mkdocs gh-deploy --force")` →
  `run(["uv", "run", "mkdocs", "gh-deploy", "--force"])` (`:169`)

The dry-run print statement (`print(f"  $ {cmd}")`) must still render a readable command line;
join the argv list with spaces for display purposes only (`" ".join(cmd)`), never re-execute
that joined string.

**Alternative considered**: keep `shell=True` and `shlex.quote()` every interpolated value.
Rejected — it still routes through a shell interpreter for no functional benefit; argv-only
execution eliminates the entire class of shell-metacharacter risk rather than mitigating one
instance of it.

### 2. `/status` → `/health` is a textual spec fix only

No code changes. `src/ot/direct_auth.py` already defines and uses `/health`
(`HEALTH_PATH = "/health"`, line 21) and `/run`, `/ready`. Only
`openspec/specs/direct-run/spec.md` needs correction, at the two exact anchors from the
report (lines 76 and 93) plus one adjacent wording fix for consistency: the "Non-OneTool or
unauthenticated service" scenario's phrase "signed status/readiness fails" becomes "signed
health/readiness fails" (this occurrence has no literal `/status` slash-path so it is not
caught by the `rg "/status"` verification check, but leaving the word "status" there next to
a corrected `/health` reference would read as a leftover inconsistency).

### 3. Version bump via the existing `just release::prep` recipe, not hand-editing

`release.just:19-34` (`prep`) already calls `release::set-version` (`release.just:62-67`,
which updates `pyproject.toml`, `server.json`, and `packages/onetool-pack/pyproject.toml`
together via `sed`) and drafts `tmp/changelog-entry.md` via `git cliff --unreleased`. Run
`just release::prep 3.0.0` rather than hand-editing the three files, so all three change
atomically from one source of truth and the drift risk of a partial bump is eliminated.

### 4. Changelog is hand-written from `release-v3-features.md`'s content, git-cliff output is a cross-check only

`git cliff --unreleased` groups by raw commit message and will not produce breaking-changes-first
ordering, grouped "New tools and improvements," or omission of net-zero churn — all of which
are mandated by the source inventory's own "Converting This File Into The Changelog" section.
Use the `git cliff` draft only as a completeness cross-check (nothing it lists should be
missing from the hand-written entry, unless it belongs to the omitted churn list), then write
the final `## [3.0.0]` entry directly into `CHANGELOG.md` using the content specified in
tasks.md section 4 below (copied verbatim from the source inventory).

### 5. Direct-run gate is a documented manual step, not new automation

The recipe (`tests/explore/test-cli.md:122-128`) requires a live root process (`onetool serve`
or a running direct host) and is explicitly scoped by the report as something to "run ... as a
recorded release gate" — manual, not CI-automated, in this change. Add it as Step 2.5 (between
"Check" and "Publish") in `dev/practices/release.md`, and actually run it once as part of
cutting this release.

## Risks / Trade-offs

- **Version bump touches files also touched by sibling changes' final commits** → Mitigation:
  this change is explicitly ordered last; do not begin section 3 (version bump) until all
  Wave 1/2/other-Wave-3 changes are merged to `main`.
- **Hand-written changelog could drift from the actual shipped commit set if new commits
  landed after `release-v3-features.md` was compiled** → Mitigation: tasks.md includes a
  `git log --oneline --no-merges v2.2.2..HEAD` re-check and an `rg` sweep for removed-surface
  names before finalizing the entry; report any commit not accounted for in the inventory
  instead of silently omitting or guessing at its category.
- **The `gh release create ... dist/*` argv conversion changes glob-expansion timing** (shell
  expansion at invocation time vs. Python `glob()` at script-build time) → Mitigation: build
  the file list immediately before the `gh` call, after the build step has already run, so the
  glob always reflects the just-built `dist/` contents.
- **Publish script's calling convention change could break something that imports it** →
  Mitigation: `release.just:97` imports only `extract_release_notes`, whose signature is
  unchanged; grep for other importers of `scripts.release_publish` before finalizing (none
  expected, but verify).
- **`DRY_RUN=True` short-circuits before any `subprocess.run` call, so a dry run alone cannot
  prove `shell=True` is gone** → Mitigation: the verification is a static `rg` check against
  the source file, independent of dry-run/force state; run it regardless of which publish mode
  was exercised.

## Implementation guardrails

- **No compatibility shims.** V3 is a breaking window. The `/status`→`/health` spec fix is a
  correction, not a deprecation — do not add a `/status` alias route or leave a "deprecated,
  use /health" note anywhere. The `run()` helper's string-based calling convention is deleted,
  not kept alongside a new argv path.
- **No stubbing or TODO-deferral.** If a call site cannot be cleanly converted to argv form
  (e.g., a command that genuinely needs shell features like piping), stop and report it rather
  than leaving `shell=True` in place with a comment. None of the current call sites need shell
  features (confirmed by design decision 1's full enumeration above).
- **Tests are part of every code task.** The `scripts/release_publish.py` argv rewrite gets a
  new unit test (`tests/unit/scripts/test_release_publish.py`, `@pytest.mark.unit`) that mocks
  `subprocess.run` and asserts every `run()` call site passes a `list[str]` and that
  `subprocess.run` is never called with `shell=True`. `just check` (lint + typecheck + test)
  must pass before this change is considered complete.
- **Every listed `rg` acceptance command must actually be run and must return empty/expected
  output** — not merely asserted as "should pass" in a task description. This applies to
  `rg "shell=True" scripts/`, `rg "/status" openspec/ docs/ src/ tests/`, and the
  removed-surface-name sweep.
