## MODIFIED Requirements

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

### Requirement: Server Restart

The system SHALL support restarting a named proxy server under both stdio root
mode and Streamable HTTP root mode. A restart SHALL invalidate any cached
tool-name or parameter-name resolutions for that server so that calls after a
restart resolve against the server's current tool list, not a stale one.

#### Scenario: Restart a connected server
- **WHEN** `ot_servers.restart(name="devtools-isolated")` is called
- **THEN** it SHALL disconnect and reconnect the server
- **AND** return a confirmation message with tool count after reconnection

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
