## Purpose

Provide a local admin dashboard foundation with display as the first feature route for rich OneTool artifacts and bounded message navigation, without turning display output into durable storage or model-visible context.

## Requirements

### Requirement: In-Process Display State And Direct API Routes
The system SHALL keep display state in the current OneTool MCP server process and expose signed MCP Direct API routes for Admin App access without starting a browser-facing service from `display.*` tool calls.

#### Scenario: Status initializes display state
- **WHEN** an agent calls `display.status()` before display state has been accessed in the current MCP process
- **THEN** the system creates or reuses display state for the current MCP process and returns metadata for that process

#### Scenario: Display tools do not start Admin App
- **WHEN** an agent calls any `display.*` tool
- **THEN** the tool call does not start the shared Admin App or return a browser URL

#### Scenario: Signed Direct API routes are available
- **WHEN** the MCP-owned Direct API is running
- **THEN** signed routes under `/api/admin/display/...` expose display status, messages, payloads, previews, assets, focus, open, and events for the current MCP process

### Requirement: MCP Instance Scoping
The system SHALL assign each running OneTool MCP server process a generated `mcp_instance_id` and SHALL scope display UI state, messages, and API routes to that instance.

#### Scenario: Current process receives instance ID
- **WHEN** display state is first accessed in a running MCP process
- **THEN** the system creates or reuses a generated `mcp_instance_id` for that process

#### Scenario: Concurrent processes are separated
- **WHEN** two running MCP processes use display state
- **THEN** each process has a separate `mcp_instance_id` and message timeline

#### Scenario: Same process clients share timeline
- **WHEN** multiple browser clients inspect the same discovered MCP instance through the Admin App
- **THEN** they see the same display messages for that MCP instance

### Requirement: Display Status Tool
The system SHALL expose `display.status()` to return current display and MCP instance metadata without creating messages, returning message payloads, or returning browser URLs.

#### Scenario: Status returns metadata only
- **WHEN** an agent calls `display.status()`
- **THEN** the result includes `status`, `mcp_instance_id`, `message_count`, `started_at`, and `updated_at`
- **AND** the result does not include a browser URL

#### Scenario: Status is metadata-only
- **WHEN** an agent calls `display.status()` after messages have been shown
- **THEN** the result reports counts and timestamps without returning message payloads

#### Scenario: Status does not create message
- **WHEN** an agent calls `display.status()`
- **THEN** the current instance message count is not increased by that call

### Requirement: Display Show Tool
The system SHALL expose `display.show(...)` to create one typed user-visible display message and return path-first message metadata.

#### Scenario: Show creates message
- **WHEN** an agent calls `display.show(...)` with a valid kind and payload or payload reference
- **THEN** the system creates a display message in the current MCP instance timeline and returns `path`, `kind`, stable `id`, and `metadata`
- **AND** the message `id` SHALL be 12 lowercase hexadecimal characters with no prefix
- **AND** message ID generation SHALL retry on collisions within the current display instance

#### Scenario: Show does not start Admin App
- **WHEN** an agent calls `display.show(...)`
- **THEN** the system creates the message without starting the shared Admin App or returning a browser URL

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
- **AND** the response includes `path`, `kind: "image"`, `id`, and `metadata`

#### Scenario: Clipboard contains file list
- **WHEN** an agent calls `display.show_clip()` while the clipboard contains one or more file paths
- **THEN** the system uses the first file path
- **AND** the system creates an `image` display message when the file is a supported image
- **AND** the system creates a `file` display message otherwise

#### Scenario: Clipboard contains text path
- **WHEN** an agent calls `display.show_clip()` while the clipboard contains text
- **THEN** the system treats the text as a path only when it resolves to an existing file
- **AND** the system SHALL NOT infer markdown, diff, Mermaid, JSON, YAML, table, or other non-path display kinds from clipboard text

#### Scenario: Clipboard cannot resolve display path
- **WHEN** an agent calls `display.show_clip()` with an empty clipboard, non-image clipboard, or clipboard text that is not an existing file path
- **THEN** the system returns a clear error

### Requirement: Typed V1 Display Kinds
The system SHALL support V1 display message kinds for `text`, `markdown`, `code`, `file`, `diff`, `file_diff`, `image`, `json`, `mermaid`, `yaml`, and `table`.

#### Scenario: Supported kind is accepted
- **WHEN** an agent calls `display.show(...)` with any V1 display kind and valid kind-specific payload
- **THEN** the system creates a message for that kind

