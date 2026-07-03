## Why

When an agent hits a wall inside a `run()` command, OneTool's own error text is the only
signal it gets — there is no human in the loop to interpret a stack trace. Four seams in that
recovery path currently fail agents silently instead of teaching them the fix:

1. Calling a tool on a server that is *configured but not yet connected* produces `Tool 'click'
   not found in MCP server 'playwright'. Available:` with an empty list — indistinguishable from
   a genuinely missing tool, with no mention of the one-line fix (`ot_servers.enable(...)`).
2. Typo'ing a pack name (`brvae.search(...)` instead of `brave.search(...)`) raises a raw Python
   `NameError` with no suggestion and no pointer to `ot.packs()`, even though the sibling
   "wrong-tool-in-a-known-server" path already offers fuzzy suggestions.
3. `ot.tool_info(name=...)` — the contract's designated "inspect before you call" move — returns
   a bare `{}` on a typo'd exact name, giving the agent nothing to act on.
4. Large-result deflection hints are inconsistent: the executor's own `ot.result` path already
   hints `ot.result(handle=...)`, but the ctx-backed result store still hints `ctx.toc/ctx.ask/
   ctx.read(...)` — commands that only exist when the optional `[util]` extra is installed. On a
   base install those hints dead-end.

Each of these is small in isolation but compounds: an agent that hits any one of them burns a
turn re-deriving what OneTool already knows and could have said directly.

## What Changes

- `src/ot/executor/pack_proxy.py`: when an MCP tool lookup fails on a server that is configured
  but not connected (`proxy.get_connection(server_name) is None`), raise a distinct
  `AttributeError` that names the server, states it is disconnected, and gives the exact
  `ot_servers.enable(name='<server>')` recovery command — instead of falling through to the
  generic "not found. Available: (empty)" message.
- `src/ot/meta/_help_formatting.py` (`_format_server_help`): when server `status != "connected"`,
  append the same `ot_servers.enable(name='<server>')` recovery line to the formatted server help
  output (`ot.help(query='<server>')` / `ot.server(name='<server>')`).
