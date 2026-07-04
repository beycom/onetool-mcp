## 1. Baseline capture

- [x] 1.1 Run `uv pip list --outdated` at the repo root and save the output for later comparison.
      Expect it to roughly match the 2026-07-04 measurement in design.md (fastmcp 3.3.1→3.4.2, mcp
      1.27.1→1.28.1, openai 2.38.0→2.44.0, pymupdf 1.27.2.3→1.28.0, uvicorn 0.48.0→0.49.0,
      sqlalchemy, trafilatura, pillow, google-genai, typer, beautifulsoup4, resvg-py, crawl4ai
      0.8.6→0.9.0, lxml 5.4.0→6.1.1, importlib-metadata, rich-rst, snowballstemmer) — if the set
      differs significantly (new majors appeared, or something in this list is no longer outdated),
      use the live output as the source of truth, not the numbers quoted here.
- [x] 1.2 Confirm `packages/onetool-pack` is a uv workspace member with no separate lock file:
      `rg -n "workspace" pyproject.toml` should show `[tool.uv.workspace] members =
      ["packages/onetool-pack"]` and `onetool-pack = { workspace = true }` (around lines 119-123),
      and `find packages/onetool-pack -maxdepth 1 -name "uv.lock"` should return nothing. This
      confirms only one `uv lock --upgrade` invocation (at the repo root) is needed — see design.md
      Decision D1.

## 2. Lock refresh

- [x] 2.1 Run `uv lock --upgrade` at the repo root. This refreshes all direct + transitive
      dependencies for both the root project and the `packages/onetool-pack` workspace member in
      one pass (design.md D1).
- [x] 2.2 Run `uv sync --group dev --all-extras` to materialize the refreshed environment. If
      resolution fails or conflicts, stop and report the specific conflict — do not resolve it by
      silently removing or lowering a floor pin (design.md D2, Open Questions).

## 3. Floor bumps in pyproject.toml

- [x] 3.1 `pyproject.toml:23` — change `"fastmcp>=3.1.1,<4"` to `"fastmcp>=3.4.1,<4"`. This is a
      fixed security floor (Starlette CVE-2026-48710 + native `isError`), not derived from the lock
      refresh's resolved version — set it to exactly `3.4.1` as the minimum even if the refresh
      resolves a newer patch. Keep the `<4` upper cap (FastMCP 4.0 has not shipped). Note:
      `p12-core-flow-hardening`'s `ToolError`/`isError` fix already works on fastmcp 3.3.1 — this
      bump is security-driven, do not treat it as blocked on or blocking p12.
- [x] 3.2 `pyproject.toml:26` — raise `"mcp>=1.27.0"` to the version `uv.lock` resolved in task 2.1
      (measured 2026-07-04: `1.28.1`; re-check `uv.lock`'s actual `mcp` entry at implementation
      time and use that number).
- [x] 3.3 `pyproject.toml:27` — check whether `pydantic` appears in task 1.1's outdated list. If it
      does, raise `"pydantic>=2.13.3"` to the resolved version. If it does not (pydantic 2.13.4 was
      already current as of 2026-07-04), leave the floor unchanged and note "already current, no
      bump" rather than bumping cosmetically.
- [x] 3.4 `pyproject.toml:37` — raise `"openai>=2.32.0"` to the version `uv.lock` resolved in task
      2.1 (measured 2026-07-04: `2.44.0`; re-check at implementation time).
- [x] 3.5 `pyproject.toml:44` — raise `"uvicorn>=0.46.0"` to the version `uv.lock` resolved in task
      2.1 (measured 2026-07-04: `0.49.0`; re-check at implementation time).
- [x] 3.6 Do NOT add a direct `starlette` dependency line to `pyproject.toml`. Confirm instead that
      `uv.lock`'s resolved `starlette` entry (pulled in transitively via `fastmcp` and
      `sse-starlette`) is consistent with what `fastmcp>=3.4.1` requires — i.e., the CVE floor is
      satisfied by task 3.1 alone. If the resolved `starlette` looks pre-CVE-fix despite the
      `fastmcp` bump, stop and report rather than adding an ad hoc direct pin (design.md D3).
- [x] 3.7 `packages/onetool-pack/pyproject.toml:8-11` — check `loguru>=0.7.3`, `httpx>=0.28.1`,
      `pydantic>=2.12.5`, `pyyaml>=6.0.3` against task 1.1's outdated output. None of these four are
      named in R8 M6's floor-bump list; bump only the ones that actually show up as outdated, and
      leave the rest untouched. Decide whether to align `pydantic>=2.12.5` here with the root's
      `pydantic>=2.13.3` floor, or keep it lower intentionally (broader standalone-install range for
      `otpack` as a library) — record whichever choice is made and why (design.md Open Questions).

## 4. lxml major-bump evaluation

- [x] 4.1 Identify and run the test coverage that exercises `trafilatura`, `beautifulsoup4[lxml]`,
      and `markdown` against the refreshed lxml (resolved to a 6.x release by task 2.1). Use `rg
      -l "trafilatura|BeautifulSoup|import markdown" tests/` to locate the relevant test files, then
      run them explicitly (including any marked `integration`, since `just test`'s default
      `-m "not integration"` filter would otherwise skip them and hide a real break — design.md D4).
- [x] 4.2 If all three pass: change `pyproject.toml:69` from `"lxml>=5.3,<6"` to
      `"lxml>=5.3,<7"`.
