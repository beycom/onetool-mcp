## Purpose (reference — for the post-archive `openspec/specs/console-outbox/spec.md` Purpose section)

> The OpenSpec archive tool auto-generates a placeholder Purpose ("TBD - created by archiving change
> p23-console-outbox-contract. Update Purpose after archive.") for brand-new capabilities. Task 2.4 in
> `tasks.md` requires replacing that placeholder with the exact text below — copied verbatim from
> `feature/display:openspec/specs/console-outbox/spec.md`, with the "protocol v1" ships-with-display
> annotation appended as required by report R6's minimal scope.

Defines the signed MCP-owned Console outbox protocol used by the separate OneTool Console App to consume
read-only MCP instance and display events.

**Status: protocol v1 — server implementation ships with display (3.1).** This capability defines the
wire contract only. No `main` code implements these endpoints yet; `src/ot/console_outbox.py` and the
`/api/console/outbox` / `/api/console/outbox/ack` HTTP routes ship with the display pack in release 3.1.

## ADDED Requirements

### Requirement: Console Outbox Protocol

The MCP Direct API SHALL expose a local Console outbox protocol for read-only Console consumption.

The protocol SHALL use JSON-compatible payloads with:
- `protocol: "onetool.console"`
- `protocol_version: 1`
- stable event envelopes
- ISO-8601 timestamp strings
- string event types

#### Scenario: Poll outbox batch

- **WHEN** a signed Console consumer requests `GET /api/console/outbox?limit=100&after=<cursor>`
- **THEN** the MCP Direct API SHALL return a signed outbox batch containing protocol identity, MCP instance identity, batch identity, cursors, `has_more`, and zero or more events
- **AND** the request SHALL NOT remove events from the MCP outbox

#### Scenario: Acknowledge consumed events

- **WHEN** a signed Console consumer posts `POST /api/console/outbox/ack` with matching protocol identity, MCP instance identity, batch identity, and `acked_through`
- **THEN** the MCP Direct API SHALL record the acknowledgement
- **AND** acknowledged outbox entries MAY be dropped earlier than natural queue expiry

#### Scenario: At-least-once delivery

- **WHEN** Console polls the outbox without acknowledging delivered events
- **THEN** MCP SHALL keep retained events eligible for later poll responses until they are acknowledged or removed by bounded retention
- **AND** Console SHALL be able to de-duplicate events by event `id` or by `(instance_id, sequence)`

### Requirement: Console Outbox Authentication

Console outbox endpoints SHALL use a separate outbox consumer key and SHALL NOT reuse the general Direct API `/run` key for Console authority.

#### Scenario: Outbox key authorizes only Console endpoints

- **WHEN** a request is signed with the Console outbox consumer key
- **THEN** it SHALL be accepted only for Console outbox poll and ack endpoints
- **AND** it SHALL NOT authorize `/run` or other general MCP Direct API operations

#### Scenario: Invalid Console signature rejected

- **WHEN** a Console outbox request has no valid outbox signature, a stale timestamp, a mismatched body hash, or a replayed nonce
- **THEN** the MCP Direct API SHALL return a signed authentication error
- **AND** the request SHALL NOT poll, acknowledge, or mutate outbox state

#### Scenario: Outbox key location

- **WHEN** Console is configured with an active OneTool MCP config/state directory
- **THEN** Console SHALL resolve the outbox consumer key from that directory
- **AND** the default key path SHALL be `<ot-dir>/auth/console-outbox.key`

### Requirement: Console Outbox Retention

MCP SHALL keep Console outbox state bounded so tool execution and MCP startup do not depend on Console availability.

#### Scenario: Console unavailable during display writes

- **WHEN** `display.show(...)` creates messages while Console is not running
- **THEN** MCP SHALL append retained events up to the configured producer limit
- **AND** `display.show(...)` SHALL return promptly without waiting for Console

#### Scenario: Retention limit exceeded

- **WHEN** the Console outbox exceeds its configured retention limit
- **THEN** MCP SHALL remove the oldest unacknowledged events according to bounded retention
- **AND** newer events SHALL remain eligible for Console polling

### Requirement: Console Event Types

MCP SHALL publish small, stable Console events for instance metadata and display messages.

#### Scenario: Instance snapshot event

- **WHEN** MCP startup initializes Console outbox state
- **THEN** MCP SHALL append an `instance.snapshot` event with instance identity, start time, current workspace paths, allowed roots, status, message count, update timestamp, and runtime metadata

#### Scenario: Display message event

- **WHEN** `display.show(...)` creates a display message
- **THEN** MCP SHALL append a `display.message.created` event containing the display message metadata, payload mode, bounded preview metadata, and stable message ID

#### Scenario: Unknown future event type

- **WHEN** a Console consumer receives an event type it does not understand
- **THEN** the protocol contract SHALL allow the consumer to ignore or store the unknown event without failing the whole batch

### Requirement: Console Display Message Contract

Display message events SHALL use a language-neutral public message shape for Console consumption.

Message payload modes SHALL be:
- `inline`
- `file_ref`
- `file_diff_ref`

#### Scenario: Inline message payload

- **WHEN** MCP publishes a display message whose renderable content is inline
- **THEN** the event SHALL include payload mode `inline`, MIME type, bounded JSON-compatible content, and size metadata

#### Scenario: File reference payload

- **WHEN** MCP publishes a display message that points to a local file
- **THEN** the event SHALL include payload mode `file_ref`, a canonical absolute path, MIME type, and size metadata
- **AND** MCP SHALL NOT require Console to fetch the file through an MCP file preview route

#### Scenario: File diff reference payload

- **WHEN** MCP publishes a display message that points to a local diff
- **THEN** the event SHALL include payload mode `file_diff_ref`, a canonical absolute diff path, optional canonical old and new paths, MIME type, and size metadata
- **AND** Console SHALL own diff rendering from the referenced local file data

### Requirement: Console Outbox Protocol Fixtures Stay Schema-Valid

The vendored Console protocol JSON Schemas and example fixtures under `tests/fixtures/console-protocol/` SHALL remain mutually consistent and SHALL be validated in CI.

#### Scenario: Vendored fixtures validate against vendored schemas

- **WHEN** the CI test suite runs `tests/unit/core/test_console_protocol_fixtures.py`
- **THEN** every fixture in `tests/fixtures/console-protocol/fixtures/*.json` SHALL validate against its corresponding JSON Schema in `tests/fixtures/console-protocol/schemas/*.json` using Draft 2020-12 validation
- **AND** a schema or fixture change that breaks validation SHALL fail CI
