---
name: ot-ref
description: Optional OneTool advanced reference — recovery loops, proxy handling, security, ctx traps
tags: [reference, cheatsheet]
---

# OneTool Advanced Reference

`ot-ref` is optional. Base run instructions are sufficient for normal OneTool use.

## Fast Recovery (fail-first)

1. Execute requested `pack.tool(...)` call.
2. If it fails, inspect once with `ot.tool_info(name='pack.tool')`.
3. If unknown/missing tool, check `ot.tools(pattern='name')` or `ot.packs(pattern='name')`.
4. If still unclear, run `ot.help(query='topic')`.
5. Retry once with corrected kwargs. Do not guess beyond one retry.

## Proxy Server Recovery

- Known disconnected server: `ot_servers.enable(name='github')` then retry once.
- Unknown server name/status: `ot.servers()` first, then enable.
- Discovery stays read-only in `ot.*`; state changes are in `ot_servers.*`.

## Security Boundaries

- Python glue is allowed (variables, dict/list transforms, last-expression returns).
- Arbitrary imports are blocked; use pack tools instead.
- Check policy: `ot.security()` or `ot.security(check='json')`.

## Decision Boundary: `run` vs Local Python

Use `run` for:
- Direct `pack.tool(...)` calls
- Short composition around tool calls (small variable prep, one-pass mapping, final expression return)
- Discovery and recovery flows (`ot.help`, `ot.tool_info`, `ot_servers.enable`)

Use local Python files for:
- Standard file manipulation or ETL-style transforms
- Large inline datasets (long row lists, embedded workbook payloads)
- Multi-step remapping/normalization logic that should be reviewed in git
- Reusable generation pipelines (scenario builders, workbook assemblers)

Tie-break rule:
- If most of the code is custom manipulation and only a small part is tool invocation, move it to local Python and keep `run` calls thin/tool-centric.

## Output Controls

```python
__format__ = 'yml_h'; ot.help(query='search')
```

Supported `__format__` values: `json`, `json_h`, `yml`, `yml_h`, `raw`.

Runtime dunders:
- `__format__`: controls result serialization format (`json`, `json_h`, `yml`, `yml_h`, `raw`).
- `__sanitize__`: toggles output sanitization (default from config). IMPORTANT use `False` only when you explicitly need raw output and trust the source.
- `__compact__`: compacts final serialized output (default from config).
- `__force_context__`: forces result to be stored in ctx and returned as a handle.

## ctx Handle Trap + Navigation Hints

Large results may return:
```python
{'handle': 'b2d18a1b', ...}
```

Always pass the string handle, not the dict:
```python
h = ot.tool_info(pattern='figma')
ctx.grep(handle=h['handle'], pattern='page')
```

Quick context flow:
- `ctx.toc(handle=...)`: first pass map of sections.
- `ctx.read(handle=..., offset=1, limit=50)`: paginated raw lines.
- `ctx.slice(handle=..., select='10:50')`: pull exact line range.
- `ctx.grep(handle=..., pattern='error')`: targeted search before asking.
- `ctx.query(handle=..., expr='key.path')`: structured JSON/YAML access.
- `ctx.ask(handle=..., q='What changed?')`: summarize or answer questions from stored content.
