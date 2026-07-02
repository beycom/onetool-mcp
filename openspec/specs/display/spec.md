# display Specification

## Purpose

Provide an MCP-local display producer for rich artifacts and publish those artifacts to the separate OneTool Console App through the signed Console outbox protocol.

## Requirements

### Requirement: In-Process Display State And Console Outbox

The system SHALL keep display state in the current OneTool MCP server process and publish display changes to the MCP-owned Console outbox without starting a browser-facing service from `display.*` tool calls.

#### Scenario: Status initializes display state
- **WHEN** an agent calls `display.status()` before display state has been accessed in the current MCP process
- **THEN** the system creates or reuses display state for the current MCP process and returns metadata for that process

#### Scenario: Display tools do not start Console
- **WHEN** an agent calls any `display.*` tool
- **THEN** the tool call does not start the OneTool Console App or return a browser URL

#### Scenario: Console outbox routes are used
- **WHEN** the MCP-owned Direct API is running
- **THEN** MCP SHALL NOT expose browser-facing display routes under `/api/admin/display/...`
- **AND** Console SHALL consume display changes through `GET /api/console/outbox`

### Requirement: Display Show Tool

The system SHALL expose `display.show(...)` to create one typed user-visible display message, append a Console outbox event, and return path-first message metadata.

#### Scenario: Show creates message
- **WHEN** an agent calls `display.show(...)` with a valid kind and payload or payload reference
- **THEN** the system creates a display message in the current MCP instance timeline and returns `path`, `kind`, stable `id`, and `metadata`
- **AND** the message `id` SHALL be 12 lowercase hexadecimal characters with no prefix
- **AND** message ID generation SHALL retry on collisions within the current display instance

#### Scenario: Show appends Console event
- **WHEN** `display.show(...)` creates a display message
- **THEN** the system SHALL append a `display.message.created` event to the current MCP instance Console outbox
- **AND** the event SHALL use Console protocol payload modes `inline`, `file_ref`, or `file_diff_ref`

#### Scenario: Show does not start Console
- **WHEN** an agent calls `display.show(...)`
- **THEN** the system creates the message and outbox event without starting the OneTool Console App or returning a browser URL

#### Scenario: Show validates kind
- **WHEN** an agent calls `display.show(...)` with an unsupported kind
- **THEN** the system rejects the call through normal tool validation

#### Scenario: Show uses key-value metadata
- **WHEN** an agent calls `display.show(...)` with `metadata={"title": "Run", "task": "audit"}`
- **THEN** the system stores those values as message metadata only
- **AND** user-provided metadata SHALL NOT control rendering, routing, validation, payload selection, or display behavior

#### Scenario: Removed display fields are rejected
- **WHEN** an agent calls `display.show(...)` with removed top-level fields such as `title`, `summary`, `source`, `expand`, `language`, or `mime_type`
- **THEN** the system rejects the call through the current tool signature or request validation path

### Requirement: Display Clipboard Tool

The system SHALL expose `display.show_clip(...)` to resolve clipboard images or clipboard file paths into path-backed display messages.

#### Scenario: Clipboard contains image
- **WHEN** an agent calls `display.show_clip()` while the clipboard contains an image
- **THEN** the system saves the image using the same session storage and hash deduplication behavior as `image.load(img="clip")`
- **AND** the system creates an `image` display message for the stored image path

#### Scenario: Clipboard contains file or text path
- **WHEN** clipboard content resolves to an existing local file
- **THEN** the system creates an `image` message for supported images and a `file` message otherwise
- **AND** it SHALL NOT infer non-path display kinds from clipboard text

### Requirement: Typed V1 Display Kinds

The system SHALL support V1 display message kinds for `text`, `markdown`, `code`, `file`, `diff`, `file_diff`, `image`, `json`, `mermaid`, `yaml`, and `table`.

#### Scenario: Supported kind is accepted
- **WHEN** an agent calls `display.show(...)` with any V1 display kind and valid kind-specific payload
- **THEN** the system creates a message for that kind

### Requirement: Retention Limits

The system SHALL enforce bounded retention for MCP-side display producer messages, payload previews, and Console outbox events per MCP display instance.

#### Scenario: Long session reaches producer queue limit
- **WHEN** a display instance exceeds `display.max_queue_messages`
- **THEN** the MCP process removes the oldest message IDs and cached records FIFO
- **AND** removed messages are no longer available through MCP-side `display.list(...)`, `display.read(id=...)`, or retained Console outbox events
- **AND** Console state is the browser-facing owner for messages already ingested from MCP events

#### Scenario: Queue limit is configurable
- **WHEN** configuration sets `display.max_queue_messages`
- **THEN** the MCP-side producer queue SHALL enforce that positive limit capped by the implementation maximum of `5000`

#### Scenario: Payload previews are bounded
- **WHEN** a display payload is stored inline, generated from a file preview, or generated from a file diff
- **THEN** the system keeps model-visible preview text bounded to 64 KiB windows

#### Scenario: Inline payload views are bounded
- **WHEN** MCP returns a display payload view for a large inline string, dict, or list
- **THEN** the system returns a bounded string preview, a bounded preview envelope, or the first 500 list items rather than an unbounded payload

#### Scenario: Generated file diffs are bounded
- **WHEN** a generated file diff request compares two workspace files and either input is larger than 1 MiB
- **THEN** the system returns a bounded skip preview rather than reading both files into memory for diff generation

#### Scenario: Generated file diffs keep structured source paths
- **WHEN** a generated file diff request compares two workspace files
- **THEN** the payload reference stores the resolved old and new file paths as separate metadata fields
- **AND** the system does not flatten the pair into one ambiguous path string

### Requirement: Security And Persistence

Display producer state SHALL be in-session only. Console SHALL own browser-facing read models after it ingests outbox events.

#### Scenario: Unsafe paths are rejected
- **WHEN** a display payload path is a remote URL, a `file://` URL, or resolves outside allowed roots
- **THEN** display validation SHALL reject it before creating a message
