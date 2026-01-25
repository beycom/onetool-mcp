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

#### Scenario: Get specific tool by name
- **GIVEN** a name parameter
- **WHEN** `ot.tools(name="brave.search")` is called
- **THEN** it SHALL return a single tool dict for that exact tool
- **AND** return an error if the tool is not found

#### Scenario: Filter by pattern
- **GIVEN** a pattern parameter
- **WHEN** `ot.tools(pattern="search")` is called
- **THEN** it SHALL return only tools with names matching the pattern (case-insensitive substring)

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

#### Scenario: Proxy tool signature from schema
- **GIVEN** a proxy MCP server with tools exposing `inputSchema`
- **WHEN** `ot.tools()` lists proxy tools
- **THEN** signature SHALL be derived from schema properties (e.g., `github.search(query: str, repo: str = '...')`)
- **AND** required parameters SHALL appear without defaults
- **AND** optional parameters SHALL show default values or `'...'` placeholder

#### Scenario: Proxy tool arguments from schema
- **GIVEN** a proxy tool with `inputSchema` containing property descriptions
- **WHEN** `ot.tools(name="github.search")` is called (non-compact)
- **THEN** the response SHALL include an `args` field
- **AND** args SHALL be a list of `"param_name: description"` strings extracted from schema
- **AND** format SHALL match local tool args output

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

### Requirement: Notify Message

The `ot.notify()` function SHALL publish messages to configured topics.

#### Scenario: Send notification
- **WHEN** `ot.notify(topic="notes", message="Remember to review PR #123")`
- **THEN** the message is routed to the matching topic file
- **AND** appended as a YAML document

---

### Requirement: Reload Configuration

The `ot.reload()` function SHALL force reload of all configuration.

#### Scenario: Reload config
- **GIVEN** configuration files have been modified
- **WHEN** `ot.reload()` is called
- **THEN** it SHALL clear all cached configuration
- **AND** reload from disk
- **AND** return "OK: Configuration reloaded"

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

### Requirement: Pack Discovery

The `ot.packs()` function SHALL list packs or get detailed pack info with instructions.

#### Scenario: List all packs
- **GIVEN** packs are registered (local and proxy)
- **WHEN** `ot.packs()` is called
- **THEN** it SHALL return a list of pack summaries
- **AND** each entry SHALL include: `{name, source, tool_count}`
- **AND** source SHALL be "local" or "proxy"

#### Scenario: Get specific pack by name
- **GIVEN** a name parameter
- **WHEN** `ot.packs(name="brave")` is called
- **THEN** it SHALL return detailed pack info including:
  - Pack header with name
  - Configured instructions (if present in prompts.yaml)
  - List of tools in the pack with descriptions
- **AND** return an error if the pack is not found

#### Scenario: Filter by pattern
- **GIVEN** a pattern parameter
- **WHEN** `ot.packs(pattern="brav")` is called
- **THEN** it SHALL return only packs with names matching the pattern (case-insensitive substring)

#### Scenario: Pack not found
- **GIVEN** an unknown pack name
- **WHEN** `ot.packs(name="nonexistent")` is called
- **THEN** it SHALL return an error with available packs

#### Scenario: Pack with configured instructions
- **GIVEN** prompts.yaml contains instructions for pack "excel"
- **WHEN** `ot.packs(name="excel")` is called
- **THEN** it SHALL include the configured instructions text

#### Scenario: Proxy pack
- **GIVEN** a proxy server "github" is configured
- **WHEN** `ot.packs(name="github")` is called
- **THEN** it SHALL list tools from the proxy server
- **AND** show source as "proxy"

---

### Requirement: Alias Introspection

The `ot.aliases()` function SHALL list aliases, filter by pattern, or get a specific alias.

#### Scenario: List all aliases
- **GIVEN** aliases are configured
- **WHEN** `ot.aliases()` is called with no arguments
- **THEN** it SHALL return all alias mappings

#### Scenario: Get specific alias by name
- **GIVEN** an alias "ws" configured to "brave.web_search"
- **WHEN** `ot.aliases(name="ws")` is called
- **THEN** it SHALL return: `ws -> brave.web_search`

#### Scenario: Filter by pattern
- **GIVEN** aliases are configured
- **WHEN** `ot.aliases(pattern="search")` is called
- **THEN** it SHALL return only aliases where name or target matches the pattern (case-insensitive substring)

#### Scenario: Alias not found
- **GIVEN** an unknown alias name
- **WHEN** `ot.aliases(name="xyz")` is called
- **THEN** it SHALL return an error with available aliases

---

### Requirement: Snippet Introspection

The `ot.snippets()` function SHALL list snippets, filter by pattern, or get a specific snippet definition.

#### Scenario: List all snippets
- **GIVEN** snippets are configured
- **WHEN** `ot.snippets()` is called with no arguments
- **THEN** it SHALL return all snippet names with descriptions

#### Scenario: Get specific snippet by name
- **GIVEN** a snippet "brv_research" is configured
- **WHEN** `ot.snippets(name="brv_research")` is called
- **THEN** it SHALL return the snippet definition including:
  - description
  - params with types and defaults
  - body template
- **AND** it SHALL include an example expansion with defaults

#### Scenario: Filter snippets by pattern
- **GIVEN** snippets are configured
- **WHEN** `ot.snippets(pattern="pkg")` is called
- **THEN** it SHALL return only snippets where name or description matches the pattern (case-insensitive substring)

#### Scenario: Snippet not found
- **GIVEN** an unknown snippet name
- **WHEN** `ot.snippets(name="xyz")` is called
- **THEN** it SHALL return an error with available snippets

#### Scenario: Snippet output format
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

