# Test Direct Commands

Exploratory tests for `onetool direct` subcommands: `run`, `repl`, and server management.

## Setup

Config path: `.onetool/onetool.yaml`

## Tests

### 1. Help / structure
- `onetool --help` — top-level help, confirm `direct` group is visible
- `onetool direct --help` — confirm run, repl, start, stop, status, restart, logs subcommands visible
- `onetool direct run --help` — confirm flags: --config, --secrets, --format, --no-host
- `onetool direct start --help` — confirm --port, --wait flags

### 2. direct run — in-process execution
- `onetool direct run -c .onetool/onetool.yaml "ot.version()"` — basic run
- `onetool direct run -c .onetool/onetool.yaml "ot.debug()"` — larger output
- `onetool direct run -c .onetool/onetool.yaml --format json "ot.version()"` — JSON output format
- `onetool direct run -c .onetool/onetool.yaml --format yml "ot.version()"` — YAML output format
- `echo 'ot.version()' | onetool direct run -c .onetool/onetool.yaml -` — stdin input

### 3. direct run — error cases
- `onetool direct run -c .onetool/onetool.yaml` (no command) — should exit 2
- `onetool direct run -c .onetool/onetool.yaml --format bad "ot.version()"` — bad format, exit 2
- `onetool direct run -c /nonexistent/onetool.yaml "ot.version()"` — missing config, exit 2

### 4. execution server lifecycle
- `onetool direct status` — should say "No execution server running", exit 1
- `onetool direct start -c .onetool/onetool.yaml` — start in background
- `onetool direct status` — should show PID, port, uptime
- `onetool direct run "ot.version()"` — auto-detect server (no --config needed)
- `onetool direct stop` — stop server
- `onetool direct status` — should say "No execution server running" again

### 5. direct stop idempotency
- `onetool direct stop` (when not running) — should handle gracefully

### 6. direct repl
- Non-interactive exit: `echo "" | onetool direct repl` — should reject non-TTY input, exit 1

### 7. proxy server tools via direct run
- `onetool direct run -c .onetool/onetool.yaml "ot.servers()"` — list configured proxy servers
- Enable a proxy server then call a tool through it:
  `onetool direct run -c .onetool/onetool.yaml "ot_servers.enable(name='github'); ot.servers()"`
- Call a proxied tool: `onetool direct run -c .onetool/onetool.yaml "github.get_me()"`
  (may fail if not authenticated — capture error message)
- Disable: `onetool direct run -c .onetool/onetool.yaml "ot_servers.disable(name='github')"`
- Via background server: start server, then call proxy tool without --config flag
