# serve-server-management Specification

## Purpose

Defines read-only `ot.server()` status views plus mutable `ot_servers.*` actions for named proxy servers at runtime. Enable/disable state changes are in-memory only; restart re-reads the named server's entry from config on disk before reconnecting. No YAML configuration files are ever modified.
## Requirements
### Requirement: Server Listing

The system SHALL provide an `ot.server()` function that lists all configured
proxy servers and their status under both stdio root mode and Streamable HTTP
root mode.

#### Scenario: ot.server is read-only
- **WHEN** `ot.server()` and `ot.server(status="...")` are used
- **THEN** they SHALL NOT mutate server state
- **AND** runtime state changes SHALL be handled by `ot_servers.enable/disable/restart`

#### Scenario: List all servers
- **WHEN** `ot.server()` is called with no arguments
- **THEN** it SHALL return a formatted list of all configured servers
- **AND** each entry SHALL include the server name, enabled state, and connection status (connected/disconnected)
- **AND** connected servers SHALL show the number of tools they expose

#### Scenario: List servers under HTTP root mode
- **GIVEN** OneTool is running in Streamable HTTP root mode
- **WHEN** `ot.server()` is called through the root MCP server
- **THEN** it SHALL report the current in-memory proxy server state
- **AND** it SHALL NOT block unrelated HTTP MCP requests while reading that state
- **AND** it SHALL NOT mutate proxy configuration or runtime state

### Requirement: Server Status Query

The system SHALL support querying detailed status for a single named server.

#### Scenario: Show server status
- **WHEN** `ot.server(status="devtools-isolated")` is called
- **THEN** it SHALL return the connection state and tool count for that server

#### Scenario: Unknown server name
- **WHEN** `ot.server(status="unknown-server")` is called
- **THEN** it SHALL return an error message listing configured server names

### Requirement: Runtime Server Enable/Disable

The system SHALL support enabling and disabling named proxy servers at runtime
without restarting the MCP server, including under concurrent Streamable HTTP
root requests.

#### Scenario: Enable a disabled server
- **WHEN** `ot_servers.enable(name="devtools-auto")` is called
- **AND** `devtools-auto` is currently disabled
- **THEN** it SHALL set the server's enabled flag to true in-memory
- **AND** connect the server via `proxy_manager.connect_additional_sync()`
- **AND** return a confirmation message with tool count

#### Scenario: Disable an enabled server
- **WHEN** `ot_servers.disable(name="devtools-isolated")` is called
- **AND** `devtools-isolated` is currently enabled
- **THEN** it SHALL set the server's enabled flag to false in-memory
- **AND** disconnect the server
- **AND** return a confirmation message

#### Scenario: Concurrent HTTP root mutations
- **GIVEN** OneTool is running in Streamable HTTP root mode
- **WHEN** multiple clients concurrently call `ot_servers.enable`,
  `ot_servers.disable`, or `ot_servers.restart` for the same proxy server
- **THEN** those mutations SHALL be serialized or otherwise protected
- **AND** the final in-memory server state SHALL be consistent
- **AND** no proxy subprocess, transport, or registered tool mapping SHALL be
  left orphaned or duplicated

#### Scenario: Enable already-enabled server
- **WHEN** `ot_servers.enable(name="devtools-auto")` is called
- **AND** `devtools-auto` is already enabled and connected
- **THEN** it SHALL report that the server is already enabled
- **AND** SHALL NOT reconnect

#### Scenario: Disable already-disabled server
- **WHEN** `ot_servers.disable(name="devtools-auto")` is called
- **AND** `devtools-auto` is already disabled
- **THEN** it SHALL report that the server is already disabled

#### Scenario: Enable unknown server
- **WHEN** `ot_servers.enable(name="nonexistent")` is called
- **THEN** it SHALL return an error message listing configured server names

#### Scenario: State is in-memory only
- **WHEN** `ot_servers.enable(name="devtools-auto")` is called
- **THEN** the YAML configuration file SHALL NOT be modified
- **AND** the change SHALL be lost when the MCP server restarts

#### Scenario: HTTP root mutation does not modify YAML
- **GIVEN** OneTool is running in Streamable HTTP root mode
- **WHEN** `ot_servers.enable(name="devtools-auto")` or
  `ot_servers.disable(name="devtools-auto")` is called
- **THEN** the YAML configuration file SHALL NOT be modified
- **AND** the change SHALL be lost when the MCP server restarts

### Requirement: Server Restart