#### Scenario: Table kind is bounded prototype
- **WHEN** an agent calls `display.show(...)` with kind `table`
- **THEN** the system provides a table display contract with at least an initial grid prototype and bounded payload handling

### Requirement: Payload References And Lazy Loading
The system SHALL keep large display payloads outside model-visible tool responses and SHALL load payload previews lazily through signed Direct API routes proxied by the Admin App.

#### Scenario: Large file is referenced
- **WHEN** an agent shows a file, diff, image, table, or blob-like artifact
- **THEN** the tool response returns message identifiers and metadata without copying the full artifact content into the response

#### Scenario: Timeline returns metadata
- **WHEN** the browser loads a display timeline
- **THEN** the timeline response contains message metadata and summaries without eagerly returning every message payload

#### Scenario: Timeline row fetches fixed preview
- **WHEN** a user views the display timeline in the browser UI
- **THEN** each row fetches the relevant bounded preview or payload view and clips it to a bounded visual preview area without nested vertical scrollbars

#### Scenario: Recent messages are visible on initial browser load
- **WHEN** a display instance has more messages than the browser's initial page size
- **THEN** the browser timeline SHALL load the latest message page initially while preserving oldest-to-newest visual order within that page
- **AND** recent `display.show(...)` messages SHALL become visible quickly in high-volume sessions

#### Scenario: Timeline exposes scroll-to-bottom affordance
- **WHEN** a user is not viewing the newest loaded message or unseen messages arrive
- **THEN** the browser SHALL expose a scroll-to-bottom control that jumps to the newest loaded message without stealing scroll while the user is reading older messages

#### Scenario: Message actions use overflow menu
- **WHEN** a user opens message actions in the browser UI
- **THEN** the browser shows an overflow menu with secondary text-labeled actions such as copy path and rich view toggle
- **AND** copy content is exposed as a standalone row toolbar icon
- **AND** copy path is not exposed as a standalone row toolbar icon
- **AND** timeline rows for inline message kinds SHALL expose visible toolbar actions as copy content, message info, then open in side panel
- **AND** timeline rows for openable file-backed message kinds SHALL order visible toolbar actions as copy content, message info, open in side panel, then open
- **AND** timeline rows SHALL NOT show the overflow menu as a visible toolbar button
- **AND** side panel rows SHALL expose message info as a visible toolbar action
- **AND** file-backed side panel rows SHALL order visible toolbar actions as overflow menu, message info, then open file
- **AND** selecting an overflow menu item SHALL close the overflow menu after invoking the item action
- **AND** message info SHALL include core message fields, payload references, and caller-provided key-value metadata except `summary`
- **AND** message info SHALL label preview line count as `Lines`
- **AND** message info SHALL NOT show message status, payload mode, or raw timestamp strings next to formatted timestamps

#### Scenario: File previews use content-aware renderers
- **WHEN** a user opens a file display message with known language, MIME type, or extension metadata
- **THEN** the browser routes markdown, JSON, YAML, and code-like files through the matching rich renderer while unknown files use a raw text fallback
- **AND** markdown files SHALL render as continuous documents without page-like vertical gaps between normal block elements
- **AND** file-backed JSON and YAML renderers SHALL parse the fetched preview/source text when no inline structured content is present

#### Scenario: Rich rendering can be disabled
- **WHEN** a user disables rich view for a message in the browser UI
- **THEN** the browser shows the bounded raw/source payload for that message instead of the rich renderer
- **AND** the user can enable rich view again without reloading the display page

#### Scenario: Structured payloads have tree and source views
- **WHEN** a user views JSON or YAML display content in the browser UI
- **THEN** the browser provides a collapsible structured tree view and a source-code view
- **AND** the tree/source segmented control SHALL size to its content instead of stretching across the message body
- **AND** collapsing the root node SHALL keep the collapsed root row directly below the tree/source controls without introducing blank vertical gaps
- **AND** valid structured file previews SHALL NOT render as `root undefined` or as a single quoted source string in tree mode

#### Scenario: Mermaid payloads have render and source views
- **WHEN** a user views Mermaid display content in the browser UI
- **THEN** the browser provides rendered diagram controls for pan, zoom, reset, and fit plus a source-code view

### Requirement: Message Metadata Shape
The system SHALL store display messages as metadata records plus payload references rather than full eager payload records.

