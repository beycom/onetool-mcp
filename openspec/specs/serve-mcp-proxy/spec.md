# serve-mcp-proxy Specification

## Purpose

Enable OneTool to proxy external MCP servers, exposing their tools through OneTool's single `run` tool using pack dot-notation (e.g., `wix.ListWixSites()`).
## Requirements
### Requirement: Proxy Server Lifecycle

The system SHALL manage proxy MCP server connections through the server lifecycle, and SHALL
sanitize connect-error strings before they are stored or surfaced to the agent or logs.

#### Scenario: Startup connection
- **GIVEN** servers configured in onetool.yaml
- **WHEN** the OneTool server starts
- **THEN** it SHALL begin connecting to all enabled MCP servers
- **AND** readiness/status surfaces SHALL distinguish proxy servers that are connected, connecting, or failed

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
- **THEN** connections SHALL be established independently so one slow server does not delay unrelated servers
- **AND** failures SHALL be recorded per server without failing unrelated connections

#### Scenario: Connect-error strings sanitized before surfacing
- **GIVEN** an MCP server connection attempt fails with an exception whose string representation
  could contain an `Authorization`/`Bearer`/`Basic`-style credential fragment (e.g. built from a
  decrypted secret used as a bearer token for an HTTP-transport server)
- **WHEN** the error is stored in `self._errors[name]` (`src/ot/proxy/manager.py:489,733`) for
  later surfacing via `ot.servers()`/status output
- **THEN** the stored string SHALL have any `Authorization:`/`Bearer `/`Basic `-prefixed credential
  fragments stripped or redacted before storage
- **AND** the sanitized string SHALL still identify the failure reason (e.g. connection
  refused/timeout/DNS failure) so the error remains diagnosable

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

### Requirement: Tool Name Aliasing

The system SHALL support automatic aliasing for MCP tools with non-Python-friendly names.

MCP servers may use naming conventions incompatible with Python identifiers (e.g., hyphens in `list-accounts`). The system SHALL transparently resolve Python-friendly accessors to actual tool names via canonical normalization.

#### Scenario: Hyphenated tool access via underscores
- **GIVEN** MCP server `github` with tool `list-organisation-details`
- **WHEN** run() receives `github.list_organisation_details()`
- **THEN** it SHALL resolve to tool `list-organisation-details` and call it

#### Scenario: Hyphenated tool access via camelCase
- **GIVEN** MCP server `github` with tool `list-organisation-details`
- **WHEN** run() receives `github.listOrganisationDetails()`
- **THEN** it SHALL resolve to tool `list-organisation-details` and call it

#### Scenario: Hyphenated tool access via PascalCase
- **GIVEN** MCP server `github` with tool `list-organisation-details`
- **WHEN** run() receives `github.ListOrganisationDetails()`
- **THEN** it SHALL resolve to tool `list-organisation-details` and call it

#### Scenario: Exact match takes precedence
- **GIVEN** MCP server has both `list_accounts` and `list-accounts`
- **WHEN** run() receives `github.list_accounts()`
- **THEN** it SHALL use exact match `list_accounts` (no fuzzy matching needed)

#### Scenario: Ambiguous match error
- **GIVEN** MCP server has tools `list-accounts` and `list_accounts` (both normalize to same canonical form)
- **WHEN** run() receives `github.listAccounts()`
- **THEN** it SHALL return an error: "Ambiguous tool name 'listAccounts': matches multiple tools: ['list-accounts', 'list_accounts']"

#### Scenario: No match with suggestions
- **GIVEN** MCP server `github` with tool `list-organisation-details`
- **WHEN** run() receives `github.list_organisat()`
- **THEN** it SHALL return an error with suggestions
- **AND** suggestions SHALL include `list-organisation-details`

#### Scenario: Mixed separators and case
- **GIVEN** MCP server with tool `get-user-account`
- **WHEN** run() receives any of: `getUserAccount()`, `get_user_account()`, `GetUserAccount()`, `GET_USER_ACCOUNT()`
- **THEN** all SHALL resolve to tool `get-user-account`

#### Scenario: Canonical normalization rules
- **GIVEN** any tool name
- **WHEN** canonical form is computed
- **THEN** it SHALL:
  - Remove all hyphens (`-`)
  - Remove all underscores (`_`)
  - Convert to lowercase
  - Example: `list-Account_Details` → `listaccountdetails`

### Requirement: Server Name Aliasing

The system SHALL expose MCP servers via Python-accessible namespace aliases when the server name contains hyphens.

Server names with hyphens cannot be used as Python variable names (e.g., `billing-service` is parsed as subtraction, not a namespace). The system SHALL register Python-safe aliases so users can call tools via dot notation.

#### Scenario: hyphenated server gets generic underscore alias

- **GIVEN** a hyphenated MCP server is connected (e.g., `billing-service`)
- **WHEN** the execution namespace is built
- **THEN** the full name with hyphens replaced by underscores SHALL be accessible as a variable (e.g., `billing_service`)
- **AND** `billing-service` -> `billing_service`, `cost-explorer` -> `cost_explorer`, `well-architected` -> `well_architected`

