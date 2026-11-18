# Python through CodeMode

OneTool exposes FastMCP's native `search`, `get_schema` and `execute`, plus OneTool `help`. Clients may add their own prefix to those MCP names. Use the names and schemas the client advertises.

## Find and inspect tools

Start with `help()` for the server overview. An exact tool name shows its signature and description; an exact server shows state, instructions and observed tools. Other queries return grouped server/tool matches, with close spellings for discovery only. Detail levels are `names`, `default`, `signatures` and `full`. Help never calls a business tool or connects a lazy/disabled server. Enable a lazy server explicitly or use search to discover it.

The following MCP requests use the repository fixtures:

```json
{"tool":"search","arguments":{"query":"add"}}
```

```json
{"tool":"get_schema","arguments":{"tools":["alpha_add","beta_add"]}}
```

Search returns exact callable names. If a server's tools are missing from search, check `onetool_status`: unavailable servers contribute no tools, while healthy servers remain usable.

## Execute a chain

Pass Python in the `code` argument to `execute`. Use `await server.tool(**kwargs)` with exact advertised names. `call_tool(name, arguments)` remains available for every tool, including names that Python cannot spell. Use keyword arguments with dot calls. Select the final value with `return`, or end the submission with an expression.

```python
values = []
for number in [1, 2, 3]:
    if number > 1:
        item = await alpha.add(a=number, b=10)
        values.append(item["value"])
return {"values": values}
```

The result is `{"values": [12, 13]}`. Surrounding python/py/plain Markdown fences and common indentation are accepted. Source line numbers retain the submitted layout. Empty code is an error. Unknown names/parameters suggest exact spellings without dispatching those suggestions. Intermediate tool results remain inside the sandbox. Python variables are fresh on the next execution. A stateful upstream connection can persist across executions until shutdown, restart, reload or connection loss.

## Supported behavior