#### Scenario: Message record contains metadata
- **WHEN** the system creates a display message
- **THEN** the stored message record includes `id`, `kind`, key-value metadata, timestamps, and payload reference metadata

#### Scenario: Message record supports summaries
- **WHEN** the system returns timeline or listing rows
- **THEN** each row can include lightweight display metadata such as key-value user metadata, size, and status without full payload content
- **AND** the system SHALL NOT generate default `summary` metadata
- **AND** the browser timeline preview is not required to display title, summary, kind, byte count, or line count as row chrome
- **AND** the browser timeline and side panel SHALL NOT display generic title or summary chrome by default
- **AND** file-backed `file`, `image`, and `file_diff` rows SHALL display a compact filename header above the payload while keeping the full path available through message info or actions
- **AND** file-backed rows SHALL NOT repeat the file path or filename in footer metadata
- **AND** file-backed source renderers SHALL NOT duplicate the compact filename header inside the payload body
- **AND** footer message IDs SHALL show the full 12-character display message ID
- **AND** browser-rendered message timestamps SHALL use `HH:mm, dd-Mon` format, such as `23:01, 03-Jun`

#### Scenario: Text payloads render as plain content
- **WHEN** a user views a `text` display message in rich mode
- **THEN** the browser renders the payload as plain text on the message card background
- **AND** the browser SHALL NOT wrap the text in code-style raw block chrome unless rich rendering is disabled

### Requirement: Retention Limits
The system SHALL enforce bounded retention for MCP-side display producer messages and payload previews per MCP display instance.

#### Scenario: Long session reaches producer queue limit
- **WHEN** a display instance exceeds `display.max_queue_messages`
- **THEN** the MCP process removes the oldest message IDs and cached records FIFO
- **AND** removed messages are no longer available through MCP-side `display.list(...)`, `display.read(id=...)`, or signed display routes
- **AND** Admin App state is the browser-facing owner for messages already ingested from MCP events

#### Scenario: Queue limit is configurable
- **WHEN** configuration sets `display.max_queue_messages`
- **THEN** the MCP-side producer queue SHALL enforce that positive limit capped by the implementation maximum of `5000`

#### Scenario: Payload previews are bounded
- **WHEN** a display payload is stored inline, generated from a file preview, or generated from a file diff
- **THEN** the system keeps model-visible preview text bounded to 64 KiB windows

#### Scenario: Inline payload views are bounded
- **WHEN** the browser requests a lazy payload view for a large inline string, dict, or list
- **THEN** the system returns a bounded string preview, a bounded preview envelope, or the first 500 list items rather than an unbounded payload

#### Scenario: Generated file diffs are bounded
- **WHEN** a generated file diff request compares two workspace files and either input is larger than 1 MiB
- **THEN** the system returns a bounded skip preview rather than reading both files into memory for diff generation

#### Scenario: Generated file diffs keep structured source paths
- **WHEN** a generated file diff request compares two workspace files
- **THEN** the payload reference stores the resolved old and new file paths as separate metadata fields
- **AND** the system does not flatten the pair into one ambiguous path string

#### Scenario: Browser payload cache is bounded
- **WHEN** a browser client lazily loads many expanded payload views
- **THEN** the browser keeps at most 100 payload views cached in client state and prunes payloads for evicted messages

#### Scenario: Browser uses query-scoped server state
- **WHEN** the browser loads display/admin API data
- **THEN** server state is fetched and cached through query keys scoped by display instance and resource type
- **AND** message list queries use keys equivalent to `["display", instance_id, "messages"]`
- **AND** payload queries use keys equivalent to `["display", instance_id, "payload", message_id]`
- **AND** view-only UI state such as selected panel message, panel width, rich/raw toggles, theme, and scroll state remains local UI state

#### Scenario: Timeline payload loading follows user intent
- **WHEN** the browser renders a display timeline with many messages
- **THEN** timeline rows SHALL NOT fetch every message payload as a render side effect
- **AND** the browser MAY prefetch only a small bounded recent-message window
- **AND** selected, focused, hovered, copied, or inspector-opened messages MAY fetch their payload lazily

#### Scenario: Table grid rendering is bounded
- **WHEN** a table message contains many rows or columns
- **THEN** the browser renders a bounded grid preview of up to 200 rows by 80 columns
- **AND** the browser SHALL NOT show row/column truncation status text above the grid