- `src/ot/executor/runner.py` (`execute_command`'s exception handler): when the caught exception
  is a `NameError` (the shape a typo'd pack name takes — Python raises `NameError` for an
  undefined namespace identifier), enrich the returned error text with a fuzzy did-you-mean
  suggestion drawn from the same execution namespace the command ran against, plus a pointer to
  `ot.packs()`. Non-`NameError` exceptions are unaffected.
- `src/ot/meta/_discovery.py` (`tool_info`): **BREAKING return-shape change.** On an exact-name
  miss (`name=` provided, no match), return `{"error": "...", "did_you_mean": [...]}` instead of
  `{}`. `did_you_mean` is a fuzzy-matched list (possibly empty) of known tool full-names.
- `src/ot/ctx/result_backend.py` (`CtxResultStoreBackend.format_store_response`): replace the
  `ctx.toc(...)` / `ctx.ask(...)` / `ctx.read(...)` next-command hints with a single
  `ot.result(handle='<handle>')` hint, matching what `src/ot/executor/result_store.py` already
  emits. `ctx.*` navigation remains fully functional — it is documented (elsewhere, by `p21`) as
  the richer `[util]`-only enhancement, but no runtime hint should recommend a command that may
  not exist in the caller's install.
- Update the one existing test that asserts the old `ctx.*` hint shape
  (`tests/unit/core/test_force_context_dunder.py::test_deflect_summary_includes_next_commands`,
  lines 198-200) to assert the new `ot.result(handle=...)` shape.
- Add one new unit test per seam (see `tasks.md` for exact assertions).

None of these changes alter which packs, tools, or servers exist, or how a *successful* call
behaves — only the text and shape of specific failure paths.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `tool-ot`: the `ot.tool_info()` "Tool Detail" requirement changes its return shape on an
  exact-name miss from `{}` to `{"error": ..., "did_you_mean": [...]}`. This is a genuine
  contract change (return shape), so it gets a formal MODIFIED delta.

No other capability gets a spec delta. The master planning report (`wip/release-v3/
release-v3-report-2.md`, R2) explicitly rules "OpenSpec: ... no for error-text fixes" for the
disconnected-server message (item 10) and the typo'd-pack suggestion (item 11), and the hint
unification (item 8) is an internal string-content fix with no change to any documented return
shape or tool signature. Verified against the existing specs before deciding this:
- `openspec/specs/serve-run-tool/spec.md` "Pack Resolution" > "Unknown pack" scenario already
  requires "an error listing available packs" for `unknown.func()` — the current `NameError`
  passthrough returns *an* error but lists nothing, so today's behavior only nominally satisfies
  the letter of that scenario. This change makes it substantively true (packs are actually
  listed via the did-you-mean suggestion + `ot.packs()` pointer) without altering the scenario's
  normative shape, so no delta is required — the fix is conformance, not a new contract.
- `openspec/specs/serve-mcp-proxy/spec.md` "Pack Tool Access" > "Unknown tool in pack" scenario
  is scoped to a server that "exists" (is connected); the disconnected-server case this change
  fixes is a distinct, previously-unspecified path, not a modification of that scenario.
- `openspec/specs/serve-mcp-proxy/spec.md` and `openspec/specs/serve-run-tool/spec.md` are
  otherwise untouched by this change.

## Impact

- **Affected code**: `src/ot/executor/pack_proxy.py` (`_create_mcp_proxy_pack.__getattr__`),
  `src/ot/meta/_help_formatting.py` (`_format_server_help`), `src/ot/executor/runner.py`
  (`execute_command`'s `except Exception as e:` block, currently lines 679-686), `src/ot/meta/
  _discovery.py` (`tool_info`, currently line 213), `src/ot/ctx/result_backend.py`
  (`CtxResultStoreBackend.format_store_response`, currently lines 130-140).
- **Affected tests**: `tests/unit/core/test_pack_proxy.py` (new test), `tests/unit/core/
  test_servers_redesign.py` or a new small test module for `_format_server_help` (new test),
  a new runner-level test for the typo'd-pack path, `tests/unit/tools/test_info.py` (new test),
  `tests/unit/core/test_force_context_dunder.py` (existing test updated at lines 198-200).
- **Dependency / coordination with `p12-core-flow-hardening`**: that change's D2 item also
  rewrites `src/ot/executor/runner.py`'s `execute_command` exception handling (to raise
  `fastmcp.exceptions.ToolError` on `success=False` instead of always returning a `CommandResult`)
  and touches the same `except Exception as e:` block (currently lines 679-686). This change only
  edits the *text* placed into `CommandResult.result` before that block returns; it does not
  change `success`/`error_type` semantics. Implementers of either change should check the other's
  current diff before editing this block to avoid clobbering each other's edit — rebase/coordinate
  rather than editing blind.
- **Dependency on `p21-run-contract-and-command-index`**: `p21` owns rewriting the `ot-ref` skill
  body, which currently documents `ctx.toc/read/slice/grep/query/ask` as the primary result-
  navigation idiom (`src/ot/config/global_templates/skills/ot-ref.md:85-90`). This change removes
  the `ctx.*` *runtime hint* but does not touch `ot-ref.md` prose — `p21` is responsible for
  repositioning `ctx.*` there as the richer `[util]`-only enhancement over the universal
  `ot.result(handle=...)` hint this change installs. Do not edit `ot-ref.md` in this change.
- **No config schema, CLI flag, or pack signature changes.** No new dependencies.

## Anchor verification note

Every `file:line` anchor cited above and in `tasks.md` was independently re-verified against
`main`@`151a52b3` (2026-07-04, the same commit the source report was verified against) before
writing this proposal. No drift was found — all anchors matched exactly.
