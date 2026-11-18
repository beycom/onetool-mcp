# Configuration

Pass an explicit path to `onetool serve --config PATH` or `onetool check-config --config PATH`. OneTool does not search parent directories, load `.env`, create config files or migrate older configs. Validation never launches a process, connects to a server or opens an OAuth login.

Use UTF-8 YAML, one mapping document, at most 1 MiB. Unknown keys, duplicate keys, unsafe tags, anchors and aliases fail validation. Types are strict. A boolean is not a timeout or byte count.

## Top level

| Key | Meaning |
| --- | --- |
| `version` | Required integer `4` |
| `servers` | Required mapping, which may be empty |
| `execution` | Optional execution limits |
| `logging` | Optional operational logging |

Server names match `[a-z][a-z0-9_]*`. `onetool` and sandbox helper names `call_tool`, `call_tools`, `set_format`, `results` are reserved. Native namespaces normally produce `server_tool` names. If two server/tool combinations produce the same name, discovery/execution fails with both source names.

## Stdio servers

| Key | Default | Meaning |
| --- | --- | --- |
| `transport` | Required | `stdio` |
| `command` | Required | Nonempty executable name or path; no interpolation |
| `args` | `[]` | String arguments, passed without a shell |
| `cwd` | `null` | Child working directory |
| `env` | `{}` | String environment overrides |
| `inherit_env` | `false` | Pass the full parent environment |
| `enabled` | `true` | Include the server in discovery and routing |
| `timeout_seconds` | `30` | Per-server request timeout |

Bare commands use PATH. Resolve path-containing commands and `cwd` from the config directory, preserving executable symlinks. OneTool keeps its own working directory. Arguments remain literal except for `${NAME}` substitution. There is no `~`, shell or glob expansion.

The child receives the upstream MCP default environment plus `env`. On the tested macOS build, defaults included HOME, PATH, SHELL, USER, LOGNAME and terminal/locale keys. Other parent variables require `inherit_env: true` or an explicit `env` entry.

## HTTP servers

| Key | Default | Meaning |
| --- | --- | --- |
| `transport` | Required | `http`, using Streamable HTTP |
| `url` | Required | HTTPS endpoint; loopback HTTP is allowed for development |
| `headers` | `{}` | String header values |
| `auth` | `null` | Upstream OAuth configuration |
| `enabled` | `true` | Include the server |
| `timeout_seconds` | `30` | Per-server request timeout |

URLs must have a host and must not include embedded usernames/passwords or fragments. Caller credentials are not implicitly forwarded. Stdio-only fields on HTTP entries, and HTTP-only fields on stdio entries, fail validation.

OAuth has exactly `type: oauth` and optional `scopes: [read, write]`. An Authorization header and OAuth together fail validation. See [server authentication](servers.md#authentication).

## Environment references

`${NAME}` works inside each argument, env value, header value and HTTP URL. Missing variables fail by name; errors never print the substituted value. Keys, `command` and YAML source are not interpolated.

For a running loopback fixture, an HTTP entry can use:

```yaml
version: 4
servers:
  remote:
    transport: http
    url: http://127.0.0.1:8765/mcp
    headers:
      X-Fixture-Token: ${FIXTURE_TOKEN}
```

Use environment references for credentials. Values supplied by substitution are masked in diagnostic text even when short. Literal env/header values are masked only at eight characters or more, to avoid corrupting messages containing values such as `1` or `info`. Literal argument values are not masks. Payloads are never intentionally logged.

## Execution and logging

| Key | Default | Range |
| --- | --- | --- |
| `execution.timeout_seconds` | `60` | Finite, greater than 0, at most 3,600 |
| `execution.max_tool_calls` | `50` | Integer, 1 through 1,000 |
| `execution.max_output_bytes` | `65536` | Integer, 1,024 through 1,048,576 |
| `logging.level` | `INFO` | DEBUG, INFO, WARNING, ERROR or CRITICAL |
| `logging.file` | `null` | Optional path relative to the config directory |

Every execution has one deadline, including discovery needed by that execution. Calls use the lesser of the server timeout and time remaining. The upstream sandbox also limits compute time, memory and tool-call count.

Logs go to stderr. A requested file also receives JSON event records and rotates at 10 MiB with three backups. Failure to open it is a startup error. Records omit code, arguments, results and credential values; wire logs and raw upstream stderr are suppressed.

`onetool_reload()` validates the file, then replaces all upstreams. It rejects changed execution/logging settings; restart the gateway process for those. Set `enabled: false` in YAML for a persistent setting, or use `onetool_servers(action="disable", name=...)` for a session override. See [operations](troubleshooting.md#server-controls-and-reload).
