# Test Runtime CLI Modes

Exploratory tests for the OneTool runtime CLI surface. Spawn the actual CLI
commands and verify that `onetool serve` works over both stdio and Streamable
HTTP, and that `onetool direct` and `onetool child` still execute real tool pack
calls through the running root process without starting independent roots.

## Setup

Use a temporary OneTool directory for exploratory runs:

```bash
OT_DIR="$(pwd)/tmp/explore-runtime/.onetool"
mkdir -p "$OT_DIR"
```

Create `$OT_DIR/onetool.yaml` with at least:

```yaml
version: 2
tools_dir:
  - src/ottools/*.py
security:
  sanitize:
    enabled: false
direct:
  host:
    enabled: true
    port: 8765
```

Use free ports if `8765` or `8767` are already occupied. Record the config path,
HTTP MCP URL, Direct API port, commands run, and any stderr logs needed to
explain failures.

## Required Tool Pack Probes

Every runtime mode must execute actual tool pack calls, not only help text or
`ot.version()`.

Use this minimum set in each mode:

```python
ot.debug()
ot.tools(pattern="mem", info="full")
ot.tools(pattern="ripgrep", info="full")
ripgrep.search(pattern="TODO", path=".")
mem.write(topic="tmp/test/cli-runtime", content="cli runtime probe", category="note")
mem.read(topic="tmp/test/cli-runtime")
mem.delete(topic="tmp/test/", confirm=True)
```

When network access and credentials/config are available, also test one external
or networked pack:

```python
ground.search(q="OneTool MCP", limit=3)
webfetch.fetch(url="https://en.wikipedia.org/wiki/Python_(programming_language)")
```

If a pack is unavailable because optional dependencies, credentials, or network
access are missing, record it as an environment gap. If the same pack call works
in one runtime mode and fails in another, file it as a runtime defect.

## Tests

### 1. Help and command structure

- `onetool --help` - confirm `serve`, `child`, `direct`, and `init` are visible
- `onetool serve --help` - confirm `--config`, `--secrets`, `--transport`, `--host`, `--port`, and `--path`
- `onetool direct --help` - confirm `run` is visible
- `onetool direct run --help` - confirm `--port`, `--ot-dir`, `--format`, `--sanitize`, and `--timeout`
- `onetool child --help` - confirm `--url` and `--ot-dir` are required
- `onetool serve-http --help` - confirm removed command fails through normal unknown-command handling

### 2. stdio root server

Start the actual stdio root CLI through an MCP stdio client, not by running it
as a standalone terminal command that waits forever:

```bash
onetool serve --transport stdio --config "$OT_DIR/onetool.yaml"
```

Verify through the MCP client:

- `list_tools` includes `run`
- `run` with every Required Tool Pack Probe succeeds or is classified as an environment gap
- Direct API starts when `direct.host.enabled: true`
- startup logs identify stdio root mode separately from Direct API startup

### 3. HTTP root server

Start the actual Streamable HTTP root CLI:

```bash
onetool serve --transport http --config "$OT_DIR/onetool.yaml" --host 127.0.0.1 --port 8767 --path /mcp
```

Verify with a Streamable HTTP MCP client:

- Connect to `http://127.0.0.1:8767/mcp`
- `ping` succeeds
- `list_tools` includes `run`
- `run` with every Required Tool Pack Probe succeeds or is classified as an environment gap
- startup logs include the HTTP bind host, port, path, and URL
- Direct API is still available when enabled, and its URL is distinct from the HTTP MCP URL

Error checks:

- `onetool serve --transport http --config "$OT_DIR/onetool.yaml" --path mcp` fails before startup
- `onetool serve --transport bad --config "$OT_DIR/onetool.yaml"` fails before startup
- `onetool serve --transport http --config "$OT_DIR/onetool.yaml" --host 0.0.0.0` logs a non-loopback warning

### 4. direct CLI against running root

Run these while either stdio or HTTP root mode is already running with
`direct.host.enabled: true`. `--ot-dir` selects the parent Direct API auth key
directory; it does not load config.

```bash
onetool direct run --ot-dir "$OT_DIR" --port 8765 "ot.version()"
onetool direct run --ot-dir "$OT_DIR" --port 8765 "ot.debug()"
onetool direct run --ot-dir "$OT_DIR" --port 8765 "ripgrep.search(pattern='TODO', path='.')"
onetool direct run --ot-dir "$OT_DIR" --port 8765 "mem.write(topic='tmp/test/cli-runtime', content='direct probe', category='note'); mem.read(topic='tmp/test/cli-runtime'); mem.delete(topic='tmp/test/', confirm=True)"
onetool direct run --ot-dir "$OT_DIR" --port 8765 --format json "ot.version()"
onetool direct run --ot-dir "$OT_DIR" --port 8765 --format yml "ot.version()"
echo 'ot.version()' | onetool direct run --ot-dir "$OT_DIR" --port 8765 -
```

Verify:

- calls execute in the running root process
- real pack calls execute through the root registry, not only `ot.*` introspection
- output formats are honored
- stdin command input works
- `ot.servers()` reports the root process proxy state
- tool calls such as `ot.help(query="web search")` use the root process registry

Error checks:

- `onetool direct run "ot.version()"` fails for missing port
- `onetool direct run --port 8765` fails for missing command
- `onetool direct run --ot-dir "$OT_DIR" --port 8765 --format bad "ot.version()"` fails for bad format
- `onetool direct run --ot-dir "$OT_DIR" --port 1 "ot.version()"` fails for unreachable port without executing user code

### 5. child CLI against running root

Run child mode through an MCP stdio client:

```bash
onetool child --url http://127.0.0.1:8765 --ot-dir "$OT_DIR"
```

Verify through the child MCP client:

- `list_tools` exposes only `run`
- `run` with `ot.debug()` succeeds by forwarding to the parent Direct API
- `run` with every Required Tool Pack Probe succeeds or is classified as an environment gap
- child logs do not include auth key material or command bodies by default
- the parent root process remains the only process with full config, secrets, registry, proxy state, and stats behavior

Error checks:

- `onetool child --url http://127.0.0.1:8765` fails before startup because `--ot-dir` is required
- `onetool child --url http://127.0.0.1:8765 --ot-dir .onetool` fails before startup because `--ot-dir` must resolve to an absolute path
- using an `--ot-dir` with the wrong `mcp-direct/auth.key` fails authentication without executing user code
- using a parent URL where Direct API is disabled or unreachable fails clearly

## Failure Triage

For each failure, classify it as:

- CLI contract bug
- runtime transport bug
- Direct API auth or reachability bug
- child forwarding bug
- test setup bug
- environment gap

File code or documentation defects as `wip/issues/1-new/exp-cli-<issue>.md`.
Do not file issues for intentionally skipped environment dependencies or
occupied ports when a free-port retry succeeds.

Write detailed output to `wip/test-output/cli-runtime-test.md`.
