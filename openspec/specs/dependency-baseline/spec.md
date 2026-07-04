# dependency-baseline Specification

## Purpose
TBD - created by archiving change p32-dependency-refresh. Update Purpose after archive.
## Requirements
### Requirement: Direct dependency floors are current at release time
`pyproject.toml` (root) and `packages/onetool-pack/pyproject.toml` SHALL declare floor pins such
that `uv pip list --outdated` (run after `uv lock --upgrade` and `uv sync --group dev
--all-extras`) reports no direct dependency as outdated. A direct dependency MAY remain behind
latest only if it is listed, by name, with a one-line reason, in the change's verification record
(`tasks.md` Verification section) — an unlisted outdated direct dependency is a spec violation.

#### Scenario: Outdated scan is clean after refresh
- **WHEN** `uv pip list --outdated` is run against the environment produced by `uv lock --upgrade`
  followed by `uv sync --group dev --all-extras`
- **THEN** every row in the output corresponds to a transitive-only package (not listed under
  `[project.dependencies]` / `[project.optional-dependencies]` in `pyproject.toml` or under
  `[project.dependencies]` in `packages/onetool-pack/pyproject.toml`), or, if a direct dependency
  does appear, it is one of the names recorded with a reason in `tasks.md`'s Verification section

### Requirement: fastmcp floor carries the Starlette CVE-2026-48710 fix
`pyproject.toml`'s `fastmcp` dependency line SHALL read `fastmcp>=3.4.1,<4` (the `<4` upper bound
is retained — FastMCP 4.0 has not shipped and is out of scope). This floor is a security minimum,
not a feature dependency: `p12-core-flow-hardening`'s `ToolError`/`isError` fix works on the
previously-installed `fastmcp` 3.3.1 and does not require this bump.

#### Scenario: fastmcp floor is at or above the security minimum
- **WHEN** `rg -n "fastmcp>=" pyproject.toml` is run
- **THEN** the output shows `fastmcp>=3.4.1,<4`

### Requirement: lxml major-version cap decision is recorded and consistent with test evidence
`pyproject.toml`'s `lxml` dependency line (`dev` extra) SHALL be widened from `lxml>=5.3,<6` to
`lxml>=5.3,<7` if and only if `trafilatura`, `beautifulsoup4[lxml]`, and `markdown` all pass their
existing test coverage when resolved against an lxml 6.x release via the refreshed lock. If any of
the three fails, the cap SHALL remain `lxml>=5.3,<6` and the specific failure SHALL be recorded in
`tasks.md`'s Verification section — the cap MUST NOT be silently forced past a failing dependency.

#### Scenario: lxml 6 is compatible — cap widened
- **WHEN** the refreshed lock resolves `lxml` to a 6.x release and the `trafilatura` /
  `beautifulsoup4[lxml]` / `markdown` test coverage passes against it
- **THEN** `rg -n "lxml>=" pyproject.toml` shows `lxml>=5.3,<7`

#### Scenario: lxml 6 breaks a consumer — cap held
- **WHEN** any of `trafilatura`, `beautifulsoup4[lxml]`, or `markdown` fails its test coverage
  against the refreshed lxml 6.x resolution
- **THEN** `rg -n "lxml>=" pyproject.toml` still shows `lxml>=5.3,<6`, and `tasks.md`'s
  Verification section names the failing package and the specific test/error that blocked the bump

### Requirement: Native-dependency smoke gate passes on the refreshed lock
The refreshed lock SHALL NOT be considered release-ready until the whiteboard/pydoll,
playwright/patchright, and pymupdf integration paths have been exercised against the refreshed
dependency versions and pass, in addition to `just check` (lint, typecheck, and the
unit/integration-excluded test suite) and the direct-run sanity recipe (`tests/explore/test-cli.md`,
section "4. direct CLI against running root", lines 121-129).

#### Scenario: just check passes on the refreshed lock
- **WHEN** `just check` is run after the lock refresh and floor bumps
- **THEN** it exits successfully (lint, typecheck, and the non-integration test suite all pass)

#### Scenario: Native smoke suites pass on the refreshed lock
- **WHEN** `uv run --all-extras pytest -m pydoll -v`, `uv run --all-extras pytest -m playwright -v`,
  and `uv run --all-extras pytest tests/integration/tools/test_convert.py
  tests/otutil/unit/tools/test_convert.py -v` are run after the lock refresh
- **THEN** all three invocations pass

#### Scenario: Direct-run sanity recipe passes on the refreshed lock
- **WHEN** the commands in `tests/explore/test-cli.md` lines 121-129 (`onetool direct run ...`
  against a running root process with `direct.host.enabled: true`) are executed against the
  refreshed dependency set
- **THEN** every command succeeds and the documented verifications hold (calls execute in the root
  process, real pack calls hit the root registry, output formats are honored, stdin input works)

