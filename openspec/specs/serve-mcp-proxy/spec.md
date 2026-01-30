# serve-mcp-proxy Specification

## Purpose

Enable OneTool to proxy external MCP servers, exposing their tools through OneTool's single `run` tool using pack dot-notation (e.g., `wix.ListWixSites()`).

## Requirements
### Requirement: Proxy Server Lifecycle

The system SHALL manage proxy MCP server connections through the server lifecycle.

#### Scenario: Startup connection
- **GIVEN** servers configured in onetool.yaml
- **WHEN** the OneTool server starts
- **THEN** it SHALL connect to all enabled MCP servers before accepting requests

#### Scenario: Startup connection failure
- **GIVEN** an MCP server that fails to connect
- **WHEN** the OneTool server starts
- **THEN** it SHALL log a warning and continue without that server
- **AND** other MCP servers SHALL still be available

#### Scenario: Shutdown cleanup
- **GIVEN** connected proxy MCP servers
- **WHEN** the OneTool server shuts down
- **THEN** it SHALL disconnect all MCP servers cleanly
- **AND** terminate any stdio subprocesses

#### Scenario: Parallel connection
- **GIVEN** multiple MCP servers configured
- **WHEN** the OneTool server starts
- **THEN** connections MAY be established in parallel for faster startup

### Requirement: Pack Tool Access

The system SHALL expose proxied MCP tools via pack dot-notation.

#### Scenario: Simple proxied tool call
- **GIVEN** MCP server `context7` with tool `resolve_library_id`
- **WHEN** run() receives `context7.resolve_library_id(library_name="next.js")`
- **THEN** it SHALL call the proxied tool and return the result

#### Scenario: Proxied tool with multiple arguments
- **GIVEN** MCP server `wix` with tool `get_product`
- **WHEN** run() receives `wix.get_product(product_id="abc", include_variants=True)`
- **THEN** it SHALL pass all arguments to the proxied tool

#### Scenario: Unknown proxy pack
- **GIVEN** no MCP server named `unknown` is configured
- **WHEN** run() receives `unknown.some_tool()`
- **THEN** it SHALL return an error listing available packs

#### Scenario: Unknown tool in pack
- **GIVEN** MCP server `wix` exists but has no tool `nonexistent`
- **WHEN** run() receives `wix.nonexistent()`
- **THEN** it SHALL return an error listing available tools in that pack

#### Scenario: Multiple proxy calls in one request
- **GIVEN** multiple MCP servers configured
- **WHEN** run() receives code with multiple pack calls (e.g., `sites = wix.list_sites(); pages = notion.search(query=sites[0].name)`)
- **THEN** it SHALL execute both calls and return combined results

### Requirement: Local Tool Precedence

The system SHALL prioritize local tools over proxied tools when names conflict.

#### Scenario: Pack collision
- **GIVEN** local pack `brave` with `web_search`
- **AND** proxied MCP named `brave` with `web_search`
- **WHEN** run() receives `brave.web_search(query="test")`
- **THEN** it SHALL use the local tool (local wins)

#### Scenario: No collision
- **GIVEN** local pack `brave` with `web_search`
- **AND** proxied MCP named `wix` with `list_sites`
- **WHEN** run() receives `wix.list_sites()`
- **THEN** it SHALL use the proxied tool

### Requirement: Proxy Tool Observability

The system SHALL log proxy operations with LogSpan.

#### Scenario: Proxy initialization logging
- **GIVEN** servers configured
- **WHEN** the server starts
- **THEN** it SHALL log `proxy.init` span with:
  - `serverCount`: Number of enabled servers to connect
  - `connected`: Number of successfully connected servers
  - `failed`: Number of servers that failed to connect
  - `toolCount`: Total number of tools across all connected servers

#### Scenario: Connection logging
- **GIVEN** an MCP server connection
- **WHEN** connection is established
- **THEN** it SHALL log `proxy.connect` span with:
  - `server`: Server name
  - `type`: http or stdio
  - `toolCount`: Number of tools discovered
  - `status`: SUCCESS or FAILED (auto-added by LogSpan)

#### Scenario: Tool call logging
- **GIVEN** a proxied tool is called
- **WHEN** the call completes
- **THEN** it SHALL log `proxy.tool.call` span with:
  - `server`: Server name
  - `tool`: Tool name
  - `resultLength`: Length of result string
  - `duration`: Call duration (auto-added by LogSpan)
  - `status`: SUCCESS or FAILED (auto-added by LogSpan)

#### Scenario: Error logging
- **GIVEN** a proxied tool call fails
- **WHEN** the error occurs
- **THEN** LogSpan SHALL automatically log with:
  - `status`: FAILED
  - `errorType`: Exception type
  - `errorMessage`: Error message

### Requirement: Proxy Introspection

The system SHALL provide utilities to inspect proxied MCP servers.

#### Scenario: List proxy servers
- **GIVEN** code `proxy.list_servers()`
- **WHEN** run() executes it
- **THEN** it SHALL return a list of configured MCP servers with:
  - Server name
  - Connection type (http/stdio)
  - Enabled status
  - Connection status

#### Scenario: List proxy tools
- **GIVEN** code `proxy.list_tools(server="wix")`
- **WHEN** run() executes it
- **THEN** it SHALL return a list of tools available on that server

#### Scenario: Unknown server for list_tools
- **GIVEN** code `proxy.list_tools(server="nonexistent")`
- **WHEN** run() executes it
- **THEN** it SHALL return an error with available server names

### Requirement: Async Proxy Execution

The system SHALL handle async proxy calls within the executor.

#### Scenario: Async tool call
- **GIVEN** a proxied tool is async
- **WHEN** run() calls it from sync code
- **THEN** it SHALL properly await the result

#### Scenario: Timeout handling
- **GIVEN** a proxied tool call exceeds timeout
- **WHEN** timeout is reached
- **THEN** it SHALL return an error with timeout details
- **AND** the operation SHALL be cancelled

### Requirement: HTTP Transport Support

The system SHALL support HTTP/SSE transport for remote MCP servers.

#### Scenario: HTTP with headers
- **GIVEN** HTTP MCP config with custom headers
- **WHEN** connecting
- **THEN** it SHALL include the headers in requests

#### Scenario: HTTPS required
- **GIVEN** HTTP MCP config with http:// URL
- **WHEN** connecting
- **THEN** it SHALL upgrade to https:// automatically

### Requirement: Stdio Transport Support

The system SHALL support stdio transport for local MCP servers.

#### Scenario: NPX command
- **GIVEN** stdio MCP config with `command: npx`
- **WHEN** connecting
- **THEN** it SHALL spawn the subprocess correctly

#### Scenario: Environment variables for subprocess
- **GIVEN** stdio MCP config with `env` section
- **WHEN** subprocess is spawned
- **THEN** environment variables SHALL be set with expanded values

#### Scenario: Subprocess crash
- **GIVEN** a stdio MCP subprocess crashes
- **WHEN** a tool call is attempted
- **THEN** it SHALL return an error indicating server unavailable
