# tool-ot Specification

## Purpose

Defines the `ot` pack providing internal tool functions for accessing ot-serve state, tool discovery, configuration inspection, and system health. All output uses YAML flow style for compact, readable context that LLMs can easily parse.

This spec consolidates `tool-internal` and `tool-info`.
## Requirements
### Requirement: List Tools

The `ot.tools()` function SHALL list all available tools with optional filtering.

#### Scenario: List all tools
- **GIVEN** tools are registered
- **WHEN** `ot.tools()` is called
- **THEN** it SHALL return YAML listing all tools
- **AND** each entry SHALL include: `{name, signature, description, source}`
- **AND** source SHALL be "local" or "proxy:{server}"

#### Scenario: Filter by pattern
- **GIVEN** a pattern parameter
- **WHEN** `ot.tools(pattern="search")` is called
- **THEN** it SHALL return only tools with names matching the pattern (case-insensitive)

#### Scenario: Filter by pack
- **GIVEN** a pack parameter
- **WHEN** `ot.tools(pack="brave")` is called
- **THEN** it SHALL return only tools in the "brave" pack

#### Scenario: Compact output
- **GIVEN** compact=True parameter
- **WHEN** `ot.tools(compact=True)` is called
- **THEN** it SHALL return only `{name, description}` for each tool
- **AND** output size SHALL be significantly smaller than full output

#### Scenario: Output format
- **GIVEN** tools are found
- **WHEN** results are returned
- **THEN** output SHALL use YAML flow style:
```yaml
- {name: brave.web_search, signature: "brave.web_search(query, count=10)", description: "Search the web", source: local}
- {name: demo.foo, signature: "demo.foo(text)", description: "Demo function", source: local}
```

---

### Requirement: Configuration Summary

The `ot.config()` function SHALL return key configuration values.

#### Scenario: Show config
- **GIVEN** configuration is loaded
- **WHEN** `ot.config()` is called
- **THEN** it SHALL return YAML with:
```yaml
aliases: {ws: brave.web_search, alias_f: demo.foo}
snippets: {foon: {description: "Get foo() for n items"}, barn: {description: "Get bar() for n items"}}
servers: [proxy_package_version]
```

#### Scenario: Empty config
- **GIVEN** no aliases or snippets configured
- **WHEN** `ot.config()` is called
- **THEN** it SHALL return empty values: `{aliases: {}, snippets: {}, servers: []}`

---

### Requirement: Health Check

The `ot.health()` function SHALL check health of OneTool components.

#### Scenario: Show health
- **GIVEN** OneTool is running
- **WHEN** `ot.health()` is called
- **THEN** it SHALL return YAML with component status:
```yaml
version: "1.0.0"
python: "3.11.x"
cwd: /current/working/directory
registry: {status: ok, tool_count: 15}
proxy: {status: ok, server_count: 1, servers: {proxy_package_version: connected}}
```

#### Scenario: Disconnected server
- **GIVEN** an MCP server is configured but not connected
- **WHEN** `ot.health()` is called
- **THEN** server status SHALL show "disconnected"
- **AND** proxy status SHALL show "degraded"

---

### Requirement: Push Message

The `ot.push()` function SHALL publish messages to configured topics.

#### Scenario: Push message
- **WHEN** `ot.push(topic="status:scan", message="Scanning...")`
- **THEN** the message is routed to the matching topic file
- **AND** appended as a YAML document

---

### Requirement: YAML Flow Style Output

All `ot.*` functions SHALL format output using YAML flow style.

#### Scenario: Flow style formatting
- **GIVEN** any ot function is called
- **WHEN** results are formatted
- **THEN** simple objects SHALL use inline flow style: `{key: value, key2: value2}`
- **AND** lists of objects SHALL use block sequence with flow items

#### Scenario: Readability
- **GIVEN** YAML output is generated
- **WHEN** formatted
- **THEN** output SHALL be readable by humans and easily parseable by LLMs
- **AND** nested structures SHALL not exceed 2 levels of flow style

---

### Requirement: Logging

The tool SHALL follow [tool-conventions](../tool-conventions/spec.md) for logging.

#### Scenario: Span naming
- **GIVEN** an ot function is called
- **WHEN** LogSpan is created
- **THEN** span name SHALL be `ot.{function_name}` (e.g., `ot.tools`, `ot.health`)

---

### Requirement: Help Tool

The `ot.help()` function SHALL display full documentation for a tool, including proxy tools.

#### Scenario: Get local tool help
- **GIVEN** a valid local tool name
- **WHEN** `ot.help(tool="brave.search")` is called
- **THEN** it SHALL return the tool's full docstring
- **AND** include the function signature
- **AND** include Args, Returns, and Example sections if present

