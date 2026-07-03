## Why

V3 is the project's deliberate breaking window (maintainer ruling: renames not aliases, removals not
deprecations), and it is the last checkpoint before `p33-release-cut` runs `just release::prep`. A
2026-07-04 dependency audit (`uv pip list --outdated` on `main`@`151a52b3`) found the lockfile is
behind on the bulk of direct and transitive dependencies, and one floor pin (`fastmcp>=3.1.1,<4`,
`pyproject.toml:23`) is below the version that carries the Starlette CVE-2026-48710 fix and FastMCP's
native `isError` support. Shipping v3.0.0 on a stale, unaudited dependency set defeats the point of a
release checkpoint. This change refreshes the lock to latest-compatible, raises the floor pins that
matter for security/features, evaluates the one explicit major-version cap in the repo (`lxml<6`), and
gates the result with the native-dependency smoke tests most likely to break silently on a bump
(whiteboard/pydoll, playwright/patchright, pymupdf). It must land immediately before `p33-release-cut`
so the 3.0.0 release ships on the tested, refreshed set.

## What Changes

- Refresh `uv.lock` to latest-compatible for all direct and transitive dependencies via
  `uv lock --upgrade`, run once at the repo root (the workspace also resolves
  `packages/onetool-pack`'s dependencies — see design.md Decision D1 for why no second lockfile
  exists to refresh separately).
- Raise floor pins in `pyproject.toml` for dependencies where a newer minimum matters for
  security or features: `fastmcp>=3.4.1,<4` (Starlette CVE-2026-48710 floor + native `isError`;
  the `<4` cap stays — 4.0 has not shipped), plus `mcp`, `pydantic`, `openai`, and `uvicorn` raised
  to the versions the refreshed lock actually resolves (measured 2026-07-04: mcp 1.27.1→1.28.1,
  openai 2.38.0→2.44.0, uvicorn 0.48.0→0.49.0; pydantic was already current at 2.13.4 as of this
  measurement — re-verify at implementation time, do not bump cosmetically if it is still current).
  `starlette` itself gets no direct pin — it is transitive-only in this repo (pulled in via
  `fastmcp`/`sse-starlette`, not listed under `pyproject.toml`'s `[project.dependencies]`); the CVE
  floor is satisfied entirely by the `fastmcp>=3.4.1` bump.
- Evaluate widening the one explicit major-version cap in the repo, `lxml>=5.3,<6`
  (`pyproject.toml:69`, `dev` extra; latest is 6.1.1): if `trafilatura`, `beautifulsoup4[lxml]`, and
  `markdown` all pass their tests against the refreshed lxml 6.x, widen to `lxml>=5.3,<7`. If any
  breaks, keep the `<6` cap and record the specific failure — do not force the bump.
- Gate the refreshed lock with `just check` (lint + typecheck + test), the direct-run sanity recipe
  (`tests/explore/test-cli.md:121-129`), and the three native-dependency smoke suites most likely to
  break silently on a version bump: whiteboard/pydoll (`-m pydoll`), playwright/patchright
  (`-m playwright`), and pymupdf (`tests/integration/tools/test_convert.py`,
  `tests/otutil/unit/tools/test_convert.py`).
- No tool contracts, CLI flags, or MCP-observable error responses change as a result of this work —
  this is a lockfile/floor-pin/build-config change only. `pyproject.toml`'s dependency floors are the
  one externally observable artifact (they gate what `pip install onetool-mcp` can resolve), so a
  minimal spec captures that contract; see Capabilities below.

## Capabilities

### New Capabilities
- `dependency-baseline`: the verifiable contract that direct dependency floor pins in
  `pyproject.toml` (root) and `packages/onetool-pack/pyproject.toml` are current (no direct
  dependency outdated, or only intentionally-held ones with a documented reason), that the
  `fastmcp` floor carries the CVE-2026-48710 fix, that the `lxml` major-cap decision is recorded,
  and that the native-dependency smoke gate passes on the refreshed set.

### Modified Capabilities
(none — no existing spec in `openspec/specs/` covers dependency floors or lockfile freshness; this
is new ground, not a behavior change to an existing capability)

## Impact

- Affected files: `pyproject.toml` (floor pins at lines 23, 26, 27, 37, 44, 69), `uv.lock` (full
  refresh), `packages/onetool-pack/pyproject.toml` (floors checked, bumped only if outdated).
- No source code changes — this change touches only dependency manifests and the lockfile, plus
  whatever test/version drift the refresh surfaces (if `just check` or the native smoke gate fails
  after the refresh, fixing that regression is in scope for this change; it must not be silently
  skipped or deferred).
- Sequencing: this change owns report section R8 M6 only. It runs in Wave 3, immediately before
  `p33-release-cut`, so 3.0.0 ships on the refreshed, tested dependency set. It depends on Waves 1–2
  having landed (in particular `p16-extras-restructure`, which moves `pydoll-python` out of the
  `whiteboard` extra into `util` and deletes the `whiteboard` extra — by the time this change is
  implemented, `pyproject.toml`'s extras layout may already differ from the 2026-07-04 snapshot
  quoted here; re-verify line numbers and extras membership before editing, per the note in
  design.md).
- Out of scope (owned elsewhere, do not add tasks here): `p33-release-cut` owns
  `just release::prep`/`release::check`/publish and the changelog; `p22-technical-foundation` owns
  the rest of R8 (S1–S3, M1–M3, M5); `p12-core-flow-hardening` owns R8 P1–P4 (event-loop offload,
  cache bound, serialization/AST perf) and R9; `p17-pack-api-consistency`/`p18-docs-debt-sweep` own
  the `package.audit` doc-signature bug that would let OneTool dogfood this same check — not fixed
  here, only noted in design.md as a follow-up opportunity.