#### Scenario: Hyphenated server gets underscore primary + warning

- **GIVEN** an MCP server whose name contains hyphens (e.g., `my-server`)
- **WHEN** the execution namespace is built
- **THEN** the underscore form SHALL be the primary namespace key (e.g., `my_server`)
- **AND** the original hyphen name SHALL also be accessible as an exact server-name key for namespace-dictionary lookups
- **AND** a `UserWarning` SHALL be emitted advising to rename the config key to underscore form

#### Scenario: Alias does not overwrite existing local pack

- **GIVEN** a local pack named `iam` already exists in the namespace
- **AND** a `billing-service` server is connected
- **WHEN** the execution namespace is built
- **THEN** the existing `iam` local pack SHALL take precedence
- **AND** `billing-service` SHALL still be accessible via the full hyphenated key for exact server-name access

### Requirement: Tool Prefix Omission

Some MCP servers expose tools whose names carry a prefix that is redundant when accessed via dot notation (e.g., a docs server exposes `docs_search_documentation` but callers write `knowledge.search_documentation()`). The system SHALL support a `tool_prefix` config field on `McpServerConfig` that enables prefix-omission when resolving tool names.

When `tool_prefix` is declared for a server, the proxy pack SHALL attempt a second match with the prefix prepended if the first canonical match fails. This allows callers to omit the prefix entirely.

#### Scenario: Caller omits tool prefix

- **GIVEN** a server with `tool_prefix: "docs_"` connected as `docs-knowledge`
- **AND** the server exposes a tool named `docs_search_documentation`
- **WHEN** code calls `knowledge.search_documentation()`
- **THEN** the system SHALL resolve it to `docs_search_documentation` via prefix prepend
- **AND** SHALL call the tool successfully

#### Scenario: Exact prefixed name still works

- **GIVEN** a server with `tool_prefix: "docs_"` configured
- **WHEN** code calls `knowledge.docs_search_documentation()`
- **THEN** the exact tool name SHALL match directly (prefix not prepended again)

#### Scenario: No tool_prefix — no fallback

- **GIVEN** a server with no `tool_prefix` configured
- **AND** the server exposes `docs_search_documentation`
- **WHEN** code calls `server.search_documentation()`
- **THEN** the system SHALL raise `AttributeError` (no prefix fallback attempted)

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

The system SHALL emit structured runtime log events for proxy operations.

#### Scenario: Proxy initialization logging
- **GIVEN** servers configured
- **WHEN** the server starts
- **THEN** it SHALL log a `proxy.init` event with:
  - `serverCount`: Number of enabled servers to connect
  - `connected`: Number of successfully connected servers
  - `failed`: Number of servers that failed to connect
  - `toolCount`: Total number of tools across all connected servers

#### Scenario: Connection logging
- **GIVEN** an MCP server connection
- **WHEN** connection is established
- **THEN** it SHALL log a `proxy.connect` event with:
  - `server`: Server name
  - `type`: http or stdio
  - `toolCount`: Number of tools discovered
  - `status`: SUCCESS or FAILED

#### Scenario: Tool call logging
- **GIVEN** a proxied tool is called
- **WHEN** the call completes
- **THEN** it SHALL log a `proxy.tool.call` event with:
  - `server`: Server name
  - `tool`: Tool name
  - `resultLength`: Length of result string
  - `duration`: Call duration
  - `status`: SUCCESS or FAILED

#### Scenario: Error logging
- **GIVEN** a proxied tool call fails
- **WHEN** the error occurs
- **THEN** the runtime log event SHALL include:
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

### Requirement: Server Instructions

The system SHALL support per-server instructions for guiding agent usage.

#### Scenario: Server config with instructions
- **GIVEN** an MCP server config with `instructions` field
- **WHEN** the server is enabled
- **THEN** instructions SHALL be surfaced in MCP protocol instructions
- **AND** instructions SHALL be available via `ot.servers(info="full")`
- **AND** instructions SHALL be available via `ot.help(query="servername")`

#### Scenario: Instructions in MCP protocol
- **GIVEN** enabled servers with instructions configured
- **WHEN** client connects to OneTool
- **THEN** MCP protocol instructions SHALL include a "MCP Server Instructions" section
- **AND** each server's instructions SHALL be under a `## servername` heading

#### Scenario: Server without instructions
- **GIVEN** an MCP server config without `instructions` field
- **WHEN** the server is enabled
- **THEN** it SHALL function normally without instructions
- **AND** no placeholder instructions SHALL be generated

### Requirement: Resources Proxying

The system SHALL support listing and reading resources from proxied MCP servers.

#### Scenario: List resources from server
- **GIVEN** code `proxy.list_resources(server="context7")`
- **WHEN** run() executes it
- **THEN** it SHALL return a list of resource metadata dicts with:
  - `uri`: Resource URI
  - `name`: Resource name
  - `description`: Resource description

