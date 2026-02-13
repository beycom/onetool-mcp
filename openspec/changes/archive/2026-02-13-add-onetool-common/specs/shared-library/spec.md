## ADDED Requirements

### Requirement: Shared Configuration Loading
The `onetool-common` library SHALL provide a generic YAML configuration loader that supports file includes (up to 5 levels deep), recursive deep merge of dictionaries, array flattening, version validation, and Pydantic model validation with any user-provided schema class.

#### Scenario: Load config with default schema
- **WHEN** `load_config(path="~/.onetool/xero.yaml", schema=XeroConfig)` is called
- **THEN** the YAML file is loaded, includes are processed, secrets are expanded, and a validated `XeroConfig` instance is returned

#### Scenario: Config with includes
- **WHEN** a config file contains `include: [base.yaml, overrides.yaml]`
- **THEN** the included files are loaded and deep-merged (later files override earlier), up to 5 levels of nesting

#### Scenario: Config file not found
- **WHEN** the specified config path does not exist
- **THEN** a `ConfigNotFoundError` is raised with the path in the message

### Requirement: Secrets Management
The `onetool-common` library SHALL provide secrets loading from YAML files and variable expansion supporting `${VAR}` and `${VAR:-default}` syntax, with secrets checked before environment variables.

#### Scenario: Expand secret variable
- **WHEN** a config value contains `${XERO_CLIENT_ID}` and secrets file has `XERO_CLIENT_ID: abc123`
- **THEN** the value is expanded to `abc123`

#### Scenario: Expand with default
- **WHEN** a config value contains `${MISSING_VAR:-fallback}` and no secret or env var exists
- **THEN** the value is expanded to `fallback`

#### Scenario: Missing variable without default
- **WHEN** a config value contains `${REQUIRED_VAR}` and no secret or env var exists
- **THEN** an error is raised indicating the missing variable

### Requirement: Structured Logging
The `onetool-common` library SHALL provide structured logging via `LogEntry` (field-based log records with auto-timing) and `LogSpan` (context manager that logs on exit), backed by loguru with dev-friendly and JSON output formatters.

#### Scenario: LogSpan context manager
- **WHEN** code runs inside `with LogSpan(ctx="xero.get_invoices", count=10) as span:`
- **THEN** on exit, a structured log entry is emitted with the span context, fields, duration, and success/failure status

#### Scenario: Configure logging for backend
- **WHEN** `configure_logging(name="onetool-xero", level="INFO", log_file="~/.onetool/logs/xero.log")` is called
- **THEN** loguru is configured with file rotation (10MB), dev formatter on stderr (if TTY), and stdlib logging is intercepted

### Requirement: Path Resolution
The `onetool-common` library SHALL provide path resolution utilities for the shared `~/.onetool/` global directory, with environment variable overrides and subdirectory creation helpers.

#### Scenario: Get global directory
- **WHEN** `get_global_dir()` is called without env override
- **THEN** `~/.onetool/` is returned (expanded to absolute path)

#### Scenario: Environment override
- **WHEN** `OT_GLOBAL_DIR=/custom/path` is set and `get_global_dir()` is called
- **THEN** `/custom/path` is returned

#### Scenario: Ensure global directory
- **WHEN** `ensure_global_dir()` is called and `~/.onetool/` does not exist
- **THEN** the directory is created with `config/`, `logs/`, and `cache/` subdirectories

### Requirement: HTTP Client Utilities
The `onetool-common` library SHALL provide a shared httpx client with connection pooling, automatic shutdown, and helper functions for building API headers from secrets.

#### Scenario: HTTP GET with shared client
- **WHEN** `http_get(url="https://api.example.com/data", headers={"Authorization": "Bearer token"})` is called
- **THEN** the request uses a shared httpx client with connection pooling and returns parsed JSON or text

#### Scenario: API headers from secrets
- **WHEN** `api_headers(secret_name="BRAVE_API_KEY", header_name="X-Subscription-Token")` is called
- **THEN** the secret value is retrieved and a headers dict is returned with the specified header

### Requirement: Tool Wrapper Decorator
The `onetool-common` library SHALL provide a `@tool_wrapper()` decorator that auto-imports sync tool implementations and wraps them as async functions for FastMCP, preserving the original function signature for introspection.

#### Scenario: Wrap sync tool as async
- **WHEN** `@tool_wrapper("my_backend.tools.analytics")` decorates an async stub function
- **THEN** calling the function imports the sync implementation from the specified module and executes it

#### Scenario: Signature preservation
- **WHEN** a `@tool_wrapper` decorated function is registered with `@mcp.tool()`
- **THEN** FastMCP sees the original function signature (parameters, types, docstring) for schema generation

### Requirement: CLI Boilerplate
The `onetool-common` library SHALL provide Typer-based CLI helpers for creating backend server entry points with `--config` flag, `--version` flag, `init` subcommands, and first-run detection.

#### Scenario: Create CLI with config flag
- **WHEN** a backend uses the CLI helper with `create_cli(name="onetool-xero", default_config="~/.onetool/xero.yaml")`
- **THEN** a Typer app is created with `--config` option that defaults to the specified path

#### Scenario: First-run detection
- **WHEN** the backend CLI is run and no config file exists at the default path
- **THEN** the user is prompted to initialise (if TTY) or an error is shown (if non-interactive)
