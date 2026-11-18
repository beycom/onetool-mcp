# Configuration

Create a starter with `onetool init --config PATH`, then run its printed validation command. Missing parent directories are created. Existing files are unchanged unless `--force` is supplied; force names the backup and refuses symlinks. A failed replacement restores the original when possible.

Pass an explicit path to `onetool serve --config PATH` or `onetool check-config --config PATH`. OneTool does not search parent directories, load `.env` or migrate older configs. Validation never launches a process, connects to a server or opens an OAuth login.

Use UTF-8 YAML, one mapping document, at most 1 MiB. Unknown keys, duplicate keys, unsafe tags, anchors and aliases fail validation. Types are strict. A boolean is not a timeout or byte count.

## Top level

| Key | Meaning |
| --- | --- |
| `version` | Required integer `4` |
| `servers` | Required mapping, which may be empty |
| `execution` | Optional execution limits |
| `logging` | Optional operational logging |
| `instructions` | Gateway guidance; built-in discovery/execution guidance by default |
| `env` | Shared string values, also passed to every stdio server |

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

`${NAME}` and `${NAME:-default}` work inside each argument, env value, header value and HTTP URL. Resolution order is the explicit secrets file, shared top-level `env`, process environment, then the default. Per-server `env` wins when constructing the child environment. Missing variables fail by name; errors never print the substituted value. Keys, `command` and YAML source are not interpolated.

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

## Curation

Both server transports accept `description`, `source` and `instructions`. Configured instructions appear beneath `MCP Server Instructions` and a `## server` heading in the initialize response. Native upstream instructions appear in status/help after connection, redacted and capped at 8 KiB per server. Changed gateway instructions require client reconnection after reload.

Per-server `tools` keys are upstream names, without the server prefix. Allowed tool fields are `description`, `enabled`, `tags`, `meta` and `arguments`. Each argument accepts `description`, scalar `default`, `hide`, `required: true` and `examples`. Native FastMCP fills hidden defaults and rejects caller overrides. Renames are unsupported. Unknown targets produce catalog-time status warnings. `include_tags` and `exclude_tags` use native filters; a disabled tool cannot be called.

```yaml
version: 4
instructions: Use help and inspect schemas before calling.
servers:
  alpha:
    transport: stdio
    command: python
    args: [tests/fixtures/fixture_server.py]
    description: Fixture arithmetic
    instructions: Use keyword arguments.
    tools:
      add:
        description: Add two integers.
        arguments:
          b:
            default: 7
            hide: true
```

## Secrets

Pass `--secrets PATH` explicitly to `serve` or `check-config`. The file is a flat mapping of variable names to strings, using the same strict one-document, 1 MiB YAML limits. No file is discovered automatically. `check-config` checks references and shape without decrypting or accessing the keychain. Serve decrypts an `age1enc:` value only when a connection references it. A missing identity, insecure keyring or malformed value fails that server only, with no plaintext fallback.

Owner commands are `onetool secrets init|encrypt|status|rotate|audit --secrets PATH` and `onetool secrets set NAME --secrets PATH`. Set prompts without echo; never put values in arguments. Init creates an age X25519 identity in the supported system keyring. Set encrypts when an identity exists; encrypt converts plaintext entries. Writes are atomic and owner-only. Rotate verifies the new file before replacing the identity and restores the prior file on failure. No plaintext backup is made. Status/audit show key names, storage form, permissions and identity presence, never values.

Secrets-file values, including short values and decrypted values, are masked in diagnostics and returned/stored results. Avoid names or values so broad that masking makes useful output unreadable. Real platform keychain prompts remain an owner check.

V4 uses its own keyring item: service `onetool-mcp`, account `secrets-identity`. It never reads V3's `onetool/age_identity`. Existing V3 `age1enc:` ciphertext cannot decrypt with the V4 identity. Keep the V3 file unchanged: prepare a separate V4 file from the original plaintext, run V4 `secrets init`, then `secrets encrypt`; or use the non-echoing `secrets set NAME` prompt after init. Copying V3 ciphertext into the new file is insufficient. V4 rotation therefore does not change the V3 bridge's identity.

## Includes

Keep shared definitions in local YAML files. For example, [examples/composed.yaml](../examples/composed.yaml) sits beside the checkout's fixtures file:

```yaml
version: 4
include: [fixtures.yaml]
servers: {}
execution:
  max_tool_calls: 10
```

Includes resolve from the declaring file, depth first in listed order; the declaring file wins last. Each server entry replaces its whole definition. Other sections merge one immediate property, and lists replace. Empty `servers: {}` adds no overrides. Root version is required4; an included file may omit version, but any declared version must be4. No globs, URLs, variable expansion, optional files or packaged fallback.

Limits are8levels including root,32file reads and1MiB combined. Cycles, missing files, unsafe/duplicate YAML and invalid final values fail with file/line/field context, without rejected values. Command/cwd resolve from the winning server definition's file; logging.file resolves from its winning property's file. Arguments stay literal. Check-config lists the files read and each server's source; status reports those sources too. Reload and named restart validate every include before changing runtime state. Defaults still need review against the owner's real shared configs.