#### Scenario: Read resource content
- **GIVEN** code `proxy.read_resource(server="context7", uri="file:///docs/api.md")`
- **WHEN** run() executes it
- **THEN** it SHALL return the resource content as text

#### Scenario: List resources for disconnected server
- **GIVEN** server is not connected
- **WHEN** `proxy.list_resources(server="disconnected")` is called
- **THEN** it SHALL raise ValueError with message "Server 'disconnected' not connected"

#### Scenario: Resources in ot.servers() output
- **GIVEN** code `ot.servers(info="resources")`
- **WHEN** run() executes it
- **THEN** it SHALL return a list with:
  - `server`: Server name
  - `status`: "connected", "disconnected", or "error"
  - `resource_count`: Number of resources (if connected)
  - `resources`: List of resource metadata (if connected)

#### Scenario: Resource count in full server info
- **GIVEN** code `ot.servers(info="full")`
- **WHEN** run() executes it for a connected server
- **THEN** it SHALL include `Resources: N` in the output

### Requirement: Prompts Proxying

The system SHALL support listing and getting prompts from proxied MCP servers.

#### Scenario: List prompts from server
- **GIVEN** code `proxy.list_prompts(server="github")`
- **WHEN** run() executes it
- **THEN** it SHALL return a list of prompt metadata dicts with:
  - `name`: Prompt name
  - `description`: Prompt description

#### Scenario: Get rendered prompt
- **GIVEN** code `proxy.get_prompt(server="github", name="summarize", arguments={"text": "..."})`
- **WHEN** run() executes it
- **THEN** it SHALL return the rendered prompt content as text

#### Scenario: List prompts for disconnected server
- **GIVEN** server is not connected
- **WHEN** `proxy.list_prompts(server="disconnected")` is called
- **THEN** it SHALL raise ValueError with message "Server 'disconnected' not connected"

#### Scenario: Prompts in ot.servers() output
- **GIVEN** code `ot.servers(info="prompts")`
- **WHEN** run() executes it
- **THEN** it SHALL return a list with:
  - `server`: Server name
  - `status`: "connected", "disconnected", or "error"
  - `prompt_count`: Number of prompts (if connected)
  - `prompts`: List of prompt metadata (if connected)

#### Scenario: Prompt count in full server info
- **GIVEN** code `ot.servers(info="full")`
- **WHEN** run() executes it for a connected server
- **THEN** it SHALL include `Prompts: N` in the output

### Requirement: Downstream Result Conversion

The system SHALL correctly convert every downstream MCP content-block type a proxied tool can return, and SHALL NOT force-coerce plain text results into a different type.

#### Scenario: EmbeddedResource content is surfaced, not dropped
- **GIVEN** a proxied MCP tool returns a result whose content includes a `types.EmbeddedResource` block (payload under `.resource`)
- **WHEN** the proxy call completes
- **THEN** the resource's text (or a binary marker, if the resource is not text) SHALL be surfaced in the returned result
- **AND** the caller SHALL NOT receive `"Tool returned empty response."`

#### Scenario: Structured-only result falls back to structured_content
- **GIVEN** a proxied MCP tool returns a result with no text/embedded content parts but with `structured_content` (or `.data`) populated
- **WHEN** the proxy call completes
- **THEN** the returned result SHALL be derived from `structured_content`/`.data`
- **AND** the caller SHALL NOT receive `"Tool returned empty response."`

#### Scenario: Plain string result is not force-coerced
- **GIVEN** a proxied MCP tool returns a single text result `"007"`
- **WHEN** the proxy call completes
- **THEN** the returned result SHALL be the string `"007"`
- **AND** it SHALL NOT be coerced to the integer `7`

#### Scenario: JSON-shaped text is still parsed
- **GIVEN** a proxied MCP tool returns a single text result that, stripped of whitespace, starts with `{` or `[` (e.g. `"[1,2]"` or `'{"a":1}'`)
- **WHEN** the proxy call completes
- **THEN** the text SHALL be parsed as JSON and returned as the corresponding structured Python value

#### Scenario: Non-JSON-shaped scalars pass through as text
- **GIVEN** a proxied MCP tool returns a single text result that does not start with `{` or `[` (e.g. `"null"`, `"true"`, `"NaN"`, `"42"`)
- **WHEN** the proxy call completes
- **THEN** the text SHALL be returned unchanged as a string
- **AND** it SHALL NOT be parsed into `None`, a boolean, a float, or an int

### Requirement: Thread-Safe Tool Listing

The system SHALL allow `list_tools()` to be read concurrently with proxy connection mutations without raising an unhandled concurrency error.

#### Scenario: Concurrent connect during a full tool listing
- **GIVEN** a worker thread is iterating `list_tools(server=None)` across all connected servers
- **AND** a background connection adds a new server's tools to the internal tool registry concurrently on the event-loop thread
- **THEN** `list_tools(server=None)` SHALL complete without raising `RuntimeError: dictionary changed size during iteration`
- **AND** it SHALL return either the pre- or post-connect view of the tool set (either is acceptable; a crash is not)

