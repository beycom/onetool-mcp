# tool-sdk Specification

## Purpose

Provides the ot_sdk package for building worker tools with isolated dependencies and JSON-RPC communication.
## Requirements
### Requirement: Worker Main Loop

The SDK SHALL provide a `worker_main()` function that implements the standard worker message loop.

#### Scenario: Tool entry point
- **WHEN** a tool is executed as a subprocess
- **AND** the main block calls `worker_main()`
- **THEN** the worker enters the JSON-RPC message loop
- **AND** dispatches incoming requests to tool functions

#### Scenario: Graceful shutdown
- **WHEN** the worker receives EOF on stdin
- **THEN** the worker exits cleanly

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

The SDK SHALL provide common utility functions for tool development.

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

