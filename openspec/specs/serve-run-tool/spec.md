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

#### Scenario: String passthrough
- **GIVEN** a tool function that returns a plain string
- **WHEN** the result is captured by the runner
- **THEN** the string SHALL be returned as-is without additional serialization

#### Scenario: Composed tool results
- **GIVEN** code like `{"health": ot.health(), "config": ot.config()}`
- **WHEN** each tool returns a native dict
- **THEN** the composed result SHALL be a single clean JSON object
- **AND** nested values SHALL NOT be double-escaped strings

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

### Requirement: Parameter Prefix Matching

The system SHALL resolve abbreviated parameter names to full parameter names using prefix matching.

#### Scenario: Exact parameter match
- **GIVEN** a tool function with parameter `query`
- **WHEN** called with `query="test"`
- **THEN** the parameter SHALL be passed through unchanged

#### Scenario: Single prefix match
- **GIVEN** a tool function with parameter `query`
- **WHEN** called with `q="test"`
- **THEN** the parameter SHALL resolve to `query="test"`

#### Scenario: Multiple prefix matches with first-wins
- **GIVEN** a tool function with parameters `query_info`, `query`, `quality` (in that order)
- **WHEN** called with `q="test"`
- **THEN** the parameter SHALL resolve to `query_info="test"` (first in signature order)

#### Scenario: Partial prefix match
- **GIVEN** a tool function with parameters `query_info`, `query`, `quality`
- **WHEN** called with `qual="test"`
- **THEN** the parameter SHALL resolve to `quality="test"` (only match)

#### Scenario: No match passthrough
- **GIVEN** a tool function with parameter `query`
- **WHEN** called with `xyz="test"`
- **THEN** the parameter SHALL be passed through unchanged
- **AND** the underlying function SHALL raise its normal error for unknown parameter

#### Scenario: Mixed exact and prefix parameters
- **GIVEN** a tool function with parameters `query`, `count`
- **WHEN** called with `query="test", c=5`
- **THEN** the parameters SHALL resolve to `query="test", count=5`

### Requirement: Prefix Matching Scope

Parameter prefix matching SHALL apply to all tool execution paths.

#### Scenario: Internal tool prefix matching
- **GIVEN** an internal tool (in-process, from `src/ot_tools/`)
- **WHEN** called with abbreviated parameter names
- **THEN** prefix matching SHALL be applied

#### Scenario: Extension tool prefix matching
- **GIVEN** an extension tool (worker subprocess, from `.onetool/tools/`)
- **WHEN** called with abbreviated parameter names
- **THEN** prefix matching SHALL be applied

#### Scenario: MCP proxy tool prefix matching
- **GIVEN** an MCP proxy tool
- **WHEN** called with abbreviated parameter names
- **THEN** prefix matching SHALL be applied using the tool's input schema

#### Scenario: ot pack tool prefix matching
- **GIVEN** an ot pack introspection tool (e.g., `ot.tools`, `ot.help`)
- **WHEN** called with abbreviated parameter names (e.g., `p="fire"` for `pattern`)
- **THEN** prefix matching SHALL be applied
- **AND** the abbreviated parameter SHALL resolve to the full parameter name

### Requirement: Output Format Control

The system SHALL support a `__format__` magic variable to control result serialisation.

#### Scenario: Default format (compact JSON)
- **GIVEN** code that returns a dict without setting `__format__`
- **WHEN** the result is serialised
- **THEN** it SHALL use compact JSON with no whitespace

#### Scenario: Explicit json format
- **GIVEN** code that sets `__format__ = "json"` and returns a dict
- **WHEN** the result is serialised
- **THEN** it SHALL use compact JSON (same as default)

#### Scenario: Human-readable JSON format
- **GIVEN** code that sets `__format__ = "json_h"` and returns a dict
- **WHEN** the result is serialised
- **THEN** it SHALL use JSON with 2-space indentation

#### Scenario: YAML flow format
- **GIVEN** code that sets `__format__ = "yml"` and returns a dict
- **WHEN** the result is serialised
- **THEN** it SHALL use YAML flow style (inline collections)

#### Scenario: Human-readable YAML format
- **GIVEN** code that sets `__format__ = "yml_h"` and returns a dict
- **WHEN** the result is serialised
- **THEN** it SHALL use YAML block style with proper indentation

#### Scenario: Raw format
- **GIVEN** code that sets `__format__ = "raw"` and returns any value
- **WHEN** the result is serialised
- **THEN** it SHALL use Python `str()` conversion

#### Scenario: String passthrough unchanged
- **GIVEN** code that returns a string (regardless of `__format__` setting)
- **WHEN** the result is serialised
- **THEN** the string SHALL be returned unchanged

#### Scenario: Invalid format ignored
- **GIVEN** code that sets `__format__` to an unknown value
- **WHEN** the result is serialised
- **THEN** it SHALL fall back to default compact JSON
