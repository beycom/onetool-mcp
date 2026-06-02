## Purpose

Provide a local, user-facing display service for rich OneTool artifacts and bounded message navigation without turning display output into durable storage or model-visible context.

## Requirements

### Requirement: Lazy Local Display Service
The system SHALL provide a display service that starts lazily on the first `display.*` tool call, binds to `127.0.0.1`, and serves display UI/API routes for the current running OneTool MCP server process.

#### Scenario: Status starts display service
- **WHEN** an agent calls `display.status()` before the display service is running
- **THEN** the system starts the local display service and returns service metadata for the current MCP process

#### Scenario: Service uses local binding
- **WHEN** the display service starts
- **THEN** it binds to `127.0.0.1` and does not expose a public network listener

### Requirement: MCP Instance Scoping
The system SHALL assign each running OneTool MCP server process a generated `mcp_instance_id` and SHALL scope display UI state, messages, and API routes to that instance.

#### Scenario: Current process receives instance ID
- **WHEN** the first `display.*` call occurs in a running MCP process
- **THEN** the system creates or reuses a generated `mcp_instance_id` for that process

#### Scenario: Concurrent processes are separated
- **WHEN** two running MCP processes use the display service
- **THEN** each process has a separate instance route and message timeline

#### Scenario: Same process clients share timeline
- **WHEN** multiple browser clients connect to the same MCP instance route
- **THEN** they see the same display messages for that MCP instance

### Requirement: Display Status Tool
The system SHALL expose `display.status()` to return current display service and MCP instance metadata without creating messages or returning message payloads.

#### Scenario: Status returns clickable instance URL
- **WHEN** an agent calls `display.status()`
- **THEN** the result includes `status`, `mcp_instance_id`, `url`, `message_count`, `started_at`, and `updated_at`

#### Scenario: Status is metadata-only
- **WHEN** an agent calls `display.status()` after messages have been shown
- **THEN** the result reports counts and timestamps without returning message payloads

#### Scenario: Status does not create message
- **WHEN** an agent calls `display.status()`
- **THEN** the current instance message count is not increased by that call

### Requirement: Display Show Tool
The system SHALL expose `display.show(...)` to create one typed user-visible display message and return a stable message ID.

#### Scenario: Show creates message
- **WHEN** an agent calls `display.show(...)` with a valid kind and payload or payload reference
- **THEN** the system creates a display message in the current MCP instance timeline and returns its stable `id`

#### Scenario: Show starts display service
- **WHEN** an agent calls `display.show(...)` before the display service is running
- **THEN** the system starts the display service before creating the message

#### Scenario: Show validates kind
- **WHEN** an agent calls `display.show(...)` with an unsupported kind
- **THEN** the system rejects the call through normal tool validation

### Requirement: Typed V1 Display Kinds
The system SHALL support V1 display message kinds for `text`, `markdown`, `code`, `file`, `diff`, `file_diff`, `image`, `json`, `mermaid`, `yaml`, and `table`.

#### Scenario: Supported kind is accepted
- **WHEN** an agent calls `display.show(...)` with any V1 display kind and valid kind-specific payload
- **THEN** the system creates a message for that kind

#### Scenario: Table kind is bounded prototype
- **WHEN** an agent calls `display.show(...)` with kind `table`
- **THEN** the system provides a table display contract with at least an initial grid prototype and bounded payload handling

### Requirement: Payload References And Lazy Loading
The system SHALL keep large display payloads outside model-visible tool responses and SHALL load payload previews lazily through display service routes.

#### Scenario: Large file is referenced
- **WHEN** an agent shows a file, diff, image, table, or blob-like artifact
- **THEN** the tool response returns message identifiers and metadata without copying the full artifact content into the response

#### Scenario: Timeline returns metadata
- **WHEN** the browser loads a display timeline
- **THEN** the timeline response contains message metadata and summaries without eagerly returning every message payload

#### Scenario: Expanded row fetches preview
- **WHEN** a user expands a display row in the browser UI
- **THEN** the browser fetches the relevant bounded preview or payload view from the display service

