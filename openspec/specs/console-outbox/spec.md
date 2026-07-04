# console-outbox Specification

## Purpose

Defines the signed MCP-owned Console outbox protocol used by the separate OneTool Console App to
consume read-only MCP instance and display events.

**Status: protocol v1 — served from 3.0.0, inline payloads only; file modes ship with the full
display experience in 3.1.** The `/api/console/outbox` and `/api/console/outbox/ack` HTTP routes
and the MCP-owned outbox state (`src/ot/console/outbox.py`) ship in 3.0.0 emitting `inline`
payloads only. The `file_ref` and `file_diff_ref` payload modes remain part of protocol v1 but
are not emitted until the full display experience ships in 3.1.
## Requirements
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
- **THEN** the MCP Direct API SHALL return a signed outbox batch containing protocol identity, MCP instance identity, batch identity, cursors, `oldest_retained`, `has_more`, and zero or more events
- **AND** the request SHALL NOT remove events from the MCP outbox

> The `batch_id` remains in the poll batch for logging and diagnostics only; it is not part of the acknowledgement contract.

#### Scenario: Acknowledge consumed events

- **WHEN** a signed Console consumer posts `POST /api/console/outbox/ack` with matching protocol identity, MCP instance identity, and `acked_through`
- **THEN** the MCP Direct API SHALL record the acknowledgement
- **AND** acknowledged outbox entries MAY be dropped earlier than natural queue expiry
- **AND** the ack SHALL NOT require a batch identity; a `batch_id` field, if present, SHALL be ignored

#### Scenario: At-least-once delivery

- **WHEN** Console polls the outbox without acknowledging delivered events
- **THEN** MCP SHALL keep retained events eligible for later poll responses until they are acknowledged or removed by bounded retention
- **AND** Console SHALL be able to de-duplicate events by event `id` or by `(instance_id, sequence)`

### Requirement: Consumers Tolerate Additive Fields

Console consumers SHALL ignore unknown fields anywhere in the protocol so that servers can add fields without a protocol version bump.

Within `protocol_version: 1`, servers MAY add new fields to outbox batches, event envelopes, and payloads. Consumers MUST ignore fields they do not recognize rather than rejecting the batch, envelope, or payload. The vendored JSON Schemas keep `additionalProperties: false` as a strict PRODUCER conformance check for the shipped server; they are not a consumer validation contract.

#### Scenario: Consumer receives an additive field

- **WHEN** a Console consumer receives an outbox batch, event envelope, or payload that contains a field it does not recognize
- **THEN** the consumer SHALL ignore the unknown field and process the known fields normally
- **AND** the consumer SHALL NOT reject or fail the batch because of the unknown field

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

#### Scenario: Gap signaled when retention evicts unacknowledged events

- **WHEN** a poll batch is returned
- **THEN** it SHALL include an `oldest_retained` integer equal to the sequence of the oldest retained entry, or (when no entries are retained) equal to `acked_through`
- **AND** a consumer whose cursor is `c` SHALL treat events `c+1 .. oldest_retained-1` as lost whenever `oldest_retained > c + 1`, because bounded retention evicted them before acknowledgement

### Requirement: Console Event Types

MCP SHALL publish small, stable Console events for instance metadata and display messages.

#### Scenario: Instance snapshot event

- **WHEN** MCP startup initializes Console outbox state
- **THEN** MCP SHALL append an `instance.snapshot` event with instance identity, start time, current workspace paths, allowed roots, status, message count, update timestamp, and runtime metadata

#### Scenario: Snapshot emitted only on relevant state change

- **WHEN** MCP evaluates whether to append an `instance.snapshot` event
- **THEN** MCP SHALL append one at startup, on instance change, and when snapshot-relevant state (status or message count) changes
- **AND** MCP SHALL NOT append a redundant `instance.snapshot` on every poll or status call whose status and message count are unchanged

#### Scenario: Console message event

- **WHEN** `display.show(...)` creates a display message
- **THEN** MCP SHALL append a `console.message.created` event containing the display message metadata, payload mode, bounded preview metadata, and stable message ID

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

### Requirement: Inline-Only Payload Emission In 3.0

Until the full display pack ships (3.1), the server SHALL emit `console.message.created`
events with `payload.mode: "inline"` only. The `file_ref` and `file_diff_ref` payload modes
defined by protocol v1 SHALL NOT be emitted by a 3.0 server, and no server code SHALL depend
on filesystem path validation (`allowed_roots`) for outbox payloads.

#### Scenario: Only inline payloads emitted

- **WHEN** any display message event is appended to the Console outbox on a 3.0 server
- **THEN** its payload mode SHALL be `inline`
- **AND** the payload SHALL validate against the shipped `console-message.schema.json`

#### Scenario: Protocol consumers unaffected

- **WHEN** a protocol-v1 Console consumer connects to a 3.0 server
- **THEN** it SHALL receive only payload modes it is already required to support
- **AND** later servers MAY add `file_ref`/`file_diff_ref` emission without a protocol version bump

### Requirement: Instance Snapshot On Startup

The server SHALL bind the Console outbox to the current runtime instance at Direct API
startup and SHALL append an `instance.snapshot` event so a connecting Console can identify
the instance before any display messages exist.

The server SHALL emit an `instance.snapshot` event at startup, on instance change, and when
snapshot-relevant state (status or message count) changes. The server SHALL NOT emit an
`instance.snapshot` on every poll or status call whose snapshot-relevant state is unchanged.

#### Scenario: Snapshot available to first poll

- **WHEN** the Direct API app has started with the Console outbox enabled
- **AND** a signed Console consumer polls `GET /api/console/outbox` before any display activity
- **THEN** the batch SHALL contain an `instance.snapshot` event carrying the instance identity

#### Scenario: Snapshot suppressed when state is unchanged

- **WHEN** a status or poll call occurs and neither status nor message count has changed since the last emitted snapshot
- **THEN** the server SHALL NOT append another `instance.snapshot` event

#### Scenario: Instance change resets outbox

- **WHEN** the outbox is configured with a different instance id than it is currently bound to
- **THEN** sequence, ack cursor, and retained entries SHALL reset for the new instance

