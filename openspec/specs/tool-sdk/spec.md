# tool-sdk Specification

## Purpose

Provides the ot_sdk package for building extension tools with isolated dependencies and JSON-RPC communication.
## Requirements
### Requirement: Worker Main Loop

The SDK SHALL provide a `worker_main()` function that implements the standard worker message loop for extension tools.

#### Scenario: Tool entry point
- **WHEN** an extension tool is executed as a subprocess
- **AND** the main block calls `worker_main()`
- **THEN** the worker enters the JSON-RPC message loop
- **AND** dispatches incoming requests to tool functions

#### Scenario: Graceful shutdown
- **WHEN** the worker receives EOF on stdin
- **THEN** the worker exits cleanly

#### Scenario: Internal tools do not use worker_main
- **WHEN** an internal tool (shipped with onetool) is loaded
- **THEN** it does NOT call `worker_main()`
- **AND** executes directly in-process

### Requirement: Secret Access

The SDK SHALL provide a `get_secret(name)` function for accessing secrets from `secrets.yaml`.

#### Scenario: Retrieve secret
- **WHEN** a tool calls `get_secret("brave_api_key")`
- **THEN** the SDK returns the value from secrets.yaml
- **AND** secrets are never exposed in environment variables

#### Scenario: Missing secret
- **WHEN** a tool requests a non-existent secret
- **THEN** the SDK returns None

### Requirement: Configuration Access

The SDK SHALL provide a `get_config(path)` function for accessing configuration from `ot-serve.yaml`.

#### Scenario: Retrieve config value
- **WHEN** a tool calls `get_config("tools.brave_search.timeout")`
- **THEN** the SDK returns the configured value

#### Scenario: Missing config
- **WHEN** a tool requests a non-existent config path
- **THEN** the SDK returns None or a default value

### Requirement: Structured Logging

The SDK SHALL provide a `log()` context manager for structured logging.

#### Scenario: Log with span
- **WHEN** a tool uses `with log("brave.search", query=query) as span:`
- **THEN** timing and attributes are captured
- **AND** logs are sent to stderr as JSON lines

#### Scenario: Add attributes during execution
- **WHEN** a tool calls `span.add(count=10)`
- **THEN** the attribute is included in the final log entry

### Requirement: HTTP Client

The SDK SHALL provide an `http` module with pre-configured HTTP client functionality.

#### Scenario: HTTP GET request
- **WHEN** a tool calls `http.get(url, headers={...})`
- **THEN** the request is made with default timeouts and retry logic
- **AND** the response is returned

#### Scenario: Custom HTTP client
- **WHEN** a tool needs custom configuration
- **THEN** `http.client(timeout=60.0, headers={...})` returns a configured httpx.Client

#### Scenario: Connection pooling
- **WHEN** multiple requests are made
- **THEN** connections are reused from the pool

### Requirement: Caching

The SDK SHALL provide caching utilities for memoization and manual cache operations.

#### Scenario: Memoized function
- **WHEN** a function is decorated with `@cache(ttl=3600)`
- **THEN** results are cached for the specified TTL
- **AND** subsequent calls return cached results

#### Scenario: Manual cache operations
- **WHEN** a tool uses `cache.set("key", value, ttl=600)`
- **THEN** the value is stored in memory
- **AND** `cache.get("key")` returns it before expiration

#### Scenario: Cache expiration
- **WHEN** a cached value's TTL expires
- **THEN** `cache.get("key")` returns None
- **AND** the next decorated function call recomputes the value

### Requirement: Utility Functions

The SDK SHALL provide common utility functions that are shared between internal and extension tools via re-export from `ot.utils`.

#### Scenario: Truncate long output
- **WHEN** a tool calls `truncate(text, max_length=50000)`
- **AND** text exceeds the limit
- **THEN** the output is truncated with an indicator (default: "...")

#### Scenario: Format error
- **WHEN** a tool calls `format_error("Failed to connect", details={"url": url, "status": 503})`
- **THEN** returns formatted string: `Error: Failed to connect (url=https://..., status=503)`

#### Scenario: Run subprocess
- **WHEN** a tool calls `run_command(["rg", "--json", pattern, path], timeout=30)`
- **THEN** the command is executed with the specified timeout
- **AND** returns tuple `(returncode, stdout, stderr)`

#### Scenario: Import from ot.utils
- **WHEN** an internal tool imports `from ot.utils import truncate`
- **THEN** it receives the same implementation as `from ot_sdk import truncate`

### Requirement: Testing Support

The SDK SHALL support testing tools without the full worker loop.

