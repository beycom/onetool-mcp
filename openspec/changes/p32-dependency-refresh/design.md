## Context

This change transfers report section R8 M6 (`wip/release-v3/release-v3-report-2.md`, "M6 (V3
release hygiene, maintainer ruling)") in full. It is Wave 3, running immediately before
`p33-release-cut`'s `just release::prep`, so v3.0.0 ships on a fresh, tested dependency set.

Baseline measured 2026-07-04 on `main`@`151a52b3` via `uv pip list --outdated`:

```
fastmcp       3.3.1     → 3.4.2
mcp           1.27.1    → 1.28.1
openai        2.38.0    → 2.44.0
pymupdf       1.27.2.3  → 1.28.0
uvicorn       0.48.0    → 0.49.0
sqlalchemy    2.0.50    → 2.0.51
trafilatura   2.0.0     → 2.1.0
pillow        12.2.0    → 12.3.0
google-genai  2.6.0     → 2.10.0
typer         0.26.2    → 0.26.8
beautifulsoup4 4.14.3   → 4.15.0
resvg-py      0.3.2     → 0.3.3
crawl4ai      0.8.6     → 0.9.0
lxml          5.4.0     → 6.1.1
importlib-metadata 8.7.1 → 9.0.0   (transitive)
rich-rst      1.3.2     → 2.0.2   (transitive)
snowballstemmer 2.2.0   → 3.1.1   (transitive)
```

pydantic (2.13.4) had no newer release outdated at measurement time. This baseline WILL be stale by
the time this change is implemented (it runs after Waves 1-2 land) — treat the numbers above as
"what was true 2026-07-04", not as the target to hardcode. Re-run `uv pip list --outdated` at
implementation time and use its live output for floor-pin values, except where a floor is a fixed
security/policy minimum (`fastmcp>=3.4.1`).

Current direct floor pins and their exact locations (verify before editing — line numbers drift):
- `pyproject.toml:23` — `"fastmcp>=3.1.1,<4"`
- `pyproject.toml:24` — `"httpx>=0.28.1"` (not in scope — no bump named in R8 M6)
- `pyproject.toml:26` — `"mcp>=1.27.0"`
- `pyproject.toml:27` — `"pydantic>=2.13.3"`
- `pyproject.toml:28` — `"pydantic-settings>=2.14.0"` (not named in R8 M6; leave unless outdated)
- `pyproject.toml:37` — `"openai>=2.32.0"`
- `pyproject.toml:44` — `"uvicorn>=0.46.0"`
- `pyproject.toml:69` — `"lxml>=5.3,<6"` (dev extra; the one explicit major cap in the repo)
- `packages/onetool-pack/pyproject.toml:8-11` — `loguru>=0.7.3`, `httpx>=0.28.1`,
  `pydantic>=2.12.5`, `pyyaml>=6.0.3`

Workspace structure: `pyproject.toml:119-123` declares
`[tool.uv.workspace] members = ["packages/onetool-pack"]` and
`[tool.uv.sources] onetool-pack = { workspace = true }`. There is exactly one `uv.lock` in the
repo (at the root); `packages/onetool-pack/` has no lock file of its own.

## Goals / Non-Goals

**Goals:**
- Refresh `uv.lock` to latest-compatible for every direct and transitive dependency.
- Raise floor pins where a newer minimum matters for security or a named feature
  (`fastmcp`, `mcp`, `pydantic`, `openai`, `uvicorn`).
- Decide, with test evidence, whether to widen the `lxml<6` cap to `<7`.
- Prove the refreshed set is release-safe via `just check` + the direct-run sanity recipe + the
  native-dependency smoke gate (whiteboard/pydoll, playwright/patchright, pymupdf).

**Non-Goals:**
- No new dependencies are added and no dependency is removed (that is `p16-extras-restructure`'s
  concern for the whiteboard/pydoll extras restructuring, and out of scope here).
- No change to tool contracts, CLI flags, or MCP-observable error responses.
- No work on `p33-release-cut`'s `release::prep`/`release::check`/publish/changelog.
- No fix to `package.audit`'s doc-signature bug (owned by `p17-pack-api-consistency` /
  `p18-docs-debt-sweep`) — noted here only because, once fixed, OneTool's own `package.audit` tool
  could dogfood the "no direct deps outdated" check this change performs manually.
- No pydantic-settings/httpx bump — not named in R8 M6; touch only if `uv pip list --outdated`
  shows them behind, and if so treat that as incidental to the lock refresh, not a named floor bump.

## Decisions

