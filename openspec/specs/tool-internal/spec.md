# tool-internal Specification

## Purpose

Defines the structure and patterns for internal tools shipped with OneTool. Internal tools run in-process within onetool with direct access to bundled dependencies.
## Requirements
### Requirement: Internal Tool Module Structure

Internal tools SHALL follow a standard module structure with pack declaration, exports, and Config class.

#### Scenario: Module declaration
- **WHEN** an internal tool module is created
- **THEN** it declares `pack = "<name>"` at module level
- **AND** it declares `__all__ = [...]` listing exported functions
- **AND** it does NOT have a PEP 723 header

#### Scenario: Dependency requirements declaration
- **WHEN** an internal tool has external dependencies
- **THEN** it declares `__ot_requires__ = {"secrets": [...], "system": [...]}`
- **AND** dependencies are listed in `pyproject.toml` with tool-usage comments

#### Scenario: Config class discovery
- **WHEN** an internal tool needs configuration
- **THEN** it defines a `Config(BaseModel)` class at module level
- **AND** the registry auto-discovers the Config class

### Requirement: Internal Tool Imports

Internal tools SHALL use `ot.*` imports directly rather than `ot_sdk`.

#### Scenario: Logging import
- **WHEN** an internal tool needs structured logging
- **THEN** it imports `from ot.logging import LogSpan`
- **AND** uses `with LogSpan(span="pack.func", ...) as s:` pattern

#### Scenario: Config import
- **WHEN** an internal tool needs configuration
- **THEN** it imports `from ot.config import get_tool_config, get_secret`
- **AND** calls `get_tool_config("pack", Config)` to retrieve typed config

#### Scenario: Shared utilities import
- **WHEN** an internal tool needs utilities (truncate, batch, etc.)
- **THEN** it imports from `ot.utils` or `ot_sdk` (re-exported)
- **AND** both import paths work identically

#### Scenario: HTTP client usage
- **WHEN** an internal tool needs HTTP requests
- **THEN** it imports `httpx` directly
- **AND** does NOT use `ot_sdk.http` wrapper

### Requirement: Pack Variable Declaration

Internal tools SHALL use `pack` (not `namespace`) for grouping.

#### Scenario: Pack declaration
- **WHEN** an internal tool is created
- **THEN** it declares `pack = "<name>"` at module level
- **AND** functions are accessible as `<name>.<function>()`

#### Scenario: Namespace deprecation
- **WHEN** a tool file contains `namespace = "<name>"`
- **THEN** a deprecation warning is logged
- **AND** the value is treated as `pack`

### Requirement: Internal Tool Function Pattern

Internal tool functions SHALL use keyword-only arguments and return strings or structured data.

#### Scenario: Keyword-only arguments
- **WHEN** an internal tool function is defined
- **THEN** all parameters after `*` are keyword-only
- **AND** the function signature matches MCP tool schema

#### Scenario: Docstring format
- **WHEN** an internal tool function is defined
- **THEN** it has a Google-style docstring with Args, Returns, and Example sections
- **AND** the docstring is used for tool discovery

#### Scenario: LogSpan usage
- **WHEN** an internal tool function executes
- **THEN** it wraps the implementation in `with LogSpan(...) as s:`
- **AND** logs entry/exit timing and attributes

### Requirement: Pyproject.toml Dependency Management

All internal tool dependencies SHALL be declared in `pyproject.toml` with tool-usage comments.

#### Scenario: Dependency with comment
- **WHEN** a tool requires a new dependency
- **THEN** it is added to `pyproject.toml` dependencies section
- **AND** a comment indicates which tool uses it (e.g., `# excel, convert`)

#### Scenario: Optional dependency group
- **WHEN** a tool has optional dependencies (e.g., send2trash for file deletion)
- **THEN** they are declared in `[project.optional-dependencies]`
- **AND** the tool handles ImportError gracefully

### Requirement: No Worker Pattern

Internal tools SHALL NOT use the worker subprocess pattern.

#### Scenario: No worker_main
- **WHEN** an internal tool is created
- **THEN** it does NOT have `if __name__ == "__main__": worker_main()`
- **AND** it does NOT import `worker_main` from `ot_sdk`

#### Scenario: Direct function execution
- **WHEN** an internal tool function is called
- **THEN** it executes directly in the onetool process
- **AND** no JSON-RPC serialisation occurs

