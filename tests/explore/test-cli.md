# Test Direct Commands

Exploratory tests for the `onetool direct run` signed direct API client.

## Setup

Config path: `.onetool/onetool.yaml`

For `direct run`, start OneTool as an MCP process with:

```yaml
direct:
  host:
    enabled: true
```

Use the bound port printed in MCP startup logs.

If the MCP process uses a project-local OneTool directory instead of the default
`~/.onetool`, pass an absolute `--ot-dir` pointing at that directory. `--ot-dir`
selects the direct API auth key directory only; it does not load config.

## Tests

### 1. Help / structure
- `onetool --help` — top-level help, confirm `direct` group is visible
- `onetool direct --help` — confirm only the run subcommand is visible
- `onetool direct run --help` — confirm flags: `--port`, `--format`, `--sanitize`, `--timeout`

### 2. direct run — MCP direct API execution
- `onetool direct run --port <port> "ot.version()"` — basic run
- `onetool direct run --ot-dir <absolute-ot-dir> --port <port> "ot.version()"` — basic run against a non-default OneTool directory
- `onetool direct run --port <port> "ot.debug()"` — larger output
- `onetool direct run --port <port> --format json "ot.version()"` — JSON output format
- `onetool direct run --port <port> --format yml "ot.version()"` — YAML output format
- `echo 'ot.version()' | onetool direct run --port <port> -` — stdin input

### 3. direct run — error cases
- `onetool direct run "ot.version()"` — missing port, exit 2
- `onetool direct run --port <port>` — no command, exit 2
- `onetool direct run --port <port> --format bad "ot.version()"` — bad format, exit 2
- `onetool direct run --port 1 "ot.version()"` — unreachable port, exit 1

### 4. discovery and proxy server tools via direct run
- `onetool direct run --port <port> "ot.help(query='web search')"` — discover tools from the MCP process
- `onetool direct run --port <port> "ot.servers()"` — list configured proxy servers from MCP process
- Enable a proxy server then call a tool through it:
  `onetool direct run --port <port> "ot_servers.enable(name='github'); ot.servers()"`
- Call a proxied tool: `onetool direct run --port <port> "github.get_me()"`
  (may fail if not authenticated — capture error message)
