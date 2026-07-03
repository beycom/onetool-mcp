## Context

`main`@`151a52b3` (2026-07-04), FastMCP **3.3.1** installed (pinned `>=3.1.1,<4`). This design consolidates a four-parallel-trace deep dive of the `run` MCP tool pipeline (`wip/release-v3/core-flow-deep-dive.md`, not available to implementers — every fact needed is inlined below) plus report-2 R8 P1–P4 (event-loop offload, cache bound, serialization/AST perf). The pipeline covered is: command preparation/normalization → validation → execution (in-process or thread-offloaded) → result serialization/return → (when applicable) external MCP proxy result conversion.

### One Cross-Cutting Pattern

Almost every defect fixed by this change is one shape: **a transform that should degrade gracefully instead crashes, or silently produces a wrong value.** Command normalization crashes the tool instead of falling back; `json.dumps` with no `default=` turns a good result into a reported error; `resolve_kwargs` overwrites a correct argument with an abbreviation; the proxy `json.loads`-coerces a string answer into the wrong type; the proxy result loop silently drops content it doesn't recognize. **Fixing the pattern — degrade, don't crash; refuse ambiguity, don't guess — resolves the bulk of the list.** Every decision in this design should be checked against that principle: when a transform can fail, prefer falling back to the last-known-good value over raising, *except* when the failure is a genuine ambiguity (two arguments would silently bind to the same parameter, a command is empty) — there, refuse loudly instead of guessing.

### Verified-Good Baseline (DO NOT DISTURB)

The following was confirmed correct by direct code read during the deep dive and MUST NOT be changed by this work:

- Input JSON schema is valid and `ctx`/`outputSchema` are handled right.
- `content` is always a non-empty `TextContent` list.
- No deprecated FastMCP APIs are in use.
- stdout is clean on the core path: file-only logging, `show_banner=False`, user stdout captured via `redirect_stdout`, and `paths.py` prints to stderr with a guard comment (do not change this without re-verifying the stdio JSON-RPC stream stays clean).
- The Direct API is HMAC-authed (HMAC-SHA256 + `compare_digest` + ±30s skew + 60s nonce cache, key `0600`, loopback-only) with a 1 MB body cap on every endpoint.
- `expand_vars` fails loudly on missing secrets (no silent fallback to empty string).
- Proxy alias ambiguity (canonical-name collisions between two tool names) already raises a clear error — this is the pattern D4's `resolve_kwargs` fix is bringing parameter resolution into line with, not a new mechanism to invent.
- Downstream `isError` from a proxied server already raises out of `client.call_tool` (not silently swallowed) — this change's D2 fix makes OneTool's *own* `run` tool behave the same way toward its caller.

## Goals / Non-Goals

**Goals:**
- Make `run()` unable to crash out of preparation (D1) and make its failure/success contract MCP-spec-compliant (D2).
- Make the execution path never block the FastMCP event loop, and make server-control sync bridges deadlock-proof (D3).
- Make parameter resolution and result serialization refuse ambiguity / degrade instead of silently corrupting a result (D4, D7–D10, D-b1).
- Make nested `__onetool(...)` execution and proxy caches behave hygienically under restart/reconnect (D5, D14).
- Make the MCP proxy's own result-conversion layer as correct as the framework's `ProxyProvider` for the two content-block shapes it currently mishandles (D12, D13), and thread-safe under concurrent connect (D15).
- Bound a process-lifetime-unbounded cache (R8 P2).

**Non-Goals:**
- Do not adopt FastMCP's `run_in_thread=True` / native tool timeout mechanics, `ProxyProvider` delegation, or Monty sandboxing as a wholesale replacement for the hand-rolled equivalents — see "Own vs. Delegate — Deferred" below.
- Do not narrow the `__builtins__` exposed to exec'd code or add sandbox containment (`security-model.md` doc-truth work is `p22-technical-foundation`, R8 S1 — an explicit maintainer ruling that OneTool is intentionally not a sandbox).
- Do not bump the FastMCP floor pin (`p32-dependency-refresh`, R8 M6) — D2's `ToolError` fix works today against the installed 3.3.1.
- Do not change `security.yaml`/config schema — no item here requires a config-schema change.
- R8 P3 (single-serialize deflection) and P4 (registry double AST parse) are explicitly optional/lower-priority per the source report; implement only if the primary fixes leave time, and never at the expense of the required items.

## Decisions

### D1 — Guard normalization, never let preparation crash `run`

**Root cause.** `_normalize_code` (`src/ot/executor/runner.py:121-133`) calls `ast.unparse()` then `_force_single_quotes` (`:94-118`) re-quotes double-quoted string literals to single quotes by decoding the token (`ast.literal_eval`) and re-escaping *only* `\` and `'` — not `\n`/`\r`. `ast.unparse` keeps a string double-quoted whenever it contains `'` but no `"`. When such a string also contains a real newline, that newline lands inside a single-line single-quoted literal after re-quoting, producing an unterminated string. The subsequent `ast.parse(normalized)` at `:133` raises `SyntaxError`, which propagates unguarded through `prepare_command` (`:521-523`, called under "Step 7: Normalize") and unguarded through `run` (`src/ot/server.py:543`), crashing the tool handler.

Reproduced: `_normalize_code('note(text="Here\'s the plan:\nstep 1")')` raises `SyntaxError: unterminated string literal (detected at line 1)`. Trigger: any string argument containing both an apostrophe and a newline — an everyday shape (`"Here's the plan:\n..."`).