#### Scenario: Browser side panel uses bounded layout
- **WHEN** a user opens a long payload in the browser side panel
- **THEN** the inspector uses the available panel height without nested vertical scroll caps causing scroll bounce
- **AND** the selected message chrome and action toolbar SHALL remain fixed while the message payload area scrolls
- **AND** long code/file lines SHALL remain horizontally scrollable through the inspector panel container
- **AND** inspector payload renderers SHALL NOT place their own horizontal scrollbar above the bottom of the side panel
- **AND** the browser line wrapping setting SHALL apply consistently to plain text, raw text, code/source, structured source, and diff renderers
- **AND** disabling line wrapping SHALL expose horizontal scrolling instead of clipping long text/source lines

#### Scenario: Browser side panel matches message layout
- **WHEN** a user opens a message in the browser side panel
- **THEN** the side panel uses the same message title, floating action, payload, and metadata layout as timeline message rows
- **AND** the side panel does not render a separate inspector header band or separator above the selected message content

#### Scenario: Renderer failures are isolated
- **WHEN** one payload renderer fails while rendering a timeline row or inspector payload
- **THEN** the browser SHALL show a recoverable preview error for that message
- **AND** the rest of the display app SHALL remain usable

#### Scenario: Structured renderers are bounded
- **WHEN** the browser renders JSON or YAML payloads
- **THEN** parsing and tree rendering SHALL be bounded by source size, depth, and sibling count
- **AND** oversized or invalid content SHALL remain usable through a source fallback
- **AND** collapsed tree nodes SHALL NOT render their descendants

#### Scenario: Mermaid SVG is sanitized
- **WHEN** the browser renders a Mermaid diagram
- **THEN** generated SVG SHALL be sanitized before DOM insertion
- **AND** unsafe tags, scriptable attributes, and executable links SHALL be removed

#### Scenario: Heavy renderers are lazy loaded
- **WHEN** the browser loads the display app shell
- **THEN** heavyweight markdown, code/highlighting, diff, Mermaid, structured data, table, image, and file renderers SHOULD be split from the initial app shell where supported by the frontend build

#### Scenario: Split Admin UI assets are served locally
- **WHEN** the packaged Admin UI build emits split frontend assets
- **THEN** the shared Admin App SHALL serve those assets from `onetool_admin_ui/dist/**`
- **AND** Python packaging SHALL include the generated Admin UI asset directory in wheel and sdist builds
- **AND** generated package assets SHALL NOT require editable installs from a fresh checkout to have already run the frontend build

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

### Requirement: Display Clear Tool
The system SHALL expose `display.clear()` to remove all messages from the current display instance timeline without deleting individual messages by ID.

#### Scenario: Clear removes current instance messages
- **WHEN** an agent calls `display.clear()` after messages have been shown
- **THEN** the system removes all hot and cold messages for the current MCP instance
- **AND** subsequent `display.list(...)` calls return zero messages
- **AND** subsequent `display.read(id=...)` calls for cleared message IDs return missing-message errors
- **AND** `display.status()` reports `message_count` as `0`

#### Scenario: Clear notifies connected clients
- **WHEN** an agent calls `display.clear()` while display browser clients are connected
- **THEN** the system emits a display event that causes clients to refresh their timeline to the empty state

### Requirement: Metadata-Only Display List
If the system exposes `display.list(...)` in V1, it SHALL return a paginated, metadata-only message listing for ID recovery and lightweight navigation.

#### Scenario: List returns metadata page
- **WHEN** an agent calls `display.list(...)`
- **THEN** the result contains a page of message metadata such as `id`, `kind`, key-value metadata, timestamps, size, and status

#### Scenario: List omits full payloads
- **WHEN** an agent calls `display.list(...)`
- **THEN** the result does not include full display payload content

#### Scenario: List supports lightweight filters
- **WHEN** an agent calls `display.list(...)` with supported filters such as kind or source
- **THEN** the result applies those filters against message kind and the explicit `source` metadata key while still returning metadata only

#### Scenario: List rejects invalid pagination
- **WHEN** an agent calls `display.list(...)` with `limit` outside 1 through 500 or `offset` below 0
- **THEN** the system rejects the call through normal tool validation instead of silently clamping the values

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

### Requirement: Update And Individual Delete Deferred
The system SHALL NOT expose agent-facing display message update or individual message delete operations in V1.

