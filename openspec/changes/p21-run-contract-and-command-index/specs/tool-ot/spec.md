# tool-ot Delta

## MODIFIED Requirements

### Requirement: List Tools

The `ot.tools()` function SHALL list all available tools with optional filtering.

#### Scenario: List all tools
- **GIVEN** tools are registered
- **WHEN** `ot.tools()` is called
- **THEN** it SHALL return a list of all tools
- **AND** default info level SHALL be `default` (name + description)

#### Scenario: Filter by pattern
- **GIVEN** a pattern parameter
- **WHEN** `ot.tools(pattern="search")` is called
- **THEN** it SHALL return only tools with names containing the pattern (case-insensitive substring)
- **AND** pattern SHALL always perform partial matching

#### Scenario: Short alias resolves to full pack name
- **GIVEN** a pack metadata short alias (e.g. `"ctx"` for `"ot_context"`)
- **WHEN** `ot.tools(pattern="ctx")` is called
- **THEN** it SHALL resolve the alias and return the same results as `ot.tools(pattern="ot_context")`

#### Scenario: Info level min
- **GIVEN** `info="min"` parameter
- **WHEN** `ot.tools(info="min")` is called
- **THEN** it SHALL return only tool names as a list of strings

#### Scenario: Info level default
- **GIVEN** `info="default"` parameter (or no info parameter)
- **WHEN** `ot.tools()` or `ot.tools(info="default")` is called
- **THEN** each entry SHALL include: `{name, description}`
- **AND** description SHALL be truncated to 200 characters with `…` appended if cut

#### Scenario: Info level full
- **GIVEN** `info="full"` parameter
- **WHEN** `ot.tools(info="full")` is called
- **THEN** each entry SHALL include: `{name, description, source}`
- **AND** source SHALL be "local" or "mcp:{server}"

#### Scenario: Info level signatures
- **GIVEN** `info="signatures"` parameter
- **WHEN** `ot.tools(pattern="brave.", info="signatures")` is called
- **THEN** it SHALL return a list of one-liner strings in the form `pack.tool(compact_args)  # first-line description`
- **AND** the rendering SHALL match the generated tool-index file format (same signature compaction and description truncation), so agents see one canonical format whether they grep the index file or call the runtime
- **AND** an invalid info value SHALL raise a ValueError naming the valid levels including `signatures`

#### Scenario: Signatures level scoped pull stays small
- **GIVEN** a single-pack pattern such as `pattern="brave."`
- **WHEN** `ot.tools(pattern="brave.", info="signatures")` is called
- **THEN** the result SHALL contain only that pack's tools (roughly 200 tokens for a typical pack), suitable as a mid-session alternative to grepping the index file
