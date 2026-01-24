# serve-run-tool Specification

## Purpose

Defines the `run()` MCP tool for executing Python code with access to the tool registry. Handles code fence stripping, pack resolution, alias expansion, snippet processing, result capture, and error context.
## Requirements
### Requirement: Robust Fence Stripping

The system SHALL strip various code fence formats from commands.

#### Scenario: Triple backtick with language
- **GIVEN** command wrapped in ` ```python\ncode\n``` `
- **WHEN** run() processes the command
- **THEN** it SHALL extract only the code content

#### Scenario: Triple backtick without language
- **GIVEN** command wrapped in ` ```\ncode\n``` `
- **WHEN** run() processes the command
- **THEN** it SHALL extract only the code content

#### Scenario: Inline backticks
- **GIVEN** command wrapped in single backticks like `` `code` ``
- **WHEN** run() processes the command
- **THEN** it SHALL extract only the code content

#### Scenario: Nested fences preserved
- **GIVEN** code containing fence characters as data (not wrapping)
- **WHEN** run() processes the command
- **THEN** inner fence content SHALL be preserved

#### Scenario: No fences
- **GIVEN** command without any fence wrapping
- **WHEN** run() processes the command
- **THEN** it SHALL pass through unchanged

#### Scenario: Legacy prefix rejected
- **GIVEN** command `!onetool upper(text="hello")`
- **WHEN** run() processes the command
- **THEN** it SHALL return an error indicating invalid syntax

### Requirement: Unified Execution Path

The system SHALL use a single code path for all command execution.

#### Scenario: Simple function call
- **GIVEN** command like `search(query="test")`
- **WHEN** run() executes the command
- **THEN** it SHALL use the direct executor

#### Scenario: Python code block
- **GIVEN** multi-line Python code
- **WHEN** run() executes the command
- **THEN** it SHALL use the direct executor

### Requirement: Robust Result Capture

The system SHALL capture results from any valid Python expression or statement.

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

### Requirement: Indentation-Safe Code Wrapping

The system SHALL correctly wrap code regardless of indentation.

#### Scenario: Already indented code
- **GIVEN** code that is already indented (e.g., from LLM response)
- **WHEN** wrapped for execution
- **THEN** indentation SHALL be normalized correctly

#### Scenario: Mixed indentation
- **GIVEN** code with mixed tabs and spaces
- **WHEN** wrapped for execution
- **THEN** it SHALL handle or normalize the indentation

#### Scenario: Empty lines
- **GIVEN** code with empty lines between statements
- **WHEN** wrapped for execution
- **THEN** empty lines SHALL not cause indentation errors

### Requirement: Error Context

The system SHALL provide clear error context for failures.

#### Scenario: Syntax error location
- **GIVEN** code with syntax error
- **WHEN** execution fails
- **THEN** error SHALL include line number in original code (not wrapped)

#### Scenario: Runtime error context
- **GIVEN** code that raises exception during execution
- **WHEN** execution fails
- **THEN** error SHALL include the exception type and message

#### Scenario: Tool not found
- **GIVEN** command calling non-existent tool
- **WHEN** execution fails
- **THEN** error SHALL list available tools

#### Scenario: Argument error
- **GIVEN** tool called with wrong arguments
- **WHEN** execution fails
- **THEN** error SHALL include expected signature

### Requirement: Pack Resolution

The system SHALL resolve dot-notation packs to actual tool functions.

#### Scenario: Simple pack call
- **GIVEN** command `brave.web_search(query="test")` where `brave` pack contains `web_search`
- **WHEN** run() processes the command
- **THEN** it SHALL call the `web_search` function from `brave` pack

#### Scenario: Unknown pack
- **GIVEN** command `unknown.func()` where `unknown` pack does not exist
- **WHEN** run() processes the command
- **THEN** it SHALL return error listing available packs

#### Scenario: Function not in pack
- **GIVEN** command `brave.nonexistent()` where function does not exist in `brave` pack
- **WHEN** run() processes the command
- **THEN** it SHALL return error listing available functions in that pack

#### Scenario: Same function name in different packs
- **GIVEN** `brave.search()` and `context7.search()` exist as distinct functions
- **WHEN** run() processes `brave.search(query="test")`
- **THEN** it SHALL call the brave-specific search function

### Requirement: Alias Resolution

The system SHALL resolve configured aliases to their target functions.

#### Scenario: Simple alias
- **GIVEN** alias `ws` configured to map to `brave.web_search`
- **WHEN** command `ws(query="test")` is processed
- **THEN** it SHALL execute as `brave.web_search(query="test")`

#### Scenario: Unknown alias passthrough
- **GIVEN** command `unknown(arg=val)` where `unknown` is not a configured alias
- **WHEN** run() processes the command
- **THEN** it SHALL attempt to execute `unknown(arg=val)` directly

### Requirement: Snippet Expansion

The system SHALL expand snippet templates using Jinja2.

#### Scenario: Snippet invocation
- **GIVEN** command `$wsq q1=AI q2=ML p=Compare` where `wsq` snippet is configured
- **WHEN** run() processes the command
- **THEN** it SHALL expand the snippet template and execute the result

### Requirement: Project Pack Proxy

The `proj` pack SHALL use a special proxy supporting dynamic project attributes.

#### Scenario: Dynamic attribute resolution
- **GIVEN** `projects: { onetool: ~/projects/onetool }` in config
- **WHEN** code containing `proj.onetool` is executed
- **THEN** it SHALL resolve to the configured project path as `ProjectPath`

#### Scenario: Function priority
- **GIVEN** the `proj` pack has `path` and `list` functions
- **WHEN** `proj.path` or `proj.list` is accessed
- **THEN** the function SHALL be returned, not a project lookup

#### Scenario: Path operations in code
- **GIVEN** `projects: { onetool: ~/projects/onetool }` in config
- **WHEN** code containing `proj.onetool / "src"` is executed
- **THEN** it SHALL evaluate to the joined path as `ProjectPath`

#### Scenario: Error message for unknown project
- **GIVEN** `projects: { onetool: ~/projects/onetool }` in config
- **WHEN** code containing `proj.unknown` is executed
- **THEN** it SHALL raise `AttributeError` with message listing:
  - Available functions (path, list)
  - Available projects (onetool)

### Requirement: Runner Module Organization

The runner implementation SHALL be organized into focused modules.

#### Scenario: Fence processing isolation
- **GIVEN** the runner receives a fenced command
- **WHEN** fence stripping is needed
- **THEN** it SHALL use the dedicated `fence_processor` module

#### Scenario: Tool loading isolation
- **GIVEN** the runner needs to load tool functions
- **WHEN** tools are discovered and cached
- **THEN** it SHALL use the dedicated `tool_loader` module

#### Scenario: Pack proxy isolation
- **GIVEN** the runner builds execution namespace
- **WHEN** proxy objects are created for dot notation
- **THEN** it SHALL use the dedicated `pack_proxy` module

#### Scenario: Runner focused on orchestration
- **GIVEN** the runner module
- **WHEN** examining its responsibilities
- **THEN** it SHALL focus on code execution and command routing
- **AND** it SHALL import fence, loader, and proxy functionality from dedicated modules
