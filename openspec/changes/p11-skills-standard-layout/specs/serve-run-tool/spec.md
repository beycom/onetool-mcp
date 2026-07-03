## MODIFIED Requirements

### Requirement: Robust Result Capture

The system SHALL capture results from any valid Python expression or statement and serialize them consistently.

#### Scenario: Expression result
- **GIVEN** code that is a single expression like `search(query="test")`
- **WHEN** execution completes
- **THEN** the expression result SHALL be captured

#### Scenario: Last expression in block
- **GIVEN** multi-statement code where last statement is an expression
- **WHEN** execution completes
- **THEN** the last expression result SHALL be captured

#### Scenario: Explicit return
- **GIVEN** code with explicit `return value`
- **WHEN** execution completes
- **THEN** the returned value SHALL be captured

#### Scenario: No return value
- **GIVEN** code that has no return and last statement is not an expression
- **WHEN** execution completes
- **THEN** it SHALL return a success message indicating no value

#### Scenario: None return
- **GIVEN** code that explicitly returns None or function returns None
- **WHEN** execution completes
- **THEN** it SHALL indicate None was returned (not "no return value")

#### Scenario: Native dict serialization
- **GIVEN** a tool function that returns a Python dict
- **WHEN** the result is captured by the runner
- **THEN** the dict SHALL be serialized to compact JSON using `serialize_result()`
- **AND** the result SHALL NOT contain double-escaped JSON

#### Scenario: Native list serialization
- **GIVEN** a tool function that returns a Python list
- **WHEN** the result is captured by the runner
- **THEN** the list SHALL be serialized to compact JSON using `serialize_result()`
- **AND** the result SHALL NOT contain double-escaped JSON

#### Scenario: Discovery calls keep JSON default format
- **GIVEN** a discovery/introspection call (`ot.help`, `ot.tool_info`, `ot.tools`, `ot.packs`, `ot.pack_info`, `ot.servers`, `ot.aliases`, `ot.snippets`, `ot.snippet_info`)
- **AND** no explicit `__format__` is set in the executed code
- **WHEN** the result is captured by the runner
- **THEN** the runner SHALL default to compact JSON (`json`)
- **AND** explicit `__format__` SHALL still override this default

#### Scenario: String passthrough
- **GIVEN** a tool function that returns a plain string
- **WHEN** the result is captured by the runner
- **THEN** the string SHALL be returned as-is without additional serialization

#### Scenario: Composed tool results
- **GIVEN** code like `{"status": ot.status(), "config": ot.config()}`
- **WHEN** each tool returns a native dict
- **THEN** the composed result SHALL be a single clean JSON object
- **AND** nested values SHALL NOT be double-escaped strings
