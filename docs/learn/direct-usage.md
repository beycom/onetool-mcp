# Direct Usage Guide

`onetool direct` lets shell scripts and agent harnesses run OneTool commands
without speaking MCP directly.

`direct run` is a secure bridge into an already-running OneTool MCP process. The
MCP process owns the config, secrets, proxy connections, registry, state, and
stats behavior. The CLI only signs a local HTTP request and prints the result.

---

## Enable The Direct API

Enable the MCP-owned direct API in `onetool.yaml`:

```yaml
direct:
  host:
    enabled: true
    port: 8765
```

Start OneTool as an MCP server. Startup logs include the bound direct API URL.
If the preferred port is occupied, MCP startup tries the next port.

---

## Run Commands

Use the bound port explicitly:

```bash
onetool direct run --port 8765 "ot.version()"
onetool direct run --port 8765 "brave.search(query='latest AI news')" --format raw
onetool direct run --port 8765 "ot.packs()" --format json | jq '.[0].name'
```

`--port` is required and selects the target MCP process.

**Format options** (`--format` / `-f`):

```bash
onetool direct run --port 8765 "ot.packs()"              # json_h
onetool direct run --port 8765 "ot.packs()" --format json
onetool direct run --port 8765 "ot.version()" --format raw
onetool direct run --port 8765 "ot.packs()" --format yml
```

**Multi-line scripts** from a `.py` file or stdin:

```bash
onetool direct run --port 8765 report.py
echo "ot.version()" | onetool direct run --port 8765 -
```

## Multiple MCP Processes

Run each MCP process with a distinct bound direct API port, then choose the
target explicitly:

```bash
onetool direct run --port 8765 "ot.version()"
onetool direct run --port 9000 "ot.version()"
```

The selected MCP process determines which config, secrets, tools, proxy
connections, state, and stats writer are used.

Direct API bodies are consumed incrementally before authentication. `run`
accepts at most 1,000,000 bytes; health, readiness, and Console outbox requests
accept at most 65,536 bytes. Oversized bodies receive a signed HTTP `413`
without executing commands or reading readiness/outbox state.

---

## Discovering Tools

Discovery and server status run inside the selected MCP process:

```bash
onetool direct run --port 8765 "ot.help(query='web search')" --format raw
onetool direct run --port 8765 "ot.tools(pattern='brave')" --format json
onetool direct run --port 8765 "ot.tool_info(name='brave.search')" --format raw
onetool direct run --port 8765 "ot.servers()" --format json
```

The target MCP process determines which config, tools, snippets, aliases, and
proxy servers are visible.

---

## Agent Scripting

Use `--format json` plus exit codes for automation:

```bash
RESULT=$(onetool direct run --port 8765 "ot.packs()" --format json 2>/dev/null)
if [ $? -eq 0 ]; then
    echo "$RESULT" | jq '.[0].name'
fi

onetool direct run --port 8765 "brave.search(query='AI')" --format raw 2>/dev/null | head -5
onetool direct run --port 8765 "webfetch.fetch(url='https://en.wikipedia.org/wiki/Anthropic')" --sanitize --format raw
```

Exit codes:

- `0` — command succeeded
- `1` — direct API, authentication, protocol, timeout, connection, or command failure
- `2` — argument error
