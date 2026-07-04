## 1. Seam 1a — disconnected-server error names the server and the enable command

- [x] 1.1 In `src/ot/executor/pack_proxy.py`, inside `_create_mcp_proxy_pack.__getattr__`
  (currently lines 127-168), add a branch at the top of the existing `if match_result is None:`
  block (currently line 152) that checks `proxy.get_connection(server_name) is None` (the proxy
  manager instance is already bound to `proxy` at line 135 — no new import needed) and, if true,
  raises `AttributeError` **before** falling into the existing suggestion/`available_tools`
  logic. The message MUST contain, verbatim: the literal server name, a statement that the
  server is configured but not connected (e.g. "not connected" or "disconnected"), and the exact
  substring `ot_servers.enable(name='<server_name>')` with `<server_name>` substituted (single
  quotes, matching this file's existing `f"Tool '{accessor_name}' not found..."` quoting
  convention). Do not change the existing suggestion/`available_tools` branches — they remain
  correct for a *connected* server whose tool genuinely doesn't exist.
- [x] 1.2 Confirm no other caller of `_create_mcp_proxy_pack` or `McpProxyPack.__getattr__`
  depends on the old "Available: (empty)" text for a disconnected server (`rg -n
  "Available: {available}{more}" src/ot/executor/pack_proxy.py` should show exactly one
  occurrence, now only reachable for a connected server with zero matching tools).
- [x] 1.3 Add a unit test in `tests/unit/core/test_pack_proxy.py`, in a new test class following
  the existing `TestMcpProxyPackToolPrefixFallback` pattern (same file, lines 297-355): mock
  `ot.proxy.get_proxy_manager` to return a `MagicMock` with `list_tools.return_value = []` and
  `get_connection.return_value = None` (simulating a configured-but-disconnected server named
  e.g. `"playwright"`), call `_create_mcp_proxy_pack("playwright")` then access `pack.click`
  (any attribute), and assert `pytest.raises(AttributeError)` whose message contains `"playwright"`,
  a disconnected/not-connected indicator, and the literal substring
  `"ot_servers.enable(name='playwright')"`. Mark `@pytest.mark.unit` + `@pytest.mark.core`.

## 2. Seam 1b — disconnected server help text carries the same recovery hint

