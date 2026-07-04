## 1. Publish script argv fix (`scripts/release_publish.py:45`)

- [x] 1.1 Change the `run()` helper (`scripts/release_publish.py:39-45`) from
      `run(cmd: str, check: bool = True)` calling
      `subprocess.run(cmd, shell=True, cwd=PROJECT_ROOT, check=check)` to
      `run(cmd: list[str], check: bool = True)` calling
      `subprocess.run(cmd, cwd=PROJECT_ROOT, check=check)` (no `shell=True`). Keep the
      dry-run print behavior, rendering the argv list as a space-joined string for display
      only (never re-executed as a shell string).
- [x] 1.2 Update call site `run("uv build")` at `scripts/release_publish.py:106` →
      `run(["uv", "build"])`.
- [x] 1.3 Update call site `run("git add -A")` at `scripts/release_publish.py:114` →
      `run(["git", "add", "-A"])`.
- [x] 1.4 Update call site `run(f'git commit -m "Release {version}"', check=False)` at
      `scripts/release_publish.py:115` →
      `run(["git", "commit", "-m", f"Release {version}"], check=False)`.
- [x] 1.5 Update call site `run(f'git tag -a "v{version}" -m "Release {version}"')` at
      `scripts/release_publish.py:116` →
      `run(["git", "tag", "-a", f"v{version}", "-m", f"Release {version}"])`.
- [x] 1.6 Update call site `run("git push origin main")` at
      `scripts/release_publish.py:117` → `run(["git", "push", "origin", "main"])`.
- [x] 1.7 Update call site `run(f'git push origin "v{version}"')` at
      `scripts/release_publish.py:118` → `run(["git", "push", "origin", f"v{version}"])`.
- [x] 1.8 Update call site `run(f'gh release create "v{version}" dist/* --title "v{version}"
      --notes-file tmp/release-notes.md')` at `scripts/release_publish.py:137-139`: expand
      `dist/*` in Python (e.g. `sorted((PROJECT_ROOT / "dist").glob("*"))`, stringified) and
      build the argv list — `["gh", "release", "create", f"v{version}", *dist_files, "--title",
      f"v{version}", "--notes-file", "tmp/release-notes.md"]`.
- [x] 1.9 Update call site `run(f'gh release create "v{version}" dist/* --title "v{version}"
      --generate-notes')` at `scripts/release_publish.py:142-144` with the same
      `dist/*`-glob-expansion treatment as 1.8.
- [x] 1.10 Update call site `run("uv publish")` at `scripts/release_publish.py:152` →
      `run(["uv", "publish"])`.
- [x] 1.11 Update call site `run("mcp-publisher login github")` at
      `scripts/release_publish.py:160` → `run(["mcp-publisher", "login", "github"])`.
- [x] 1.12 Update call site `run("mcp-publisher publish")` at
      `scripts/release_publish.py:161` → `run(["mcp-publisher", "publish"])`.
- [x] 1.13 Update call site `run("uv run mkdocs gh-deploy --force")` at
      `scripts/release_publish.py:169` →
      `run(["uv", "run", "mkdocs", "gh-deploy", "--force"])`.
- [x] 1.14 Grep the whole file after editing to confirm no remaining string-form `run(...)`
      calls or `shell=True` usages: `rg -n 'run\(f?"|run\(f?\x27|shell=True' scripts/release_publish.py`.
- [x] 1.15 Add `tests/unit/scripts/test_release_publish.py` (new directory,
      `@pytest.mark.unit`) that mocks `subprocess.run` and asserts: (a) every call from
      `run()` receives a `list`, not a `str`; (b) `subprocess.run` is never invoked with
      `shell=True`; (c) `DRY_RUN=True` (the default/no `--force`) never calls
      `subprocess.run` at all, only prints.
- [x] 1.16 Confirm `release.just:97`'s import of `extract_release_notes` from
      `scripts.release_publish` still works unchanged (its signature is untouched by this
      task group); grep for any other importer of `scripts.release_publish`:
      `rg -n "release_publish" --type py -g '!scripts/release_publish.py'`.

## 2. direct-run spec fix (`/status` → `/health`)

