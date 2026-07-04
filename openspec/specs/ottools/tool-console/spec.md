# tool-console Specification

## Purpose
Provide the agent-facing `console` pack for publishing inline messages to a connected
onetool-console consumer via the Console outbox, with bounded in-memory retention and
list/read/clear introspection. Inline payloads only in 3.0; file-backed payload modes ship
with the full display experience (3.1).

## Requirements
### Requirement: Console Pack Inline Messages

The `console` pack SHALL let an agent publish inline messages to a connected onetool-console.
`console.show` SHALL accept inline content (string, mapping, or list), bound it to the
configured inline payload limit, retain a message record in memory, and append a
`console.message.created` event (wire name fixed by protocol v1) to the Console outbox. In this release the pack SHALL NOT
accept file path parameters; file-backed payload modes ship with the full display pack.

#### Scenario: Show an inline message

- **WHEN** an agent calls `console.show(content="build finished", kind="note")`
- **THEN** a message record SHALL be retained with a unique message id and metadata
- **AND** a `console.message.created` event (wire name fixed by protocol v1) with `payload.mode: "inline"` SHALL be appended to the Console outbox

#### Scenario: Oversized inline content bounded

- **WHEN** `console.show` is called with content exceeding the inline payload bound
- **THEN** the stored payload SHALL be truncated to the bound with truncation indicated
- **AND** the call SHALL succeed rather than error

### Requirement: Console Message Retention And Introspection

The pack SHALL provide `console.list`, `console.read`, and `console.clear` over an in-memory,
bounded message store scoped to the current runtime instance.

#### Scenario: List and read retained messages

- **WHEN** messages have been shown and the agent calls `console.list` then `console.read` with a returned message id
- **THEN** `list` SHALL return message metadata (id, kind, created-at) newest-last with a bounded count
- **AND** `read` SHALL return the full retained message payload

#### Scenario: Clear removes retained messages and notifies

- **WHEN** the agent calls `console.clear`
- **THEN** retained message records SHALL be removed
- **AND** the cleared count SHALL be returned

#### Scenario: Retention bound respected

- **WHEN** more messages are shown than the configured retention limit
- **THEN** the oldest message records SHALL be dropped
- **AND** the store SHALL never exceed the configured limit

### Requirement: Console Pack Works Without A Consumer

Publishing messages SHALL NOT require a console consumer to be connected or polling; the pack SHALL
degrade to retention-only behavior with no errors when nothing consumes the outbox.

#### Scenario: No consumer attached

- **WHEN** `console.show` is called and no Console has ever polled the outbox
- **THEN** the call SHALL succeed
- **AND** outbox retention bounds SHALL prevent unbounded growth
