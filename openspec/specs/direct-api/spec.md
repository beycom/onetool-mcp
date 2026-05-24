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
- **AND** the error SHALL identify `direct.host.enabled` as the missing
  requirement

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

### Requirement: Direct API Supports Child Forwarding

The Direct API SHALL support signed child forwarding from restricted child MCP
servers without depending on the parent root MCP transport.

#### Scenario: Handoff child forwards run call

- **GIVEN** the root OneTool process is running with `direct.host.enabled: true`
- **WHEN** a handoff worker invokes the child OneTool `run` tool
- **THEN** the child MCP process SHALL forward the call to the root Direct API
- **AND** the forwarded call SHALL execute in the root OneTool process

#### Scenario: Handoff worker uses root process resources

- **WHEN** a forwarded run call executes
- **THEN** it SHALL use the root process's loaded config, secrets, proxy
  connections, registry, state, and stats behavior
- **AND** it SHALL NOT start a second independent OneTool root process

#### Scenario: Child forwards to stdio root parent

- **GIVEN** a parent MCP process running in stdio root mode
- **AND** `direct.host.enabled: true`
- **WHEN** a child MCP server signs a run request with the parent
  `<ot-dir>/mcp-direct/auth.key`
- **THEN** the Direct API SHALL execute the request through the parent MCP
  process

#### Scenario: Child forwards to HTTP root parent

- **GIVEN** a parent MCP process running in Streamable HTTP root mode
- **AND** `direct.host.enabled: true`
- **WHEN** a child MCP server signs a run request with the parent
  `<ot-dir>/mcp-direct/auth.key`
- **THEN** the Direct API SHALL execute the request through the parent MCP
  process

#### Scenario: Child forwarding unavailable when Direct API disabled

- **GIVEN** a parent MCP process running in stdio or Streamable HTTP root mode
- **AND** `direct.host.enabled: false`
- **WHEN** a child MCP server attempts to forward a run request to the parent
- **THEN** the request SHALL fail without executing user code
- **AND** the child-facing error SHALL identify `direct.host.enabled` or parent
  URL reachability as the missing requirement

#### Scenario: Child auth mismatch rejected

- **WHEN** a child MCP server signs a run request with an auth key from the wrong
  OneTool directory
- **THEN** the Direct API SHALL reject the request before command execution
- **AND** the child-facing error SHALL identify an authentication failure without
  logging key material

#### Scenario: Handoff child remains private

- **WHEN** the public MCP tool list is requested from the root OneTool server
- **THEN** the child forwarding interface SHALL NOT be exposed as a public tool
