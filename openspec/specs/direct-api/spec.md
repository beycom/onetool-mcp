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

### Requirement: Direct API discovery file

When the MCP-owned direct API successfully binds, MCP SHALL write a
discovery file so external consumers (for example the OneTool Console) can
find the actual bound port and identify live MCP instances without polling a
fixed, possibly stale, port.

The discovery file SHALL be written at
`<ot-dir>/runtime/direct-api/<instance_id>.json`, one file per live instance,
with JSON body:

```json
{
  "instance_id": "mcp-<uuid4hex>",
  "port": 8766,
  "pid": 12345,
  "started_at": "2026-07-05T00:00:00+00:00"
}
```

`instance_id` SHALL match the process's stable runtime instance identity.
`port` SHALL be the final auto-incremented port the direct API actually
bound. `started_at` SHALL be an ISO-8601 UTC timestamp. The file SHALL be
written atomically (temp file in the same directory, then `os.replace`) and
SHALL be created with file mode `0600`. The parent directory SHALL be
created with parents as needed.

#### Scenario: Discovery file written on successful bind

- **GIVEN** `direct.host.enabled: true`
- **WHEN** the direct API successfully binds a port
- **THEN** MCP SHALL write the discovery file for the current instance at
  `<ot-dir>/runtime/direct-api/<instance_id>.json` containing the bound port,
  process pid, and start timestamp
- **AND** the file SHALL be written atomically and created with mode `0600`

#### Scenario: No discovery file when disabled

- **GIVEN** `direct.host.enabled: false`
- **WHEN** MCP startup runs
- **THEN** no direct API listener SHALL be started
- **AND** no discovery file SHALL be written

#### Scenario: Discovery file removed on clean shutdown

- **GIVEN** the MCP-owned direct API is running and its discovery file exists
- **WHEN** stdio or HTTP root MCP shutdown runs and the direct API listener is
  stopped
- **THEN** MCP SHALL remove that instance's discovery file

#### Scenario: Stale sibling discovery files swept on startup

- **GIVEN** `<ot-dir>/runtime/direct-api/` contains discovery files left
  behind by processes that are no longer running
- **WHEN** MCP startup binds the direct API
- **THEN** MCP SHALL remove sibling discovery files whose recorded `pid` is
  not a live process (`os.kill(pid, 0)` semantics), before or as part of
  writing its own discovery file
- **AND** discovery files whose `pid` is still alive SHALL be left untouched

#### Scenario: Consumers treat a dead-pid file as stale

- **WHEN** a consumer reads a discovery file under
  `<ot-dir>/runtime/direct-api/`
- **THEN** the consumer SHALL treat the file as stale and ignore it if the
  recorded `pid` does not correspond to a live process
- **AND** the consumer MAY rely on MCP's own startup sweep to remove stale
  sibling files opportunistically, but SHALL NOT depend on it for
  correctness

### Requirement: authenticated API endpoints

The API SHALL expose:
- signed `GET /health`
- signed `GET /ready`
- signed `POST /run`
- signed `GET /api/console/outbox`

Requests and responses SHALL use OneTool HMAC headers. Two keys SHALL exist under the active
OT_DIR, both created `0600`:
- `auth/mcp-direct.key` — authorizes `/health`, `/ready`, and `/run` only
- `auth/console-outbox.key` — authorizes the Console outbox endpoint only

Every request SHALL verify method, path, body hash, timestamp, nonce, and
signature before doing work, against the key scoped to that endpoint. Replayed nonces SHALL
be rejected. Every response, including errors, SHALL be signed.

#### Scenario: Unsigned request rejected

- **WHEN** `/health`, `/ready`, `/run`, or a Console outbox endpoint is requested without valid auth headers
- **THEN** the API SHALL return signed HTTP `401`
- **AND** `/run` SHALL NOT execute the command

#### Scenario: Wrong key, stale timestamp, mismatched body, or replayed nonce

- **WHEN** request authentication fails
- **THEN** the API SHALL return signed HTTP `401`
- **AND** `/run` SHALL NOT execute the command

#### Scenario: Console key does not authorize run

- **WHEN** a `/run`, `/health`, or `/ready` request is signed with `auth/console-outbox.key`
- **THEN** the API SHALL return signed HTTP `401`
- **AND** the command SHALL NOT execute

#### Scenario: Direct key does not authorize Console outbox

- **WHEN** a Console outbox request is signed with `auth/mcp-direct.key`
- **THEN** the API SHALL return signed HTTP `401`
- **AND** outbox state SHALL NOT be read or mutated

#### Scenario: Console outbox key is ensured eagerly at startup

- **GIVEN** `direct.host.enabled: true`
- **WHEN** the direct API app is created and the Console outbox route is
  mounted
- **THEN** `auth/console-outbox.key` SHALL exist on disk immediately, before
  any Console outbox request is served
- **AND** a Console started as soon as MCP is up SHALL be able to
  authenticate without waiting for a first outbox request to lazily create
  the key

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
