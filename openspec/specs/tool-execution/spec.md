# tool-execution Specification

## Purpose

Defines how external tools execute in persistent worker subprocesses with JSON-RPC communication over stdin/stdout.
## Requirements
### Requirement: Persistent Worker Subprocess Execution

Extension tools (user-created tools with PEP 723 headers) SHALL execute in persistent worker subprocesses that handle multiple calls, rather than spawning a new process per call.

#### Scenario: Worker startup on first call
- **WHEN** an extension tool function is called for the first time
- **THEN** the system spawns a worker subprocess using `uv run`
- **AND** the worker remains running for subsequent calls

#### Scenario: Subsequent calls use existing worker
- **WHEN** an extension tool function is called while its worker is running
- **THEN** the system routes the call to the existing worker via JSON-RPC
- **AND** no new subprocess is spawned

#### Scenario: Worker idle timeout
- **WHEN** a worker has been idle for 10 minutes (configurable)
- **THEN** the system terminates the worker subprocess
- **AND** removes it from the worker pool

#### Scenario: Session refresh on call
- **WHEN** an extension tool function is called
- **THEN** the worker's idle timer is reset
- **AND** the worker remains alive for another timeout period

### Requirement: PEP 723 Dependency Declaration

Extension tools SHALL declare dependencies using PEP 723 inline script metadata. The metadata parser SHALL use Python's `tomllib` standard library for full TOML spec compliance.

#### Scenario: Tool with dependencies
- **WHEN** a tool file contains `# /// script` metadata with dependencies
- **THEN** the system parses the TOML content using `tomllib`
- **AND** the system uses `uv run` to execute in an isolated environment
- **AND** dependencies are installed automatically

#### Scenario: TOML parsing compliance
- **WHEN** PEP 723 metadata is extracted from a tool file
- **THEN** the comment prefixes (`# `) are stripped from each line
- **AND** the content is parsed as valid TOML using `tomllib.loads()`
- **AND** malformed TOML is gracefully handled (returns None)

### Requirement: Internal Tool In-Process Execution

Internal tools (shipped with onetool, without PEP 723 headers) SHALL execute in-process within ot-serve with direct access to bundled dependencies.

#### Scenario: Internal tool detection
- **WHEN** a tool file in `src/ot_tools/` does NOT contain PEP 723 metadata
- **THEN** the system loads and executes it in-process
- **AND** it has direct access to ot-serve state

#### Scenario: Internal tool has ot-serve access
- **WHEN** an internal tool executes
- **THEN** it can access registry, config, and LLM capabilities directly
- **AND** uses `ot.*` imports (not `ot_sdk`)

#### Scenario: Internal tool dependencies
- **WHEN** an internal tool requires a dependency
- **THEN** the dependency is bundled in `pyproject.toml`
- **AND** no PEP 723 header is required

### Requirement: Extension Tool Location

Extension tools SHALL be discovered from the `.onetool/tools/` directory structure.

#### Scenario: Project extension discovery
- **WHEN** ot-serve starts
- **THEN** it scans `.onetool/tools/<pack>/<pack>_tools.py` for extensions
- **AND** loads them as worker-based tools

#### Scenario: Global extension discovery
- **WHEN** ot-serve starts
- **THEN** it also scans `~/.onetool/tools/<pack>/<pack>_tools.py`
- **AND** project extensions take precedence over global extensions

### Requirement: Tool Type Detection

The system SHALL distinguish between internal and extension tools based on file location and PEP 723 headers.

#### Scenario: Internal tool identification
- **WHEN** a tool file is in `src/ot_tools/`
- **AND** has no PEP 723 header
- **THEN** it is loaded as an internal tool (in-process)

#### Scenario: Extension tool identification
- **WHEN** a tool file is in `.onetool/tools/`
- **AND** has a PEP 723 header
- **THEN** it is loaded as an extension tool (worker subprocess)

#### Scenario: Invalid extension without PEP 723
- **WHEN** a tool file is in `.onetool/tools/`
- **AND** has no PEP 723 header
- **THEN** it is still loaded but may fail if it has unmet dependencies

