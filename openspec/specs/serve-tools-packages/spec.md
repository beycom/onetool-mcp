# serve-tools-packages Specification

## Purpose

Defines how tools are organized and discovered. Tools are auto-discovered from the `src/ottools/` directory using AST parsing. Individual tool specifications are defined in separate specs (tool-web, tool-brave, tool-context7, etc.).
## Requirements
### Requirement: Tool Auto-Discovery

OneTool SHALL auto-discover tools from bundled core packs and installed domain extra packs.

#### Scenario: Core tool discovery on startup
- **GIVEN** Python files in the bundled `src/ottools/` package
- **WHEN** the server starts
- **THEN** it SHALL scan tool modules for public callable functions with docstrings

#### Scenario: Domain extra tool discovery on startup
- **GIVEN** installed domain packages exposing `otdev.tools` and/or `otutil.tools`
- **WHEN** the server starts
- **THEN** it SHALL include those pack modules in discovery
- **AND** pack namespaces from those modules SHALL be callable

#### Scenario: New domain tool pack detection
- **GIVEN** a new pack module is added under `otdev.tools` or `otutil.tools`
- **WHEN** tool loading or registry rescan occurs
- **THEN** the new pack SHALL be discoverable and callable without additional registry wiring changes

#### Scenario: Tool removal
- **GIVEN** a previously discovered pack module is removed
- **WHEN** the registry is rescanned
- **THEN** the removed pack SHALL no longer be available

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

#### Scenario: Pack metadata extraction
- **GIVEN** a pack module declares `pack_aliases` or `doc_slug` beside `pack = "..."`
- **WHEN** the tool registry scans the module
- **THEN** aliases and doc slug metadata SHALL be available to execution, help, and pack discovery surfaces

#### Scenario: Runtime service registration
- **GIVEN** a loaded pack module exposes `register_services(registry)`
- **WHEN** the execution tool loader imports the module
- **THEN** it SHALL call the registration function explicitly
- **AND** packs MAY register output policy, result-store, compaction, LLM, or reload hooks without core importing concrete pack modules

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