- [x] 2.1 In `openspec/specs/direct-run/spec.md:76`, change "Before `/run`, the client SHALL
      perform signed `/status` and `/ready` checks." to "Before `/run`, the client SHALL
      perform signed `/health` and `/ready` checks."
- [x] 2.2 In `openspec/specs/direct-run/spec.md:93` (the "Protocol mismatch" scenario),
      change "**WHEN** `/status` or `/run` returns a different direct protocol version" to
      "**WHEN** `/health` or `/run` returns a different direct protocol version".
- [x] 2.3 For wording consistency (not itself matched by the `rg "/status"` check but a
      direct consequence of the endpoint rename), change the "Non-OneTool or unauthenticated
      service" scenario's "signed status/readiness fails" (currently at
      `openspec/specs/direct-run/spec.md:87`) to "signed health/readiness fails".
- [x] 2.4 Confirm no other `/status` references exist anywhere that need the same fix:
      `rg -n "/status" openspec/ docs/ src/ tests/` — expect only the two now-fixed lines to
      have shown up before this task, and zero matches after.

## 3. Version bump to 3.0.0

- [x] 3.1 Run `just release::prep 3.0.0`. This runs `release::set-version 3.0.0`
      (`release.just:62-67`), which updates `pyproject.toml:3`, `server.json:4`, and
      `packages/onetool-pack/pyproject.toml:3` via `sed`, and drafts
      `tmp/changelog-entry.md` via `git cliff --unreleased --strip header`.
- [x] 3.2 Confirm all three files now read `version = "3.0.0"` / `"version": "3.0.0"`:
      `rg -n '"?version"?\s*[:=]\s*"3\.0\.0"' pyproject.toml server.json packages/onetool-pack/pyproject.toml`
      — expect one match per file.
- [x] 3.3 Keep `tmp/changelog-entry.md` (git-cliff draft) open only as a completeness
      cross-check for section 4 below; do not paste it into `CHANGELOG.md` unedited.

## 4. CHANGELOG.md 3.0.0 entry

Write a new `## [3.0.0] - 2026-07-04` entry at the top of `CHANGELOG.md` (above the existing
`## [2.2.2]` entry). Breaking changes and migration notes come first, verbatim in substance
from the verified features inventory (source file `wip/release-v3/release-v3-features.md`
will not exist at a later date — this content is fully transferred below).

- [x] 4.1 Add a "### Breaking Changes" (or equivalent top) subsection, listed before any
      other subsection, containing all of the following as individual bullets:
  - [x] 4.1.1 **Explicit invocation trigger renamed**: canonical trigger is `__onetool`,
        short form `__ot`. The old `__run` / `__r` forms are removed (no shims). Migration:
        replace `__run` with `__onetool` in prompts, agent instructions, and snippets.
        Snippet calls keep their colon syntax; explicit `pack.tool(...)` calls never use a
        colon.
  - [x] 4.1.2 **`mem` operations renamed**: `mem.export` → `mem.dump`, `mem.snap` →
        `mem.snapshot`.
  - [x] 4.1.3 **Direct settings restructured**: `direct.*` config moved under
        `direct.host.*` (`DirectHostConfig`, `src/ot/config/models.py:511`). Migration: nest
        existing direct keys under `host:`.
  - [x] 4.1.4 **`file.read` defaults to raw lines**: line numbers are now opt-in.
  - [x] 4.1.5 **Removed surfaces**, verified gone with no stale references in `src/`,
        `docs/`, or `openspec/`:
        - `onetool-bench` benchmark package, specs, and justfile targets.
        - AWS pack.
        - Handoff — the entire pack, not just the child runtime: `src/ot/handoff/*`,
          `src/ottools/handoff.py`, Codex worker delegation, docs, and spec.
        - Public proxy server reference pages and obsolete agent config files.
        - `output.compact` config and the `__compact__` dunder (removed with compaction
          support).
  - [x] 4.1.6 **This release cycle's own removals** (from the p11/p16/p17 changes landed
        earlier in this same release plan): `ot.skills` runtime and `install_skills`
        installer surface (p11); the `[whiteboard]` install extra (p16); pack API param
        renames — kb `q`→`query`, mem `pattern`→`keyword`, brave `count`→`max_results`
        (p17).
  - [x] 4.1.7 Confirm the added-and-removed churn items are explicitly NOT included anywhere
        in the entry: caveman compaction, the IDE/VS Code bridge pack and extension, and
        handoff Codex worker delegation (all net-zero for users within this window).
