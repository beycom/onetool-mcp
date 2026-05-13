# tool-ide Specification

## Purpose
Define the read-only VS Code IDE state integration exposed through the `[dev]` `ide` tool pack and its local companion bridge.

## Requirements
### Requirement: IDE connection workflow
The system SHALL expose `ide.connect(id=...)` to select a user-facing VS Code connection id for subsequent IDE state calls.

#### Scenario: Connect validates and stores default
- **WHEN** `ide.connect(id="ot1")` is called for an active VS Code bridge connection
- **THEN** the tool SHALL validate the connection by fetching state for `ot1`
- **AND** it SHALL store `ot1` in memory
- **AND** it SHALL persist `packs.ide.connection_id: ot1` in project-local `.onetool/state.yaml`

#### Scenario: Stored default reused after restart
- **WHEN** an IDE state command is called without `id`
- **AND** no in-memory default exists
- **AND** project-local state contains `packs.ide.connection_id`
- **THEN** the tool SHALL use the project-local connection id

#### Scenario: Missing default rejected
- **WHEN** an IDE state command is called without `id`
- **AND** no default connection has been selected or persisted
- **THEN** the tool SHALL fail with a clear error instructing the caller to run `ide.connect(id=...)` or pass `id=...`

#### Scenario: Per-command override
- **WHEN** `ide.connect(id="main")` has selected a default connection
- **AND** `ide.sel(id="lib")` is called
- **THEN** the call SHALL target `lib`
- **AND** the stored default SHALL remain `main`

### Requirement: IDE state tool contract
The system SHALL expose `ide.state()` and `ide.get_state()` in the `[dev]` surface to retrieve read-only structured IDE state.

#### Scenario: Default include behavior
- **WHEN** `ide.state(id="ot1")` is called without `include`
- **THEN** the tool SHALL behave as `include="all"`

#### Scenario: Explicit include list
- **WHEN** `ide.state(id="ot1", include=["selection", "active_editor"])` is called
- **THEN** the tool SHALL return only the requested sections from the validated state snapshot

#### Scenario: Structured state is not externally wrapped
- **WHEN** callers use `ide.state()` or `ide.get_state()`
- **THEN** the tool SHALL return structured IDE state that is not wrapped in external-content boundaries

#### Scenario: Focused state helpers
- **WHEN** callers use `ide.sel()`, `ide.file()`, `ide.editor()`, `ide.workspace()`, or `ide.paths()`
- **THEN** each helper SHALL use the same default/override connection resolution as `ide.state()`
- **AND** each helper SHALL return concise plain text that is not wrapped in external-content boundaries

### Requirement: Include validation and grouping
The system SHALL accept only `"all"` or a list of `connection`, `selection`, `active_editor`, and `workspace` for `ide.state(include=...)`.

#### Scenario: Include all expands to all supported sections
- **WHEN** `ide.state(id="ot1", include="all")` is called
- **THEN** the response SHALL include `connection`, `selection`, `active_editor`, and `workspace`

#### Scenario: Workspace include covers workspace metadata
- **WHEN** `ide.state(id="ot1", include=["workspace"])` is called
- **THEN** the response SHALL include grouped `workspace.name`, `workspace.workspace_folders`, and `workspace.workspace_file`

#### Scenario: Invalid include value rejected
- **WHEN** `ide.state(id="ot1", include=["selection", "diagnostics"])` is called
- **THEN** the tool SHALL fail with a validation error listing the accepted include values

### Requirement: Bridge discovery and routing
The system SHALL route IDE state requests to a specific VS Code connection using a user-facing connection id discovered over loopback.

#### Scenario: Auto-port discovery succeeds
- **WHEN** `ide.connect(id="ot1")` is called without `tools.ide.base_url`
- **THEN** the pack SHALL scan `127.0.0.1:port_start..port_start + port_count - 1`
- **AND** it SHALL call authenticated `GET /health`
- **AND** it SHALL connect to the first bridge whose `connection.id` is `ot1`
- **AND** it SHALL cache the matched base URL in memory only

#### Scenario: Base URL override skips discovery
- **WHEN** `tools.ide.base_url` is configured
- **THEN** the pack SHALL use that loopback URL directly
- **AND** it SHALL NOT persist the URL or port to project state

#### Scenario: Cached URL rescan
- **WHEN** a cached discovered base URL fails due to connection, authentication, protocol, or unknown-connection failure
- **THEN** the pack SHALL clear the cached URL and rescan once
- **AND** it SHALL fail clearly if the rescan does not find a matching bridge

#### Scenario: Unknown connection rejected
- **WHEN** no authenticated bridge reports the requested connection id
- **THEN** the tool SHALL fail with a clear no-bridge or unknown-connection error

### Requirement: Authenticated read-only bridge
The system SHALL use an authenticated read-only HTTP bridge on `127.0.0.1` for IDE state retrieval.

#### Scenario: Bridge request uses get_state
- **WHEN** `ide.state(id="ot1")` is called
- **THEN** the pack SHALL use the `get_state` bridge operation on `POST /state`
- **AND** it SHALL NOT invoke editor mutation commands

