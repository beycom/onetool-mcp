# Direct Usage Guide

!!! tip "New in v2.2.1"
    `onetool direct` was introduced in v2.2.1 as a first-class CLI execution mode for agent harnesses, scripts, and automation.

The `onetool direct` subcommand group lets you run tools directly from the shell without an AI model in the loop. Useful for scripts, automation, and interactive exploration.

---

## Why direct?

In 2026, a growing class of agent harnesses — Claude Code, Codex CLI, Gemini CLI — call tools via subprocess or HTTP rather than MCP. These systems benefit from a stable, low-overhead CLI contract with structured JSON output and no server lifecycle to manage. `onetool direct` is that contract.

| | MCP (via Claude/Cursor) | onetool direct |
|---|---|---|
| **Who invokes it** | AI host via MCP tool call | Shell, script, or agent subprocess |
| **Tool definition tokens** | ~2K per session | Zero — no schema loaded |
| **State across calls** | Stateless | In-process or execution host |
| **Output format** | MCP content blocks | JSON, YAML, or raw |
| **Best for** | Interactive AI sessions | Automation, pipelines, agent harnesses |

**Same call, two ways:**

```bash
# Via MCP (agent writes this inside an MCP session):
>>> brave.search(query='react docs 2026')

# Via onetool direct (agent calls as subprocess — no MCP client needed):
onetool direct run "brave.search(query='react docs 2026')" --format raw
```

---

## In-process execution (no server)

The simplest mode: load config, execute one tool call, print the result, exit. Packs are initialised fresh on every invocation — suitable for one-off calls.

```bash
onetool direct run --config .onetool/onetool.yaml "ot.debug()"
onetool direct run --config .onetool/onetool.yaml "ot.version()"
onetool direct run --config .onetool/onetool.yaml "brave.search(query='latest AI news')"
```

**Format options** (`--format` / `-f`):

```bash
# Default: human-readable JSON
onetool direct run --config onetool.yaml "ot.packs()"

# Compact JSON (for parsing in scripts)
onetool direct run --config onetool.yaml "ot.packs()" --format json

# Raw string (no serialisation)
onetool direct run --config onetool.yaml "ot.version()" --format raw

# YAML
onetool direct run --config onetool.yaml "ot.packs()" --format yml
```

**Multi-line scripts** from a `.py` file or stdin:

```bash
onetool direct run --config onetool.yaml report.py
echo "ot.version()" | onetool direct run --config onetool.yaml -
```

---

## Execution host (persistent state)

**Why use host mode?**

| | In-process | Execution host |
|---|---|---|
| **Performance** | Packs re-initialised on every call | Loaded once at startup — negligible per-call overhead |
| **State persistence** | Starts fresh each call | Module-level state survives (whiteboard canvas, DB connections, caches) |
| **Config** | `--config` required every call | Host owns the config; callers can omit `--config` after host start (pass it when you want run-time context sync) |
| **Best for** | One-off calls | AI agents, scripts making many sequential calls |

**When NOT to use host mode:** one-off calls (in-process is simpler), or environments where a persistent background process is undesirable (CI, containers).

`direct.host.enabled` defaults to `false` in `onetool.yaml`, so direct commands run in-process by default. Set `direct.host.enabled: true` to enable host optimization on first use.

---

Starting an execution host keeps tool state alive between calls — tool packs stay loaded and module-level state (e.g. whiteboard sessions) persists across multiple `direct run` invocations.

Secrets resolution for direct commands uses this precedence:
1. `--secrets`
2. `OT_SECRETS_FILE`
3. `<config_dir>/secrets.yaml` (when present)

When `direct run` routes to local host and detects host context mismatch (config/secrets) against the current call, it automatically restarts the host to sync context before execution.

```bash
# Start the execution host (blocks until ready, then exits)
onetool direct start --config .onetool/onetool.yaml --secrets .onetool/secrets.yaml

# Confirm it's running
onetool direct status

# Run tools — no --config needed (routes to host automatically)
onetool direct run "wb.draw(dsl='box A')"
onetool direct run "wb.draw(dsl='box B; A -> B')"   # board state persists!

# Check the logs if something looks wrong
onetool direct logs

# Restart after config changes
onetool direct restart

# Stop
onetool direct stop
```

`direct start` blocks until the host is accepting connections (up to 5 seconds), so the next command is always safe to run immediately after.

**Multiple hosts** on different ports:

```bash
onetool direct start --config project-a.yaml --secrets project-a-secrets.yaml            # port 8765
onetool direct start --config project-b.yaml --secrets project-b-secrets.yaml --port 9000

onetool direct status --port 8765
onetool direct status --port 9000

onetool direct stop --port 9000
```

---

## Interactive REPL

The REPL runs in-process — great for exploration and multi-step workflows.

```bash
onetool direct repl --config .onetool/onetool.yaml
```

```
OneTool REPL — type :quit or press Ctrl+D to exit
>>> brave.search(query='AI news 2026')
{"results": [...]}
>>> for r in _:
...     print(r['title'])
...
AI Safety Update — April 2026
...
>>> :quit
```

**Key bindings:**

| Action | Key |
|--------|-----|
| Submit line | Enter |
| Tab complete | Tab |
| Previous command | ↑ |
| Next command | ↓ |
| Cancel current input | Ctrl+C |
| Exit | Ctrl+D or `:quit` |

**Multi-line input:** open brackets or block statements (`for x in y:`) show a `... ` continuation prompt. An empty line submits a block.

**Help:** type `:help` to list available packs and tools.

---

## Discovering tools

```bash
# List all tools (one per line, pipe-friendly)
onetool direct list
onetool direct list brave
onetool direct list | fzf              # interactive picker

# Full signatures
onetool direct list --info full

# Search by intent
onetool direct search "web search"
onetool direct search "convert pdf"

# Detailed help for a specific tool
onetool direct help brave.search
onetool direct help "web search"       # fuzzy match
```

---

## Agent scripting

Use `--format json` + exit codes for reliable automation:

```bash
# Run a tool that returns a dict/list and capture the JSON output
RESULT=$(onetool direct run "ot.packs()" --format json 2>/dev/null)
if [ $? -eq 0 ]; then
    echo "$RESULT" | jq '.[0].name'
fi

# For string-returning tools (search, fetch), use --format raw and process as plain text:
onetool direct run "brave.search(query='AI')" --format raw 2>/dev/null | head -5

# Feed tool output to an AI pipeline (enable sanitization)
onetool direct run --config onetool.yaml "webfetch.fetch(url='...')" --sanitize --format raw | ai-pipeline
```

!!! note "`--format json` and jq"
    `--format json` only serialises `dict`/`list` return values. String-returning tools (most search and fetch tools) pass through unchanged regardless of format. Use tools like `ot.packs()`, `ot.stats()`, or `db.query()` when piping to `jq`. For string results, use `--format raw` and process as plain text.

**For AI agents calling onetool direct:**

1. Start the execution host once: `onetool direct start --config onetool.yaml --secrets secrets.yaml`
2. Run tools without `--config` (host handles state): `onetool direct run "pack.tool(...)"`
3. Use `--format json` for machine-readable results
4. Exit code 0 = success, 1 = tool error, 2 = config error