Loops, conditionals, lists, dictionaries, ordinary expressions and tool chaining are tested. Monty is a sandbox, not unrestricted CPython. Generators/yield are unsupported. A final expression returns its value; an expression inside a branch is not a final top-level expression. Explicit `None` and a block without a selected value both produce native empty output. A subprocess import fails. Some standard-library functions have virtual implementations, so do not assume every import fails or provides host filesystem access. Read the [upstream CodeMode documentation](https://gofastmcp.com/docs/servers/transforms/code-mode) for its evolving subset.

Native projection follows the upstream tool's schema. A dictionary with an output schema stays a dictionary. A schema-backed string or number can arrive in a `result` dictionary. Plain text without an output schema remains a string, including `007`:

```python
value = await call_tool("alpha_echo", {"value": "007"})
return {"literal": value}
```

Tool failures interrupt the chain and remain errors. Image content currently becomes a string representation with base64 inside Python. Connect image-heavy tools directly to the client. OneTool adds no image adapter. Resources and prompts use native MCP methods rather than Python tool aliases.

Two concurrent executions have separate progress callbacks in the fixture proof. Sampling, elicitation and roots use upstream proxy handling; those callback families are not claimed tested inside Python here.

## Deadlines and uncertain outcomes

The execution timeout includes the entire chain. Backend calls cannot extend it by starting another timeout. CPU-bound loops and pending I/O are cancelled when their limits expire. A later request can still run.

Cancellation or a lost transport after dispatch leaves that call's outcome unknown. Never replay automatically, including operations that appear read-only. Resolve an uncertain write by checking the target's state or asking its owner. Explicitly starting a later operation can reconnect a failed upstream.

## Large output

At or below the inline cap, the selected result returns inline. Larger output becomes a UTF-8 JSON file. The response has a local path, exact bytes, SHA-256, preview and a no-repeat message. Errors retain their error status.

The receipt also contains an opaque process-local handle. Use `onetool_results(action="read", handle=...)` without file access, or the `results` namespace in Python. Your client's file tools can also read the path. The directory and files are owner-only. Individual results over 16 MiB are not retained. The directory keeps at most 256 MiB and evicts oldest files first; orderly shutdown removes it. A crash can leave temp files for OS cleanup.

This bounds final output, not the memory used to receive an upstream result. See the [measured memory limitation](troubleshooting.md#large-responses-and-memory).

## Exact namespaces

Namespaces are built afresh from the execution's catalog and assigned by the longest configured server prefix. No fuzzy names, aliases or argument abbreviations route calls. Tools whose upstream names are not Python identifiers, are keywords, or start with an underscore, are callable only with exact `call_tool` names, such as `alpha_odd-tool`. Builtins and local variables shadow namespaces: a server named `len` uses `call_tool`; assigning `alpha = ...` hides that namespace for the submission. Server names cannot equal `call_tool`, `call_tools`, `set_format` or `results`.

## Printed output and formatting

Sandbox `print()` is captured per execution and returned with the selected value. Prints never go to gateway stderr or logs, even when they look like JSON-RPC. Earlier prints survive an error, which remains an error. Capture is bounded by the inline cap; dropped output has a visible truncation notice. Prints and the final value together use the normal result-file path when oversized.

Choose the final text rendering with `set_format`: `json` (default), `json-indent`, `yaml` (flow), `yaml-block` or `text`. A literal invalid format is rejected before statements run; computed values validate when passed. This changes inline text only; structured content and retained files keep the native value. Non-finite or unsupported final values degrade to strings, without unsafe YAML tags.

```python
set_format("yaml-block")
print("Selected answer:")
return await alpha.add(a=2, b=3)
```

## Bounded batches

`await call_tools(calls, concurrency=4)` accepts a list of `(exact_name, arguments)` pairs or mappings with `tool` and `arguments`. The complete shape is checked before dispatch. Concurrency is an integer from 1 to 16. Results retain input order: each has `index`, `tool`, `status`, and `value` or `error`. Status is `ok`, `error`, `cancelled` for an undispatched item, or `unknown` for an interrupted dispatched item. Successful items survive other failures. Never replay an unknown item automatically.

```python
return await call_tools([
    ("alpha_add", {"a": 2, "b": 3}),
    ("beta_add", {"a": 4, "b": 5}),
], concurrency=2)
```

`execution.max_tool_calls` defaults to 50 and accepts 1 through 1,000. Dot calls, native calls and batches share that budget and the execution deadline; remaining batch items are cancelled without dispatch. Client cancellation and shutdown still propagate. An empty batch makes no business call. Native `asyncio.gather` also overlaps calls; wrap each call in its own try/except for partial successes because Monty does not support `return_exceptions=True`.

## Result handles

Use `await results.write(value, source="label")` to force-store even a small value. Later executions and the `onetool_results` admin tool share the same store. No arbitrary paths are accepted. Handles expire on process exit; 4,096 live handles and 1,024 recent tombstones are retained within the 256 MiB cap, oldest first. Recent deleted/evicted handles have distinct errors; older handles say "unknown handle (expired or never issued)".

```python
saved = await results.write({"items": [{"name": "first", "count": 2}]}, source="fixture")
return await results.query(saved["handle"], expression="items[0].count")
```

Actions are `write`, `read`, `grep`, `slice`, `toc`, `query`, `append`, `list`, `inspect`, `delete` and `purge`, with the same names inside `results`. Read uses zero-based `offset`, `limit=100` up to 500, and optional `tail=true`. Lines longer than 500 characters carry `[+N chars]`. Grep is case-insensitive by default, supports `context` up to 50 and at most 500 matched lines; output also fits the inline cap. Patterns are at most 1 KiB, run off the event loop and time out after one second by default. Timeout errors reveal no pattern or content. Query/grep use one store worker at a time. Cancelling the caller returns promptly; the next search waits for that worker to finish. Amplified answers are bounded before serialization/copying, and stored answers over16MiB are not retained.

Slice accepts `select="1:10"` (one-based inclusive lines), `"#2"` (Markdown section number) or a heading substring. TOC reports Markdown sections or structured key/type/size information. Query accepts JMESPath expressions up to 4 KiB on typed JSON/YAML values; arbitrary tool text is never guessed to be JSON. Explicit writes detect JSON, YAML mappings/lists, Markdown or text once when stored. Append preserves the handle; inspect retains the original error flag. These operations never rerun an upstream call. Responses that cannot fit return a bounded preview and truncation notice.

## Measured imports

`onetool_status(check="json")` probes one module; ordinary status lazily probes the standard set and caches results for this process. Working in Monty 1.6.0: json, re, datetime, csv, collections, itertools, math, base64, hashlib, functools, typing, dataclasses, decimal, random, time, copy, bisect and asyncio. Missing: statistics, difflib, textwrap, html, urllib.parse, uuid, operator, string, zoneinfo, heapq, enum and fractions. Ask status on your installed version rather than assuming CPython's modules are available.

## Preflight validation

Execute checks statically known dot calls and literal `call_tool` names/argument keys against its fresh collision-checked catalog before the first business call. A typo in the third static call stops the whole submission before the first call. Diagnostics name the line/column and exact suggestions. Computed names/argument dictionaries and locally shadowed namespaces remain unresolved; normal dispatch validates them when reached. Open argument schemas remain upstream-owned. Native Monty parses execution syntax; no source wrapper or name rewriting is used.

Use the separate `check` discovery tool for an advisory inspection:

```json
{"tool":"check","arguments":{"code":"return await alpha.add(a=2,b=3)"}}
```

Check uses only already-observed catalogs, reports their ages and unknown servers, and never refreshes a connection or runs statements, imports or loops. Its syntax checks are provisional CPython AST checks. Monty's public type checker rejects CodeMode's valid top-level return, and there is no public parse-only entrypoint, so native Monty remains authoritative during execute. `valid` covers only the checks possible with that cached information; warnings/unknown schemas still matter, and it never guarantees a later request succeeds. Diagnostics respect the inline cap and contain no logged source.