### Requirement: Message Metadata Shape
The system SHALL store display messages as metadata records plus payload references rather than full eager payload records.

#### Scenario: Message record contains metadata
- **WHEN** the system creates a display message
- **THEN** the stored message record includes `id`, `kind`, timestamps, and payload reference metadata

#### Scenario: Message record supports summaries
- **WHEN** the system returns timeline or listing rows
- **THEN** each row can include lightweight display metadata such as title, summary, source, size, and status without full payload content

### Requirement: Retention Limits
The system SHALL enforce bounded in-memory retention for display messages and payload previews per MCP display instance.

#### Scenario: Long session reaches retention limit
- **WHEN** a display instance exceeds 1,000 retained message metadata records
- **THEN** the system evicts older in-memory message records without making persistence or archive recovery a V1 guarantee

#### Scenario: Payload previews are bounded
- **WHEN** a display payload is stored inline, generated from a file preview, or generated from a file diff
- **THEN** the system keeps model-visible preview text bounded to 64 KiB windows

#### Scenario: Inline payload views are bounded
- **WHEN** the browser requests a lazy payload view for a large inline string, dict, or list
- **THEN** the system returns a bounded string preview, a bounded preview envelope, or the first 500 list items rather than an unbounded payload

#### Scenario: Generated file diffs are bounded
- **WHEN** a generated file diff request compares two workspace files and either input is larger than 1 MiB
- **THEN** the system returns a bounded skip preview rather than reading both files into memory for diff generation

#### Scenario: Browser payload cache is bounded
- **WHEN** a browser client lazily loads many expanded payload views
- **THEN** the browser keeps at most 100 payload views cached in client state and prunes payloads for evicted messages

#### Scenario: Table grid rendering is bounded
- **WHEN** a table message contains many rows or columns
- **THEN** the browser renders a bounded grid preview of up to 200 rows by 80 columns

### Requirement: Display Read Tool
The system SHALL expose `display.read(id=...)` to return one display message record by ID with metadata, payload references, and bounded preview only.

#### Scenario: Read returns bounded message record
- **WHEN** an agent calls `display.read(id=...)` for an existing display message
- **THEN** the result includes message metadata, payload references, and any available bounded preview

#### Scenario: Read does not return full large payload
- **WHEN** an agent calls `display.read(id=...)` for a large artifact message
- **THEN** the result does not return the full large payload content

#### Scenario: Read rejects unknown message
- **WHEN** an agent calls `display.read(id=...)` with an ID that is not in the current MCP instance
- **THEN** the system returns an error for the missing message

### Requirement: Display Focus Tool
The system SHALL expose `display.focus(id=...)` to direct connected display UI clients to a specific message without returning payload content.

#### Scenario: Focus connected client
- **WHEN** an agent calls `display.focus(id=...)` for an existing message while a browser client is connected
- **THEN** the system sends a focus event and reports that it was delivered

#### Scenario: Focus queued for reconnect
- **WHEN** an agent calls `display.focus(id=...)` for an existing message while no browser client is connected
- **THEN** the system records the focus target and reports that delivery is queued or pending

#### Scenario: Focus rejects unknown message
- **WHEN** an agent calls `display.focus(id=...)` with an ID that is not in the current MCP instance
- **THEN** the system returns an error for the missing message

### Requirement: Metadata-Only Display List
If the system exposes `display.list(...)` in V1, it SHALL return a paginated, metadata-only message listing for ID recovery and lightweight navigation.

#### Scenario: List returns metadata page
- **WHEN** an agent calls `display.list(...)`
- **THEN** the result contains a page of message metadata such as `id`, `kind`, `title`, timestamps, source, size, and summary or status

#### Scenario: List omits full payloads
- **WHEN** an agent calls `display.list(...)`
- **THEN** the result does not include full display payload content

#### Scenario: List supports lightweight filters
- **WHEN** an agent calls `display.list(...)` with supported filters such as kind or source
- **THEN** the result applies those filters while still returning metadata only

### Requirement: Display Search Deferred
The system SHALL NOT expose `display.search(...)` in V1.

