# tool-conventions Specification

## Purpose

Defines common conventions and patterns that ALL tool implementations must follow. Individual tool specs reference this spec for standard behaviors instead of duplicating requirements.
## Requirements
### Requirement: File Structure

All tool files SHALL follow a standard structure.

#### Scenario: Module header
- **GIVEN** a tool file in `src/ot_tools/`
- **WHEN** the file is created
- **THEN** it SHALL include in order:
  1. Module docstring (description, requirements, references)
  2. `from __future__ import annotations`
  3. `pack = "<name>"` declaration
  4. `__all__ = [...]` export list
  5. Standard library imports
  6. Project imports
  7. Third-party imports (with graceful error handling)

#### Scenario: Pack declaration position
- **GIVEN** a tool file
- **WHEN** `pack` is declared
- **THEN** it SHALL appear before all imports except `from __future__`

#### Scenario: Export control
- **GIVEN** a tool file with multiple functions
- **WHEN** `__all__` is defined
- **THEN** only functions listed in `__all__` SHALL be exposed as tools
- **AND** imported functions SHALL NOT be exposed

---

### Requirement: Keyword-Only Arguments

All public tool functions SHALL use keyword-only arguments.

#### Scenario: Function signature
- **GIVEN** a public tool function
- **WHEN** the function is defined
- **THEN** it SHALL use `*,` to make all parameters keyword-only:
  ```python
  def search(*, query: str, count: int = 10) -> str:
  ```

#### Scenario: Why required
- **GIVEN** tools execute via JSON-RPC
- **WHEN** `WorkerFunctionProxy` forwards kwargs
- **THEN** positional arguments SHALL NOT be supported
- **AND** positional arguments SHALL cause runtime errors

---

### Requirement: Docstring Format

All public tool functions SHALL include complete docstrings.

#### Scenario: Required sections
- **GIVEN** a public tool function
- **WHEN** the docstring is written
- **THEN** it SHALL include:
  - Brief one-line description (imperative form)
  - Args section with all parameters
  - Returns section describing output
  - Example section with realistic usage

#### Scenario: Args documentation
- **GIVEN** function parameters
- **WHEN** documented in Args section
- **THEN** each SHALL include: name, description, type info, default value

#### Scenario: Example format
- **GIVEN** an Example section
- **WHEN** examples are provided
- **THEN** they SHALL show pack.function() calls with realistic parameters

---

### Requirement: Logging with LogSpan

All public tool functions SHALL use LogSpan for structured operation logging.

#### Scenario: LogSpan wrapper
- **GIVEN** a public tool function
- **WHEN** the function executes
- **THEN** it SHALL wrap execution in `LogSpan` context manager

#### Scenario: Span naming
- **GIVEN** a tool in pack `pack` with function `fn`
- **WHEN** LogSpan is created
- **THEN** span name SHALL be `{pack}.{fn}` (e.g., `brave.search`, `db.query`)

#### Scenario: Input logging
- **GIVEN** a function with input parameters
- **WHEN** LogSpan is created
- **THEN** key inputs SHALL be logged as span fields

#### Scenario: Result metrics
- **GIVEN** a function that returns results
- **WHEN** the function completes successfully
- **THEN** it SHALL add result metrics:
  - `resultCount` - number of items
  - `resultLen` - string length
  - `found` - boolean indicator

#### Scenario: Error logging
- **GIVEN** an error occurs
- **WHEN** within LogSpan
- **THEN** it SHALL add `error` field before returning
- **AND** span SHALL automatically log `status=FAILED`

#### Scenario: Import pattern
- **GIVEN** an in-process tool
- **WHEN** using LogSpan
- **THEN** import SHALL be `from ot.logging import LogSpan`

---

### Requirement: Error Handling

Tool functions SHALL return error messages as strings, not raise exceptions.

#### Scenario: Error return format
- **GIVEN** an error condition
- **WHEN** the function encounters the error
- **THEN** it SHALL return `"Error: {description}"`
- **AND** it SHALL NOT raise an exception

#### Scenario: API key missing
- **GIVEN** a tool requiring an API key
- **WHEN** the key is not configured
- **THEN** it SHALL return `"Error: {KEY_NAME} not configured in secrets.yaml"`

#### Scenario: HTTP error
- **GIVEN** an HTTP request fails
- **WHEN** the response has an error status
- **THEN** it SHALL return `"HTTP error ({status}): {message}"`

#### Scenario: Validation error
- **GIVEN** an input validation fails
- **WHEN** the function is called
- **THEN** it SHALL return `"Error: {validation description}"`

---

### Requirement: API Key Configuration

Tools requiring API keys SHALL use secrets.yaml for configuration.

#### Scenario: Key retrieval
- **GIVEN** a tool requiring `MY_API_KEY`
- **WHEN** the function needs the key
- **THEN** it SHALL use `get_secret("MY_API_KEY")`

#### Scenario: Missing key handling
- **GIVEN** `get_secret()` returns None or empty
- **WHEN** the key is required
- **THEN** the function SHALL return an error message
- **AND** log the error via LogSpan

