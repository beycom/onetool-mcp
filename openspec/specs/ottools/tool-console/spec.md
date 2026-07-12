# tool-console Specification

## Purpose
Provide the agent-facing `console` pack for publishing messages to a connected
onetool-console consumer via the Console outbox: inline messages via `console.show`,
context-saving display of tool output and file references via `console.display`, and
bounded metadata retention with session-scoped disk bodies and list/read/clear
introspection.

## Requirements
### Requirement: Console Pack Inline Messages

The `console` pack SHALL let an agent publish inline messages to a connected onetool-console.
`console.show` SHALL accept inline content (string, mapping, or list), bound it to the
configured inline payload limit, retain message metadata in memory, atomically write the
preview and inline payload to the current instance's disk store, and append a body-free
`console.message.created` outbox entry (wire name fixed by protocol v1).

#### Scenario: Show an inline message

- **WHEN** an agent calls `console.show(content="build finished", kind="text")`
- **THEN** message metadata SHALL be retained in memory with a unique message id
- **AND** the preview and inline payload SHALL be written to the message's JSON body file
- **AND** a `console.message.created` event (wire name fixed by protocol v1) with `payload.mode: "inline"` SHALL be appended to the Console outbox

#### Scenario: Oversized inline content bounded

- **WHEN** `console.show` is called with content exceeding the inline payload bound
- **THEN** the disk-backed payload SHALL be truncated to the bound with truncation indicated
- **AND** the call SHALL succeed rather than error

### Requirement: Console Display With Digest Receipts

`console.display` SHALL accept exactly one input form — a positional value, `path`, or
`old_path` with `new_path` — publish it as one Console message, and return a single-line
string receipt of at most 240 characters beginning with the message id in the form
`console[<id>]`. Receipts SHALL summarize the payload structurally (row count and column
names for tables, top-level keys or item count for JSON, first line for text and markdown,
path with size and language for file references) and SHALL NOT embed more than 80
characters of payload content. Any other combination of input forms SHALL raise an error
without publishing.

When `kind` is not provided it SHALL be inferred: a list of dicts sharing at least 80% of
their keys infers `table`; other dicts and lists infer `json`; strings infer `markdown`
when markdown syntax signals are present, otherwise `text`; paths infer from extension
(`image`, `markdown`, `diff`, `code`, `json`, `yaml`, else `file`). An explicit `kind`
argument SHALL override inference.

#### Scenario: Composed tool result returns a receipt, not the value

- **WHEN** an agent executes `console.display(<tool call returning 20 uniform result dicts>)`
- **THEN** one `console.message.created` event with `payload.mode: "inline"` and kind `table` SHALL be appended to the outbox
- **AND** the tool SHALL return a one-line receipt containing the message id, kind, row count, and column names

#### Scenario: Receipt id resolves via console.read

- **WHEN** an agent calls `console.read(id=<id from a receipt>)`
- **THEN** the retained message for that receipt SHALL be returned

#### Scenario: Explicit kind overrides inference

- **WHEN** `console.display` receives a dict with `kind="yaml"`
- **THEN** the published message SHALL have kind `yaml`

### Requirement: Console Display File References

Given `path` pointing to an existing readable file whose realpath is contained in the
published `allowed_roots`, `console.display` SHALL publish a `file_ref` payload carrying
the absolute path, size, and detected MIME type and language — without the file content.
Textual files SHALL include a bounded head preview; binary files SHALL carry no preview
text. `old_path` with `new_path` SHALL publish a `file_diff_ref` payload with kind
defaulting to `diff`. A nonexistent or unreadable path SHALL raise an error without
publishing.

When a path's realpath falls outside `allowed_roots`, the tool SHALL NOT publish a file
reference and SHALL NOT widen the roots; it SHALL fall back to bounded inline publication
with `metadata.fallback = "outside-allowed-roots"` and state the fallback in the receipt.

#### Scenario: In-root file publishes a file_ref

