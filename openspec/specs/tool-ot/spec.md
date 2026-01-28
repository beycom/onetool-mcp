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
- **THEN** it SHALL return a list of all tools
- **AND** default info level SHALL be `min`

#### Scenario: Filter by pattern
- **GIVEN** a pattern parameter
- **WHEN** `ot.tools(pattern="search")` is called
- **THEN** it SHALL return only tools with names containing the pattern (case-insensitive substring)
- **AND** pattern SHALL always perform partial matching

#### Scenario: Info level list
- **GIVEN** `info="list"` parameter
- **WHEN** `ot.tools(info="list")` is called
- **THEN** it SHALL return only tool names as a list of strings

#### Scenario: Info level min
- **GIVEN** `info="min"` parameter (or default)
- **WHEN** `ot.tools()` or `ot.tools(info="min")` is called
- **THEN** each entry SHALL include: `{name, description}`

#### Scenario: Info level full
- **GIVEN** `info="full"` parameter
- **WHEN** `ot.tools(info="full")` is called
- **THEN** each entry SHALL include: `{name, signature, description, source}`
- **AND** each entry SHALL include `{args, returns, example}` when available
- **AND** source SHALL be "local" or "proxy:{server}"

#### Scenario: Proxy tool signature from schema
- **GIVEN** a proxy MCP server with tools exposing `inputSchema`
- **WHEN** `ot.tools(info="full")` lists proxy tools
- **THEN** signature SHALL be derived from schema properties (e.g., `github.search(query: str, repo: str = '...')`)
- **AND** required parameters SHALL appear without defaults
- **AND** optional parameters SHALL show default values or `'...'` placeholder

#### Scenario: Proxy tool arguments from schema
- **GIVEN** a proxy tool with `inputSchema` containing property descriptions
- **WHEN** `ot.tools(pattern="github.search", info="full")` is called
- **THEN** the response SHALL include an `args` field
- **AND** args SHALL be a list of `"param_name: description"` strings extracted from schema

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

The `ot.packs()` function SHALL list packs with optional filtering.

#### Scenario: List all packs
- **GIVEN** packs are registered (local and proxy)
- **WHEN** `ot.packs()` is called
- **THEN** it SHALL return a list of all packs
- **AND** default info level SHALL be `min`

#### Scenario: Filter by pattern
- **GIVEN** a pattern parameter
- **WHEN** `ot.packs(pattern="brav")` is called
- **THEN** it SHALL return only packs with names containing the pattern (case-insensitive substring)

#### Scenario: Info level list
- **GIVEN** `info="list"` parameter
- **WHEN** `ot.packs(info="list")` is called
- **THEN** it SHALL return only pack names as a list of strings

#### Scenario: Info level min
- **GIVEN** `info="min"` parameter (or default)
- **WHEN** `ot.packs()` or `ot.packs(info="min")` is called
- **THEN** each entry SHALL include: `{name, source, tool_count}`
- **AND** source SHALL be "local" or "proxy"

#### Scenario: Info level full
- **GIVEN** `info="full"` parameter
- **WHEN** `ot.packs(pattern="brave", info="full")` is called
- **THEN** it SHALL return detailed pack info including:
  - Pack header with name
  - Configured instructions (if present in prompts.yaml)
  - List of tools in the pack with descriptions

#### Scenario: Pack with configured instructions
- **GIVEN** prompts.yaml contains instructions for pack "excel"
- **WHEN** `ot.packs(pattern="excel", info="full")` is called
- **THEN** it SHALL include the configured instructions text

#### Scenario: Proxy pack
- **GIVEN** a proxy server "github" is configured
- **WHEN** `ot.packs(pattern="github", info="full")` is called
- **THEN** it SHALL list tools from the proxy server
- **AND** show source as "proxy"

---

### Requirement: Alias Introspection

The `ot.aliases()` function SHALL list aliases with optional filtering.

#### Scenario: List all aliases
- **GIVEN** aliases are configured
- **WHEN** `ot.aliases()` is called with no arguments
- **THEN** it SHALL return all alias mappings
- **AND** default info level SHALL be `min`

#### Scenario: Filter by pattern
- **GIVEN** aliases are configured
- **WHEN** `ot.aliases(pattern="search")` is called
- **THEN** it SHALL return only aliases where name or target matches the pattern (case-insensitive substring)

#### Scenario: Info level list
- **GIVEN** `info="list"` parameter
- **WHEN** `ot.aliases(info="list")` is called
- **THEN** it SHALL return only alias names as a list of strings

#### Scenario: Info level min
- **GIVEN** `info="min"` parameter (or default)
- **WHEN** `ot.aliases()` or `ot.aliases(info="min")` is called
- **THEN** it SHALL return mappings as: `alias_name -> target`

#### Scenario: Info level full
- **GIVEN** `info="full"` parameter
- **WHEN** `ot.aliases(info="full")` is called
- **THEN** it SHALL return structured data: `{name, target}`

---

### Requirement: Snippet Introspection

The `ot.snippets()` function SHALL list snippets with optional filtering.