#### Scenario: Get proxy tool help
- **GIVEN** a proxy server "github" with tool "create_issue"
- **WHEN** `ot.help(tool="github.create_issue")` is called
- **THEN** it SHALL return the tool's description from MCP schema
- **AND** include parameters with types and required markers
- **AND** include source as "proxy:github"

#### Scenario: Tool not found
- **GIVEN** an invalid tool name not in local or proxy packs
- **WHEN** `ot.help(tool="nonexistent.tool")` is called
- **THEN** it SHALL return an error message listing available packs

#### Scenario: Local tool output format
- **GIVEN** a valid local tool
- **WHEN** help is displayed
- **THEN** output SHALL be formatted as:
```

### Requirement: Pack Instructions

The `ot.instructions()` function SHALL return usage instructions for a pack.

#### Scenario: Get pack instructions from config
- **GIVEN** prompts.yaml contains key "excel" with instructions text
- **WHEN** `ot.instructions(pack="excel")` is called
- **THEN** it SHALL return the configured instructions text

#### Scenario: Get local pack instructions fallback
- **GIVEN** no config override for pack "brave"
- **AND** "brave" is a local pack
- **WHEN** `ot.instructions(pack="brave")` is called
- **THEN** it SHALL return aggregated docstrings from brave tools

#### Scenario: Get proxy pack instructions fallback
- **GIVEN** no config override for pack "github"
- **AND** "github" is a proxy server
- **WHEN** `ot.instructions(pack="github")` is called
- **THEN** it SHALL return the MCP server_info if available
- **OR** return a default message listing available tools

#### Scenario: Unknown pack
- **GIVEN** pack "nonexistent" is not local or proxy
- **WHEN** `ot.instructions(pack="nonexistent")` is called
- **THEN** it SHALL return an error with available packs

#### Scenario: Logging
- **GIVEN** `ot.instructions()` is called
- **WHEN** LogSpan is created
- **THEN** span name SHALL be `ot.instructions`

## brave.search

Search the web using Brave Search API.

**Signature**: brave.search(*, query: str, count: int = 10)

**Args**:
- query: Search query (max 400 chars)
- count: Number of results (1-20, default: 10)

**Returns**: YAML flow style search results

**Example**:
brave.search(query="Python async patterns", count=5)
```

---

### Requirement: Alias Introspection

The `ot.alias()` function SHALL show alias definitions.

#### Scenario: Show alias
- **GIVEN** an alias "ws" configured to "brave.web_search"
- **WHEN** `ot.alias(name="ws")` is called
- **THEN** it SHALL return: `ws -> brave.web_search`

#### Scenario: Alias not found
- **GIVEN** an unknown alias name
- **WHEN** `ot.alias(name="xyz")` is called
- **THEN** it SHALL return an error with available aliases

#### Scenario: List all aliases
- **GIVEN** aliases are configured
- **WHEN** `ot.alias(name="*")` is called
- **THEN** it SHALL return all alias mappings

---

### Requirement: Snippet Introspection

The `ot.snippet()` function SHALL show snippet definitions and previews.

#### Scenario: Show snippet definition
- **GIVEN** a snippet "brv_research" is configured
- **WHEN** `ot.snippet(name="brv_research")` is called
- **THEN** it SHALL return the snippet definition including:
  - description
  - params with types and defaults
  - body template

#### Scenario: Show snippet preview
- **GIVEN** a snippet with default params
- **WHEN** `ot.snippet(name="brv_research")` is called
- **THEN** it SHALL include an example expansion with defaults

#### Scenario: Snippet not found
- **GIVEN** an unknown snippet name
- **WHEN** `ot.snippet(name="xyz")` is called
- **THEN** it SHALL return an error with available snippets

#### Scenario: List all snippets
- **GIVEN** snippets are configured
- **WHEN** `ot.snippet(name="*")` is called
- **THEN** it SHALL return all snippet names with descriptions

#### Scenario: Output format
- **GIVEN** a valid snippet
- **WHEN** definition is displayed
- **THEN** output SHALL be formatted as:
```yaml
name: brv_research
description: Search web and extract structured findings
params:
  topic: {description: "Topic to research"}
  count: {default: 5, description: "Number of sources"}
body: |
  results = brave.search(query="{{ topic }}", count={{ count }})
  llm.transform(input=results, prompt="Extract key findings")

# Example with defaults:
# $brv_research topic=Python
# Expands to:
results = brave.search(query="Python", count=5)
llm.transform(input=results, prompt="Extract key findings")
```
