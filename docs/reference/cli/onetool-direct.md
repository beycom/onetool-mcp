# onetool direct

Run tools from the shell, manage the execution server, or launch the interactive REPL.

```
onetool direct [OPTIONS] COMMAND [ARGS]...
```

---

## onetool direct run

Execute a tool command from the shell.

```
onetool direct run [OPTIONS] [COMMAND]
```

**Arguments:**

- `COMMAND` — tool call to execute (e.g. `"ot.debug()"`). Omit to use stdin.
  - Pass `-` to read the command from stdin
  - Pass a path to an existing `.py` file to read and execute its contents

**Options:**

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--config PATH` | `-c` | — | Path to `onetool.yaml`; required for in-process execution |
| `--secrets PATH` | `-s` | — | Path to secrets file |
| `--format MODE` | `-f` | `json_h` | Output format: `json_h`, `json`, `yml`, `yml_h`, `raw` |
| `--no-host` | | false | Skip server routing; always run in-process (requires --config) |
| `--sanitize` | | false | Enable output sanitization (for AI pipeline use) |
| `--timeout N` | `-t` | from config | Server request timeout in seconds (overrides `direct.host.timeout`) |

**Output formats:**

| Mode | Description |
|------|-------------|
| `json_h` | Human-readable JSON with 2-space indent (default) |
| `json` | Compact JSON (no whitespace) |
| `yml` | YAML |
| `yml_h` | Human-readable YAML |
| `raw` | Raw result string with no serialisation |

Format is injected into the execution namespace as `__format__`. Exit code communicates success (0) or failure (1). No envelope wrapper.

**Secrets resolution:** direct commands resolve secrets in this order:
1. `--secrets PATH`
2. `OT_SECRETS_FILE` environment variable
3. `<config_dir>/secrets.yaml` (when `--config` is provided and the file exists)

**Server routing:** without `--no-host`, `direct run` probes for a running execution server and routes to it if found. Falls back to in-process when none is detected. When `--config` is provided, `direct.host.enabled: true` enables auto-start if no server is running. When routing to local host (`127.0.0.1`), if the running host context (config/secrets) does not match the current run context, the host is restarted automatically to sync context before command execution.

**Exit codes:**

- `0` — success
- `1` — tool execution error or server error
- `2` — config/argument error

**Examples:**

```bash
onetool direct run --config .onetool/onetool.yaml "ot.debug()"
echo "ot.version()" | onetool direct run --config .onetool/onetool.yaml -
onetool direct run --config .onetool/onetool.yaml report.py
onetool direct run --config .onetool/onetool.yaml "brave.search(query='AI')" --format json
onetool direct run "ot.version()"            # routes to server if running
onetool direct run --no-host --config .onetool/onetool.yaml "ot.version()"
onetool direct run "ot_llm.transform(data='...', prompt='summarise')" --timeout 120
```

---

## onetool direct repl

Launch an interactive REPL for tool execution with persistent in-process state.

```
onetool direct repl [OPTIONS]
```

**Options:**

| Flag | Short | Description |
|------|-------|-------------|
| `--config PATH` | `-c` | Path to `onetool.yaml` (required) |
| `--secrets PATH` | `-s` | Path to secrets file |

**Features:**

- Prompt: `>>> ` (continuation: `... `)
- Tab completion on `pack.tool` names, `:quit`, `exit()`, `quit()`, `:help`
- Up/down arrow history, persisted to `~/.onetool/repl_history` (1000 entries)
- Multi-line input: unclosed brackets/blocks show `... ` prompt; empty line terminates a block
- Spinner shown during execution
- Pack state persists within a session (module-level state survives across lines)
- Exit: `:quit`, `exit()`, `quit()`, or Ctrl+D
- Ctrl+C cancels the current input/execution without exiting
- `:help` prints available packs and tools

Requires an interactive terminal (TTY). Non-TTY stdin exits with code 1.

---

## onetool direct list

List available tools, one per line (pipe-friendly).

```
onetool direct list [OPTIONS] [PATTERN]
```

**Arguments:**

- `PATTERN` — pack name (e.g. `brave`) or glob pattern (e.g. `brave.*`); optional

**Options:**

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--config PATH` | `-c` | — | Path to `onetool.yaml` (built-in packs shown without config) |
| `--info MODE` | `-i` | `min` | `min` (names only) or `full` (signature + description) |

