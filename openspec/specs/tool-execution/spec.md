# tool-execution Specification

## Purpose

Defines how external tools execute in persistent worker subprocesses with JSON-RPC communication over stdin/stdout.
## Requirements
### Requirement: Persistent Worker Subprocess Execution

External tools SHALL execute in persistent worker subprocesses that handle multiple calls, rather than spawning a new process per call or executing in-process.

#### Scenario: Worker startup on first call
- **WHEN** an external tool function is called for the first time
- **THEN** the system spawns a worker subprocess using `uv run`
- **AND** the worker remains running for subsequent calls

#### Scenario: Subsequent calls use existing worker
- **WHEN** an external tool function is called while its worker is running
- **THEN** the system routes the call to the existing worker via JSON-RPC
- **AND** no new subprocess is spawned

#### Scenario: Worker idle timeout
- **WHEN** a worker has been idle for 10 minutes (configurable)
- **THEN** the system terminates the worker subprocess
- **AND** removes it from the worker pool

#### Scenario: Session refresh on call
- **WHEN** an external tool function is called
- **THEN** the worker's idle timer is reset
- **AND** the worker remains alive for another timeout period

### Requirement: JSON-RPC Communication Protocol

Workers SHALL communicate with the main process via JSON-RPC over stdin/stdout.

#### Scenario: Function call request
- **WHEN** the main process needs to call a worker function
- **THEN** it sends a JSON-RPC request: `{"function": "name", "kwargs": {...}, "config": {...}, "secrets": {...}}`
- **AND** config and secrets are passed with each request
- **AND** waits for a JSON-RPC response

#### Scenario: Successful response
- **WHEN** a worker function completes successfully
- **THEN** the worker sends: `{"result": "...", "error": null}`
- **AND** the main process returns the result to the caller

#### Scenario: Error response
- **WHEN** a worker function raises an exception
- **THEN** the worker sends: `{"result": null, "error": "message"}`
- **AND** the main process raises an appropriate exception

#### Scenario: Structured logging
- **WHEN** a worker logs using the SDK
- **THEN** logs are sent to stderr as JSON lines
- **AND** the main process can capture and display them

### Requirement: PEP 723 Dependency Declaration

External tools SHALL declare dependencies using PEP 723 inline script metadata. The metadata parser SHALL use Python's `tomllib` standard library for full TOML spec compliance.

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

### Requirement: Worker Lifecycle Management

The system SHALL manage worker process lifecycle including spawning, monitoring, and cleanup.

#### Scenario: Worker crash recovery
- **WHEN** a worker subprocess crashes unexpectedly
- **THEN** the system detects the dead process
- **AND** spawns a new worker on the next call

#### Scenario: Graceful shutdown
- **WHEN** ot-serve is shutting down
- **THEN** all active workers are terminated gracefully
- **AND** resources are cleaned up

### Requirement: Internal Tool In-Process Execution

Internal tools (without PEP 723 headers) SHALL continue to execute in-process within ot-serve.

#### Scenario: Internal tool detection
- **WHEN** a tool file does NOT contain PEP 723 metadata
- **THEN** the system loads and executes it in-process
- **AND** it has direct access to ot-serve state

#### Scenario: Internal tool has ot-serve access
- **WHEN** an internal tool executes
- **THEN** it can access registry, config, and LLM capabilities directly