#### Scenario: Mock secrets in tests
- **WHEN** a test sets `ot_sdk.config._current_secrets = {"api_key": "test"}`
- **THEN** subsequent `get_secret("api_key")` calls return "test"
- **AND** no actual secrets.yaml is read

#### Scenario: Mock config in tests
- **WHEN** a test sets `ot_sdk.config._current_config = {"tools": {"timeout": 5}}`
- **THEN** subsequent `get_config("tools.timeout")` calls return 5

#### Scenario: Direct function testing
- **WHEN** a test imports and calls a tool function directly
- **THEN** the function executes without requiring the worker loop
- **AND** module-level config/secrets can be set for testing

### Requirement: Project Path Resolution

The SDK SHALL provide a `get_project_path(path)` function for resolving paths relative to the project working directory.

#### Scenario: Resolve relative path
- **GIVEN** project path is available via config `_project_path`
- **WHEN** a tool calls `get_project_path("diagrams/flow.svg")`
- **THEN** the SDK returns an absolute path joining `_project_path` with the relative path

#### Scenario: Preserve absolute paths
- **WHEN** a tool calls `get_project_path("/tmp/output.svg")`
- **THEN** the SDK returns `/tmp/output.svg` unchanged

#### Scenario: Expand tilde
- **WHEN** a tool calls `get_project_path("~/output.svg")`
- **THEN** the SDK returns the path with `~` expanded to home directory

#### Scenario: Fallback to cwd
- **GIVEN** `_project_path` is not in config
- **WHEN** a tool calls `get_project_path("output.svg")`
- **THEN** the SDK resolves relative to `Path.cwd()`

### Requirement: Config Path Resolution

The SDK SHALL provide a `get_config_path(path)` function for resolving paths relative to the config directory.

#### Scenario: Resolve relative path
- **GIVEN** config directory is available via config `_config_dir`
- **WHEN** a tool calls `get_config_path("templates/flow.mmd")`
- **THEN** the SDK returns an absolute path joining `_config_dir` with the relative path

#### Scenario: Preserve absolute paths
- **WHEN** a tool calls `get_config_path("/etc/templates/flow.mmd")`
- **THEN** the SDK returns `/etc/templates/flow.mmd` unchanged

#### Scenario: Expand tilde
- **WHEN** a tool calls `get_config_path("~/templates/flow.mmd")`
- **THEN** the SDK returns the path with `~` expanded to home directory

#### Scenario: Fallback to cwd
- **GIVEN** `_config_dir` is not in config
- **WHEN** a tool calls `get_config_path("templates/flow.mmd")`
- **THEN** the SDK resolves relative to `Path.cwd()`

### Requirement: Path Expansion Utility

The SDK SHALL provide an `expand_path(path)` function for basic path expansion.

#### Scenario: Expand tilde only
- **WHEN** a tool calls `expand_path("~/config.yaml")`
- **THEN** the SDK returns the path with `~` expanded to home directory

#### Scenario: No variable expansion
- **WHEN** a tool calls `expand_path("${HOME}/config.yaml")`
- **THEN** the SDK returns the literal path `${HOME}/config.yaml` (no variable expansion)

### Requirement: Unified Path Resolution

The SDK SHALL provide a `resolve_path(path, base)` function for path resolution with prefix support.

#### Scenario: Default base (CWD)
- **WHEN** a tool calls `resolve_path("data/file.txt")`
- **THEN** the SDK resolves the path relative to the project working directory (OT_CWD)

#### Scenario: OT_DIR base
- **WHEN** a tool calls `resolve_path("templates/flow.mmd", base="OT_DIR")`
- **THEN** the SDK resolves the path relative to the active .onetool directory

#### Scenario: GLOBAL base
- **WHEN** a tool calls `resolve_path("logs/app.log", base="GLOBAL")`
- **THEN** the SDK resolves the path relative to ~/.onetool/

#### Scenario: Prefix overrides base
- **WHEN** a tool calls `resolve_path("GLOBAL/logs/app.log", base="CWD")`
- **THEN** the GLOBAL prefix overrides the CWD base
- **AND** the SDK resolves relative to ~/.onetool/

#### Scenario: CWD prefix
- **WHEN** a tool calls `resolve_path("CWD/output.txt", base="OT_DIR")`
- **THEN** the CWD prefix overrides the OT_DIR base
- **AND** the SDK resolves relative to the project working directory

#### Scenario: OT_DIR prefix
- **WHEN** a tool calls `resolve_path("OT_DIR/templates/flow.mmd", base="CWD")`
- **THEN** the OT_DIR prefix overrides the CWD base
- **AND** the SDK resolves relative to the active .onetool directory

