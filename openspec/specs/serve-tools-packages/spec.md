# serve-tools-packages Specification

## Purpose

Defines how tools are organized and discovered. Tools are auto-discovered from the `src/ot_tools/` directory using AST parsing. Individual tool specifications are defined in separate specs (tool-web-fetch, tool-brave-search, tool-context7, tool-code-search, tool-demo).
## Requirements
### Requirement: Tool Auto-Discovery

OneTool SHALL auto-discover tools from Python files in the `src/ot_tools/` directory.

#### Scenario: Tool discovery on startup
- **GIVEN** Python files in the `src/ot_tools/` directory
- **WHEN** the server starts
- **THEN** it SHALL scan all `.py` files for public functions with docstrings

#### Scenario: New tool detection
- **GIVEN** a new `.py` file added to `src/ot_tools/`
- **WHEN** a tool call is made or registry is rescanned
- **THEN** the new tool SHALL be discovered and available

#### Scenario: Tool removal
- **GIVEN** a `.py` file removed from `src/ot_tools/`
- **WHEN** the registry is rescanned
- **THEN** the tool SHALL no longer be available

### Requirement: Tool Metadata Extraction

OneTool SHALL extract metadata from tool functions using AST parsing.

#### Scenario: Function signature extraction
- **GIVEN** a function with type hints
- **WHEN** the tool is discovered
- **THEN** it SHALL extract parameter names, types, and defaults

#### Scenario: Docstring extraction
- **GIVEN** a function with a Google-style docstring
- **WHEN** the tool is discovered
- **THEN** it SHALL extract the description, args, and returns sections

#### Scenario: No execution during discovery
- **GIVEN** a Python file with top-level code
- **WHEN** the tool is discovered
- **THEN** the file SHALL NOT be executed (AST parsing only)

### Requirement: Keyword-Only Arguments

All tool functions SHALL use keyword-only arguments.

#### Scenario: Keyword-only enforcement
- **GIVEN** a tool function definition
- **WHEN** the function is called with positional arguments
- **THEN** it SHALL raise TypeError
- **EXAMPLE** `add(1, 2)` raises error; use `add(a=1, b=2)`

#### Scenario: Function signature
- **GIVEN** a tool function
- **WHEN** defined
- **THEN** it SHALL use `*` to enforce keyword-only arguments
- **EXAMPLE** `def my_tool(*, arg1: str, arg2: int) -> str:`