#### Scenario: In-process tools
- **GIVEN** an in-process tool
- **WHEN** accessing secrets
- **THEN** it SHALL use `from ot.config.secrets import get_secret`

#### Scenario: Worker tools
- **GIVEN** a worker tool
- **WHEN** accessing secrets
- **THEN** it SHALL use `from ot_sdk import get_secret`

---

### Requirement: Configuration Access

Tools SHALL access configuration via get_config().

#### Scenario: Tool-specific config
- **GIVEN** a tool with configurable options
- **WHEN** accessing configuration
- **THEN** it SHALL use `get_config().tools.<pack>.<field>`

#### Scenario: Default values
- **GIVEN** a config field is not set
- **WHEN** accessed
- **THEN** the Pydantic model default SHALL be used

#### Scenario: In-process tools
- **GIVEN** an in-process tool
- **WHEN** accessing config
- **THEN** it SHALL use `from ot.config import get_config`

#### Scenario: Worker tools
- **GIVEN** a worker tool
- **WHEN** accessing config
- **THEN** it SHALL use `from ot_sdk import get_config`

---

### Requirement: HTTP Client Usage

Tools making HTTP requests SHALL use httpx with proper error handling.

#### Scenario: Request pattern
- **GIVEN** a tool making HTTP requests
- **WHEN** implementing the request
- **THEN** it SHALL use `httpx.Client` with configurable timeout

#### Scenario: Error handling
- **GIVEN** an HTTP request
- **WHEN** catching errors
- **THEN** it SHALL handle:
  - `httpx.HTTPStatusError` - HTTP errors
  - `httpx.RequestError` - Network errors

#### Scenario: Return pattern
- **GIVEN** a helper function for HTTP requests
- **WHEN** returning results
- **THEN** it SHALL return `tuple[bool, dict | str]`:
  - `(True, data)` on success
  - `(False, error_message)` on failure

---

### Requirement: Input Validation

Tools SHALL validate inputs early and return clear error messages.

#### Scenario: Required parameter missing
- **GIVEN** a required parameter is empty or None
- **WHEN** the function is called
- **THEN** it SHALL return `"Error: {param} is required"`

#### Scenario: Numeric clamping
- **GIVEN** a numeric parameter with valid range
- **WHEN** a value outside the range is provided
- **THEN** it SHALL clamp to the valid range (not error)
- **AND** log a warning if significantly out of range

#### Scenario: String length validation
- **GIVEN** a parameter with length limit
- **WHEN** input exceeds the limit
- **THEN** it SHALL return `"Error: {param} exceeds {limit} character limit ({actual} chars)"`

---

### Requirement: Output Formatting

Tools SHALL format output consistently.

#### Scenario: Empty results
- **GIVEN** a query returns no results
- **WHEN** formatting output
- **THEN** it SHALL return `"No results found."` or similar

#### Scenario: Native type returns
- **GIVEN** structured data output (lists, dicts)
- **WHEN** returning from a tool function
- **THEN** it SHALL return the native Python type directly
- **AND** serialization to JSON occurs at the runner level via `serialize_result()`

#### Scenario: String returns
- **GIVEN** a tool returning text output or error messages
- **WHEN** returning from a tool function
- **THEN** it SHALL return a plain string
- **AND** strings pass through the runner unchanged

#### Scenario: Result truncation
- **GIVEN** output exceeds max length
- **WHEN** truncating
- **THEN** it SHALL append truncation indicator (e.g., "... (truncated)")

#### Scenario: Runner serialization
- **GIVEN** a tool returns a dict or list
- **WHEN** the runner captures the result
- **THEN** it SHALL serialize using `serialize_result()` from `ot.utils`
- **AND** the output SHALL be compact JSON with no whitespace

---

### Requirement: Worker Tool Requirements

Worker tools (with PEP 723 headers) SHALL follow additional requirements.

#### Scenario: PEP 723 header
- **GIVEN** a tool with external dependencies
- **WHEN** declaring dependencies
- **THEN** it SHALL include:
  ```python
  # /// script
  # requires-python = ">=3.11"
  # dependencies = ["my-dep>=1.0", "httpx>=0.27.0", "pyyaml>=6.0.0"]
  # ///
  ```

#### Scenario: Required SDK dependencies
- **GIVEN** a worker tool
- **WHEN** listing PEP 723 dependencies
- **THEN** it SHALL include `httpx>=0.27.0` and `pyyaml>=6.0.0`

#### Scenario: Worker entry point
- **GIVEN** a worker tool
- **WHEN** the file is executed
- **THEN** it SHALL include:
  ```python
  if __name__ == "__main__":
      worker_main()
  ```

#### Scenario: SDK imports
- **GIVEN** a worker tool
- **WHEN** importing utilities
- **THEN** it SHALL use `from ot_sdk import ...`
- **NOT** `from ot.* import ...`

---

### Requirement: Batch Operations

Tools supporting batch operations SHALL use concurrent execution.

#### Scenario: Concurrent execution
- **GIVEN** a batch operation
- **WHEN** executing multiple requests
- **THEN** it SHALL use `ThreadPoolExecutor` for concurrency

