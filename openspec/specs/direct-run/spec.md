# direct-run Specification

## Purpose

Defines `onetool direct run` as a secure CLI bridge into an already-running
OneTool MCP process. Execution always happens inside that MCP process.

---

## Requirements

### Requirement: direct run command

The system SHALL provide `onetool direct run --port PORT COMMAND` for direct
tool execution from the shell.

`COMMAND` is positional. Passing `-` reads from stdin. Passing a path to an
existing `.py` file reads the file contents and executes them.

Flags:
- `--port`/`-p` — required target MCP direct API port
- `--ot-dir` — absolute OneTool directory containing `mcp-direct/auth.key`; default `~/.onetool`
- `--format`/`-f` — output format: `json_h` (default), `json`, `yml`, `yml_h`, `raw`
- `--sanitize` — enable output sanitization
- `--timeout`/`-t` — direct API request timeout in seconds

#### Scenario: Basic execution through MCP process

- **GIVEN** an MCP process exposes the direct API on port `8765`
- **WHEN** `onetool direct run --port 8765 "ot.version()"` is run
- **THEN** the command SHALL be sent to signed HTTP `POST /run`
- **AND** execution SHALL occur inside the MCP process
- **AND** stdout SHALL contain the MCP result
- **AND** exit code SHALL be `0` when the MCP run succeeds

#### Scenario: Target port required

- **WHEN** `onetool direct run "ot.version()"` is run
- **THEN** the command SHALL exit with code `2`
- **AND** the error SHALL clearly state that the target port is required

#### Scenario: Stdin via dash

- **WHEN** `echo "ot.version()" | onetool direct run --port 8765 -` is run
- **THEN** the command SHALL be read from stdin and sent to the MCP direct API

#### Scenario: .py file path

- **WHEN** `onetool direct run --port 8765 script.py` is run and `script.py` exists
- **THEN** the file contents SHALL be sent as the command
- **AND** non-existent paths with `.py` extension SHALL be treated as literal command strings

#### Scenario: Output shaping

- **WHEN** `--format` or `--sanitize` is provided
- **THEN** those values SHALL be sent in the direct API JSON request body
- **AND** the MCP process SHALL apply them to the command result

#### Scenario: Invalid format

- **WHEN** `--format` is set to an unsupported value
- **THEN** the command SHALL exit with code `2`
- **AND** print an error listing valid values

### Requirement: authenticated direct API client

`onetool direct run` SHALL connect only to `127.0.0.1:PORT` and use the
`mcp-direct` HMAC key from `OT_DIR/mcp-direct/auth.key`. The client-side
OT_DIR SHALL come from `--ot-dir`, defaulting to `~/.onetool`.

`--ot-dir` SHALL be an explicit absolute directory selector after `~`
expansion. It SHALL NOT load OneTool config and SHALL NOT resolve relative to
cwd or `.onetool`. Relative `--ot-dir` values SHALL fail with a clear argument
error.

Before `/run`, the client SHALL perform signed `/status` and `/ready` checks.
The client SHALL verify signed responses before printing or trusting response
content.

#### Scenario: Unreachable selected port

- **WHEN** no service is listening on the selected port
- **THEN** the command SHALL fail clearly

#### Scenario: Non-OneTool or unauthenticated service

- **WHEN** a service is listening but signed status/readiness fails
- **THEN** the command SHALL fail clearly as an authentication or protocol error
- **AND** no command SHALL be sent without valid authentication

#### Scenario: Protocol mismatch

- **WHEN** `/status` or `/run` returns a different direct protocol version
- **THEN** the command SHALL fail clearly with a protocol mismatch
- **AND** `/ready` SHALL still be signed and parseable before it is trusted

#### Scenario: Execution failure

- **WHEN** `/run` returns `{"protocol_version":1,"success":false,"result":"..."}`
- **THEN** the result SHALL be printed
- **AND** the CLI SHALL exit with code `1`

### Requirement: request and response shape

The `/run` request body SHALL be compact JSON:

```json
{"protocol_version":1,"operation":"run","command":"...","format":"json_h","sanitize":false}
```

The `/run` response body SHALL be small JSON:

```json
{"protocol_version":1,"result":"...","success":true,"duration_ms":12}
```