- [x] 4.2 Add a "### New tools and improvements" subsection (grouped by area, no raw commit
      lists), covering:
  - [x] 4.2.1 MCP-managed Direct API lifecycle: authenticated direct execution against an
        already-running MCP-owned runtime — direct host lifecycle management, bound-port
        routing, host context sync, secrets path resolution, direct CLI docs. Endpoints are
        `/run`, `/health`, `/ready`.
  - [x] 4.2.2 Local history pack (`localhist`): new project-local snapshot pack, hardened
        through git identity setup, storage protection, scoped save paths, nested ignore
        behavior, and scoped force-include handling. Users keep project-local history
        without capturing the history store itself.
  - [x] 4.2.3 Server management and diagnostics: new `ot_servers` pack with read-only
        `ot.server` (enable/disable/restart/status for proxied MCP servers from inside the
        agent loop); `ot.help` ask mode and richer status diagnostics; disabled servers
        skipped in runtime readiness checks; proxy transports close more reliably;
        configured server packs exposed; Chrome/Playwright annotation utilities accept
        compatible MCP server names instead of one fixed name.
  - [x] 4.2.4 Tool improvements: **file** — directory resolution and safer default list
        output, file reference resolver, grep match limits aligned with ripgrep;
        **ripgrep** — `follow_symlinks`, `smart_case`, `filenames_only`; **db** — table
        sampling and optional row counts; **arch** — new model-centric architecture pack
        with generation, round-trip, and parallel render flows; **ground** — structured
        search extraction, provenance, and batch envelopes; search timeout and retry
        guardrails; knowledge/scrape event-loop and browser lifecycle cleanup; convert batch
        loop handling; web loopback error improvements; diagram compound extension
        handling; package tool fixes for empty versions and dotted dependencies.
  - [x] 4.2.5 Configuration and runtime: Azure MCP server template; config rejects invalid
        typed pack configuration; unknown root/nested keys warn-and-ignore on load; runtime
        cache reload tightened for tool helper modules; tool output/result services;
        runtime attribution and snippet metadata in structured logs; prompt templates
        prefer single-quoted literals.
  - [x] 4.2.6 Documentation, specs, and quality gates: specs normalized and synced to
        implemented contracts; spec-writing guidance added; dev docs reorganized; generated
        tool references refreshed; direct usage docs rewritten; shipped-surface
        lint/typecheck now covers `ot`, `ottools`, `onetool`, `otdev`, `otutil`, `otpack`.
- [x] 4.3 Before finalizing, re-run `git log --oneline --no-merges v2.2.2..HEAD | wc -l` and
      compare against the inventory's stated commit count (110 as of the source pass, plus
      whatever landed in Wave 1/2/other-Wave-3 changes since); if new user-facing commits
      exist beyond the inventory, classify and add them rather than silently omitting them —
      do not guess; if unclear whether a commit is user-facing, stop and report it instead of
      omitting it.
- [x] 4.4 Sweep for stale references to every removed-surface name before finalizing:
      `rg -n "onetool-bench|src/ot/handoff|output\.compact|__compact__|install_skills" openspec/ docs/ src/` —
      expect zero matches (outside `CHANGELOG.md` itself, which is exempt as it is the
      historical record).

## 5. Release gates, in order

- [x] 5.1 Run `just release::check` (lint, typecheck, full test suite, secrets scan, strict
      docs build, and the `/p:test-explore sanity.md retest all` sanity pass per
      `release.just:39-48`). All steps must pass; do not proceed past a failing step.
- [x] 5.2 Add a documented "Step 2.5: Direct-run sanity gate" section to
      `dev/practices/release.md` (between the existing "Step 2: Check" and "Step 3: Publish"
      sections), instructing the releaser to start a root process
      (`onetool serve` or a running direct host with `direct.host.enabled: true`) and run the
      seven probe commands from `tests/explore/test-cli.md:122-128`:
      `ot.version()`, `ot.debug()`, a `ripgrep.search(...)` call, a `mem.write/read/delete`
      sequence, `--format json`/`--format yml` variants of `ot.version()`, and the stdin-dash
      form — all against the running root, per `tests/explore/test-cli.md`'s "Verify" list
      (calls execute in the running root process; real pack calls route through the root
      registry, not only `ot.*` introspection; output formats honored; stdin works).
      State explicitly that this gate must pass before `just release::publish` is invoked.
