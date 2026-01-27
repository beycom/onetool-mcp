# tool-sdk Specification Delta

## ADDED Requirements

### Requirement: Pack Access

The SDK SHALL provide a `get_pack(name)` function for accessing other tool packs.

#### Scenario: Retrieve pack proxy
- **WHEN** a tool calls `get_pack("llm")`
- **AND** the llm pack is available
- **THEN** the SDK returns a pack proxy with callable methods
- **AND** the proxy passes config and secrets to the underlying tool

#### Scenario: Pack not found
- **WHEN** a tool calls `get_pack("nonexistent")`
- **THEN** the SDK returns None

### Requirement: Tool Invocation

The SDK SHALL provide a `call_tool(name, **kwargs)` function for calling tools by qualified name.

#### Scenario: Call tool successfully
- **WHEN** a tool calls `call_tool("llm.transform", input="hello", prompt="summarize")`
- **AND** the llm pack is available
- **THEN** the SDK invokes `llm.transform(input="hello", prompt="summarize")`
- **AND** returns the result

#### Scenario: Pack not found error
- **WHEN** a tool calls `call_tool("nonexistent.foo", arg="value")`
- **AND** the pack does not exist
- **THEN** the SDK raises `ValueError` with message "Pack not found: nonexistent"

### Requirement: Batch Execution

The SDK SHALL provide a `batch_execute()` function for concurrent processing of multiple items.

#### Scenario: Execute batch with default formatting
- **WHEN** a tool calls `batch_execute(["a", "b", "c"], processor_func)`
- **THEN** the SDK executes `processor_func` on each item concurrently
- **AND** returns formatted output with section separators

#### Scenario: Execute batch with labels
- **WHEN** a tool calls `batch_execute([("url1", "Site A"), ("url2", "Site B")], fetch_func)`
- **THEN** the SDK uses the labels in the formatted output
- **AND** preserves the original order

#### Scenario: Control concurrency
- **WHEN** a tool calls `batch_execute(items, func, max_workers=3)`
- **THEN** the SDK limits concurrent executions to 3

### Requirement: Item Normalization

The SDK SHALL provide a `normalize_items()` function for converting batch inputs to labelled tuples.

#### Scenario: Normalize strings
- **WHEN** a tool calls `normalize_items(["a", "b"])`
- **THEN** the SDK returns `[("a", "a"), ("b", "b")]`

#### Scenario: Preserve tuples
- **WHEN** a tool calls `normalize_items([("a", "Label A"), ("b", "Label B")])`
- **THEN** the SDK returns `[("a", "Label A"), ("b", "Label B")]`

### Requirement: Safe HTTP Requests

The SDK SHALL provide a `safe_request()` function for HTTP requests with error handling.

#### Scenario: Successful request
- **WHEN** a tool calls `safe_request(client, "GET", url)`
- **AND** the request succeeds
- **THEN** the SDK returns `(True, response_data)`

#### Scenario: HTTP error
- **WHEN** a tool calls `safe_request(client, "GET", url)`
- **AND** the server returns a 4xx or 5xx status
- **THEN** the SDK returns `(False, "HTTP error (status): truncated_body")`

#### Scenario: Connection error
- **WHEN** a tool calls `safe_request(client, "GET", url)`
- **AND** the connection fails
- **THEN** the SDK returns `(False, "Request failed: error_message")`

### Requirement: API Headers

The SDK SHALL provide an `api_headers()` function for building authentication headers from secrets.

#### Scenario: Bearer token header
- **WHEN** a tool calls `api_headers("MY_API_KEY")`
- **AND** the secret exists
- **THEN** the SDK returns `{"Authorization": "Bearer <secret_value>"}`

#### Scenario: Custom header name
- **WHEN** a tool calls `api_headers("BRAVE_API_KEY", header_name="X-Subscription-Token", prefix="")`
- **THEN** the SDK returns `{"X-Subscription-Token": "<secret_value>"}`

#### Scenario: Missing secret
- **WHEN** a tool calls `api_headers("MISSING_KEY")`
- **AND** the secret does not exist
- **THEN** the SDK returns an empty dict `{}`

### Requirement: Lazy Client Factory

The SDK SHALL provide a `lazy_client()` function for thread-safe lazy initialization.

#### Scenario: Create lazy getter
- **WHEN** a tool calls `lazy_client(lambda: ExpensiveClient())`
- **THEN** the SDK returns a callable that lazily initializes the client

#### Scenario: Thread-safe initialization
- **WHEN** multiple threads call the lazy getter simultaneously
- **THEN** the factory function is called exactly once
- **AND** all threads receive the same client instance

#### Scenario: Conditional initialization with secret
- **WHEN** a tool calls `lazy_client(factory, secret_name="API_KEY")`
- **AND** the secret does not exist
- **THEN** the lazy getter returns None without calling the factory

### Requirement: CLI Dependency Declaration

The SDK SHALL provide a `requires_cli()` decorator for declaring CLI dependencies.

#### Scenario: Declare single CLI dependency
- **WHEN** a tool is decorated with `@requires_cli("rg")`
- **THEN** the tool's metadata includes the CLI requirement
- **AND** the requirement is discoverable via `check_deps()`

#### Scenario: Declare CLI with version check
- **WHEN** a tool is decorated with `@requires_cli("ffmpeg", version_flag="--version")`
- **THEN** the dependency check can verify the CLI is installed and get its version

### Requirement: Library Dependency Declaration

The SDK SHALL provide a `requires_lib()` decorator for declaring Python library dependencies.

#### Scenario: Declare library dependency
- **WHEN** a tool is decorated with `@requires_lib("pandas")`
- **THEN** the tool's metadata includes the library requirement
- **AND** the requirement is discoverable via `check_deps()`

### Requirement: Dependency Checking

The SDK SHALL provide a `check_deps()` function for validating tool dependencies.

#### Scenario: Check all tools
- **WHEN** a caller invokes `check_deps()`
- **THEN** the SDK returns a report of all tool dependencies and their status

#### Scenario: Check specific tool
- **WHEN** a caller invokes `check_deps(tool="ripgrep")`
- **THEN** the SDK returns the dependency status for that tool only

#### Scenario: CLI not installed
- **WHEN** a tool requires CLI "nonexistent"
- **AND** `check_deps()` is called
- **THEN** the report shows status "missing" for that CLI