**Decision.** Three-layer defense, all required:
1. In `_force_single_quotes`, skip re-quoting any token whose decoded value contains a control character: `if "\n" in val or "\r" in val or any(ord(c) < 0x20 for c in val): result.append(tok); continue`. The re-quoting is purely cosmetic (cleaner wire format); skipping it for control-char strings is a no-op on correctness.
2. Wrap the normalization call inside `prepare_command` in try/except; on any exception, fall back to the validated-but-unnormalized code (it is already valid Python — normalization is cosmetic, not required for correctness).
3. Wrap the `prepare_command(command)` call inside `run` (`server.py`) in try/except so that even an unanticipated exception in preparation becomes a clean `prepared.error`-shaped failure (which then flows through D2's `ToolError` path) instead of an uncaught exception escaping the tool handler.

**Alternative considered and rejected.** Fixing only `_force_single_quotes` (layer 1) without the try/except wrappers (layers 2–3) was rejected: it fixes the *known* trigger but leaves `run` crashable by any *other* normalization bug, violating "degrade, don't crash." All three layers are required.

### D2 — Raise `ToolError` for `isError:true`

**Root cause.** Confirmed against installed FastMCP 3.3.1 (`fastmcp.tools.tool.ToolResult` — fields `content`/`structured_content`/`meta` only, no `is_error` field in this version): `isError` is set *exclusively* by raising — a raised `fastmcp.exceptions.ToolError` produces `isError:true`; a *returned* `ToolResult` always produces `isError:false`. `run()` (`src/ot/server.py:538-572`) always returns — including at `:546` for `prepared.error` and at `:572` which wraps `result.result` regardless of `result.success`. So validation failures, user-code exceptions, and snippet errors all reach the client as `isError:false`. This is also internally inconsistent: an *unexpected* raise from `prepare_command` (before D1's guard) already propagated and became `isError:true`, so a crash was flagged as an error while a clean, intentional validation message was not — backwards.

**Decision.** `from fastmcp.exceptions import ToolError`. Replace `return ToolResult(content=f"Error: {prepared.error}")` with `raise ToolError(f"Error: {prepared.error}")`. Replace the unconditional `return ToolResult(content=text)` after `execute_command` with: if `not result.success`, `raise ToolError(text)`; else `return ToolResult(content=text)`. Keep the actionable error text (post-sanitization, per D-b2) in the exception message so the calling model still sees exactly what went wrong. **No FastMCP version bump required** — `ToolError` → `isError:true` is core behavior, not a 3.4.0 feature. (3.4.0's `ToolResult(is_error=True)` is a convenience alternative FastMCP added later; not required here and not adopted, to avoid coupling this fix to a version bump owned by a different change.)

**Alternative considered and rejected.** Waiting for the `p32-dependency-refresh` floor bump to `fastmcp>=3.4.1` and using `ToolResult(is_error=True)` was rejected — it works today at zero dependency cost, and gates a spec-compliance fix behind an unrelated change's timeline.

### D3 — Always offload to a thread; guard the sync bridges; add a per-tool timeout

**Root cause — three facets of one cause.** `src/ot/executor/runner.py:598` sets `use_thread_pool = bool(proxy.servers)`; with no proxy servers *connected* (the common default), user code runs synchronously on the event-loop thread (`:635-642`).
- **Freeze**: a blocking tool (`file.read`, a SQLite query, `webfetch` up to 30s) stalls the whole FastMCP server — no concurrent `run`, `ping`, or cancellation processing.
- **Deadlock**: if that inline (event-loop-thread) code calls a server-control tool while nothing is connected, `connect_additional_sync` (`src/ot/proxy/manager.py:737`) and `disconnect_server_sync` (`:782`) do `run_coroutine_threadsafe(...).result(timeout=120/30)` onto the *same* loop the calling code is currently blocking → the scheduled coroutine can never run on that loop → multi-minute freeze then `TimeoutError`. `reconnect_sync` (`src/ot/proxy/manager.py:813` region, guard around line 836-837) already has the fix pattern: `if running_loop is loop: ...` (schedule via `create_task` instead of blocking `.result()`). `connect_additional_sync` and `disconnect_server_sync` lack this guard. Reachable via `ot_servers.enable`/`ot_servers.restart` at startup or with any single disconnected server (~150s frozen for a restart).
- **Dead cancellation**: because the inline path blocks the loop, `notifications/cancelled` cannot even be processed, and synchronous Python code cannot receive `CancelledError` regardless. No per-tool timeout exists today (`@mcp.tool` sets none).

**Decision.**
1. Always dispatch user code via `asyncio.to_thread` in `execute_command` — delete the `use_thread_pool` conditional and its `bool(proxy.servers)` check; always take the `asyncio.to_thread(execute_python_code, ...)` branch. This keeps the event loop free for `run_coroutine_threadsafe`-based proxy calls in *all* cases, which also makes the deadlock in facet 2 moot for the tool-execution path itself (the loop is never blocked by user code).
2. Add the same `running_loop is self._loop` guard `reconnect_sync` has to `connect_additional_sync` and `disconnect_server_sync`: if the sync method is invoked from code already running on the proxy manager's own loop, schedule via `self._loop.create_task(...)` (fire-and-continue, matching `reconnect_sync`'s pattern) instead of blocking on `future.result(timeout=...)` — a blocking wait on your own loop from your own loop can never complete. This closes the deadlock even for the (now rare, but still reachable via other code paths) case where connect/disconnect is invoked from loop-thread code.
3. Add a bounded per-tool execution timeout around the `asyncio.to_thread` call (implementation: `asyncio.wait_for` around the `to_thread` coroutine, matching the timeout conventions already used elsewhere in `runner.py`/`manager.py`, e.g. the `timeout + 5` pattern at `manager.py:303`). On timeout, produce a clean `CommandResult(success=False, ...)` that flows through D2's `ToolError` path rather than hanging indefinitely.

**Alternative considered and rejected — FastMCP `run_in_thread=True` / native tool timeout (3.3.0/3.0.0).** Evaluated and **not adopted in this change**: these are framework-native mechanics that could eventually replace the hand-rolled `asyncio.to_thread` + timeout code, but swapping the execution primitive is a larger, independently-testable change; the guard fix in facet 2 (same-loop bridges) is needed regardless of which primitive runs the tool code, so it is not blocked on this evaluation. Tracked as a post-V3 "own vs. delegate" watch-item (see below).

### D4 — `resolve_kwargs` refuses collisions

**Root cause.** `src/ot/executor/param_resolver.py:106-124` (`resolve_kwargs`) has no collision detection: when one provided kwarg exact-matches a parameter and a *different* provided kwarg prefix-matches the *same* parameter, dict-iteration order decides which value survives — the other is silently discarded. Reproduced:
```python
resolve_kwargs({'query': 'real', 'q': 'typo'}, ['query', 'count'])
# → {'query': 'typo'}   # correct value lost; 'q' prefix-matched 'query' and overwrote it

resolve_kwargs({'c': 'A', 'count': 'B'}, ['count'])   → {'count': 'B'}
resolve_kwargs({'count': 'B', 'c': 'A'}, ['count'])   → {'count': 'A'}   # opposite result, order-dependent
```
So `search(query="real", q="typo")` silently sends `query="typo"` to the underlying tool — silent wrong-argument binding, and the outcome depends on dict iteration order (insertion order in CPython, i.e. call-site argument order), which is not something a caller should have to reason about.

**Decision.** Track, for each resolved target parameter name, which provided key(s) already claimed it. When a second provided key (whether by exact match or prefix match) would resolve to a target parameter name that is already claimed by a *different* provided key, raise a clear `ValueError`/`TypeError` (ambiguity error) naming both colliding keys and the shared target, instead of silently overwriting. This does **not** change the existing "multiple prefix matches, first-in-signature-order wins" behavior for the case of a *single* provided kwarg that prefix-matches multiple *different* candidate parameter names (e.g. `q=` matching both `query_info` and `query` when only `q` was provided) — that is a distinct, already-specified, and already-correct behavior (see the existing "Multiple prefix matches with first-wins" scenario in `serve-run-tool`). The new refusal applies specifically when two *different* provided keys would write to the *same* resolved target.

**Alternative considered and rejected.** Silently preferring exact matches over prefix matches (instead of raising) was rejected: it would fix the reproduced case but still silently discard a value the caller explicitly provided (`q="typo"` would vanish with no signal), reintroducing the same "silently produces a wrong value" failure mode this change is designed to eliminate. Refuse, don't guess.

### D5 — Nested `__onetool` isolation

**Root cause.** `src/ot/executor/runner.py:368-383` (`_nested_run`, closing over the outer `namespace` dict) execs nested commands directly into the *same* shared `namespace` dict the outer wrapped code runs in, and both the outer code and (per `:270` region) the magic-reading logic use `global __format__, __sanitize__, __force_context__`. Because nested and outer code share one namespace and both can set these globals, a nested command that sets e.g. `__format__ = 'raw'` or `__force_context__ = True` overwrites the outer command's setting — and `execute_python_code` reads the magics *after* the (outer) `exec` completes (`:400-407`), so it observes whichever value was set last, which may be the nested command's, not the outer command's. Ordinary variables leak both directions too (nested code can read/clobber outer locals, and vice versa).

**Decision.** `_nested_run` execs into a **child namespace** — a shallow copy (`dict(namespace)`) rather than the outer namespace directly — and the three magics are **snapshotted before and restored after** the nested `exec` call, so a nested command's magic-variable settings cannot leak into the outer command's result regardless of what the nested command does internally. Ordinary variable names remain isolated as a side effect of using a copied dict (mutations to the child dict do not write back to the parent).

### D6 — Preserve the real exception type

**Root cause.** `src/ot/executor/runner.py:424-430` wraps every runtime error as `raise ValueError(f"❗️Execution error at line {n}: {str(e)}") from e` — the message keeps only `str(e)`, dropping the original type name — and the outer `execute_command` catch clause (`:677-686` region) then records `error_type=type(e).__name__`, which is now unconditionally `"ValueError"` because `e` at that point *is* the wrapper, not the original exception. A `KeyError('missing')` is reported with `error_type="ValueError"` and message `"❗️Execution error at line 2: 'missing'"` — ambiguous, and blinding both to any client branching on `error_type` and to the stats surface (`serve-stats` already specifies `error_type` is recorded on failure; this makes the recorded value meaningless).

**Decision.** Include `type(e).__name__` in the wrapped message (e.g. `f"❗️Execution error at line {n}: {type(e).__name__}: {e}"`), **and** thread the original exception's type name through to `CommandResult.error_type` — either by attaching it as an attribute on the wrapper exception before raising, or by having the outer catch clause unwrap `__cause__`/`__context__` to find the innermost original exception's type. This is a bug-fix against the *existing* `serve-run-tool` "Runtime error context" requirement scenario ("error SHALL include the exception type and message"), which the current implementation violates — no new spec requirement is needed for the message-text half of this fix; `serve-stats` gets a clarifying scenario for the `error_type` field's meaning.

### D7–D10, D-b1 — Serialization resilience in `serialize_result`

**Root causes (four related defects in `src/ot/utils/format.py` and one in `runner.py`):**
- **D7** (`runner.py:652`): `result_size = len(text_result.encode("utf-8"))` runs on essentially every call (`allow_deflect` defaults true). A lone UTF-16 surrogate (`\ud800`–`\udfff`) in the result string — which arises routinely from `os.fsdecode`/`surrogateescape` handling of invalid-UTF-8 filesystem names (real for `file`/`ripgrep`/`localhist` tools) — raises `UnicodeEncodeError` here, even though `json.dumps(..., ensure_ascii=False)` happily built the surrogate-containing string without error upstream. The tool's real, correct output is discarded and replaced with a cryptic codec error message.
- **D8** (`format.py:42-50`): `json.dumps` is called with no `default=`. A tool returning e.g. `{"generated_at": datetime.now(), "score": Decimal("1.5")}` — or any `set`/`bytes`/`Path`/custom-object/circular-ref nested anywhere in the result — raises `TypeError`, caught by `execute_python_code`'s try/except and reported as `❗️Execution error`. The tool succeeded; the caller is told it failed.
- **D9** (`format.py:44,49,64`): default `allow_nan=True` means `float('nan')` serializes to `NaN` and `float('inf')` to `Infinity` — not valid JSON. A caller's `json.loads` on the result rejects it. Reachable from any averaging/ratio/score computation with a divide-by-zero.
- **D10** (`format.py:45,50,55,60,65`): a **top-level** non-serializable value (not nested inside a dict/list) falls through to `str(result)` while `CommandResult.format` still reports `"json"` — `{1,2,3}` becomes the string `"{1, 2, 3}"` labeled as JSON. This is inconsistent with D8: the *same types*, nested one level deeper, raise instead of degrading. Behavior currently depends on nesting depth, which is not something callers should have to know.
- **D-b1** (`format.py`, `yml`/`yml_h` branches): use unsafe `yaml.dump`, which emits Python-specific tags (`!!python/object`, `!!set`) a non-Python YAML consumer cannot parse, and raises `RepresenterError` (→ same "execution error" misreport as D8) for types PyYAML's default dumper cannot represent at all.

**Decision — one change addresses all five:**
1. In `format.py`, switch every `json.dumps` call to `json.dumps(result, ensure_ascii=False, default=str, allow_nan=False, ...)` (keeping each branch's existing `separators=`/`indent=` per format mode). `default=str` degrades any non-JSON-native value (datetime, Decimal, set, bytes, Path, custom object) to its `str()` representation instead of raising (fixes D8, and makes D10's top-level-vs-nested behavior consistent since both paths now degrade the same way). `allow_nan=False` makes `json.dumps` raise `ValueError` on NaN/Infinity instead of emitting invalid JSON; catch that `ValueError` at the call site and substitute a JSON-safe sentinel (`null`, or a string marker such as `"NaN"`/`"Infinity"` — implementer's choice, document whichever is chosen) so the overall serialization still succeeds (fixes D9).
2. Switch the `yml`/`yml_h` branches to `yaml.safe_dump` with a fallback representer (e.g. register a representer that stringifies unknown types, or catch `yaml.representer.RepresenterError` and retry with values pre-coerced via the same `default=str`-style degrade used for JSON) so unsafe tags are never emitted and unrepresentable types degrade instead of crashing (fixes D-b1).
3. In `runner.py`, scrub lone surrogates at the serialize boundary before the `.encode("utf-8")` size check: `text.encode("utf-8", "replace").decode()` (or equivalent) applied to `text_result` before it leaves the serialization step; if an exact byte-accurate size is needed for the threshold comparison, encode with `errors="surrogatepass"` for the *measurement* while still scrubbing the value that is actually returned/stored (fixes D7).
4. Ensure `CommandResult.format` reflects the format mode actually used to produce the string (the requested `fmt`, since degrade-to-`str()` now happens *inside* each format branch rather than as an out-of-band fallback) — this removes the "mislabeled format" half of D10.

### D11 — Tighten `TRIGGER_PATTERN`

**Root cause.** `src/ot/utils/sanitize.py:27-30`: `TRIGGER_PATTERN = re.compile(r"(__onetool\b|__ot\b|mcp__onetool\w*)", re.IGNORECASE)`, applied to all sanitization-enabled output (`server.py:569` region). `__ot\b` is 4 characters and case-insensitive, so ordinary prose is corrupted: `"see __ot for details"` → `"see [REDACTED:trigger] for details"`; `"the __OT flag"` → `"the [REDACTED:trigger] flag"`. Any web page, source file, or log line a tool returns that happens to mention the token gets mutated. (Not a security hole on its own: `sanitize_tag_closes` strips any boundary close-tag regardless of the embedded GUID, so the 16-bit GUID is not exploitable as a bypass — this is purely a content-corruption bug.)

**Decision.** Require the invocation shape for the short `__ot` token, but note the existing test suite's genuine-trigger fixtures use `__ot <identifier>(...)` **with a space** before the call (e.g. `"Please run: __ot file.delete(path='important.py')"`, `tests/unit/core/test_sanitize.py:24`; `"__ot foo() and then __ot bar()..."`, `:53`; `"Run __ot dangerous_command()"`, `:146`) — so the fix cannot require `.`/`(` to *immediately* follow `__ot` (that would break these already-correct detections). Instead, require that a call-shape — optional whitespace, then an optional dotted identifier, then an opening `(` — follows shortly after `__ot`, with no other punctuation in between: `__ot\b\s*[\w.]*\(`. This matches every existing genuine-trigger fixture (`__ot file.delete(`, `__ot foo(`, `__ot bar(`, `__ot dangerous_command(`) while rejecting both false positives from the report (`"see __ot for details"` — no `(` follows; `"the __OT flag"` — no `(` follows) without needing to also drop `re.IGNORECASE`. `__onetool\b` and `mcp__onetool\w*` keep their current broader matching (they are long enough that false-positive prose collision is not a realistic concern).

**Test-suite consequence (call out explicitly, do not silently patch).** `tests/unit/core/test_sanitize.py::TestSanitizeOutput::test_sanitizes_when_enabled` (`:227` region) currently asserts `"Result with __ot trigger"` gets redacted — that input has no call shape after `__ot` (`__ot` is followed by `" trigger"`, no parens) and is now, correctly, a false positive this fix must stop redacting. This test's fixture string must be updated to a genuine call-shaped trigger (e.g. `"Result with __ot.file.delete() trigger"` or reuse the `__onetool` form) as part of this task — this is an intentional behavior change to a test that encoded the bug, not a regression to avoid.

### D-b2, D-b3 — Sanitize-treatment consistency

- **D-b2** (`runner.py:680-686` region vs. `server.py:546`): trusted error `CommandResult`s built in `execute_command`'s except clause keep the dataclass default `should_sanitize=True`, so first-party error text gets boundary-wrapped and trigger-redacted (subject to D11's fix) even though it originates from OneTool itself, not untrusted tool output — while `prepare_command` errors returned at `server.py:546` bypass `sanitize_output` entirely (that early-return branch never reaches the `sanitize_output(...)` call at `:569`). Two different error surfaces get opposite treatment. **Decision**: set `should_sanitize=False` on error `CommandResult`s (first-party error text does not need boundary-wrapping or trigger redaction — it is not untrusted external content), and route the `prepare_command`-error path through the same `should_sanitize=False` treatment explicitly (rather than accidentally skipping sanitization by not calling it at all) so both surfaces are handled by the same code path once D2's `ToolError` change unifies them.
- **D-b3** (`runner.py:656-662`): large-output deflection calls `result_store.store(ctx_content, ...)` with the **unsanitized** full body, so a later `ctx.read(handle)` returns raw, un-wrapped content — bypassing the sanitization boundary entirely for anything large enough to be deflected. It also always re-serializes `ctx_content` as indented JSON (`json.dumps(raw_result, indent=2, ...)` when `raw_result` is a dict/list) even when the caller requested `__format__ = 'yml'` or `'raw'`, so the stored form silently differs from what the inline response would have shown. **Decision**: sanitize `ctx_content` before calling `result_store.store` (or sanitize at `ctx.read` time — implementer's choice, document which), and serialize `ctx_content` using the caller's requested `fmt` (the same `result_fmt` already threaded through `execute_python_code`'s return tuple) instead of unconditionally re-encoding as JSON.

### D-a1 — Empty command: explicit validation error (decision recorded here)

**Current behavior.** An empty or whitespace-only command bypasses the `!onetool` legacy-prefix check (`runner.py:465-472`), passes fence-stripping/snippet/alias/validation steps (an empty `ast.Module` has no body, nothing to flag), and executes as a no-op function body — returning `success=True` with the message `"Code executed successfully (no return value)"` (`runner.py:412`).

**Decision — treat as an explicit validation error.** Add a check immediately after `stripped_cmd = command.strip()` in `prepare_command` (alongside the existing `!onetool` prefix check, same style): if `not stripped_cmd`, return `PreparedCommand(code="", original=command, error="Command is empty. Provide a Python expression or tool call, e.g. pack.tool(arg=value).")`. This flows through D2's `ToolError` path, so an agent that accidentally sends an empty command gets an immediate, actionable `isError:true` instead of a silent, misleading "success." **Rationale**: this is the "refuse ambiguity, don't guess" half of the cross-cutting pattern — an empty command has no discoverable intent, so silently declaring victory is worse than telling the caller nothing happened.

### D-a2, D-a4 — Nested execution depth guard and error line offset

- **D-a2**: `_nested_run` (`runner.py:368`) has no recursion depth counter, and `__onetool` passes the AST validator (it is not a blocked builtin/import), so a command that calls `__onetool(...)` recursively (directly or via a snippet that expands to another `__onetool(...)` call) can exhaust the Python call stack, surfacing as an unhandled `RecursionError` rather than a clean error. **Decision**: add a small depth counter (module-level or threaded through `_nested_run`'s closure) with a low bound (e.g. 5) that raises a clear `ValueError` ("nested __onetool call depth exceeded") before the stack is at risk.
- **D-a4**: `_map_error_line` (`runner.py:293-315`) computes original-source line numbers for error messages using the *outer* command's `line_offset`, even for exceptions raised inside a nested `__onetool(...)` exec — so nested error line numbers are systematically wrong (pointing at a line in the outer command instead of the nested one). **Decision**: `_nested_run` must compute and pass its own `line_offset` (from `wrap_code_for_exec` on the *nested* code) so `_map_error_line` maps nested exceptions against the nested code's offset, not the outer one.

### D-c1 — `future.cancel()` on the proxy sync-call timeout path

**Root cause.** `ProxyManager.call_tool_sync` (`src/ot/proxy/manager.py:296-303`) schedules `self.call_tool(...)` via `run_coroutine_threadsafe` and blocks with `future.result(timeout=timeout + 5)`. If that `future.result()` call itself times out (raising `concurrent.futures.TimeoutError`), the scheduled coroutine keeps running on the event loop — `future.cancel()` is never called — and if the downstream `call_tool` ignores `CancelledError` (or is simply slow), it continues running to completion in the background after the caller has already received a timeout error, leaking work. This is also inconsistent with the *existing* `serve-mcp-proxy` "Timeout handling" scenario, which already specifies "the operation SHALL be cancelled" on timeout — the current code does not do this.

**Decision.** Wrap the `future.result(timeout=timeout + 5)` call in a `try`/`except concurrent.futures.TimeoutError` that calls `future.cancel()` before re-raising (or before raising OneTool's own `TimeoutError`, matching the pattern already used in the `fire_and_forget` branch's error handling above it). This is a bug-fix bringing the implementation into line with an existing spec scenario — no new delta needed for `serve-mcp-proxy`'s async-execution requirement text itself.

### D12, D13 — Proxy result-conversion correctness

**Root cause.** `ProxyManager.call_tool`'s result-extraction loop (`src/ot/proxy/manager.py:222-237`):
```python
for content in result.content:
    if isinstance(content, types.TextContent):
        text_parts.append(content.text)
    elif hasattr(content, "data"):
        text_parts.append(f"[Binary content: {type(content).__name__}]")
```
- **D12**: only `TextContent` and objects exposing `.data` are handled. A `types.EmbeddedResource` (payload under `.resource`, common for document/file-oriented MCP servers) matches neither branch and is silently dropped — `text_parts` stays empty, and the caller receives `"Tool returned empty response."` even though the downstream tool actually returned a payload. `result.structured_content`/`result.data` are never consulted as a fallback either.
- **D13**: when exactly one text part is present, it is unconditionally force-parsed with `json.loads` (`:232-237` region): `"007"` → `7` (int, not string `"007"`), `"null"` → `None`, `"true"` → `True`, `"NaN"`/`"Infinity"` → floats, `"[1,2]"` → a list. A downstream tool whose contract is "return a plain text answer" has its result silently coerced to a different type whenever the text happens to parse as JSON.

**Decision.**
1. Add a branch handling `types.EmbeddedResource`: extract its `.resource.text` (or a blob marker if binary) as a text part, so document/file-server payloads are no longer dropped.
2. When the `content` loop yields no text parts at all, fall back to `result.structured_content` or `result.data` (whichever the FastMCP `CallToolResult` exposes) before giving up and reporting "empty response."
3. Restrict the JSON-coercion attempt to text that structurally looks like JSON: only call `json.loads` when the text, stripped, starts with `{` or `[`. Plain scalars/strings pass through untouched — `"007"` stays the string `"007"`. (Structured returns that need type fidelity should prefer `structured_content`, per point 2, rather than relying on brittle text-shape sniffing for objects/arrays — the `{`/`[` heuristic is a pragmatic compromise for servers that only return text.)

**Delegation note (context, not a decision for this change).** FastMCP's own `ProxyProvider` (3.0.0+) handles all content-block types, `structuredContent`, and `isError` forwarding correctly — this is a live example of "the one piece of the proxy OneTool still hand-rolls has bugs the framework's equivalent doesn't." Delegating result-conversion to `ProxyProvider` wholesale is evaluated and explicitly deferred post-V3 (see "Own vs. Delegate — Deferred" below); D12/D13 fix the hand-rolled version to framework-equivalent correctness in the meantime.

### D14 — Evict stale proxy caches on restart/connect/disconnect

**Root cause.** Two independent caches key on server identity but neither is evicted on `restart`:
- `pack_proxy.py`'s namespace cache (`_namespace_cache`, keyed `(id(registry), frozenset(proxy_mgr.servers), configured_server_fingerprint)`, `:257-304` region) *does* change key when a server connects or disconnects (the `frozenset(proxy_mgr.servers)` membership changes), so a plain connect/disconnect correctly gets a fresh `McpProxyPack` with an empty `_function_cache`. But a **restart** (disconnect immediately followed by reconnect of the *same* server name) leaves the server-name set unchanged before and after — so the cache key is identical, and the *same* cached `McpProxyPack` (with its stale `_function_cache` mapping old accessor names → old tool names) is returned. After a downstream schema change, calls resolve to stale tool/param names silently.
- `param_resolver.py`'s `_mcp_param_cache` (keyed `(server_name, tool_name)`, `:36` region) is never cleared by *any* connect/disconnect/restart event — it is a purely time/size-bounded LRU (`_MCP_PARAM_CACHE_MAXSIZE = 256`), with no invalidation hook at all.
- `pack_proxy.reset()` (`:364-369`, clears `_namespace_cache`) is currently only called by `ot.reload()`, never by `ot_servers.enable`/`disable`/`restart` (`connect_additional`, `disconnect_server`, `reconnect` in `manager.py`).

**Decision.** Inside `ProxyManager.connect_additional`, `disconnect_server`, and `reconnect`, evict the affected server's entries from both caches:
- For the namespace cache: since the `McpProxyPack` object itself (not just the outer namespace dict) needs a fresh `_function_cache`, the cleanest fix is to evict/rebuild the specific server's `McpProxyPack` instance (not just bump the outer namespace cache key) — e.g. maintain per-server `McpProxyPack` instances in a dict keyed by server name (rather than relying solely on the outer namespace-cache key to force a rebuild), and drop/reconstruct that entry on connect/disconnect/reconnect for the affected server. (Implementer's choice on exact data structure; the observable requirement is: after a restart, calls resolve against the *current* tool list, not a stale one.)
- For `_mcp_param_cache`: on disconnect/restart of a server, remove all entries whose key's `server_name` matches; on connect, no eviction needed (a newly connected server has no stale entries by definition).

### D15 — Snapshot `_tools_by_server` under lock before iterating

**Root cause.** `ProxyManager.list_tools(server=None)` (`manager.py:159-163`) does a full-scan read — `[(srv, t) for srv, ts in self._tools_by_server.items() for t in ts]` — without holding `_mutation_lock`, while every *mutation* to `_tools_by_server` does take the lock. If a background connect adds a key to `_tools_by_server` on the event-loop thread while `list_tools(server=None)` is mid-iteration on a worker thread (reachable from `ot.tools()`/`ot.packs()`), Python raises `RuntimeError: dictionary changed size during iteration`.

**Decision.** Take `_mutation_lock` to snapshot `_tools_by_server` (e.g. `dict(self._tools_by_server)` or `list(self._tools_by_server.items())`) before building the `items` list, then release the lock and iterate the snapshot. This is a narrow, low-risk change (a lock held only long enough to copy a dict reference/shallow-copy, not for the full iteration).

### F3 — Regression test for `output_schema is None`

**Why this matters.** `run`'s return type annotation (`-> ToolResult`) is load-bearing: if it were changed to `-> str`/`-> dict`, FastMCP would auto-generate an `output_schema` for the tool. Because `run` always returns `structured_content=None` (by design — see Verified-Good Baseline), the lowlevel FastMCP handler's output-schema validation would then reject `structured_content=None` against a non-null schema and return `isError:true` on **every** call, breaking the tool completely. There is currently no test guarding this invariant.

**Decision.** Add a unit test asserting the registered `run` tool's `output_schema is None` (introspecting the FastMCP tool registration, e.g. via `mcp._tool_manager` or equivalent public/internal accessor already used elsewhere in the test suite for tool introspection), with a comment at the assertion site explaining *why* (referencing this exact failure mode) so a future contributor does not "fix" the annotation without understanding the consequence.

### F4 — `uvicorn.Config(log_config=None)`

**Root cause.** `src/ot/server.py:165-171`'s `uvicorn.Config` for the Direct API sets no `log_config`. On `uvicorn.Server.run()`, uvicorn's default `dictConfig` installs `uvicorn.access → StreamHandler(stdout)`, which would override the loguru `InterceptHandler` OneTool relies on for clean stdout. The Direct API shares the process (and file descriptor 1) with the stdio MCP transport — if the log level were ever lowered from the current `warning` (which currently suppresses access logs), uvicorn access lines would be written directly to stdout and corrupt the JSON-RPC stream. Latent today, not currently triggered.

**Decision.** Pass `log_config=None` to `uvicorn.Config` (loguru's `InterceptHandler` already covers uvicorn's loggers elsewhere in the codebase — verify this at implementation time and, if it does not, provide an explicit stderr-only/InterceptHandler-based config instead). Defensive fix; no observable behavior change at the current `warning` log level.

### Annotations — `destructiveHint: True`

**Decision.** `@mcp.tool(annotations={...})` for `run` (`server.py:531-536`) currently sets `"destructiveHint": False` on a meta-tool that can call `file.delete` (and anything else in the tool catalog). A client that gates a confirmation prompt on this hint would skip it for a genuinely destructive call. **Decision: change to `"destructiveHint": True`** — a single `run` surface that can do anything is, conservatively, destructive-capable; a false negative here (a client skips a confirmation it should have shown) is worse than a false positive (a client shows a confirmation for a harmless call). (`"title": "🧿"` is spec-valid and is *not* changed by this decision — it renders as a bare glyph in some tool-pickers, which is a cosmetic nit, not a compliance issue, and out of scope here.)

### R8 P2 — Bound the `otpack` memoize cache

**Root cause.** `packages/onetool-pack/src/otpack/cache.py:167`: `cache = Cache(max_size=0)` — the shared singleton is unbounded, and TTL eviction is lazy (only checked on same-key refetch; no background sweep). `src/otdev/tools/webfetch.py:130`, `@cache.memoize(ttl=300)` on `_fetch_url_cached`, memoizes full page HTML/markdown per distinct URL; because distinct URLs are rarely re-requested, bodies accumulate and stay resident for the process lifetime (a monotonically growing steady-state RSS leak, not just a webfetch-specific concern — the singleton is shared by `context7`, `ot_forge`, and `skills` too). `Cache` already implements LRU eviction internally (per the deep dive); it is simply never given a bound.

**Decision.** Set a finite `max_size` on the shared `Cache` singleton (`otpack/cache.py:167`) so LRU eviction actually engages once the cache is full. Exact bound is an implementation choice (pick something generous enough not to thrash normal usage, e.g. a few hundred to low-thousands of entries — the report does not mandate a specific number); document the chosen value and rationale at the call site. This is a global, cross-pack change (affects every consumer of the singleton), so verify webfetch/context7/skills tests still pass after bounding it.

## Own vs. Delegate — Deferred (context for future changes, not actioned here)

The proxy already proves the "delegate plumbing, own product" model: `src/ot/proxy/manager.py` delegates the entire MCP-client burden to FastMCP (`Client`, `StdioTransport`, `StreamableHttpTransport`, `BearerAuth`, `OAuth`) and OneTool owns only the product layer on top (Python namespaces, name aliasing, runtime control). D12/D13 are bugs in the *one* piece of the proxy OneTool still hand-rolls (result conversion) — a live example of the principle failing exactly where it wasn't applied. The following FastMCP-native capabilities were reviewed and are **explicitly not adopted in this change**:

| Feature | Status |
|---|---|
| Code Mode (meta-tools + Monty sandbox) | Not adopted — build-time framework feature, not an end-user product surface; OneTool already *is* the shipped product built on ingredients like this. Sandbox sub-component is V4-at-earliest and only if the threat model changes (sandboxing was deliberately dropped pre-V1 as complexity). |
| `@mcp.tool(run_in_thread=…)` + native tool timeouts | Not adopted — D3 uses hand-rolled `asyncio.to_thread` + a bounded timeout instead; re-evaluate replacing the primitive post-V3. |
| `ProxyProvider` (namespacing, correct multi-content-block/`structuredContent`/`isError` forwarding) | Not adopted — D12/D13 bring the hand-rolled equivalent to framework-parity correctness instead of a wholesale swap, because OneTool's proxy has custom naming/alias/`ot_servers` behavior `ProxyProvider` does not replicate. Evaluate post-V3. |
| OpenTelemetry tracing | Not adopted — roadmap observability bet, likely post-V3. |
| `fastmcp-slim` | Not adopted — packaging evaluation for the Direct CLI client, out of scope here. |
| `structuredContent` | Deliberately omitted (unchanged) — OneTool wants clients to show formatted text, not structured output; F3's test guards this. |
| FastMCP `Context` progress/logging | Not adopted — `ctx` remains accepted-but-unused in `run`'s signature; incremental adoption (progress reporting on long calls) is a future improvement, complementary to D3's timeout work. |
| Middleware | Not adopted — stats/logging/attribution stay inline in `run`; optional post-V3 cleanup. |

Re-check each of these at every FastMCP minor version bump; re-evaluate the whole-engine "Code Mode as `run`'s executor" move specifically once Code Mode reaches namespace/handle/format parity (or exposes extension hooks for them) and Monty proves stable in production.

## Implementation guardrails

- **No compatibility shims/aliases.** V3 is a breaking window. `resolve_kwargs`'s new ambiguity refusal, `run`'s `isError:true` contract change, and the tightened `TRIGGER_PATTERN` are all intentionally breaking for callers relying on the old (buggy) behavior — do not add a config flag or legacy code path to preserve the old silent-overwrite / always-`isError:false` / over-eager-redaction behavior.
- **No stubbing or TODO-deferral.** If a task in tasks.md cannot be completed as specified (e.g. a chosen NaN sentinel value turns out to break an existing test in a way that reveals a design gap), stop and report — do not comment out the assertion, weaken the test, or leave a `# TODO` in place of the fix.
- **Every code task ships with its test.** Unit tests for pure-function fixes (`_force_single_quotes`, `resolve_kwargs`, `serialize_result`, `TRIGGER_PATTERN`, cache eviction), integration tests for concurrency/timing-sensitive fixes (always-`to_thread` non-blocking behavior, sync-bridge same-loop guard). Use the existing markers (`@pytest.mark.unit`, `@pytest.mark.integration`, plus `@pytest.mark.tools` where a test exercises a real tool pack) per repo convention.
- **`just check` must pass before the change is considered complete** — this runs lint (ruff), strict mypy, and the full pytest suite.
- **Every `rg` command listed in tasks.md's Verification section that is expected to return empty MUST actually be run, and MUST actually return empty** — do not mark a task done because the code "looks right"; run the check.
- **Verify anchors before editing.** File:line references throughout this design were verified against `main`@`151a52b3` at design time (0 lines of drift found across every location checked). If a task's anchor does not match current code when you reach it (e.g. the repo has moved since design time), stop and re-locate the actual code by symbol name/grep rather than guessing — do not silently edit the wrong location.

## Risks / Trade-offs

- **[Risk] Always-`asyncio.to_thread` adds a thread-hop to every `run` call, even fast in-process tool calls that previously ran synchronously.** → Mitigation: `asyncio.to_thread` overhead is a single thread-pool dispatch (microseconds), negligible next to typical tool latencies (file I/O, network, subprocess calls); this is explicitly the trade the deep dive recommends ("always using `asyncio.to_thread` is both safe and correct... and makes the guard unnecessary"). Verify with the integration test that concurrent `run`/`ping` no longer stalls.
- **[Risk] `raise ToolError` is a breaking response-shape change for any existing client code that inspects `ToolResult.content` on failure rather than catching/branching on `isError`.** → Mitigation: this is the entire point of D2 (MCP-spec compliance) and is explicitly a V3 breaking-window change; the error text is preserved in the exception message so no information is lost, only the signaling channel changes.
- **[Risk] Tightening `TRIGGER_PATTERN`'s `__ot` matching could under-redact a genuine injection attempt shaped like `__ot .foo()` (space before the dot) or other unusual spacing.** → Mitigation: the existing `__onetool\b` and `mcp__onetool\w*` alternatives are unaffected and remain broad-matching (real injection payloads targeting OneTool specifically would very likely use the full `__onetool` or `mcp__onetool` form to be unambiguous); the lookahead-based fix for `__ot` is deliberately conservative (require immediate `.`/`(`, no intervening whitespace) — document this as an accepted trade-off (fewer false positives on prose, at the cost of not catching unusually-spaced `__ot` invocation attempts, which existing sanitization boundaries at other layers still constrain).
- **[Risk] Bounding the shared `otpack` memoize cache (R8 P2) affects every consumer of the singleton (webfetch, context7, ot_forge, skills), not just the one tool that motivated the fix.** → Mitigation: run the full test suite for all four consumers after the change; pick a generous bound so normal single-session usage does not thrash.
- **[Risk] D14's cache-eviction fix touches concurrency-sensitive proxy-manager code (`connect_additional`/`disconnect_server`/`reconnect`), which already has a `_mutation_lock`.** → Mitigation: perform cache eviction for the affected server *inside* the existing locked sections (or immediately adjacent, consistent with how `_tools_by_server`/`_errors`/etc. are already mutated under the lock in `disconnect_server`), not as an unsynchronized side effect.

## Migration Plan

No data migration. This is a behavior/bug-fix change to in-process code paths; deploy as a normal release. No feature flag — all fixes are unconditional corrections to existing, already-broken behavior (per the V3 no-backcompat-shim rule). Rollback is a normal revert if `just check` or post-deploy smoke testing surfaces a regression.

## Open Questions

- **Exact NaN/Infinity JSON sentinel** (D9): the design mandates `allow_nan=False` plus a substitution on the resulting `ValueError`, but does not mandate whether the substitution is `null` or a string marker (`"NaN"`/`"Infinity"`) — implementer's choice; pick one, document it at the call site and in the task's regression test.
- **Exact `otpack` cache `max_size`** (R8 P2): no specific number is mandated; implementer picks a generous bound and documents the rationale.
- **Per-tool timeout duration** (D3): no specific number is mandated by the source material; implementer should pick a value consistent with the longest legitimate existing tool call observed elsewhere in the codebase (e.g. the `webfetch` 30s figure cited in D3's own freeze description is a reasonable floor) and document the choice.