- [x] 5.3 Actually execute the direct-run sanity gate now, as part of cutting this release
      (not merely documenting it for future releases), and record the outcome.
- [x] 5.4 Run `just release::publish 3.0.0` (dry-run; `DRY_RUN=True` by default per
      `scripts/release_publish.py:19,83`) and confirm it completes without error, printing
      the full argv-based command sequence.
- [ ] 5.5 Run `just release::publish 3.0.0 --force` and confirm PyPI publish
      (`scripts/release_publish.py:148-153`, Step 4) completes successfully before the MCP
      Registry step (`scripts/release_publish.py:156-162`, Step 5) is confirmed — the
      existing step ordering in the script already enforces this; do not reorder it.

## Verification

Run every command below; each MUST produce the stated result. A task is only done when its
verification command passes — do not mark a task complete on the basis of "the file was
edited" alone.

- [x] `rg "shell=True" scripts/` → empty output (exit code 1, no matches).
- [x] `rg -n "/status" openspec/ docs/ src/ tests/` → no endpoint (`/status`) references
      remain.
- [x] `rg -n '"?version"?\s*[:=]\s*"3\.0\.0"' pyproject.toml server.json packages/onetool-pack/pyproject.toml`
      → one match per file, all `3.0.0`.
- [x] Head of `CHANGELOG.md` shows `## [3.0.0]` as the first entry, with breaking
      changes/migration notes as its first subsection, and contains each of the items from
      task 4.1 (verify by reading the rendered section, item by item).
- [x] `rg -n "onetool-bench|src/ot/handoff|output\.compact|__compact__|install_skills" openspec/ docs/ src/`
      → zero matches.
- [x] `dev/practices/release.md` contains the new direct-run sanity gate step, referencing
      `tests/explore/test-cli.md:122-128`.
- [x] `uv run pytest tests/unit/scripts/test_release_publish.py -m unit` → passes.
- [x] `just check` → passes (lint + typecheck + full test suite).
- [x] `just release::check` → passes end-to-end.
- [x] `just release::publish 3.0.0` (dry-run) → completes with no errors and no
      `shell=True`-style shell strings printed as the executed form (argv lists shown).
- [ ] `just release::publish 3.0.0 --force` → PyPI step succeeds before the MCP Registry
      step is invoked.

## Execution notes (2026-07-04)

- 5.1 `just release::check`: lint, typecheck, full test suite (2882 passed), secrets scan
  (gitleaks clean after allowlisting the fake `sk-abc123...` redaction-test fixture pattern in
  `.gitleaks.toml`), docs-sync, and strict mkdocs build all passed. The final nested
  `claude /p:test-explore sanity.md` step failed on the *harness* side ("monthly spend limit"),
  not on any project check; an equivalent in-session sanity pass was run instead (fresh
  `onetool serve` HTTP root + direct-run probes + quick-smoke items, all green).
- 5.3 direct-run sanity gate: fresh root (`tmp/explore-runtime/.onetool`, direct host on a free
  port), all seven probes from tests/explore/test-cli.md passed — version/debug report 3.0.0,
  ripgrep/mem pack calls route through the root registry, `--format json`/`yml` honored, stdin
  dash works. Also ran ot.status, file.tree, param-prefix, snippet expansion (snippet failed only
  because the bare test config includes no snippets.yaml — config gap, not a bug).
- 5.4 dry-run publish: completes, argv lists printed (no shell strings). Fixed a defect the dry
  run surfaced: the `dist/*` glob expansion picked up `dist/.gitignore` and the `dist/site`
  directory (mkdocs site_dir); now restricted to `*.whl` + `*.tar.gz`.
- 4.4 rg sweep: zero matches in `docs/` and `src/`; remaining matches are removal descriptions in
  `openspec/changes/**` and deliberate absence-assertions in `openspec/specs/serve-skills/spec.md`.
- 5.5 (`--force` publish to PyPI/MCP Registry) NOT run — awaiting maintainer go-ahead.
