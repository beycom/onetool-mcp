## Context

OneTool's `run()` contract tells an agent to recover from failures by inspecting available
packs/tools and retrying (`ot.tool_info`, `ot.packs()`, `ot_servers.enable(...)`). Four specific
paths in the code behind that contract currently defeat it — verified by direct code reading
against `main`@`151a52b3` (2026-07-04), the same commit the source report (`wip/release-v3/
release-v3-report-2.md`, R2 items 8, 10, 11, 12) was verified against. No anchor drift was found
during this verification pass.

**Seam 1 — disconnected server masquerades as missing tool.**
`build_execution_namespace` (`src/ot/executor/pack_proxy.py:326`, the line
`known_servers = sorted(set(proxy_mgr.servers) | configured_server_names)`) deliberately injects
every *configured* MCP server into the run() namespace — including ones not yet connected — so
that `ot_servers.enable(name='x')` followed by `x.tool(...)` works inside a single command block
(this is intended, existing, correct behavior — see `serve-run-tool` spec's "Enabled proxy server
pack available in same command" scenario, and must not be changed).

The bug is downstream: when an agent calls a tool on a server injected this way but not yet
connected, `ProxyManager.list_tools(server)` (`src/ot/proxy/manager.py:150-167`) resolves
`self._tools_by_server.get(server, [])` (line 160) — which is `[]` for a server that has never
connected, because `_tools_by_server` is only populated on successful connect. In
`_create_mcp_proxy_pack.__getattr__` (`src/ot/executor/pack_proxy.py:127-168`), `available_tools`
is then `[]`, `find_canonical_match` returns `None`, `suggest_similar_names([], ...)` returns
`[]`, and the code falls into the final `else` branch (lines 162-168):

```python
else:
    available = ", ".join(f"'{t}'" for t in sorted(available_tools)[:10])
    more = f" (and {len(available_tools) - 10} more)" if len(available_tools) > 10 else ""
    raise AttributeError(
        f"Tool '{accessor_name}' not found in MCP server '{server_name}'. "
        f"Available: {available}{more}"
    )
```

With `available_tools == []`, this produces `"Tool 'click' not found in MCP server 'playwright'.
Available: "` — a trailing empty list, indistinguishable from "this tool genuinely does not
exist on a fully-connected server." The agent has no signal that the fix is a one-line
`ot_servers.enable(name='playwright')` call. The same gap exists in the human/agent-facing help
formatter: `_format_server_help` (`src/ot/meta/_help_formatting.py:339-389`) receives a `status`
string (`"connected"` or `"disconnected"`, computed by its one caller at `src/ot/meta/
_help.py:207-208`: `conn = _proxy.get_connection(query_as_server); status = "connected" if conn
else "disconnected"`) and prints it (line 365: `f"**Status:** {status}"`) but never suggests the
enable command.

**Seam 2 — typo'd pack → raw NameError.**
`ASTSecurityVisitor._check_qualified_call` (`src/ot/executor/validator.py:353-436`) only blocks
calls that match a known dangerous pattern or a known stdlib module; a call like
`brvae.search(query='x')` is not a tool namespace (line 377's `_is_tool_namespace` check fails —
`brvae` isn't registered), not blocked, not warned, and its module part isn't a known stdlib
module, so it falls through to the final default at line 436: "allow method calls on variables."
The validator has no way to distinguish an intentional local-variable method call from a
misspelled pack, so it correctly lets both through — the fix belongs downstream, not in the
validator.

At execution time, Python's `exec()` raises `NameError: name 'brvae' is not defined` when it
tries to resolve the undefined `brvae` identifier. `execute_command`'s catch-all handler
(`src/ot/executor/runner.py:679-686`):

```python
except Exception as e:
    return CommandResult(
        command=command,
        result=str(e),
        executor="python",
        success=False,
        error_type=type(e).__name__,
    )
```

returns `str(e)` verbatim — `"name 'brvae' is not defined"` — with no suggestion and no pointer
to `ot.packs()`. Contrast this with the sibling path one layer down: when a pack name resolves
correctly but the *tool* name inside it doesn't, `McpProxyPack.__getattr__`
(`src/ot/executor/pack_proxy.py:152-161`) already calls `suggest_similar_names` and offers
"Did you mean" text. The typo'd-*pack* case has no equivalent because a `NameError` on an
undefined pack name never reaches pack-proxy code at all — Python fails before any attribute
lookup happens.

**Seam 3 — `ot.tool_info` dead-ends on typos.**
`tool_info` (`src/ot/meta/_discovery.py:126-215`) builds `results` by iterating all local and
proxied tools and appending only those whose full name (`"pack.tool"`) contains
`filter_lower` as a substring (the `continue` at line 179 skips non-matches). When `name=` is an
exact typo like `"brave.serch"`, no tool's full name contains that substring, so `results` stays
empty for the entire loop. The exact-match check (lines 209-213):

```python
if name:
    for result in results:
        if result["name"] == filter_pattern:
            return result
    return {}
```

iterates the (already-empty) `results` and falls through to `return {}` — a bare empty dict with
no signal at all. **Important implementation trap**: because `results` is filtered *during* the
same loop that would otherwise let us compute suggestions, a correct fix cannot reuse `results`
for did-you-mean candidates — it must collect (or re-derive) the *unfiltered* set of all tool
full names separately, or the suggestion list will always be empty regardless of the typo.

**Seam 4 — dual handle idioms disagree.**
Two code paths format the "your output was too big, here's how to get it back" hint after a
large result is deflected to storage:

- `StoredResult`/`QueryResult` in `src/ot/executor/result_store.py` (lines 66-69) already emit
  `ot.result(handle='{handle}', offset=..., limit=...)` — the correct, universal idiom.
- `CtxResultStoreBackend.format_store_response` in `src/ot/ctx/result_backend.py` (lines 135-139)
  independently emits:
  ```python
  response["next_commands"] = [
      f"ctx.toc(handle='{stored.handle}')",
      f"ctx.ask(handle='{stored.handle}', q='What matters most here?')",
      f"ctx.read(handle='{stored.handle}', limit=80)",
  ]
  ```
  `ctx` (`ot_context`) is a tool pack shipped only via the optional `[util]` extra
  (`src/otutil/tools/ctx.py`); `ot.result` is a function in the always-present `ot` meta pack
  (`src/ot/meta/__init__.py:77` re-exporting `src/ot/meta/_stats.py:158`'s `result`), which reads
  off the *same* underlying ctx store regardless of which hint text is shown. So on a base
  install without `[util]`, `format_store_response`'s hint recommends three commands that do not
  exist in the agent's namespace at all — a dead end by construction, not by mistake.
  `format_store_response` is the one that's wrong; `result_store.py`'s hints are already correct
  and are the reference to converge on (maintainer ruling, R2 item 8).

## Goals / Non-Goals

**Goals:**
- Make each of the four failure/hint paths above name the actual problem and the actual fix,
  using only information already available at the point of failure (no new state, no new
  network calls, no new config).
- Converge on exactly one large-result hint idiom (`ot.result(handle=...)`) everywhere a runtime
  hint is emitted, regardless of install extras.
- Keep every change additive to error/hint *text* and one return *shape* (`tool_info`'s exact-
  miss dict) — no change to which packs/tools/servers are reachable, no change to successful-call
  behavior.

**Non-Goals:**
- Do not change `build_execution_namespace`'s pre-injection of configured-but-disconnected
  servers (`pack_proxy.py:326`) — that behavior is correct and required by the existing
  `serve-run-tool` "Enabled proxy server pack available in same command" scenario.
- Do not touch the AST validator (`validator.py`) — it correctly has no way to distinguish a
  typo'd pack from a legitimate local-variable method call, and should not try to.
  The fix for typo'd packs belongs entirely in `runner.py`'s exception handling, not in
  pre-execution validation.
- Do not rewrite `ot-ref.md` or reposition `ctx.*` as the `[util]`-enhanced navigation layer —
  that prose belongs to `p21-run-contract-and-command-index`. This change only touches the
  runtime hint *string* in `result_backend.py`.
- Do not change `ot.pack_info`'s existing `{"error": "Pack '...' not found. Use ot.packs()..."}`
  behavior (`src/ot/meta/_discovery.py:350`) — it is out of this change's scope (only
  `ot.tool_info` is named in R2 item 12); it is cited below only as a style precedent to match.
- Do not add fuzzy did-you-mean suggestions to the local-pack "wrong tool name" path
  (`_create_pack_proxy.__getattr__`, `pack_proxy.py:68-91`) — out of scope; only the *pack-name*
  suggestion (seam 2) and the *tool_info* suggestion (seam 3) are in scope.

## Decisions

### Seam 1: name the server and give the exact recovery command

In `_create_mcp_proxy_pack.__getattr__`, immediately inside the existing `if match_result is
None:` block (`pack_proxy.py:152`), add a first branch that checks connection state before
falling into the suggestion/available-tools logic:

```python
if match_result is None:
    if proxy.get_connection(server_name) is None:
        raise AttributeError(
            f"Server '{server_name}' is configured but not connected. "
            f"Tool '{accessor_name}' is unavailable until it connects. "
            f"Run ot_servers.enable(name='{server_name}') to connect it, then retry."
        )
    # existing suggestions / "Available: ..." logic, unchanged, for connected
    # servers where the tool genuinely doesn't exist
    suggestions = suggest_similar_names(accessor_name, available_tools)
    ...
```

`proxy` is already bound in this scope (`proxy = get_proxy_manager()`, line 135) — no new import
or state needed. `get_connection` returns `None` for a server that is configured but not (yet)
connected, and a `Client` object once connected; this is the same primitive `src/ot/meta/
_help.py:207` already uses to compute `status`.

The message MUST literally contain the substring `ot_servers.enable(name='<server_name>')`
(single-quoted, matching this file's existing quoting convention for interpolated names, e.g.
`f"Tool '{accessor_name}' not found..."`) and MUST state the server is not connected — tests
assert on both substrings, not exact string equality, so implementers have latitude in the
surrounding prose but not in these two facts.

Apply the equivalent fix to `_format_server_help` (`src/ot/meta/_help_formatting.py:339-389`):
right after the existing `lines.append(f"**Status:** {status}" + ...)` (line 364-366), add:

```python
if status != "connected":
    lines.append(f"**Recovery:** Run `ot_servers.enable(name='{server_name}')` to connect.")
```

placed before the blank-line append at line 370 so it stays grouped with the status block.

### Seam 2: fuzzy did-you-mean + `ot.packs()` pointer on `NameError`

In `execute_command`'s exception handler (`runner.py:679-686`), special-case `NameError` only —
every other exception type keeps today's `str(e)` passthrough unchanged (this handler is shared
with `p12-core-flow-hardening`'s D2 `ToolError` work; only the *text* going into
`CommandResult.result` changes here, not `success`/`error_type`):

```python
except Exception as e:
    result_text = str(e)
    if isinstance(e, NameError) and getattr(e, "name", None):
        from ot.meta._help_formatting import _fuzzy_match  # lazy import — see note below

        candidates = sorted(tool_namespace.keys())
        suggestions = _fuzzy_match(e.name, candidates)
        if suggestions:
            suggestion_list = ", ".join(f"'{s}'" for s in suggestions[:3])
            result_text = f"{result_text}. Did you mean: {suggestion_list}? Use ot.packs() to list all available packs."
        else:
            result_text = f"{result_text}. Use ot.packs() to list all available packs."
    return CommandResult(
        command=command,
        result=result_text,
        executor="python",
        success=False,
        error_type=type(e).__name__,
    )
```

Notes:
- `NameError.name` (the identifier that failed to resolve) has been available since Python 3.10;
  this repo requires 3.12+, so it is always present when the interpreter raises the error itself
  (it may be absent if code raises `NameError("...")` manually without the `name=` kwarg — the
  `getattr(e, "name", None)` guard handles that).
- `tool_namespace` (built at `runner.py:591`, `tool_namespace = build_execution_namespace(
  tool_registry)`) is already in scope at the exception handler — it is the exact set of
  pack/alias/server names the failing command executed against, so `sorted(tool_namespace.keys())`
  is the correct, already-available candidate list. Do not rebuild it from the registry
  separately.
- Reuse `_fuzzy_match` from `src/ot/meta/_help_formatting.py:34` (difflib `SequenceMatcher`-based,
  threshold 0.6 — already used by `ot.help(query=...)`'s fuzzy search) rather than
  `suggest_similar_names` from `ot/executor/naming.py`. `suggest_similar_names` only matches by
  canonical-form prefix/substring, which does **not** catch letter-transposition typos like
  `brvae` → `brave` (neither is a substring of the other); `_fuzzy_match`'s similarity-ratio
  approach does. This is the correct, already-battle-tested utility for this exact kind of typo —
  do not write a new similarity function.
- Import `_fuzzy_match` lazily, inside the branch, not at module level. `ot.meta` already imports
  from `ot.executor` (e.g. `ot.meta._discovery.tool_info` does `from ot.executor.tool_loader
  import load_tool_registry` inside the function body, and `ot.executor.tool_loader` imports `ot.
  meta` inside `_register_ot_pack`). A module-level `ot.executor.runner → ot.meta._help_formatting`
  import would risk a circular import at package init time; a lazy import inside the function
  body follows the existing pattern used at both ends of this same cross-package edge and avoids
  the risk entirely.
- Cap suggestions shown to 3 (`suggestions[:3]`) to keep the message short — `_fuzzy_match` has no
  built-in cap (unlike `suggest_similar_names`'s `max_suggestions`).

### Seam 3: `ot.tool_info` returns `{error, did_you_mean}` instead of `{}`

In `tool_info` (`_discovery.py:126-215`), the exact-name-miss branch (lines 209-213) must gain
access to *all* tool full names, not the pattern-filtered `results` list (which is empty by
construction on a miss — see Context above). The minimal, correct fix: collect the unfiltered
names as a second list alongside the existing loop, then use it only in the miss branch:

```python
all_full_names: list[str] = []
...
for func_name, func in func_items:
    full_name = f"{pack_name}.{func_name}"
    all_full_names.append(full_name)
    if filter_lower and filter_lower not in full_name.lower():
        continue
    ...
...
for proxy_tool in proxy.list_tools():
    ...
    all_full_names.append(tool_name)
    if filter_lower and filter_lower not in tool_name.lower():
        continue
    ...
...
if name:
    for result in results:
        if result["name"] == filter_pattern:
            return result
    from ot.meta._help_formatting import _fuzzy_match

    return {
        "error": f"Tool '{filter_pattern}' not found.",
        "did_you_mean": _fuzzy_match(filter_pattern, all_full_names)[:5],
    }
return results
```

(`_fuzzy_match` is already in the same package — `ot.meta._help_formatting` — as `_discovery.py`,
so this import has no circularity concern; it does not need to be lazy, but keeping it inline
next to the one call site is fine and matches this file's existing lazy-import style for
optional/heavy dependencies.)

Cap `did_you_mean` at 5 entries — matches `pack_info`'s existing precedent of a single
concise pointer sentence (`_discovery.py:350`: `f"Pack '{name}' not found. Use ot.packs() to list
available packs."`) without being unbounded.

### Seam 4: converge on `ot.result(handle=...)`

Replace `CtxResultStoreBackend.format_store_response`'s `next_commands` list (`result_backend.py:
135-139`) with a single universal hint:

```python
def format_store_response(self, stored: Any) -> dict[str, Any]:
    """Format runner response with the universal ot.result follow-up hint."""
    if not isinstance(stored, StoredResult):
        raise TypeError("ctx result store expected StoredResult")
    response = stored.to_dict()
    response["next_commands"] = [f"ot.result(handle='{stored.handle}')"]
    return response
```

This is deliberately a single-item list, not a re-creation of the old three-hint structure with
`ot.result` swapped in for each — the old three hints (`toc`/`ask`/`read`) don't have three
distinct `ot.result` equivalents (`ot.result` has no table-of-contents or natural-language-ask
mode; only paginated/searched read), so presenting three near-duplicate `ot.result(...)` calls
would be noise, not signal. One canonical entry point is the correct convergence, matching the
"one primary idiom everywhere" maintainer ruling (R2 item 8).

`tests/unit/core/test_force_context_dunder.py::test_deflect_summary_includes_next_commands`
(lines 179-200) asserts the *old* three-hint shape at lines 198-200 and **must be updated** as
part of this change, or it will fail after the fix lands. This is not optional cleanup — it is
the test that currently pins the behavior being changed.

## Risks / Trade-offs

- **[Risk]** Enriching every `NameError` with a pack-suggestion pointer could produce a slightly
  irrelevant hint for a `NameError` that has nothing to do with packs (e.g. a genuinely undefined
  local variable in otherwise-valid user code, like referencing `y` before assignment).
  **Mitigation**: the added text is always accurate as *general* recovery guidance (`ot.packs()`
  does list available packs, unconditionally true) and never asserts something false; when no
  fuzzy match clears the similarity threshold, the "Did you mean" clause is omitted entirely, so
  the enrichment degrades gracefully to just the `ot.packs()` pointer rather than a wrong guess.
- **[Risk]** `_fuzzy_match` is currently a module-private helper (`_` prefix) in `ot.meta.
  _help_formatting`, used elsewhere only within `ot.meta`. Importing it from `ot.executor.runner`
  and `ot.meta._discovery` reuses it beyond its original single call site.
  **Mitigation**: this is an internal reuse within the same codebase (not a public API boundary),
  the function has no side effects and a stable, already-tested signature
  (`_fuzzy_match(query: str, candidates: list[str], threshold: float = 0.6) -> list[str]`), and
  duplicating a second difflib-based similarity function instead would be worse (two subtly
  different fuzzy-match implementations to keep in sync). If a future change wants to formalize
  this as a shared utility (e.g. hoist to `otpack`), that is a separate refactor, not required
  here.
- **[Trade-off]** `format_store_response`'s new single-hint `next_commands` is less rich than the
  old three-hint list for callers who *do* have `[util]` installed. This is accepted per the
  maintainer ruling (R2 item 8): richer `ctx.*` navigation remains fully available and will be
  taught in the `ot-ref` skill body by `p21` — this change only removes it from the
  *unconditional runtime hint*, where it was actively misleading on a base install.

## Migration Plan

No data migration, no config migration, no deployment sequencing required — this is a pure code
change to error/hint text and one API return shape, released as part of the normal V3 cut. The
one required "migration" is the test update described in Seam 4's decision (update the pinned
old-shape assertion before/alongside the `result_backend.py` change, in the same commit, so the
suite is never red on `main` between the two edits).

## Open Questions

None outstanding. All four seams have concrete, fully-specified fixes above; the only cross-change
coordination point (shared edit region in `runner.py:679-686` with `p12-core-flow-hardening`'s D2)
is a sequencing/rebase concern, not an open design question — see `proposal.md`'s Impact section.

## Implementation guardrails

- **No compatibility shims or aliases.** The old `ctx.toc/ctx.ask/ctx.read` hint strings in
  `format_store_response` are deleted outright, not kept alongside the new `ot.result(...)` hint
  "just in case." V3 is a breaking window; there is no back-compat requirement for hint text.
- **No stubbing, no TODO-deferral.** If any task below cannot be completed as specified (for
  example, if `_fuzzy_match` turns out not to import cleanly from `ot.executor.runner` for a
  reason not anticipated here), stop and report the blocker — do not land a partial fix, a
  hard-coded suggestion list, or a `# TODO: fuzzy match` placeholder.
- **Tests are part of every code task**, using this repo's existing marker convention
  (`@pytest.mark.unit` + a component tag such as `@pytest.mark.core` or `@pytest.mark.serve` —
  see `tasks.md` for the exact marker per test). `just check` (lint + type + test) MUST pass
  before any task in this change is considered complete.
- **Every `rg` verification command listed in `tasks.md`'s Verification section that is
  documented to return empty MUST actually be run, and MUST actually return empty**, before the
  change is marked done. A verification step that is merely read and judged "probably fine" does
  not satisfy this change's exit criteria.
- **Do not touch `ot-ref.md`, `prompts.yaml`, the AST validator, or the disconnected-server
  namespace-injection logic** — each is explicitly out of scope (see Non-Goals) and owned
  elsewhere or intentionally unchanged.
