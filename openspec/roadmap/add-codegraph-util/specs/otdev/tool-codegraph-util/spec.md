## ADDED Requirements

### Requirement: codegraph_util Pack Declaration

The system SHALL provide a `codegraph_util` tool pack with `cg` as a short alias.

#### Scenario: Pack discovery
- **GIVEN** the `otdev` extra is installed
- **WHEN** tools are discovered
- **THEN** the `codegraph_util` pack SHALL expose `status`, `symbols`, `neighborhood`, `flow`, `hotspots`, and `diff_impact`
- **AND** callers MAY use the `cg` alias

### Requirement: CodeGraph Project Resolution

The `codegraph_util` pack SHALL resolve a CodeGraph project from a `project_path` argument by locating the nearest `.codegraph/codegraph.db` at or above that path.

#### Scenario: Resolve indexed project
- **GIVEN** `project_path` points inside a project containing `.codegraph/codegraph.db`
- **WHEN** any `codegraph_util` function is called with that `project_path`
- **THEN** the function SHALL read from that database

#### Scenario: Missing index
- **GIVEN** `project_path` does not resolve to a `.codegraph/codegraph.db`
- **WHEN** any `codegraph_util` function is called with that `project_path`
- **THEN** it SHALL return an error string indicating that the project is not indexed with CodeGraph
- **AND** the error SHALL mention that the user can run `codegraph init`

### Requirement: Read-Only CodeGraph Database Access

The `codegraph_util` pack SHALL access CodeGraph SQLite databases in read-only mode and SHALL NOT create, update, delete, migrate, or repair CodeGraph data.

#### Scenario: Read-only helper call
- **GIVEN** a valid `.codegraph/codegraph.db`
- **WHEN** `codegraph_util.status(project_path=...)` is called
- **THEN** the function SHALL only read database tables
- **AND** it SHALL return native structured data rather than a JSON-encoded string

#### Scenario: Unsupported schema
- **GIVEN** a `.codegraph/codegraph.db` missing required CodeGraph tables or columns
- **WHEN** a `codegraph_util` function is called
- **THEN** it SHALL return an error string naming the unsupported or incomplete schema

### Requirement: Index Status Summary

The `status()` function SHALL summarize the resolved CodeGraph index.

#### Scenario: Status for indexed project
- **GIVEN** a valid CodeGraph database
- **WHEN** `codegraph_util.status(project_path=...)` is called
- **THEN** it SHALL return counts for files, nodes, edges, unresolved references, languages, node kinds, and edge kinds
- **AND** it SHALL include the resolved project path and database path

### Requirement: Symbol Search

The `symbols()` function SHALL return compact structured symbol matches from the CodeGraph index.

#### Scenario: Search symbols by query
- **GIVEN** a valid CodeGraph database containing matching symbols
- **WHEN** `codegraph_util.symbols(query="auth", project_path=..., limit=20)` is called
- **THEN** it SHALL return at most 20 symbol records
- **AND** each record SHALL include symbol name, qualified name, kind, language, file path, start line, end line, and signature when available

#### Scenario: Filter symbol search
- **GIVEN** a valid CodeGraph database containing multiple languages and node kinds
- **WHEN** `codegraph_util.symbols(query="handler", kind="function", language="python", project_path=...)` is called
- **THEN** it SHALL only return symbols matching the requested kind and language filters

### Requirement: Symbol Neighborhood

The `neighborhood()` function SHALL return callers, callees, and adjacent graph relationships for a selected symbol.

#### Scenario: Neighborhood for symbol
- **GIVEN** a valid CodeGraph database containing a symbol and graph edges
- **WHEN** `codegraph_util.neighborhood(symbol="login", project_path=..., depth=1, direction="both")` is called
- **THEN** it SHALL return the selected symbol, adjacent symbols, and connecting edges
- **AND** each edge SHALL include source, target, kind, line, column, and provenance when available

#### Scenario: Ambiguous symbol
- **GIVEN** multiple symbols match the requested `symbol`
- **WHEN** `codegraph_util.neighborhood(symbol="run", project_path=...)` is called without a file filter
- **THEN** it SHALL return an ambiguity result listing candidate symbols rather than choosing one silently

### Requirement: Flow Path

The `flow()` function SHALL find a bounded graph path between two selected symbols.

#### Scenario: Flow between symbols
- **GIVEN** a valid CodeGraph database containing a path from a source symbol to a target symbol
- **WHEN** `codegraph_util.flow(source="AuthMiddleware", target="UserService.login", project_path=..., max_depth=6)` is called
- **THEN** it SHALL return a structured path containing ordered nodes and edges
- **AND** each node SHALL include file path and line information

#### Scenario: No flow found
- **GIVEN** a valid CodeGraph database with no bounded path between the selected symbols
- **WHEN** `codegraph_util.flow(source="A", target="B", project_path=..., max_depth=2)` is called
- **THEN** it SHALL return a structured result indicating that no path was found

### Requirement: Graph Hotspots

The `hotspots()` function SHALL report high-signal symbols or files from the CodeGraph index.

#### Scenario: Fan-in hotspots
- **GIVEN** a valid CodeGraph database
- **WHEN** `codegraph_util.hotspots(project_path=..., by="fan_in", limit=10)` is called
- **THEN** it SHALL return at most 10 symbols ordered by inbound edge count

#### Scenario: Fan-out hotspots
- **GIVEN** a valid CodeGraph database
- **WHEN** `codegraph_util.hotspots(project_path=..., by="fan_out", limit=10)` is called
- **THEN** it SHALL return at most 10 symbols ordered by outbound edge count

### Requirement: Git Diff Impact

The `diff_impact()` function SHALL map changed files and line ranges to CodeGraph symbols and likely impacted graph dependents.

#### Scenario: Impact for changed symbols
- **GIVEN** a git repository with a valid CodeGraph database
- **WHEN** `codegraph_util.diff_impact(project_path=..., ref="HEAD", limit=100)` is called
- **THEN** it SHALL return changed files, matched changed symbols, impacted symbols, and unmatched changed files
- **AND** impacted symbols SHALL be bounded by the requested limit

#### Scenario: Not a git repository
- **GIVEN** `project_path` is indexed by CodeGraph but is not inside a git repository
- **WHEN** `codegraph_util.diff_impact(project_path=..., ref="HEAD")` is called
- **THEN** it SHALL return an error string indicating that git diff impact requires a git repository

### Requirement: CodeGraph MCP Server Companion

The system SHALL provide a disabled shared MCP server template for upstream CodeGraph so users can proxy `codegraph serve --mcp` through OneTool.

#### Scenario: Shared server template
- **WHEN** the shared server templates are listed or included
- **THEN** a disabled `codegraph` stdio server template SHALL be available
- **AND** it SHALL run the `codegraph` command with `serve --mcp`
- **AND** it SHALL configure `tool_prefix: "codegraph_"`

#### Scenario: Proxied explore naming
- **GIVEN** the shared `codegraph` server is enabled and connected
- **WHEN** callers access the proxied CodeGraph MCP server through OneTool
- **THEN** upstream `codegraph_explore` SHALL be callable as `codegraph.explore(...)`
