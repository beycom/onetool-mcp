# Narrator MCP server

A trivial macOS `say`-wrapping stdio MCP server used to narrate the OneTool demos. It is itself a
demonstration of the [MCP proxy story](../../mcp-proxy.md): a stdio server registered under
`servers:` becomes a callable Python namespace (`narrator.speak(text=...)`) with no OneTool-side
code changes.

**macOS only.** `say` ships with macOS; on other platforms `narrator.speak(...)` returns a no-op
message instead of speaking, so the substantive (tool-call) portion of each demo still runs.

## Register it

```yaml
# In onetool.yaml
servers:
  narrator:
    type: stdio
    command: python
    args: ["docs/learn/demos/narrator/say_server.py"]
```

## Smoke test

With the OneTool server running and `direct.host.enabled: true`:

```bash
onetool direct run --port 8765 "narrator.speak(text='OneTool online')"
```

Expect exit code `0` (and, on macOS, spoken audio).