#### Scenario: Tilde prefix
- **WHEN** a tool calls `resolve_path("~/shared/file.txt")`
- **THEN** the SDK expands ~ to the home directory

#### Scenario: Absolute path unchanged
- **WHEN** a tool calls `resolve_path("/tmp/output.txt")`
- **THEN** the SDK returns `/tmp/output.txt` unchanged

### Requirement: CWD Path Resolution

The SDK SHALL provide a `resolve_cwd_path(path)` convenience function.

#### Scenario: Resolve relative to CWD
- **WHEN** a tool calls `resolve_cwd_path("data/file.txt")`
- **THEN** the SDK resolves the path relative to the project working directory
- **AND** this is equivalent to `resolve_path(path, base="CWD")`

### Requirement: OT_DIR Path Resolution

The SDK SHALL provide a `resolve_ot_path(path)` convenience function.

#### Scenario: Resolve relative to OT_DIR
- **WHEN** a tool calls `resolve_ot_path("templates/flow.mmd")`
- **THEN** the SDK resolves the path relative to the active .onetool directory
- **AND** this is equivalent to `resolve_path(path, base="OT_DIR")`

### Requirement: Get OT_DIR

The SDK SHALL provide a `get_ot_dir()` function to get the active OneTool config directory.

#### Scenario: Config dir from context
- **GIVEN** `_config_dir` is set in the worker config
- **WHEN** a tool calls `get_ot_dir()`
- **THEN** the SDK returns the configured config directory path

#### Scenario: Project-local .onetool
- **GIVEN** `_config_dir` is not set
- **AND** `.onetool/` exists in the project directory
- **WHEN** a tool calls `get_ot_dir()`
- **THEN** the SDK returns the project's `.onetool/` path

#### Scenario: Global fallback
- **GIVEN** `_config_dir` is not set
- **AND** no project `.onetool/` exists
- **WHEN** a tool calls `get_ot_dir()`
- **THEN** the SDK returns `~/.onetool/`

### Requirement: Shared Utilities Re-export

The SDK SHALL re-export context-agnostic utilities from `ot.utils` to maintain a stable API for extension tools.

#### Scenario: Truncate utilities re-export
- **WHEN** an extension tool imports `from ot_sdk import truncate, format_error`
- **THEN** it receives re-exports from `ot.utils.truncate`

#### Scenario: Batch utilities re-export
- **WHEN** an extension tool imports `from ot_sdk import batch_execute, normalize_items, format_batch_results`
- **THEN** it receives re-exports from `ot.utils.batch`

#### Scenario: HTTP utilities (extension-specific)
- **WHEN** an extension tool imports `from ot_sdk import safe_request, api_headers, check_api_key`
- **THEN** it receives extension-specific implementations from `ot_sdk.request`
- **AND** these use `ot_sdk.config.get_secret` (JSON-RPC) rather than direct config access

#### Scenario: Dependency utilities re-export
- **WHEN** an extension tool imports `from ot_sdk import ensure_cli, ensure_lib, check_cli, check_lib`
- **THEN** it receives re-exports from `ot.utils.deps`

#### Scenario: Factory utilities re-export
- **WHEN** an extension tool imports `from ot_sdk import lazy_client, LazyClient`
- **THEN** it receives re-exports from `ot.utils.factory`

### Requirement: SDK Purpose Documentation

The SDK module docstring SHALL clarify that ot_sdk is for extension tools only.

#### Scenario: Module docstring
- **WHEN** a developer reads the ot_sdk module
- **THEN** the docstring clearly states it is for extension tools
- **AND** internal tools should use `ot.*` imports instead

### Requirement: Context-Specific Functions

The SDK SHALL provide functions that have extension-specific implementations distinct from `ot.*` equivalents.

#### Scenario: Config via JSON-RPC
- **WHEN** an extension tool calls `get_config(path)`
- **THEN** the SDK retrieves the value from `_current_config` (set via JSON-RPC)
- **AND** this differs from internal tools which use `ot.config.get_tool_config()`

#### Scenario: Secret via JSON-RPC
- **WHEN** an extension tool calls `get_secret(name)`
- **THEN** the SDK retrieves the value from `_current_secrets` (set via JSON-RPC)
- **AND** this differs from internal tools which use `ot.config.get_secret()`

#### Scenario: Logging to stderr
- **WHEN** an extension tool uses `with log("pack.func") as s:`
- **THEN** logs are written to stderr as JSON lines for collection
- **AND** this differs from internal tools which use `ot.logging.LogSpan`

