# OneTool Recovery & Advanced Reference

Deep-dive companion to the ot-ref skill body. Pull sections as needed.

## Fast recovery (fail-first)

1. Execute the requested `pack.tool(...)` call.
2. If it fails, inspect once with `ot.tool_info(name='pack.tool')`.
3. If the tool is unknown/missing, check `ot.tools(pattern='name')` or `ot.packs(pattern='name')`.
4. If still unclear, run `ot.help(query='topic')`.
5. Retry once with corrected kwargs. Do not guess beyond one retry.

Close-call recovery:

- If a call is syntactically valid but may have wrong args, calling first is OK; repair from the
  error plus `ot.tool_info`.
- If the input is natural language or invalid Python, inspect/synthesize instead of sending code
  that can only fail syntax validation.
- For readable discovery output: `__format__ = 'yml_h'; ot.help(query='topic')`.

## Param prefixes

- An exact param match always wins.
- Otherwise any signature/schema param starting with the provided key can match.
- A prefix that matches multiple params, or collides with another provided kwarg, raises an
  ambiguity error instead of silently binding — use longer keys when ambiguity matters.

## Proxy server recovery

- Known disconnected server: `ot_servers.enable(name='playwright')`, then retry once.
- Unknown server name/status: `ot.servers()` first, then enable.
- Restart a misbehaving server: `ot_servers.restart(name='...')`; inspect with
  `ot_servers.status(name='...')`.
- Discovery stays read-only in `ot.*`; state changes live in `ot_servers.*`.

## Security boundaries

- Python glue is allowed (variables, dict/list transforms, last-expression returns).
- Arbitrary imports are blocked; use pack tools instead.
- Check policy: `ot.security()` or `ot.security(check='json')`.
- OneTool is not a sandbox: the boundary is your process/user isolation. Do not feed untrusted
  content into commands.

## Decision boundary: `run` vs local Python

Use `run` for:

- Direct `pack.tool(...)` calls.
- Short composition around tool calls (small variable prep, one-pass mapping, final expression return).
- Discovery and recovery flows (`ot.help`, `ot.tool_info`, `ot_servers.enable`).

Use local Python files for:

- Standard file manipulation or ETL-style transforms.
- Large inline datasets (long row lists, embedded workbook payloads).
- Multi-step remapping/normalization logic that should be reviewed in git.
- Reusable generation pipelines (scenario builders, workbook assemblers).

Tie-break: if most of the code is custom manipulation and only a small part is tool invocation,
move it to local Python and keep `run` calls thin and tool-centric.

## Output controls

```python
__format__ = 'yml_h'; ot.help(query='search')
```

Runtime dunders:

- `__format__`: result serialization format (`json`, `json_h`, `yml`, `yml_h`, `raw`).
- `__sanitize__`: toggles output sanitization (default from config). IMPORTANT: use `False` only
  when you explicitly need raw output and trust the source.
- `__force_context__`: forces the result to be stored and returned as a handle.

## Large-result handles

Large results return a handle dict:

```python
{'handle': 'b2d18a1b', ...}
```

Always pass the string handle, not the dict:

```python
h = ot.tool_info(pattern='figma')
ot.result(handle=h['handle'], search='page')
```

`ot.result` is available on every install:

- `ot.result(handle=..., offset=1, limit=100)`: paginated lines.
- `ot.result(handle=..., search='error', context=2)`: regex filter with context.
- `ot.result(handle=..., tail=50)`: last N lines.

With the `[util]` extra installed, the `ctx` pack adds richer, format-aware navigation:

- `ctx.toc(handle=...)`: first-pass map of sections.
- `ctx.read(handle=..., offset=1, limit=50)`: paginated raw lines.
- `ctx.slice(handle=..., select='10:50')`: exact line range.
- `ctx.grep(handle=..., pattern='error')`: targeted search before asking.
- `ctx.query(handle=..., expr='key.path')`: structured JSON/YAML access.
- `ctx.ask(handle=..., q='What changed?')`: summarize or answer questions from stored content.