#### Scenario: Max workers
- **GIVEN** concurrent execution
- **WHEN** configuring the pool
- **THEN** it SHALL limit to reasonable max_workers (default: 5)

#### Scenario: Result aggregation
- **GIVEN** batch results
- **WHEN** formatting output
- **THEN** each result SHALL be labeled with its input

---

### Requirement: Type Hints

All tool functions SHALL use type hints consistently.

#### Scenario: Return type
- **GIVEN** a public tool function
- **WHEN** defining the signature
- **THEN** it SHALL specify `-> str` return type

#### Scenario: Parameter types
- **GIVEN** function parameters
- **WHEN** defining the signature
- **THEN** all parameters SHALL have type hints

#### Scenario: Literal types
- **GIVEN** a parameter with enumerated values
- **WHEN** defining the type
- **THEN** it SHALL use `Literal["value1", "value2", ...]`

---

### Requirement: Tool Specification

Each tool SHALL have an OpenSpec specification.

#### Scenario: Spec file location
- **GIVEN** a tool named `<name>`
- **WHEN** creating its specification
- **THEN** it SHALL be at `openspec/specs/tool-<name>/spec.md`

#### Scenario: Spec references conventions
- **GIVEN** a tool specification
- **WHEN** describing common patterns
- **THEN** it SHALL reference this spec (tool-conventions)
- **NOT** duplicate the requirements

#### Scenario: Spec content
- **GIVEN** a tool specification
- **WHEN** documenting the tool
- **THEN** it SHALL focus on:
  - Tool-specific functionality
  - API-specific scenarios
  - Unique error conditions

### Requirement: Format Helper Module

A centralised serialization helper SHALL provide consistent output formatting at the runner level.

#### Scenario: Module location
- **GIVEN** the serialization helper module
- **WHEN** locating it
- **THEN** it SHALL be at `src/ot/utils/format.py`

#### Scenario: Dict and list serialization
- **GIVEN** `serialize_result(data)` is called with a dict or list
- **WHEN** serializing for MCP response
- **THEN** it SHALL return compact JSON with no whitespace: `{"key":"value"}`

#### Scenario: String passthrough
- **GIVEN** `serialize_result(data)` is called with a string
- **WHEN** serializing for MCP response
- **THEN** it SHALL return the string unchanged

#### Scenario: Unicode handling
- **GIVEN** data contains non-ASCII characters
- **WHEN** serialized
- **THEN** it SHALL preserve Unicode (not escape to `\uXXXX`)

### Requirement: Source Attribution Model

Tool implementations SHALL follow a three-tier attribution model for upstream acknowledgment.

#### Scenario: Attribution levels
- **GIVEN** a tool implementation
- **WHEN** determining attribution level
- **THEN** it SHALL be classified as one of:
  - **Based on**: Code derived or ported from upstream project
  - **Inspired by**: Similar functionality with independent implementation
  - **Original**: Clean room implementation or API wrapper

#### Scenario: Based on requirements
- **GIVEN** a tool classified as "Based on"
- **WHEN** implementing the tool
- **THEN** it SHALL include in the module docstring:
  ```
  Based on {project-name} by {Author Name} ({License}).
  {URL}
  ```
- **AND** a license file SHALL exist at `licenses/{project-name}-LICENSE`

#### Scenario: Inspired by requirements
- **GIVEN** a tool classified as "Inspired by"
- **WHEN** implementing the tool
- **THEN** it SHALL include in the module docstring:
  ```
  Inspired by {project-name} by {Author Name} ({License}).
  {URL}
  ```
- **AND** no license file is required (independent code)

#### Scenario: Original requirements
- **GIVEN** a tool classified as "Original"
- **WHEN** implementing the tool
- **THEN** it MAY optionally include a reference comment:
  ```
  API docs: {URL}
  ```
- **AND** no attribution section is required

### Requirement: License File Management

Tools derived from upstream projects SHALL include license files.

#### Scenario: License file location
- **GIVEN** a "Based on" tool
- **WHEN** including the license
- **THEN** the license file SHALL be at `licenses/{project-name}-LICENSE`
- **AND** the file SHALL be a copy of the upstream LICENSE file

#### Scenario: License file naming
- **GIVEN** an upstream project named "my-project"
- **WHEN** creating the license file
- **THEN** it SHALL be named `my-project-LICENSE`

#### Scenario: No license for inspired tools
- **GIVEN** an "Inspired by" tool
- **WHEN** checking license requirements
- **THEN** no license file SHALL be required
- **AND** the independent implementation does not create license obligations

### Requirement: Attribution Consistency

Source code attribution SHALL match documentation attribution.

#### Scenario: Source header matches doc
- **GIVEN** a tool with source header attribution
- **WHEN** the tool documentation is written
- **THEN** the attribution level in the doc SHALL match the source header
- **AND** "Based on" in source requires "Based on" section in doc
- **AND** "Inspired by" in source requires "Inspired by" section in doc

#### Scenario: No source attribution
- **GIVEN** a tool without source header attribution
- **WHEN** the tool documentation is written
- **THEN** the doc SHALL NOT include an attribution section

