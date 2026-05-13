# direct-api Specification

## Purpose

Defines the MCP-owned direct API exposed by a running OneTool MCP process when
`direct.host.enabled: true`.

---

## Requirements

### Requirement: MCP-owned direct API startup

When `direct.host.enabled: true`, MCP startup SHALL bind an authenticated local
HTTP API inside the MCP process.

Config fields:
- `direct.host.enabled` — bind the MCP direct API when true
- `direct.host.port` — preferred port, default `8765`

The API SHALL bind only to loopback (`127.0.0.1`) by default. Startup SHALL try
the configured port first, then increment until a free port is found.

#### Scenario: Direct API disabled

- **GIVEN** `direct.host.enabled: false`
- **WHEN** MCP startup runs
- **THEN** no direct API listener SHALL be started
- **AND** startup logs SHALL state that the direct API is disabled

#### Scenario: Direct API enabled

- **GIVEN** `direct.host.enabled: true` and `direct.host.port: 9000`
- **WHEN** MCP startup runs
- **THEN** it SHALL try ports `9000, 9001, ...` until one binds
- **AND** startup logs SHALL include the configured port, candidates tried, occupied ports skipped, and successful base URL

#### Scenario: Startup failure degrades MCP startup

- **GIVEN** `direct.host.enabled: true`
- **AND** direct API startup fails
- **WHEN** MCP startup runs
- **THEN** MCP startup SHALL continue
- **AND** logs SHALL include the direct API degradation error

#### Scenario: MCP shutdown closes listener

- **GIVEN** the MCP-owned direct API is running
- **WHEN** MCP shutdown runs
- **THEN** the direct API listener SHALL be stopped with the MCP process

### Requirement: authenticated API endpoints

The API SHALL expose:
- signed `GET /health`
- signed `GET /ready`
- signed `POST /run`

Requests and responses SHALL use OneTool HMAC headers with the `mcp-direct`
auth namespace. The HMAC key SHALL be stored at
`mcp-direct/auth.key` under the active OT_DIR using `resolve_ot_path(".")`
as the `otpack.ensure_hmac_key("mcp-direct", base_dir=...)` base directory.

Every request SHALL verify method, path, body hash, timestamp, nonce, and
signature before doing work. Replayed nonces SHALL be rejected. Every response,
including errors, SHALL be signed.

#### Scenario: Unsigned request rejected

- **WHEN** `/health`, `/ready`, or `/run` is requested without valid auth headers
- **THEN** the API SHALL return signed HTTP `401`
- **AND** `/run` SHALL NOT execute the command

#### Scenario: Wrong key, stale timestamp, mismatched body, or replayed nonce

- **WHEN** request authentication fails
- **THEN** the API SHALL return signed HTTP `401`
- **AND** `/run` SHALL NOT execute the command

### Requirement: health, readiness, and run contracts

`GET /health` SHALL return authenticated protocol and identity information.

`GET /ready` SHALL return authenticated readiness information, including proxy
readiness where available.

`POST /run` SHALL accept compact JSON:

```json
{"protocol_version":1,"operation":"run","command":"...","format":"json_h","sanitize":false}
```

`POST /run` success and execution-error responses SHALL use:

```json
{"protocol_version":1,"result":"...","success":true,"duration_ms":12}
```

The response shape SHALL stay intentionally small.

`POST /run` SHALL reject request bodies larger than the direct API payload
limit before command execution.

#### Scenario: Protocol mismatch

- **WHEN** `/run` receives a request with `protocol_version` other than `1`
- **THEN** it SHALL return a signed error response
- **AND** SHALL NOT execute the command

#### Scenario: Oversized request

- **WHEN** `/run` receives a request body larger than the direct API payload limit
- **THEN** it SHALL return a signed HTTP `413`
- **AND** SHALL NOT execute the command

#### Scenario: Execute command via MCP process

- **WHEN** signed `POST /run` receives a valid run request
- **THEN** the command SHALL execute in the MCP process using that process's loaded config, secrets, proxy connections, registry, state, and stats behavior
- **AND** command success SHALL return `success: true`
- **AND** execution failure SHALL return `success: false`

Multiple MCP processes SHALL be supported by binding distinct ports; users
select the target process with `onetool direct run --port PORT`.
