# serve-mcp-discoverability Specification

## Purpose

Defines MCP discoverability features for OneTool: resources for browsing available tools, prompts for common code patterns, and tool annotations for LLM decision-making.
## Requirements
### Requirement: Tool Registry Resource

The server SHALL expose a browsable resource listing all available tools.

#### Scenario: List all tools
- **GIVEN** an MCP client connected to OneTool
- **WHEN** the client requests resource `onetool://tools`
- **THEN** it SHALL return a JSON array of tool objects
- **AND** each object SHALL contain `name` and `signature` fields

#### Scenario: Empty registry
- **GIVEN** no tools are registered
- **WHEN** the client requests resource `onetool://tools`
- **THEN** it SHALL return an empty array `[]`

---

### Requirement: Individual Tool Resource

The server SHALL expose a resource template for individual tool details.

#### Scenario: Get tool details
- **GIVEN** a tool named `brave_web_search` exists in the registry
- **WHEN** the client requests resource `onetool://tool/brave_web_search`
- **THEN** it SHALL return a JSON object with:
  - `name`: Tool name
  - `signature`: Full function signature
  - `description`: Tool description
  - `args`: List of argument definitions
  - `examples`: Usage examples from prompts config

#### Scenario: Tool not found
- **GIVEN** no tool named `nonexistent` exists
- **WHEN** the client requests resource `onetool://tool/nonexistent`
- **THEN** it SHALL return an error indicating the tool was not found

---

### Requirement: Batch Search Prompt

The server SHALL expose an MCP prompt for generating batch web search code.

#### Scenario: Generate batch search code
- **GIVEN** an MCP client requests the `batch_search` prompt
- **WHEN** the client provides `topics=["AI", "ML"]` and `count=5`
- **THEN** it SHALL return a properly formatted `__onetool__run` code block
- **AND** the code SHALL call `brave_web_search` for each topic
- **AND** the code SHALL collect results into a dictionary

#### Scenario: Prompt parameter validation
- **GIVEN** an MCP client requests the `batch_search` prompt
- **WHEN** required parameter `topics` is missing
- **THEN** it SHALL return a validation error

---

### Requirement: Transform Data Prompt

The server SHALL expose an MCP prompt for fetch-and-transform patterns.

#### Scenario: Generate transform code
- **GIVEN** an MCP client requests the `transform_data` prompt
- **WHEN** the client provides `urls=["https://example.com"]` and `instruction="Extract titles"`
- **THEN** it SHALL return a properly formatted `__onetool__run` code block
- **AND** the code SHALL call `web_fetch` for each URL
- **AND** the code SHALL include the instruction as a comment for LLM processing

---

### Requirement: Run Tool Annotations

The `run()` tool SHALL include behavioral annotations for LLM decision-making.

#### Scenario: Open world hint
- **GIVEN** an MCP client inspects the `run` tool metadata
- **WHEN** the client reads the tool annotations
- **THEN** `openWorldHint` SHALL be `true`
- **AND** `readOnlyHint` SHALL be `false`
- **AND** `destructiveHint` SHALL be `false`

#### Scenario: Client uses annotations
- **GIVEN** an MCP client with permission controls
- **WHEN** it sees `openWorldHint: true`
- **THEN** it MAY prompt the user before executing
- **AND** it MAY cache the decision for future calls