The system SHALL support restarting a named proxy server under both stdio root
mode and Streamable HTTP root mode. A restart SHALL re-read the named server's
configuration entry from disk before reconnecting, so "edit servers.yaml, then
restart" applies the new settings. A restart SHALL invalidate any cached
tool-name or parameter-name resolutions for that server so that calls after a
restart resolve against the server's current tool list, not a stale one.

#### Scenario: Restart a connected server
- **WHEN** `ot_servers.restart(name="devtools-isolated")` is called
- **THEN** it SHALL disconnect and reconnect the server
- **AND** return a confirmation message with tool count after reconnection

#### Scenario: Restart applies config edits from disk
- **GIVEN** a server's entry in `servers.yaml` has been edited since serve
  startup (e.g. `tool_prefix`, `command`, `args`, `env`, or `timeout` changed)
- **WHEN** `ot_servers.restart(name=...)` is called
- **THEN** it SHALL reconnect using the fresh on-disk configuration for that
  server
- **AND** the shared in-memory config entry for that server SHALL be replaced
  with the fresh one, so downstream consumers (e.g. the execution-namespace
  fingerprint keyed on `(name, tool_prefix)`) observe the change
- **AND** other servers' in-memory state (including runtime enable/disable
  toggles) SHALL NOT be affected

#### Scenario: Restart refuses a server removed from disk
- **GIVEN** the named server's entry has been removed from config on disk
- **WHEN** `ot_servers.restart(name=...)` is called
- **THEN** it SHALL return an error rather than reconnecting with the stale
  cached entry

#### Scenario: Restart surfaces an unreadable config
- **GIVEN** the config on disk fails to load (missing file or invalid YAML)
- **WHEN** `ot_servers.restart(name=...)` is called
- **THEN** it SHALL return an error message and SHALL NOT silently restart the
  server with the stale cached configuration

#### Scenario: Restart a disconnected server
- **WHEN** `ot_servers.restart(name="devtools-isolated")` is called
- **AND** the server is currently disconnected
- **THEN** it SHALL attempt to connect the server
- **AND** report success or failure

#### Scenario: Concurrent HTTP root restart
- **GIVEN** OneTool is running in Streamable HTTP root mode
- **WHEN** a proxy server restart races with status reads or enable/disable
  requests for the same server
- **THEN** runtime state SHALL remain internally consistent
- **AND** status reads SHALL return either the previous, connecting, failed, or
  connected state without raising an unhandled concurrency error

#### Scenario: Restart evicts the stale tool-accessor cache for that server
- **GIVEN** a proxy server `docs` is connected, and a prior call has cached a tool accessor (e.g. `docs.search_documentation`) resolving to a specific downstream tool name
- **AND** the downstream server is restarted with a changed tool schema (e.g. the tool is renamed or its parameters change)
- **WHEN** `ot_servers.restart(name="docs")` completes
- **THEN** subsequent calls to `docs.<accessor>(...)` SHALL resolve against the server's current (post-restart) tool list
- **AND** SHALL NOT silently reuse a pre-restart accessor-to-tool-name mapping

#### Scenario: Restart evicts the stale MCP parameter-name cache for that server
- **GIVEN** a proxy server `docs` is connected, and a prior call has cached the parameter names for one of its tools
- **AND** the downstream server is restarted with a changed parameter schema for that tool
- **WHEN** `ot_servers.restart(name="docs")` completes
- **THEN** subsequent calls resolving abbreviated parameter names for that tool SHALL use the server's current (post-restart) parameter schema
- **AND** SHALL NOT silently reuse pre-restart parameter names

### Requirement: Incremental server connect
The `ProxyManager` SHALL support connecting a single new server without disconnecting or reconnecting any existing server connections. When invoked from code already running on the `ProxyManager`'s own event loop, the synchronous wrapper SHALL NOT block that loop waiting on itself.

#### Scenario: Connect one new server
- **WHEN** `proxy_manager.connect_additional_sync(name, config)` is called
- **AND** `name` is not already in the connected servers
- **AND** `config.enabled` is true
- **THEN** the server SHALL be connected and its tools registered
- **AND** no other connected server SHALL be disconnected or restarted
- **AND** the method SHALL return a result string including tool count (e.g., `"ok (12 tools)"`)

#### Scenario: Server already connected
- **WHEN** `proxy_manager.connect_additional_sync(name, config)` is called
- **AND** `name` is already in the connected servers
- **THEN** the method SHALL return `"already connected"` without reconnecting

#### Scenario: Server disabled in config
- **WHEN** `proxy_manager.connect_additional_sync(name, config)` is called
- **AND** `config.enabled` is false
- **THEN** the method SHALL return `"disabled"` without connecting

