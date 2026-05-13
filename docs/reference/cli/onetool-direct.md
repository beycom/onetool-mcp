# onetool direct

Run tools through an already-running OneTool MCP process.

```bash
onetool direct [OPTIONS] COMMAND [ARGS]...
```

---

## onetool direct run

Execute a command through an already-running OneTool MCP process.

```bash
onetool direct run --port PORT [OPTIONS] [COMMAND]
```

`direct run` is a signed local HTTP client for the MCP-owned direct API.

**Arguments:**

- `COMMAND` — tool call to execute, such as `"ot.version()"`
- `-` — read command text from stdin
- existing `.py` path — read file contents and execute them

**Options:**

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--port PORT` | `-p` | required | Target MCP direct API port |
| `--ot-dir PATH` | | `~/.onetool` | Absolute OneTool directory containing `mcp-direct/auth.key` |
| `--format MODE` | `-f` | `json_h` | `json_h`, `json`, `yml`, `yml_h`, or `raw` |
| `--sanitize` | | false | Enable output sanitization |
| `--timeout N` | `-t` | `120` | Direct API request timeout in seconds |

**Examples:**

```bash
onetool direct run --port 8765 "ot.version()"
onetool direct run --port 8765 --ot-dir ~/.onetool "ot.version()"
echo "ot.version()" | onetool direct run --port 8765 -
onetool direct run --port 8765 report.py
onetool direct run --port 8765 "brave.search(query='AI')" --format json
onetool direct run --port 8765 "ot_llm.transform(data='...', prompt='summarise')" --timeout 120
```

The MCP process must have `direct.host.enabled: true`. MCP startup logs the
bound URL, for example `http://127.0.0.1:8765`.

`--ot-dir` must be absolute after `~` expansion. It selects the client-side
OneTool directory used for direct API auth and does not load OneTool config.

Use MCP-side tools such as `ot.help()`, `ot.tools()`, and `ot.servers()` through
`direct run` for discovery and status checks:

```bash
onetool direct run --port 8765 "ot.help(query='web search')" --format raw
onetool direct run --port 8765 "ot.tools()" --format json
onetool direct run --port 8765 "ot.servers()" --format json
```

**Exit codes:**

- `0` — command succeeded
- `1` — direct API, authentication, protocol, timeout, connection, or command failure
- `2` — argument error