- [x] 4.3 If any of the three fails: leave `pyproject.toml:69` as `"lxml>=5.3,<6"`. Do not force the
      bump, comment out the failing test, or add a skip/xfail marker. Record the failing
      package + specific test/error in this file's Verification section (see below).

## 5. Gate

- [x] 5.1 Run `just check` (lint + typecheck + non-integration test). Must exit 0.
- [x] 5.2 Run the direct-run sanity recipe from `tests/explore/test-cli.md` lines 121-129 (section
      "4. direct CLI against running root") against a running root process with
      `direct.host.enabled: true`:
      ```bash
      onetool direct run --ot-dir "$OT_DIR" --port 8765 "ot.version()"
      onetool direct run --ot-dir "$OT_DIR" --port 8765 "ot.debug()"
      onetool direct run --ot-dir "$OT_DIR" --port 8765 "ripgrep.search(pattern='TODO', path='.')"
      onetool direct run --ot-dir "$OT_DIR" --port 8765 "mem.write(topic='tmp/test/cli-runtime', content='direct probe', category='note'); mem.read(topic='tmp/test/cli-runtime'); mem.delete(topic='tmp/test/', confirm=True)"
      onetool direct run --ot-dir "$OT_DIR" --port 8765 --format json "ot.version()"
      onetool direct run --ot-dir "$OT_DIR" --port 8765 --format yml "ot.version()"
      echo 'ot.version()' | onetool direct run --ot-dir "$OT_DIR" --port 8765 -
      ```
      All seven commands must succeed; calls must execute in the root process, real pack calls must
      hit the root registry (not just `ot.*` introspection), output formats must be honored, and
      stdin input must work.
- [x] 5.3 Run the whiteboard/pydoll smoke: `uv run --all-extras pytest -m pydoll -v` (covers
      `tests/otdev/integration/tools/test_excalidraw.py`). Must pass.
- [x] 5.4 Run the playwright/patchright smoke: `uv run --all-extras pytest -m playwright -v`
      (covers `tests/otdev/integration/tools/test_play_util.py`). Must pass.
- [x] 5.5 Run the pymupdf smoke: `uv run --all-extras pytest tests/integration/tools/test_convert.py
      tests/otutil/unit/tools/test_convert.py -v`. Must pass. (No dedicated `pymupdf` pytest
      marker exists — run by path.)
- [x] 5.6 Run `uv pip list --outdated` again (post-refresh). Confirm no direct dependency remains
      outdated (cross-check names against `pyproject.toml`'s `[project.dependencies]` +
      `[project.optional-dependencies]`, and `packages/onetool-pack/pyproject.toml`'s
      `[project.dependencies]`). Any that remain outdated must be named with a reason in the
      Verification section below.

## Verification

Run each command for real and record the actual result — do not mark a checkbox done without
having run it (design.md Implementation guardrails).

- [x] `rg -n "fastmcp>=" pyproject.toml` → must show `fastmcp>=3.4.1,<4`
- [x] `rg -n "lxml>=" pyproject.toml` → must show either `lxml>=5.3,<7` (widened, task 4.2) or
      `lxml>=5.3,<6` (held, task 4.3 — with the failing package/test recorded below)
- [x] `uv pip list --outdated` → remaining entries, all blocked upstream, none freely bumpable:
      - **lxml** 5.4.0 → 6.1.1 — held at `<6` because `crawl4ai>=0.8.6` (scrape extra) depends on
        `lxml>=5.3,<6.dev0`. Forcing `lxml>=6` makes `onetool-mcp[all]` and `onetool-mcp[scrape]`
        unsatisfiable. See task 4.3 note below.
      - **trafilatura** 2.0.0 → 2.1.0 (direct dev dep) — `trafilatura 2.1.0` requires `lxml>=6.1.1`,
        so it is held by the same `crawl4ai` `lxml<6` constraint. Floor `>=2.0.0` stays satisfied.
      - **lxml-html-clean** 0.4.4 → 0.4.5, **pydantic-core** 2.46.4 → 2.47.0, **snowballstemmer**
        2.2.0 → 3.1.1 — transitive only (not direct deps); pinned by their parents, out of scope for
        task 5.6's direct-dependency check.
- [x] `just check` → passes (lint + typecheck + test)
- [x] `uv run --all-extras pytest -m pydoll -v` → passes
- [x] `uv run --all-extras pytest -m playwright -v` → passes
- [x] `uv run --all-extras pytest tests/integration/tools/test_convert.py
      tests/otutil/unit/tools/test_convert.py -v` → passes
- [x] Direct-run sanity recipe (`tests/explore/test-cli.md:121-129`) → all 7 commands succeed
      against a running root process
- [x] lxml cap held at `<6` (task 4.3). NOT a test failure — the bump is blocked at *resolution*
      time: `crawl4ai>=0.8.6` depends on `lxml>=5.3,<6.dev0`, so `uv lock` with `lxml>=6` reports
      "onetool-mcp[all] and onetool-mcp[scrape] are incompatible". The lxml consumers
      (`tests/otdev/unit/tools/test_webfetch.py`, `tests/unit/core/test_pep723.py`,
      `tests/integration/tools/test_convert.py`) all pass on the held lxml 5.4.0. Re-evaluate when
      crawl4ai relaxes its lxml cap.