**Examples:**

```bash
onetool direct list                                      # all packs
onetool direct list brave                                # tools in brave pack
onetool direct list "brave.*"                           # glob pattern
onetool direct list --config onetool.yaml brave         # with explicit config
onetool direct list --info full | head -20              # signatures + docs
onetool direct list | fzf                               # interactive picking
```

---

## onetool direct search

Find tools by name or description.

```
onetool direct search [OPTIONS] QUERY
```

**Arguments:**

- `QUERY` — search phrase (e.g. `"web search"`, `"convert pdf"`)

**Options:**

| Flag | Short | Description |
|------|-------|-------------|
| `--config PATH` | `-c` | Path to `onetool.yaml` |

**Examples:**

```bash
onetool direct search "web search"
onetool direct search "convert pdf"
onetool direct search --config onetool.yaml "database query"
```

---

## onetool direct help

Show tool signatures, parameters, and docstrings.

```
onetool direct help [OPTIONS] [QUERY]
```

**Arguments:**

- `QUERY` — tool name (`brave.search`), pack name (`brave`), or search phrase; optional

**Options:**

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--config PATH` | `-c` | — | Path to `onetool.yaml` |
| `--info MODE` | `-i` | `full` | `min`, `default`, or `full` |

**Examples:**

```bash
onetool direct help brave.search        # full signature + docstring for one tool
onetool direct help brave               # all tools in a pack with descriptions
onetool direct help "web search"        # fuzzy search across all tools
onetool direct help --config onetool.yaml brave.search
```

---

## onetool direct servers

List configured proxy servers and their connection status.

```
onetool direct servers [OPTIONS] [PATTERN]
```

**Arguments:**

- `PATTERN` — filter by server name; optional

**Options:**

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--config PATH` | `-c` | — | Path to `onetool.yaml` |
| `--info MODE` | `-i` | `default` | `min`, `default`, or `full` |

**Examples:**

```bash
onetool direct servers --config onetool.yaml
onetool direct servers github
onetool direct servers --info full
```

---

## onetool direct start

Start the HTTP execution host.

```
onetool direct start [OPTIONS]
```

**Options:**

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--config PATH` | `-c` | — | Path to `onetool.yaml` |
| `--secrets PATH` | `-s` | — | Path to secrets file |
| `--port N` | `-p` | `direct.host.port` or `8765` | Port to listen on |

Starts the HTTP execution host as a daemon, then blocks until it is ready to accept connections (up to 5 seconds). PID and log are written to `~/.onetool/direct-server-{port}.pid` and `direct-server-{port}.log`.

Secrets path resolution follows the same precedence as `direct run` (`--secrets`, `OT_SECRETS_FILE`, then `<config_dir>/secrets.yaml`).

When `--config` is omitted, the host starts with no tools loaded (a warning is printed).

The host exposes `POST /run` accepting `{"command": "..."}` and returning `{"result": "...", "success": true|false}`.

---

## onetool direct stop

Stop the running execution host.

```
onetool direct stop [--port N]
```

Reads `~/.onetool/direct-server-{port}.pid`, sends SIGTERM (Unix) or TerminateProcess (Windows), then removes the PID file. Exits `0` if the host was stopped successfully or was not running; exits `1` if the process could not be terminated.

---

## onetool direct status

Show execution server status.

```
onetool direct status [--port N]
```

Prints to stderr: `Execution host running — PID <pid>, port <port>, uptime <N>s` followed by `Config: <path>` and `Secrets: <path>` when available, and `Log: <path>`.

Exit codes: `0` running, `1` not running.

---

## onetool direct restart

Stop and restart the execution host in one command.

```
onetool direct restart [OPTIONS]
```

Reuses the saved `--config` and `--port` from the previous start. Explicit flags override the saved values. If no host is running, starts fresh.

**Options:** `--config`, `--secrets`, `--port` (same as `start`)

---

## onetool direct logs

Print the last N lines of the server log.

```
onetool direct logs [--port N] [--lines N]
```

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--port N` | `-p` | `8765` | Port of the server |
| `--lines N` | `-n` | `50` | Number of lines to show |