#### Scenario: Connection failure
- **WHEN** `proxy_manager.connect_additional_sync(name, config)` is called
- **AND** the server process fails to start
- **THEN** the method SHALL record the error and return a `"failed: <reason>"` string
- **AND** no other connected server SHALL be affected

#### Scenario: connect_additional_sync called from its own event loop does not deadlock
- **GIVEN** `proxy_manager.connect_additional_sync(name, config)` is invoked from code currently running on the `ProxyManager`'s own event loop (e.g. inline user code executing on that loop that also issues a server-control call)
- **WHEN** the call is made
- **THEN** it SHALL NOT block that loop waiting on a `run_coroutine_threadsafe(...).result()` scheduled onto the same loop
- **AND** it SHALL return promptly (not after the multi-second/multi-minute blocking timeout)

### Requirement: Incremental server disconnect
The `ProxyManager` SHALL support disconnecting a single server without affecting any other server connections. When invoked from code already running on the `ProxyManager`'s own event loop, the synchronous wrapper SHALL NOT block that loop waiting on itself.

#### Scenario: Disconnect one server
- **WHEN** `proxy_manager.disconnect_server_sync(name)` is called
- **AND** `name` is currently connected
- **THEN** the server SHALL be disconnected and its tools unregistered
- **AND** the underlying transport SHALL be closed when the client exposes a close hook
- **AND** no other connected server SHALL be disconnected
- **AND** the method SHALL return `"disconnected"`

#### Scenario: Disconnect server not connected
- **WHEN** `proxy_manager.disconnect_server_sync(name)` is called
- **AND** `name` is not in the connected servers
- **THEN** the method SHALL return `"not connected"` without error

#### Scenario: Namespace cache invalidates after connect
- **WHEN** `proxy_manager.connect_additional_sync(name, config)` succeeds
- **THEN** the namespace cache SHALL reflect the newly connected server's tools on the next resolution

#### Scenario: Namespace cache invalidates after disconnect
- **WHEN** `proxy_manager.disconnect_server_sync(name)` succeeds
- **THEN** the namespace cache SHALL no longer include the disconnected server's tools on the next resolution

#### Scenario: disconnect_server_sync called from its own event loop does not deadlock
- **GIVEN** `proxy_manager.disconnect_server_sync(name)` is invoked from code currently running on the `ProxyManager`'s own event loop
- **WHEN** the call is made
- **THEN** it SHALL NOT block that loop waiting on a `run_coroutine_threadsafe(...).result()` scheduled onto the same loop
- **AND** it SHALL return promptly (not after the multi-second/multi-minute blocking timeout)

### Requirement: Serialized full proxy lifecycle

The `ProxyManager` SHALL serialize full reconnect and shutdown transitions on
its owning event loop. Shutdown SHALL cancel and await any tracked startup
generation before cleaning every client that generation registered, and SHALL
leave zero-, partial-, and full-client states reconnectable. A new generation
SHALL NOT begin until prior startup cleanup finishes.

Same-loop `ot.reload()` SHALL retain its immediate success return while the
serialized reconnect continues in the background. Proxy readiness SHALL report
that transition as connecting, then expose the actual connected or failed
result after it completes.

#### Scenario: Zero-client startup cancellation reconnects

- **GIVEN** background startup is blocked before registering any client
- **WHEN** a full reconnect cancels that startup
- **THEN** shutdown SHALL await the cancelled startup cleanup
- **AND** the fresh generation SHALL connect from a non-initialized state

#### Scenario: Delayed stale startup cannot cross generations

- **GIVEN** an old startup task delays its cancellation cleanup
- **WHEN** a reconnect is requested and that old task is later released
- **THEN** the fresh generation SHALL not start before the old task finishes
- **AND** any client registered by the old task SHALL be closed exactly once before the fresh generation starts
- **AND** no stale client SHALL remain in the fresh generation

#### Scenario: Partial and full shutdown reset lifecycle state

- **GIVEN** startup has registered some or all configured clients
- **WHEN** shutdown runs
- **THEN** every registered client SHALL be closed exactly once
- **AND** all connection metadata SHALL be cleared
- **AND** a subsequent reconnect SHALL be admitted

#### Scenario: Same-loop reload exposes eventual readiness

- **WHEN** `ot.reload()` schedules a same-loop full reconnect
- **THEN** it SHALL return its current immediate success string
- **AND** readiness SHALL report connecting until the background lifecycle task finishes
- **AND** readiness SHALL then report each configured server as connected or failed
