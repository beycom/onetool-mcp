# Python through CodeMode

OneTool exposes FastMCP's native `search`, `get_schema` and `execute`. Clients may add their own prefix to those MCP names. Use the names and schemas the client advertises.

## Find and inspect tools

The following MCP requests use the repository fixtures:

```json
{"tool":"search","arguments":{"query":"add"}}
```

```json
{"tool":"get_schema","arguments":{"tools":["alpha_add","beta_add"]}}
```

Search returns exact callable names. If a server's tools are missing from search, check `onetool_status`: unavailable servers contribute no tools, while healthy servers remain usable.

## Execute a chain

Pass Python in the `code` argument to `execute`. Only `call_tool(name, arguments)` is available as a tool-call function. Use `await` and select the final value with `return`.

```python
values = []
for number in [1, 2, 3]:
    if number > 1:
        item = await call_tool("alpha_add", {"a": number, "b": 10})
        values.append(item["value"])
return {"values": values}
```

The result is `{"values": [12, 13]}`. Intermediate tool results remain inside the sandbox. Python variables are fresh on the next execution. A stateful upstream connection can persist across executions until shutdown, restart, reload or connection loss.

## Supported behavior

Loops, conditionals, lists, dictionaries, ordinary expressions and tool chaining are tested. Monty is a sandbox, not unrestricted CPython. A subprocess import fails. Some standard-library functions have virtual implementations, so do not assume every import fails or provides host filesystem access. Read the [upstream CodeMode documentation](https://gofastmcp.com/docs/servers/transforms/code-mode) for its evolving subset.

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

Read the file with your client's own file tools. The directory and files are owner-only. Individual results over 16 MiB are not retained. The directory keeps at most 256 MiB and evicts oldest files first; orderly shutdown removes it. A crash can leave temp files for OS cleanup.

This bounds final output, not the memory used to receive an upstream result. See the [measured memory limitation](troubleshooting.md#large-responses-and-memory).
