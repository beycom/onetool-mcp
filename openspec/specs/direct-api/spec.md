# direct-api Specification

## Purpose

Defines the MCP-owned direct API exposed by a running OneTool MCP process when
`direct.host.enabled: true`.

---

## Requirements

### Requirement: MCP-owned direct API startup

When `direct.host.enabled: true`, MCP startup SHALL bind an authenticated local
HTTP API inside the MCP process, regardless of whether the root MCP transport is
stdio or Streamable HTTP.

Config fields:
- `direct.host.enabled` — bind the MCP direct API when true
- `direct.host.port` — preferred port, default `8765`
- `direct.admin.enabled` — send Admin App registrations when true
- `direct.admin.port` — local Admin App port, default `8760`
- `direct.admin.heartbeat_seconds` — registration interval, default `15`

The API SHALL bind only to loopback (`127.0.0.1`) by default. Startup SHALL try
the configured port first, then increment until a free port is found.

#### Scenario: Direct API disabled

- **GIVEN** `direct.host.enabled: false`
- **WHEN** stdio or HTTP root MCP startup runs
- **THEN** no direct API listener SHALL be started
- **AND** startup logs SHALL state that the direct API is disabled

#### Scenario: Direct client unavailable when disabled

- **GIVEN** stdio or HTTP root MCP startup ran with `direct.host.enabled: false`
- **WHEN** `onetool direct run` targets that process
- **THEN** the command SHALL fail without executing user code
- **AND** the error SHALL clearly identify that the Direct API target is
  unavailable or unreachable

#### Scenario: Direct API enabled under stdio root

- **GIVEN** stdio root mode
- **AND** `direct.host.enabled: true` and `direct.host.port: 9000`
- **WHEN** MCP startup runs
- **THEN** it SHALL try ports `9000, 9001, ...` until one binds
- **AND** startup logs SHALL include the configured port, candidates tried,
  occupied ports skipped, and successful base URL

#### Scenario: Direct API enabled under HTTP root

- **GIVEN** Streamable HTTP root mode
- **AND** `direct.host.enabled: true` and `direct.host.port: 9000`
- **WHEN** MCP startup runs
- **THEN** it SHALL try ports `9000, 9001, ...` until one binds
- **AND** startup logs SHALL include the configured port, candidates tried,
  occupied ports skipped, and successful base URL
- **AND** the Direct API URL SHALL be logged separately from the MCP Streamable
  HTTP URL

#### Scenario: Startup failure degrades MCP startup

- **GIVEN** `direct.host.enabled: true`
- **AND** direct API startup fails
- **WHEN** stdio or HTTP root MCP startup runs
- **THEN** MCP startup SHALL continue
- **AND** logs SHALL include the direct API degradation error

#### Scenario: MCP shutdown closes listener

- **GIVEN** the MCP-owned direct API is running
- **WHEN** stdio or HTTP root MCP shutdown runs
- **THEN** the direct API listener SHALL be stopped with the MCP process

### Requirement: Admin App Registration

When Direct API binds successfully and `direct.admin.enabled: true`, MCP startup SHALL register the actual bound Direct API base URL with the local Admin App and repeat registration at the configured heartbeat interval.

#### Scenario: Registration starts after bind
- **GIVEN** `direct.host.enabled: true`
- **AND** `direct.admin.enabled: true`
- **WHEN** Direct API binds to `http://127.0.0.1:9001`
- **THEN** MCP SHALL register that exact base URL with `http://127.0.0.1:{direct.admin.port}/api/admin/register`
- **AND** registration SHALL be best-effort and SHALL NOT block MCP startup

#### Scenario: Registration heartbeat
- **GIVEN** Direct API registration is enabled
- **WHEN** the MCP process remains running
- **THEN** it SHALL repeat registration every `direct.admin.heartbeat_seconds`
- **AND** the heartbeat interval SHALL be validated as positive

### Requirement: authenticated API endpoints

The API SHALL expose:
- signed `GET /health`
- signed `GET /ready`
- signed `POST /run`

Requests and responses SHALL use OneTool HMAC headers. The HMAC key SHALL be
stored at `auth/mcp-direct.key` under the active OT_DIR.

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

#### Scenario: Execute command via stdio root process

- **GIVEN** the parent MCP process is running in stdio root mode
- **WHEN** signed `POST /run` receives a valid run request
- **THEN** the command SHALL execute in the MCP process using that process's
  loaded config, secrets, proxy connections, registry, state, and stats behavior
- **AND** command success SHALL return `success: true`
- **AND** execution failure SHALL return `success: false`

#### Scenario: Execute command via HTTP root process

- **GIVEN** the parent MCP process is running in Streamable HTTP root mode
- **WHEN** signed `POST /run` receives a valid run request
- **THEN** the command SHALL execute in the MCP process using that process's
  loaded config, secrets, proxy connections, registry, state, and stats behavior
- **AND** command success SHALL return `success: true`
- **AND** execution failure SHALL return `success: false`

Multiple MCP processes SHALL be supported by binding distinct ports; users
select the target process with `onetool direct run --port PORT`.