#### Scenario: Update is unavailable
- **WHEN** an agent attempts to update an existing display message through a display tool
- **THEN** the call fails through the normal unavailable-tool or validation path

#### Scenario: Individual delete is unavailable
- **WHEN** an agent attempts to delete an existing display message through a display tool
- **THEN** the call fails through the normal unavailable-tool or validation path

### Requirement: Test-Only Display Fixture Tool
The system SHALL expose a temporary `display.seed_mock_messages(...)` fixture tool during display/admin UI development.

#### Scenario: Fixture seeds all V1 kinds
- **WHEN** an agent calls `display.seed_mock_messages(...)`
- **THEN** the tool SHALL create representative messages for every V1 display kind through the normal display state path
- **AND** the response SHALL be metadata-only, including the MCP instance ID, count, IDs by kind, and `test_only: true`
- **AND** the tool SHALL be marked test-only in code/docs

### Requirement: Admin App Display Browser And API Routes
The system SHALL provide shared Admin App browser and API routes for accepting MCP Direct API registrations, listing registered instances, reconciling heartbeat state, and proxying display status, timeline/message creation, message reads, listing, focus events, file previews, diff previews, controlled open actions, and UI events through signed server-side Direct API calls.

#### Scenario: MCP registration discovers display instances
- **WHEN** an MCP process posts a Direct API `base_url` to `/api/admin/register`
- **THEN** the Admin App verifies the registered Direct API using signed `/health`, `/ready`, and `/api/admin/bootstrap` requests
- **AND** verified instances are stored in the Admin App's in-memory instance list

#### Scenario: Scan reconciles registered instances
- **WHEN** a user requests Scan from the browser
- **THEN** the Admin App marks connected instances disconnected after missed heartbeats derived from each instance heartbeat interval
- **AND** Scan SHALL NOT probe a Direct API port range

#### Scenario: Admin App lists discovered instances
- **WHEN** a browser requests the Admin App instance list
- **THEN** the Admin App returns the current in-memory discovered MCP instances with browser-safe metadata

#### Scenario: Display APIs use admin namespace
- **WHEN** a browser client reads or mutates display state
- **THEN** it uses same-origin Admin App routes under `/api/admin/...`
- **AND** the Admin App proxies those requests to the selected MCP instance through signed Direct API calls

#### Scenario: Admin App marks failed instances disconnected
- **WHEN** a proxied display request to a discovered MCP instance fails
- **THEN** the Admin App marks that instance `disconnected` in its in-memory instance list

#### Scenario: Browser UI supports message inspection actions
- **WHEN** a user views a message in the timeline or inspector panel
- **THEN** the browser exposes copy content, copy path, and controlled file open actions in the message header area, with visible failed-open feedback
- **AND** the controlled file open action SHALL use a compact icon button with accessible label/tooltip text

#### Scenario: Browser UI follows display theme for rendered diffs
- **WHEN** a user views parsed diff content in light or dark display mode
- **THEN** the diff renderer uses the corresponding light or dark code theme

#### Scenario: Browser inspector width is adjustable
- **WHEN** a user drags the separator between the timeline and inspector
- **THEN** the browser resizes the inspector within usable minimum widths and preserves that width locally for reloads

#### Scenario: Admin frontend uses adopted foundation stack
- **WHEN** the packaged display/admin UI is built
- **THEN** it uses Vite, React, TypeScript, TanStack Router, TanStack Query, TanStack Table, Radix-compatible UI primitives, Tailwind as the styling foundation, Recharts availability, and lucide icons
- **AND** Python serves built static assets without requiring Node at runtime

#### Scenario: Message creation route stores message
- **WHEN** the display tool creates a message through display state
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
- **THEN** the system does not rely on the display cold-message cache to recover prior display messages

### Requirement: User-Initiated Open Actions
The system SHALL make editor or OS open actions explicit user-visible actions rather than automatic side effects of `display.status()` or `display.show(...)`.

#### Scenario: Status does not auto-open browser
- **WHEN** an agent calls `display.status()`
- **THEN** the system returns metadata only and does not automatically open a browser or start the Admin App

#### Scenario: Show does not auto-open editor
- **WHEN** an agent calls `display.show(...)` for a file message
- **THEN** the system creates the message without automatically opening the file in an editor or OS application

#### Scenario: Editor scheme integrations are configured
- **WHEN** editor-specific URL scheme integrations are supported
- **THEN** the system only enables them through explicit configuration or user-visible actions