**D1 — One `uv lock --upgrade` invocation, at the repo root, covers both the root project and
`packages/onetool-pack`.** The brief's source material says "run `uv lock --upgrade` for the root
AND `packages/onetool-pack/`", which reads as two separate commands. In this repo that phrasing
describes the *effect*, not two literal invocations: `onetool-pack` is declared as a uv workspace
member (`pyproject.toml:119-123`) and has no `uv.lock` of its own — the root `uv.lock` is the single
source of truth for the whole workspace, including `onetool-pack`'s `loguru`/`httpx`/`pydantic`/
`pyyaml` dependencies. Running `uv lock --upgrade` once at the repo root refreshes both. Do not
attempt to `cd packages/onetool-pack && uv lock --upgrade` — there is no lock file there to create;
doing so would fork the resolution away from the workspace lock and is explicitly wrong.

**D2 — Floor-pin values track what the refresh actually resolves, not the 2026-07-04 snapshot,
except for the one fixed security floor.** `fastmcp>=3.4.1,<4` is a hard requirement (Starlette
CVE-2026-48710 + native `isError`) regardless of what `uv lock --upgrade` would otherwise pick — if
resolving `fastmcp>=3.4.1` conflicts with another pin, stop and report the conflict; do not lower
the floor to make resolution succeed. For `mcp`, `pydantic`, `openai`, and `uvicorn`, set the floor
to the version the refreshed `uv.lock` actually contains after `uv lock --upgrade` — read it out of
`uv.lock`, don't guess or copy the numbers from this document verbatim, since they will have moved.
If a named dependency (e.g. `pydantic`) turns out to already be at its latest release (no entry in
`uv pip list --outdated`), leave its floor unchanged and record "already current" rather than
bumping the pin cosmetically to match the currently-installed version — a floor pin is a minimum,
not a pinned-exact version, and churning it without a compatibility reason adds no value.

**D3 — `starlette` gets no direct pin.** `starlette` is not in `pyproject.toml`'s
`[project.dependencies]` — it is pulled in transitively via `fastmcp` and `sse-starlette` (see
`uv.lock`, `name = "starlette"` entry, required by both). The CVE-2026-48710 floor is satisfied
entirely by the `fastmcp>=3.4.1` bump (D2): FastMCP 3.4.1's own dependency metadata is what pulls a
patched Starlette. Adding a direct `starlette>=X` line would introduce a new direct dependency not
requested anywhere in R8 M6 ("no other direct dep needs a major bump... Transitive majors ride the
lock refresh") and should not be done. Verification step: after the refresh, confirm the resolved
`starlette` version in `uv.lock` is the one `fastmcp>=3.4.1` requires — if `uv lock --upgrade`
somehow leaves a pre-CVE-fix `starlette` resolved despite the `fastmcp` bump, that is a stop-and-
report condition (the maintainer ruling assumes the bump is sufficient; if it isn't, the floor
strategy itself needs re-litigating, which is above this task's authority).

**D4 — lxml widening is evidence-gated, not assumed.** Widen `lxml>=5.3,<6` to `lxml>=5.3,<7` only
after running the test coverage that exercises `trafilatura`, `beautifulsoup4[lxml]`, and
`markdown` against the lxml 6.x the refreshed lock resolves, and confirming it passes. This is
mechanically part of `just check`'s full test run (no dependency here needs an isolated smoke
suite beyond what already exists), but the implementer must specifically confirm those three
packages' code paths were exercised — do not assume `just check` passing implies lxml compatibility
if the relevant tests happen to be marked `integration` and were skipped from `just test`'s
`-m "not integration"` filter. If any of the three breaks, hold the cap at `<6` and record the
failure — do not comment out the failing test or force the version.

**D5 — Native smoke gate reuses existing marker-gated integration suites; no new tests are
authored.** The report's "whiteboard/pydoll + playwright/patchright + pymupdf smoke" maps onto
three suites that already exist and are already marker-gated:
- `-m pydoll` → `tests/otdev/integration/tools/test_excalidraw.py`
  (`pytestmark = [pytest.mark.integration, pytest.mark.network, pytest.mark.tools,
  pytest.mark.pydoll]`, line 17) — exercises the whiteboard pack's pydoll Chrome CDP path.
- `-m playwright` → `tests/otdev/integration/tools/test_play_util.py` — exercises the
  playwright/patchright browser-automation path.
- pymupdf → `tests/integration/tools/test_convert.py` (4 tests marked
  `integration`+`tools`) and `tests/otutil/unit/tools/test_convert.py` — exercise the convert
  pack's `fitz`/PyMuPDF path. There is no dedicated `pymupdf` pytest marker; run these two files
  by path instead of by marker.

Running these three against the refreshed lock is the "native-ish, most likely to break" gate the
report calls for — these libraries wrap C/Rust extensions and browser binaries, which is exactly
the class of dependency that a Python-level `uv lock --upgrade` can silently break (ABI mismatches,
missing browser binary versions, etc.) in a way `just check`'s pure-Python unit tests would miss.

## Risks / Trade-offs

- [Risk] `uv lock --upgrade` pulls a transitive major that breaks something not covered by any
  named floor (e.g. `crawl4ai` 0.8.6→0.9.0 changing an API the `scrape` extra depends on) →
  Mitigation: `just check` plus the native smoke gate (D5) must both pass before the refresh is
  considered done; if either fails, isolate the offending package via `uv.lock`'s dependency graph
  and either fix the break (adding/adjusting a test per the "tests are part of every code task"
  rule) or hold that one package back with a documented reason — never silently skip the failing
  test to force green.
- [Risk] lxml 6 widening breaks a downstream consumer not covered by existing tests → Mitigation:
  D4's evidence-gate — if `just check`'s existing coverage doesn't actually touch the
  `trafilatura`/`bs4`/`markdown` code paths, that gap must be closed with a regression test before
  widening the cap, not assumed away.
- [Risk] Holding a dependency back "temporarily" quietly becomes permanent and the "no direct deps
  outdated" contract silently degrades → Mitigation: `dependency-baseline`'s spec requires any held
  dependency to be named with a reason in `tasks.md`'s Verification section — an unlisted outdated
  direct dependency is a spec violation, not a soft warning.
- [Risk] Floor-pin numbers copied verbatim from this document (measured 2026-07-04) are stale by
  implementation time, producing a refresh that looks complete but isn't → Mitigation: D2 — always
  read the actual resolved version out of `uv.lock` after `uv lock --upgrade`, never copy the
  numbers quoted in this document as literal targets (except the fixed `fastmcp>=3.4.1` security
  floor).

## Implementation guardrails

- **No compatibility shims or fallback pins.** This is a floor-raise, not a rename — there is
  nothing to alias. If a floor bump breaks a consumer, fix the consumer or hold the specific
  package back with a documented reason (D2/D4); do not add a compatibility shim, a version-range
  workaround import, or an `except ImportError` fallback to dodge the break.
- **No stubbing, no TODO-deferral, no forced-green tests.** If `just check`, the native smoke gate,
  or the lxml evidence-gate fails and the fix isn't obvious, stop and report the specific failure —
  do not comment out the failing assertion, add an `xfail`/`skip` marker to make it pass, or claim
  the gate passed without having actually run it.
- **Tests are part of every code task.** Any regression surfaced by the refresh (D4's lxml risk,
  the transitive-major risk) gets a test per the repo's markers (`@pytest.mark.unit` /
  `@pytest.mark.integration` etc.) before the task is considered done. `just check` must pass
  before this change is complete.
