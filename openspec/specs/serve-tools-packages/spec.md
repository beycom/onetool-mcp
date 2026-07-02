# serve-tools-packages Specification

## Purpose

Defines how bundled and installed tool packs are discovered, exposed, and
described through execution, help, and pack discovery surfaces.
## Requirements
### Requirement: Tool Auto-Discovery

OneTool SHALL auto-discover tools from bundled core packs and installed domain extra packs.

#### Scenario: Core tool discovery on startup
- **GIVEN** bundled core tool packs are installed
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

OneTool SHALL extract tool metadata without running arbitrary top-level tool
code during discovery.

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
- **THEN** the file SHALL NOT be executed during metadata discovery

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

#### Scenario: Signature metadata
- **GIVEN** a discovered tool function
- **WHEN** help or discovery surfaces describe the tool
- **THEN** the parameter metadata SHALL show keyword parameter names and defaults