- **WHEN** `console.display(path="/repo/src/app.py")` is called and `/repo/src` is under an allowed root
- **THEN** the published payload SHALL have mode `file_ref`, the absolute path, size, and detected language, with no file content in the event

#### Scenario: Outside-root path falls back to inline

- **WHEN** `console.display(path=...)` references a textual file outside every allowed root
- **THEN** the published message SHALL have `payload.mode: "inline"` with bounded content and `metadata.fallback` equal to `outside-allowed-roots`

### Requirement: Console Display Degrades Without Transport

Publishing SHALL NOT require a connected Console. With the direct host enabled, messages
SHALL be retained in the outbox within its retention bound regardless of consumers. With
the direct host disabled, `console.display` SHALL return the bounded preview text prefixed
with a note instead of a receipt, so content is never silently dropped.

#### Scenario: Direct host disabled

- **WHEN** `console.display` is called while the direct host is disabled
- **THEN** the tool SHALL return the bounded preview text prefixed with a note that the console is disabled

### Requirement: Console Message Retention And Introspection

The pack SHALL provide `console.list`, `console.read`, and `console.clear` over a bounded
message store scoped to the current runtime instance. Memory SHALL retain metadata only.
Each message body SHALL be stored as
`{CWD}/.onetool/state/console/instances/<instance-id>/messages/<message-id>.json` with
`id`, JSON-safe `metadata`, `preview`, and `inline_payload` fields. Body writes SHALL use
a temporary file in the same directory followed by atomic replacement.

#### Scenario: List and read retained messages

- **WHEN** messages have been shown and the agent calls `console.list` then `console.read` with a returned message id
- **THEN** `list` SHALL return message metadata (id, kind, created-at) newest-last with a bounded count
- **AND** `list` SHALL NOT read message body files
- **AND** `read` SHALL load and return the retained message body without retaining it in memory

#### Scenario: Body write fails

- **WHEN** a message body cannot be written and atomically replaced
- **THEN** message creation SHALL fail with the storage error
- **AND** no metadata record or partial body file SHALL be retained

#### Scenario: Clear removes retained messages and notifies

- **WHEN** the agent calls `console.clear`
- **THEN** retained message records SHALL be removed
- **AND** the current instance's messages directory SHALL be removed
- **AND** the cleared count SHALL be returned

#### Scenario: Retention bound respected

- **WHEN** more messages are shown than the configured retention limit
- **THEN** the oldest message records SHALL be dropped
- **AND** each dropped message's body file SHALL be unlinked
- **AND** the store SHALL never exceed the configured limit

### Requirement: Console Message Storage Lifecycle

Console message bodies SHALL exist only for their runtime session. Each instance
directory SHALL record its owning process id; server startup SHALL sweep sibling
instance directories whose owning process is no longer alive (a missing or unreadable
pid record counts as dead), leaving live concurrent sessions untouched. Normal shutdown
SHALL remove the current instance directory, and process exit SHALL register a
best-effort cleanup backstop. Cleanup SHALL not use age-based retention and SHALL not
read or migrate removed Display state paths.

#### Scenario: Runtime starts after an unclean exit

- **WHEN** a Console runtime instance starts with sibling instance directories present
- **THEN** siblings whose owning process is dead (or unrecorded) SHALL be removed before new messages are retained
- **AND** siblings owned by a live process SHALL be left in place

#### Scenario: Runtime shuts down normally

- **WHEN** the MCP server lifespan ends
- **THEN** the current Console instance directory SHALL be removed

### Requirement: Console Pack Works Without A Consumer

Publishing messages SHALL NOT require a console consumer to be connected or polling; the pack SHALL
degrade to retention-only behavior with no errors when nothing consumes the outbox.

#### Scenario: No consumer attached

- **WHEN** `console.show` is called and no Console has ever polled the outbox
- **THEN** the call SHALL succeed
- **AND** outbox retention bounds SHALL prevent unbounded growth