- **Every acceptance command in tasks.md's Verification section must actually be run, and its real
  output recorded.** `rg -n "fastmcp>=" pyproject.toml`, `uv pip list --outdated`, and the pytest
  invocations in D5 are not optional to skip because "the diff looks right" — run them and paste
  the actual result.

## Migration Plan

Order of operations (each step gates the next):
1. Capture the baseline (`uv pip list --outdated`) before touching anything, for later comparison.
2. Run `uv lock --upgrade` once at the repo root (D1).
3. Bump the named floor pins in `pyproject.toml` to match the refreshed lock (D2/D3).
4. Run the lxml evidence-gate (D4) and widen or hold the cap based on the result.
5. Run `just check`.
6. Run the native smoke gate (D5): `-m pydoll`, `-m playwright`, `tests/integration/tools/
   test_convert.py` + `tests/otutil/unit/tools/test_convert.py`.
7. Run the direct-run sanity recipe (`tests/explore/test-cli.md:121-129`).
8. Confirm `uv pip list --outdated` shows no unresolved direct dependency.

Rollback: if the gate fails and no fix lands in the same session, `git checkout -- uv.lock
pyproject.toml packages/onetool-pack/pyproject.toml` reverts cleanly to the pre-refresh state — do
not commit a partial refresh (lock bumped but floors not updated, or vice versa).

## Open Questions

- If `uv lock --upgrade` cannot resolve `fastmcp>=3.4.1` together with another already-pinned
  floor (a genuine dependency conflict), the resolution strategy is not pre-decided here — stop and
  report rather than silently lowering the `fastmcp` floor below the CVE-2026-48710 minimum.
- Whether `packages/onetool-pack/pyproject.toml:10`'s `pydantic>=2.12.5` should be aligned to the
  root's `pydantic>=2.13.3` floor is left to the implementer's judgment at task 3.7 in tasks.md — a
  lower floor there may be intentional (broader standalone-install compatibility for `otpack` as a
  library); if left unaligned, record the reason instead of silently leaving it unexplained.