#### Scenario: List all snippets
- **GIVEN** snippets are configured
- **WHEN** `ot.snippets()` is called with no arguments
- **THEN** it SHALL return all snippet names with descriptions
- **AND** default info level SHALL be `min`

#### Scenario: Filter snippets by pattern
- **GIVEN** snippets are configured
- **WHEN** `ot.snippets(pattern="pkg")` is called
- **THEN** it SHALL return only snippets where name or description matches the pattern (case-insensitive substring)

#### Scenario: Info level list
- **GIVEN** `info="list"` parameter
- **WHEN** `ot.snippets(info="list")` is called
- **THEN** it SHALL return only snippet names as a list of strings

#### Scenario: Info level min
- **GIVEN** `info="min"` parameter (or default)
- **WHEN** `ot.snippets()` or `ot.snippets(info="min")` is called
- **THEN** it SHALL return: `snippet_name: description`

#### Scenario: Info level full
- **GIVEN** `info="full"` parameter
- **WHEN** `ot.snippets(pattern="brv_research", info="full")` is called
- **THEN** it SHALL return the snippet definition including:
  - description
  - params with types and defaults
  - body template
  - example invocation

#### Scenario: Snippet output format
- **GIVEN** a valid snippet
- **WHEN** definition is displayed with `info="full"`
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

### Requirement: Unified Help

The `ot.help()` function SHALL provide unified help across tools, packs, snippets, and aliases.

#### Scenario: General help (no query)
- **GIVEN** no query parameter
- **WHEN** `ot.help()` is called
- **THEN** it SHALL return a general overview with:
  - Discovery commands (`ot.tools()`, `ot.packs()`, etc.)
  - Info level documentation
  - Quick examples
  - Usage tips

#### Scenario: Exact tool lookup
- **GIVEN** a query matching a tool name exactly (e.g., `brave.search`)
- **WHEN** `ot.help(query="brave.search")` is called
- **THEN** it SHALL return detailed tool help including:
  - Tool name as heading
  - Description
  - Signature
  - Arguments with types and descriptions
  - Return type
  - Example usage
  - Documentation URL

#### Scenario: Exact pack lookup
- **GIVEN** a query matching a pack name exactly (e.g., `firecrawl`)
- **WHEN** `ot.help(query="firecrawl")` is called
- **THEN** it SHALL return pack help including:
  - Pack name as heading
  - Pack instructions (if configured)
  - List of tools in the pack
  - Documentation URL

#### Scenario: Snippet lookup
- **GIVEN** a query starting with `$` (e.g., `$b_q`)
- **WHEN** `ot.help(query="$b_q")` is called
- **THEN** it SHALL return snippet help including:
  - Snippet name
  - Description
  - Parameters with defaults
  - Body template
  - Example invocation

#### Scenario: Alias lookup
- **GIVEN** a query matching an alias name
- **WHEN** `ot.help(query="ws")` is called
- **THEN** it SHALL return alias help including:
  - Alias name
  - Target function it maps to
  - Usage hint

#### Scenario: Fuzzy search
- **GIVEN** a query that does not match exactly but matches partially or fuzzily
- **WHEN** `ot.help(query="web fetch")` is called
- **THEN** it SHALL return search results grouped by type:
  - Tools matching the query
  - Packs matching the query
  - Snippets matching the query
  - Aliases matching the query

#### Scenario: Fuzzy matching with typos
- **GIVEN** a query with typos (e.g., `scaffoldl`, `frirecrawl`)
- **WHEN** `ot.help(query="scaffoldl")` is called
- **THEN** it SHALL use fuzzy matching to find close matches
- **AND** return results sorted by match score

#### Scenario: Info level list
- **GIVEN** `info="list"` parameter
- **WHEN** `ot.help(query="web", info="list")` is called
- **THEN** it SHALL return only names of matching items

#### Scenario: Info level min (default)
- **GIVEN** `info="min"` parameter or no info parameter
- **WHEN** `ot.help(query="brave")` is called
- **THEN** it SHALL return names with brief descriptions

#### Scenario: Info level full
- **GIVEN** `info="full"` parameter
- **WHEN** `ot.help(query="brave.search", info="full")` is called
- **THEN** it SHALL return complete documentation including all available fields

#### Scenario: Documentation URL generation
- **GIVEN** a tool or pack query
- **WHEN** help is displayed
- **THEN** it SHALL include a documentation URL in format:
  `https://onetool.beycom.online/reference/tools/{doc_slug}/`
- **AND** doc_slug SHALL map from pack name using hardcoded overrides:
  - `brave` -> `brave-search`
  - `code` -> `code-search`
  - `db` -> `database`
  - `ground` -> `grounding-search`
  - `llm` -> `transform`
  - `web` -> `web-fetch`
- **AND** packs not in override map SHALL use pack name as slug

#### Scenario: No matches
- **GIVEN** a query that matches nothing
- **WHEN** `ot.help(query="xyznonexistent")` is called
- **THEN** it SHALL return a message indicating no matches found
- **AND** suggest using `ot.tools()` or `ot.packs()` to browse available items

