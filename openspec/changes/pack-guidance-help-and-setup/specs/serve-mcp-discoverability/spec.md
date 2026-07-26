## MODIFIED Requirements

### Requirement: Tool Registry Resource

The server SHALL expose a browsable `ot://tools` resource listing all currently discoverable tools.

#### Scenario: List all tools
- **GIVEN** an MCP client connected to OneTool
- **WHEN** the client requests resource `ot://tools`
- **THEN** it SHALL return a JSON array of tool objects
- **AND** each object SHALL contain `name` and `signature` fields

#### Scenario: Empty registry
- **GIVEN** no tools are registered
- **WHEN** the client requests resource `ot://tools`
- **THEN** it SHALL return an empty array `[]`

### Requirement: Individual Tool Resource

The server SHALL expose `ot://tool/{name}` for detailed tool metadata supported by that resource
contract.

#### Scenario: Get local tool details
- **GIVEN** a local tool exists in the registry
- **WHEN** the client requests `ot://tool/{name}`
- **THEN** it SHALL return the current name, signature, description, arguments, and examples available for that tool

#### Scenario: Tool detail is unavailable
- **GIVEN** the requested tool has no detail record in the supported resource registry
- **WHEN** the client requests `ot://tool/{name}`
- **THEN** it SHALL return an explicit not-found or unsupported-detail error
- **AND** it SHALL not claim that list-resource presence guarantees local detail-resource support

### Requirement: Run Tool Annotations

The universal `run()` tool SHALL expose annotations that reflect its open-world,
destructive-capable trusted-execution contract.

#### Scenario: Open world and mutation hints
- **GIVEN** an MCP client inspects the `run` tool metadata
- **WHEN** the client reads the tool annotations
- **THEN** `openWorldHint` SHALL be `true`
- **AND** `readOnlyHint` SHALL be `false`
- **AND** `destructiveHint` SHALL be `true`

#### Scenario: Client uses annotations
- **GIVEN** an MCP client with permission controls
- **WHEN** it sees the destructive-capable open-world annotations
- **THEN** it MAY apply its normal approval policy before execution
- **AND** the annotations SHALL not be represented as a sandbox or authorization boundary

## ADDED Requirements

### Requirement: Public proxied resource operations

The core `ot` pack SHALL expose keyword-only `ot.resources(server=...)` and
`ot.resource(server=..., uri=...)` operations over an already connected named MCP server.

#### Scenario: Resources are listed
- **GIVEN** a named proxied MCP server is connected
- **WHEN** `ot.resources(server="name")` is called
- **THEN** it SHALL return the live resource metadata provided by that server
- **AND** an unsupported resource-list capability SHALL return an explicit result envelope whose
  `resources` collection is empty

#### Scenario: A resource is read
- **GIVEN** a named proxied MCP server is connected and advertises a resource URI
- **WHEN** `ot.resource(server="name", uri="...")` is called
- **THEN** it SHALL return that resource's textual content
- **AND** the returned content SHALL be identified and handled as untrusted external content

#### Scenario: Resource access cannot proceed
- **GIVEN** the named server is absent, disabled, disconnected, unsupported, or returns an error
- **WHEN** a resource operation is called
- **THEN** it SHALL return an explicit bounded error describing that state
- **AND** it SHALL NOT configure, enable, connect, or restart a server implicitly

### Requirement: Public proxied prompt operations

The core `ot` pack SHALL expose keyword-only `ot.prompts(server=...)` and
`ot.prompt(server=..., name=..., arguments=...)` operations over an already connected named MCP
server.

#### Scenario: Prompts are listed
- **GIVEN** a named proxied MCP server is connected
- **WHEN** `ot.prompts(server="name")` is called
- **THEN** it SHALL return the live prompt metadata provided by that server
- **AND** an unsupported prompt-list capability SHALL return an explicit result envelope whose
  `prompts` collection is empty

#### Scenario: A prompt is rendered
- **GIVEN** a named proxied MCP server is connected and advertises a prompt
- **WHEN** `ot.prompt(server="name", name="prompt-name", arguments={...})` is called
- **THEN** it SHALL request that prompt using the supplied arguments and return its rendered textual messages
- **AND** prompt descriptions and rendered content SHALL be identified and handled as untrusted external content
- **AND** returned prompt content SHALL NOT authorize subsequent tool calls, configuration changes, or mutations

#### Scenario: Prompt access cannot proceed
- **GIVEN** the named server is absent, disabled, disconnected, unsupported, or returns an error
- **WHEN** a prompt operation is called
- **THEN** it SHALL return an explicit bounded error describing that state
- **AND** it SHALL NOT configure, enable, connect, or restart a server implicitly