#### Scenario: Search is unavailable
- **WHEN** an agent attempts to call `display.search(...)`
- **THEN** the call fails through the normal unavailable-tool or validation path

### Requirement: Display Creation Name
The system SHALL use `display.show(...)` as the V1 message creation operation and SHALL NOT expose `display.create(...)` as an alias.

#### Scenario: Create alias is unavailable
- **WHEN** an agent attempts to call `display.create(...)`
- **THEN** the call fails through the normal unavailable-tool or validation path

### Requirement: Update And Delete Deferred
The system SHALL NOT expose agent-facing display message update or delete operations in V1.

#### Scenario: Update is unavailable
- **WHEN** an agent attempts to update an existing display message through a display tool
- **THEN** the call fails through the normal unavailable-tool or validation path

#### Scenario: Delete is unavailable
- **WHEN** an agent attempts to delete an existing display message through a display tool
- **THEN** the call fails through the normal unavailable-tool or validation path

### Requirement: Display Browser And API Routes
The system SHALL provide local browser and API routes scoped to the MCP instance for status, timeline/message creation, message reads, optional listing, focus events, file previews, diff previews, controlled open actions, and UI events.

#### Scenario: Instance page opens
- **WHEN** a user opens the URL returned by `display.status()`
- **THEN** the browser displays the message timeline for that MCP instance

#### Scenario: Message creation route stores message
- **WHEN** the display tool creates a message through the display service
- **THEN** the service stores the message in the current MCP instance timeline and makes it visible to connected clients

#### Scenario: Events route delivers focus
- **WHEN** a focus event is emitted for a connected MCP instance
- **THEN** the browser client receives the event through the instance event channel

### Requirement: File Preview Security
The system SHALL restrict file preview and open actions to allowed workspace roots and SHALL reject path traversal, outside-root paths, remote URLs, and untrusted `file://` URLs.

#### Scenario: Allowed file preview succeeds
- **WHEN** a display file preview request targets a file under an allowed workspace root
- **THEN** the system returns an allowed bounded preview for that file

#### Scenario: Outside-root file preview is forbidden
- **WHEN** a display file preview request targets a file outside allowed workspace roots
- **THEN** the system rejects the request as forbidden

#### Scenario: Path traversal is forbidden
- **WHEN** a display file preview request attempts path traversal outside an allowed workspace root
- **THEN** the system rejects the request as forbidden

#### Scenario: Remote URL display is rejected
- **WHEN** an agent or browser requests display of a remote URL in V1
- **THEN** the system rejects the request

### Requirement: HTML And Terminal Exclusions
The system SHALL NOT render HTML pages, inline HTML, or terminal/log renderer messages in V1.

#### Scenario: HTML kind is rejected
- **WHEN** an agent attempts to show an HTML page or inline HTML kind
- **THEN** the system rejects the call through normal validation

#### Scenario: Terminal kind is rejected
- **WHEN** an agent attempts to show a terminal or log renderer kind
- **THEN** the system rejects the call through normal validation

### Requirement: In-Session State Only
The system SHALL NOT guarantee display message survival across MCP server process restart.

#### Scenario: Restart creates fresh display state
- **WHEN** a OneTool MCP server process restarts
- **THEN** the new process receives fresh display instance state and is not required to recover prior display messages

#### Scenario: No V1 cache contract
- **WHEN** a OneTool MCP server process restarts
- **THEN** the system does not rely on a display cache to recover prior display messages

### Requirement: User-Initiated Open Actions
The system SHALL make editor or OS open actions explicit user-visible actions rather than automatic side effects of `display.status()` or `display.show(...)`.

#### Scenario: Status does not auto-open browser
- **WHEN** an agent calls `display.status()`
- **THEN** the system returns a URL and does not require automatically opening a browser

#### Scenario: Show does not auto-open editor
- **WHEN** an agent calls `display.show(...)` for a file message
- **THEN** the system creates the message without automatically opening the file in an editor or OS application

#### Scenario: Editor scheme integrations are configured
- **WHEN** editor-specific URL scheme integrations are supported
- **THEN** the system only enables them through explicit configuration or user-visible actions