- [x] 2.1 In `src/ot/meta/_help_formatting.py`, in `_format_server_help` (currently lines
  339-389), immediately after the existing `lines.append(f"**Status:** {status}" + ...)` line
  (currently line 364-366) and before the blank-line append (currently line 370), add: when
  `status != "connected"`, append a line containing the literal substring
  `ot_servers.enable(name='<server_name>')` (using the function's `server_name` parameter,
  single-quoted per this file's convention). Leave the `status == "connected"` path unchanged.
- [x] 2.2 Add a unit test — either in `tests/unit/core/test_servers_redesign.py` (which already
  imports and exercises `ot.meta` server-formatting helpers) or a new small test module for
  `_format_server_help` directly — that calls `_format_server_help("playwright", server_cfg,
  "disconnected", [], "")` (with a minimal mock `server_cfg`, e.g. `MagicMock(source=None,
  instructions=None)`) and asserts the returned string contains
  `"ot_servers.enable(name='playwright')"`. Also assert a `status="connected"` call does NOT
  contain `"ot_servers.enable"` (no false-positive hint on a healthy server). Mark
  `@pytest.mark.unit` + `@pytest.mark.serve`.

## 3. Seam 2 — typo'd pack yields a fuzzy suggestion + `ot.packs()` pointer

- [x] 3.1 In `src/ot/executor/runner.py`, in `execute_command`'s `except Exception as e:` block
  (currently lines 679-686), special-case `NameError`: when `isinstance(e, NameError)` and
  `getattr(e, "name", None)` is truthy, compute fuzzy suggestions against
  `sorted(tool_namespace.keys())` (the execution namespace already built at line 591 — do not
  rebuild it separately) using `_fuzzy_match` imported lazily from `ot.meta._help_formatting`
  (`from ot.meta._help_formatting import _fuzzy_match`, imported inside the branch, not at
  module level — see `design.md`'s Seam 2 decision for why a lazy import is required here).
  Append `". Did you mean: 'x', 'y'? Use ot.packs() to list all available packs."` (suggestions
  capped at 3, comma-separated, single-quoted) when `_fuzzy_match` returns a non-empty list, or
  just `". Use ot.packs() to list all available packs."` when it returns empty. Every other
  exception type's handling (message = `str(e)` verbatim, `success=False`, `error_type=type(e)
  .__name__`) is unchanged. **Coordinate with `p12-core-flow-hardening`**: that change also edits
  this same block (D2, converting `success=False` results into a raised `fastmcp.exceptions.
  ToolError`) — check the current state of this block before editing and preserve both changes'
  intent (this task only changes what text goes into the message; it does not touch `success`/
  `error_type`/whether an exception is raised afterward).
- [x] 3.2 Add a unit test that exercises `execute_command` (or `runner.execute_python_code` if
  that is the more direct unit boundary — check both, use whichever integrates a `NameError` for
  an unresolved pack name without a live proxy connection) with a command that references an
  undefined pack name that is a near-miss of a real pack, e.g. `"brvae.search(query='test')"`
  where `brave` is a real, registered pack. Assert the returned error text contains `"brave"` (the
  suggestion) and the literal substring `"ot.packs()"`. Place this test in
  `tests/unit/core/test_runner_logging.py` if that file already has `execute_command` test
  scaffolding, or a new `tests/unit/core/test_runner_errors.py` if not — check first, do not
  duplicate existing scaffolding. Mark `@pytest.mark.unit` + `@pytest.mark.core`.
- [x] 3.3 Add a second assertion (in the same test or a sibling test) for the no-plausible-match
  case: a command referencing a wildly different undefined name (e.g. `"zzzqqqxxx.thing()"`)
  still returns an error whose text contains `"ot.packs()"` but does not fabricate a "Did you
  mean" clause when no candidate clears `_fuzzy_match`'s similarity threshold.

## 4. Seam 3 — `ot.tool_info` returns `{error, did_you_mean}` instead of `{}`

- [x] 4.1 In `src/ot/meta/_discovery.py`, in `tool_info` (currently lines 126-215), collect an
  unfiltered list of every local and proxied tool's full name (`"pack.tool"`) as a second list
  alongside the existing pattern-filtered `results` list (do not reuse `results` for suggestions
  — by construction it is empty on an exact-name miss, since the substring filter at line 179
  already excluded every candidate; see `design.md`'s Seam 3 decision for the exact loop
  structure). Import `_fuzzy_match` from `ot.meta._help_formatting` (same package as
  `_discovery.py` — no circularity risk, a normal top-of-function or module-level import is fine).
- [x] 4.2 Replace the exact-name-miss return (currently line 213: `return {}`) with `return
  {"error": f"Tool '{filter_pattern}' not found.", "did_you_mean": _fuzzy_match(filter_pattern,
  all_full_names)[:5]}` (or equivalent — the returned dict MUST have exactly the keys `error` and
  `did_you_mean`, `error` MUST be a non-empty string, `did_you_mean` MUST be a list, capped at 5
  entries, that is empty when no candidate is a plausible match — never a missing key).
- [x] 4.3 Add a unit test in `tests/unit/tools/test_info.py` (existing file, already has
  `tool_info`-focused tests such as `test_tools_pattern_no_match_returns_empty` at line 163 and
  `test_tool_info_resolves_short_alias_pattern` at line 335 — follow their existing mocking
  pattern for `ot.meta._discovery`'s dependencies). Call `tool_info(name="brave.serch")` and
  assert the result is a dict with exactly the keys `{"error", "did_you_mean"}`, `did_you_mean`
  is non-empty, and `"brave.search"` is present in `did_you_mean`. Mark `@pytest.mark.unit` +
  `@pytest.mark.serve` (matching this file's existing marker convention).
- [x] 4.4 Add a second test asserting the no-plausible-match case: `tool_info(name=
  "zzzzz.nonexistent")` still returns `{"error": ..., "did_you_mean": []}` — an empty list, not a
  missing key or a re-introduced bare `{}`.

## 5. Seam 4 — universal `ot.result(handle=...)` hint, no `ctx.*` runtime hints

- [x] 5.1 In `src/ot/ctx/result_backend.py`, replace `CtxResultStoreBackend
  .format_store_response`'s `next_commands` list (currently lines 135-139, the three-entry
  `ctx.toc(...)`/`ctx.ask(...)`/`ctx.read(...)` list) with a single-entry list:
  `[f"ot.result(handle='{stored.handle}')"]`. Do not keep the old three hints alongside the new
  one "for richness" — this is a breaking-window replacement, not an addition (see `design.md`'s
  Implementation guardrails).
- [x] 5.2 Update `tests/unit/core/test_force_context_dunder.py::test_deflect_summary_includes_
  next_commands` (currently lines 179-200) — this test currently pins the *old* shape at lines
  198-200 (`assert parsed["next_commands"][0].startswith("ctx.toc(handle='")`, etc.) and WILL
  fail once 5.1 lands unless updated in the same change. Replace those three assertions with one
  asserting `parsed["next_commands"] == [f"ot.result(handle='{<the handle from this test's fake
  ctx_write>}')"]` (or a substring assertion on `"ot.result(handle='"` if the exact handle value
  is inconvenient to thread through — either is acceptable as long as the old `ctx.*` strings are
  no longer asserted).
- [x] 5.3 Confirm `src/ot/executor/result_store.py` (lines 66-69, the `QueryResult.to_dict`
  `next_query` hint) is unchanged — it already emits `ot.result(handle=...)` and is the reference
  shape Seam 4 converges on; do not modify it.

## 6. Verification

- [x] 6.1 Run the four new/updated unit test targets directly and confirm they pass:
  `uv run pytest tests/unit/core/test_pack_proxy.py -m unit -k disconnected -v`,
  `uv run pytest tests/unit/core/test_servers_redesign.py -m unit -k server_help -v` (adjust `-k`
  to match whatever test name was actually used in 2.2 if different),
  `uv run pytest tests/unit/tools/test_info.py -m unit -k did_you_mean -v` (adjust `-k` to match
  4.3's actual test name), `uv run pytest tests/unit/core/test_force_context_dunder.py -m unit -v`.
- [x] 6.2 Run `rg -n "ctx\.(toc|read|slice|grep|query|ask)" src/ot/executor/result_store.py
  src/ot/ctx/result_backend.py` and confirm it returns **empty** — this is the exact acceptance
  check from the source report (R2, "Acceptance checks"). If it returns any match, Seam 4 is not
  complete.
- [x] 6.3 Run `rg -n "next_commands" tests/ src/` and confirm every remaining occurrence reflects
  the new `ot.result(handle=...)` shape (no leftover `ctx.toc`/`ctx.ask`/`ctx.read` assertions
  anywhere in the test suite, not just in the one file called out in 5.2).
- [x] 6.4 Run the full unit test marker set for this change's touched areas:
  `uv run pytest -m "unit and (core or serve)" tests/unit/core tests/unit/tools/test_info.py -v`
  and confirm no failures, including in tests this change did not intend to touch (regression
  check).
- [x] 6.5 Run `just check` (lint + type + test) and confirm it passes clean. This is the repo-wide
  gate from `openspec/config.yaml`'s per-artifact rules and is required before this change is
  considered complete — do not mark this change done on the strength of the targeted test runs
  in 6.1-6.4 alone.
- [x] 6.6 Manually re-read the final diff for `src/ot/executor/runner.py`'s exception handler and
  confirm it does not conflict with or silently revert any concurrent edit from
  `p12-core-flow-hardening`'s D2 work in the same block (currently lines 679-686) — if that
  change has already landed on this branch/main by the time this task runs, rebase this change's
  edit on top of it rather than overwriting it.