#### Scenario: Health endpoint
- **WHEN** a client calls authenticated `GET /health`
- **THEN** the bridge SHALL return `ok`, `protocol_version`, `connection`, and `workspace`

#### Scenario: HMAC authentication required
- **WHEN** a request or response is missing a valid OneTool HMAC signature
- **THEN** the receiver SHALL reject it
- **AND** it SHALL NOT silently fall back to unauthenticated mode

#### Scenario: Replay rejected
- **WHEN** a request nonce is reused within the replay TTL
- **THEN** the bridge SHALL reject the replay with an unauthorized response

### Requirement: Bridge protocol versioning
The IDE bridge protocol version SHALL be the compatibility gate between the Python `ide` pack and the VS Code companion extension.

#### Scenario: Protocol mismatch rejected
- **WHEN** a bridge response or request uses a protocol version other than the supported version
- **THEN** the receiver SHALL reject it with a clear protocol mismatch error
- **AND** it SHALL NOT silently fall back to an older request or response shape

#### Scenario: Extension artifact version independent
- **WHEN** the root OneTool package version changes
- **THEN** the VS Code extension artifact version SHALL NOT be automatically rewritten to match it
- **AND** the extension SHALL keep the stable id `beycom.onetool-ide-vscode`

#### Scenario: Local extension build version
- **WHEN** `just build-ide-vscode` is run
- **THEN** it SHALL build a VSIX using an independent `1.0.0-dev.<build>` extension version
- **AND** it SHALL keep `package.json` and `package-lock.json` version metadata coherent
- **AND** repeated local builds SHALL generate increasing versions so VS Code can replace earlier local builds without `--force`

### Requirement: Snapshot schema and normalization
The system SHALL normalize the bridge response to a grouped snapshot shape containing `connection`, `workspace`, `active_editor`, and `selection`.

#### Scenario: Expanded state payload
- **WHEN** the bridge returns state
- **THEN** `connection.id` SHALL contain the user-facing connection id
- **AND** `workspace` SHALL include `name`, `workspace_folders`, and `workspace_file`
- **AND** `active_editor` SHALL include `visible_ranges` and `document.path`, `document.dirty`, and `document.untitled`
- **AND** `selection` SHALL include `path`, `ranges`, and `text`

#### Scenario: Absent singular values normalize to null
- **WHEN** the IDE has no active text editor or no active editor selection
- **THEN** `active_editor` or `selection` respectively SHALL be returned as `null`

#### Scenario: Absent collection values normalize to empty arrays
- **WHEN** the IDE has no workspace folders or active editor visible ranges
- **THEN** those collection fields SHALL be returned as empty arrays

#### Scenario: Malformed bridge response rejected
- **WHEN** the bridge returns a response missing required fields or with invalid field types
- **THEN** the tool SHALL fail with a schema validation error naming the invalid fields

### Requirement: Selection snapshot semantics
The system SHALL represent the active editor selection with path, ranges, and selected text from the live IDE buffer.

#### Scenario: Multiple selections returned in order
- **WHEN** there are multiple active text selections in the editor
- **THEN** `selection.ranges` SHALL preserve those ranges in editor order
- **AND** `selection.text` SHALL concatenate the selected text fragments in the same order

#### Scenario: No active selection
- **WHEN** there is no active text editor or no current selection context
- **THEN** `selection` SHALL be `null`

### Requirement: Active editor metadata and dirty-buffer behavior
The system SHALL expose active-editor metadata needed to reason about unsaved IDE state and viewport.

#### Scenario: Dirty active document flagged
- **WHEN** the active editor buffer has unsaved changes
- **THEN** `active_editor.document.dirty` SHALL be `true`

#### Scenario: Visible ranges returned
- **WHEN** the active editor has one or more visible ranges
- **THEN** `active_editor.visible_ranges` SHALL include start and end line numbers for each visible range

#### Scenario: Unsaved context caveat
- **WHEN** `active_editor.document.dirty` is `true`
- **THEN** `selection.text` SHALL remain authoritative for the selected region
- **AND** non-selected file content read later from disk MAY be stale relative to the editor buffer

### Requirement: Workspace and path behavior
The system SHALL return absolute paths without restricting results to the current OneTool project workspace.

#### Scenario: Workspace mismatch warns
- **WHEN** the returned IDE state does not align with the current OneTool working tree
- **THEN** the tool SHALL emit a warning
- **AND** it SHALL still return the validated IDE state

#### Scenario: Outside-workspace file allowed
- **WHEN** the active editor or selection points outside the current OneTool project
- **THEN** the tool SHALL return the absolute path
- **AND** it SHALL NOT treat that as an error

### Requirement: Companion extension connection ids
The VS Code companion extension SHALL derive a human-friendly connection id from the workspace/project name.

#### Scenario: Default connection id
- **WHEN** the extension starts in a workspace named `onetool-mcp`
- **THEN** the connection id SHALL be `onetool-mcp`

#### Scenario: Connection id is not manually renamed
- **WHEN** the extension package contributes commands
- **THEN** it SHALL NOT contribute a command that changes the connection id

#### Scenario: First available port
- **WHEN** the extension starts and `onetoolIde.portStart` is busy
- **THEN** it SHALL bind the first available port in the configured bounded range
- **AND** the status bar SHALL show the selected port
