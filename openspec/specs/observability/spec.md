# observability Specification

## Purpose

Defines the unified logging and observability infrastructure for OneTool. Covers structured JSON logging, LogSpan timing, token/cost tracking, and domain-specific logging requirements for all CLIs and components.

This consolidated spec includes requirements previously in:
- `serve-observability` (MCP server logging)
- `tool-observability` (tool function logging)
- `bench-observability` (benchmark CLI output)
- `browse-observability` (browser session logging)

---

## Requirements

<!-- Section: Core Infrastructure -->

### Requirement: Structured JSON Logging

The system SHALL log all operations as structured JSON for machine parsing.

#### Scenario: Log entry format
- **GIVEN** any logged operation
- **WHEN** the log is written
- **THEN** it SHALL be valid JSON with `span`, `duration`, and context fields

#### Scenario: Log file output
- **GIVEN** `OT_LOG_FILE` environment variable set
- **WHEN** the server runs
- **THEN** all logs SHALL be written to the specified file in JSON format

#### Scenario: Console output
- **GIVEN** `--verbose` flag or `OT_LOG_LEVEL=DEBUG`
- **WHEN** the server runs
- **THEN** logs SHALL also appear on console in human-readable format

### Requirement: Log Span Timing

The system SHALL automatically time operations via LogSpan.

#### Scenario: Automatic duration
- **GIVEN** a LogSpan context manager
- **WHEN** the span exits
- **THEN** `duration` SHALL be calculated from entry to exit

#### Scenario: Nested spans
- **GIVEN** a span contains nested operations
- **WHEN** each completes
- **THEN** each SHALL have independent duration tracking

#### Scenario: Status tracking
- **GIVEN** a span completes
- **WHEN** it logs
- **THEN** it SHALL include `status: "SUCCESS"` or `status: "FAILED"`

#### Scenario: Sync and async support
- **GIVEN** LogSpan is used
- **WHEN** in sync context (with statement) or async context (async with)
- **THEN** timing and status tracking SHALL work identically

### Requirement: Async LogSpan Context Manager

The system SHALL provide an async context manager for span-based logging.

#### Scenario: Async span usage
- **GIVEN** an async tool function
- **WHEN** `async with LogSpan.async_span("operation", ctx=ctx) as s:` is used
- **THEN** it SHALL log start and completion with timing automatically

#### Scenario: Async span error handling
- **GIVEN** an exception occurs within async_span
- **WHEN** the context exits
- **THEN** it SHALL log the error with duration and status="FAILED"

#### Scenario: Span metadata in logs
- **GIVEN** an async span with additional fields
- **WHEN** logs are emitted
- **THEN** they SHALL include the span name and all fields in the extra dict

### Requirement: Token and Cost Tracking

The system SHALL track and log token usage and costs.

#### Scenario: Token count logging
- **GIVEN** an LLM call is made (smart tool or harness)
- **WHEN** the call completes
- **THEN** it SHALL log:
  - `input_tokens`: Prompt tokens
  - `output_tokens`: Completion tokens
  - `total_tokens`: Sum of both

#### Scenario: Cost logging
- **GIVEN** an LLM call completes
- **WHEN** the result is logged
- **THEN** it SHALL include `cost_usd`: Estimated cost based on model pricing

#### Scenario: Cumulative tracking
- **GIVEN** multiple LLM calls in a session
- **WHEN** logs are written
- **THEN** each log SHALL include running totals available via log aggregation

### Requirement: Dynamic Model Pricing

The system SHALL fetch model pricing from OpenRouter API for cost calculations.

#### Scenario: Pricing fetched from API
- **GIVEN** the OpenRouter API is reachable
- **WHEN** `calculate_cost()` is called
- **THEN** it SHALL use pricing from `https://openrouter.ai/api/v1/models`

#### Scenario: Unknown model warning
- **GIVEN** a model is not found in API response
- **WHEN** `calculate_cost()` is called for that model
- **THEN** it SHALL log a warning and return 0

### Requirement: Error Logging

The system SHALL log errors with full context for debugging.

#### Scenario: Tool execution error
- **GIVEN** a tool raises an exception
- **WHEN** the error is logged
- **THEN** it SHALL include:
  - `span: "mcp.error"`
  - `tool`: Function that failed
  - `errorType`: Exception class name
  - `error`: Error message (truncated)
  - `duration`: Time before failure

### Requirement: Debug Mode

The system SHALL support detailed debug logging for development.

#### Scenario: Debug log level
- **GIVEN** `OT_LOG_LEVEL=DEBUG`
- **WHEN** the server runs
- **THEN** it SHALL log:
  - Registry scanning details
  - Config loading steps
  - Container lifecycle events
  - Full request/response bodies

### Requirement: Log Configuration

The system SHALL support configurable logging.

#### Scenario: Log level configuration
- **GIVEN** `OT_LOG_LEVEL=WARNING`
- **WHEN** the server runs
- **THEN** only WARNING and above SHALL be logged

#### Scenario: Truncation configuration
- **GIVEN** `OT_LOG_TRUNCATE=100`
- **WHEN** a long value is logged
- **THEN** it SHALL be truncated at 100 characters with `... (N chars)` suffix

#### Scenario: Log rotation
- **GIVEN** `OT_LOG_FILE` is configured
- **WHEN** the log file grows
- **THEN** it SHALL support standard log rotation tools (logrotate compatible)

### Requirement: CLI Logging Initialization

The system SHALL ensure all CLIs initialize logging consistently.

#### Scenario: CLI startup logging
- **GIVEN** any OneTool CLI is started
- **WHEN** the CLI initializes
- **THEN** it SHALL call `configure_logging(cli_name)`

#### Scenario: Separate log files
- **GIVEN** logging is configured for a CLI
- **WHEN** log files are created
- **THEN** each CLI SHALL write to `logs/{cli_name}.log`

### Requirement: Logging Documentation

The system SHALL provide centralized logging documentation for developers.

#### Scenario: Developer guide exists
- **GIVEN** a developer needs to add logging to new code
- **WHEN** they consult `docs/logging.md`
- **THEN** it SHALL contain:
  - LogSpan usage patterns
  - Span naming conventions
  - Code examples
  - Links to this spec

---

<!-- Section: MCP Server Logging -->

### Requirement: MCP Request Logging

The system SHALL log every MCP tool call with full context.

#### Scenario: Tool call logging
- **GIVEN** an MCP `run()` call is received
- **WHEN** the call is processed
- **THEN** it SHALL log:
  - `span: "mcp.request"`
  - `tool`: Function name being called
  - `kwargs`: Arguments (truncated if large)
  - `duration`: Time to complete

#### Scenario: Tool call arguments
- **GIVEN** a tool call with arguments
- **WHEN** the call is logged
- **THEN** arguments SHALL be logged with values truncated at `OT_LOG_TRUNCATE` characters

#### Scenario: Tool call result
- **GIVEN** a tool call completes
- **WHEN** the result is logged
- **THEN** it SHALL include `resultLength` (character count of output)

### Requirement: Execution Mode Logging

The system SHALL log executor information for each call.

#### Scenario: Host execution logging
- **GIVEN** a tool executes in host process
- **WHEN** execution completes
- **THEN** it SHALL log `executor: "simple"`

### Requirement: FastMCP Context Integration

The logging system SHALL integrate with FastMCP Context when available.

#### Scenario: Context logging in MCP tools
- **GIVEN** a tool function with a FastMCP Context parameter
- **WHEN** LogSpan.async_span() is used with ctx parameter
- **THEN** log messages SHALL be sent to the MCP client via Context

#### Scenario: Fallback to loguru
- **GIVEN** no FastMCP Context available (CLI mode)
- **WHEN** LogSpan is used
- **THEN** log messages SHALL be written to loguru as before

#### Scenario: Async logging methods
- **GIVEN** a LogSpan instance with Context
- **WHEN** log_info(), log_debug(), log_warning(), or log_error() is called
- **THEN** the message SHALL be sent via the appropriate Context method

#### Scenario: Progress reporting
- **GIVEN** a LogSpan instance with Context
- **WHEN** report_progress(progress, total) is called
- **THEN** it SHALL call ctx.report_progress() if Context is available

### Requirement: MCP Server Lifecycle Logging

The system SHALL log MCP server lifecycle events.

#### Scenario: Server start logging
- **GIVEN** the MCP server is starting
- **WHEN** initialization completes
- **THEN** it SHALL log:
  - `span: "mcp.server.start"`
  - `transport`: Transport type (stdio, sse)
  - `toolCount`: Number of registered tools

#### Scenario: Server stop logging
- **GIVEN** the MCP server is running
- **WHEN** shutdown is initiated
- **THEN** it SHALL log:
  - `span: "mcp.server.stop"`
  - `duration`: Total server uptime

### Requirement: Tool Resolution Logging

The system SHALL log tool lookup in the registry.

#### Scenario: Tool lookup
- **GIVEN** a tool call is received
- **WHEN** the tool is resolved from the registry
- **THEN** it SHALL log:
  - `span: "tool.lookup"`
  - `function`: Requested function name
  - `found`: Boolean indicating success

---

<!-- Section: Tool Function Logging -->

### Requirement: Tool Function LogSpan

All public tool functions SHALL use LogSpan for structured operation logging.

#### Scenario: Public function uses LogSpan
- **GIVEN** a public tool function (non-underscore prefixed)
- **WHEN** the function is executed
- **THEN** it SHALL wrap execution in a `LogSpan` context manager with:
  - `span`: Named using dot-notation `{namespace}.{function}`
  - Key parameters logged as span fields
  - Result metrics added before exit

#### Scenario: Consistent span naming
- **GIVEN** a tool in namespace `ns` with function `fn`
- **WHEN** LogSpan is created
- **THEN** the span name SHALL be `{ns}.{fn}` (e.g., `brave.search`, `db.query`)

### Requirement: Span Field Guidelines

LogSpan fields SHALL follow consistent naming conventions.

#### Scenario: Input parameters logged
- **GIVEN** a tool function with significant input parameters
- **WHEN** LogSpan is created
- **THEN** key inputs SHALL be logged as span fields (e.g., `query`, `path`, `pattern`)

#### Scenario: Result metrics logged
- **GIVEN** a tool function that returns results
- **WHEN** the function completes successfully
- **THEN** result metrics SHALL be added (e.g., `resultCount`, `resultLen`, `found`)

#### Scenario: Error state captured
- **GIVEN** a tool function encounters an error
- **WHEN** the error occurs within LogSpan
- **THEN** the span SHALL automatically log `status=FAILED` with error details

### Requirement: Shared HTTP Client

Tools SHALL use a shared HTTP client utility for external API requests.

#### Scenario: GET request with success
- **GIVEN** a tool needs to make an HTTP GET request
- **WHEN** `http_get(url, params, headers, timeout)` is called
- **THEN** it SHALL return `(True, response_data)` on success

#### Scenario: GET request with HTTP error
- **GIVEN** a tool makes an HTTP GET request
- **WHEN** the server returns an error status code
- **THEN** it SHALL return `(False, error_message)` with status code

#### Scenario: GET request with network error
- **GIVEN** a tool makes an HTTP GET request
- **WHEN** a network error occurs (timeout, connection refused)
- **THEN** it SHALL return `(False, error_message)` describing the failure

#### Scenario: Optional LogSpan integration
- **GIVEN** a tool makes an HTTP GET request with `span_name` parameter
- **WHEN** the request completes
- **THEN** it SHALL log the request via LogSpan with endpoint and status

---

<!-- Section: Benchmark CLI Logging -->

### Requirement: CLI Verbose Mode

The system SHALL provide detailed CLI output for debugging.

#### Scenario: Verbose tool calls
- **GIVEN** `ot-bench run --verbose`
- **WHEN** a tool is called
- **THEN** it SHALL display:
  - Tool name with `→` prefix
  - Full arguments (formatted JSON with syntax highlighting)
  - Result with `←` prefix
  - Character count of result

#### Scenario: Verbose server connections
- **GIVEN** `ot-bench run --verbose`
- **WHEN** connecting to MCP servers
- **THEN** it SHALL display:
  - Server name with loading indicator
  - Tool count on success
  - Error message on failure

#### Scenario: Progress summary
- **GIVEN** a benchmark task completes
- **WHEN** results are displayed
- **THEN** it SHALL show:
  - `✓` or `✗` status
  - Input/output token counts
  - LLM call count
  - Tool call count
  - Duration
  - Cost

### Requirement: Trace Mode

The system SHALL provide timestamped request/response tracing for debugging.

#### Scenario: Trace flag enabled
- **GIVEN** `ot-bench run --trace`
- **WHEN** the benchmark runs
- **THEN** it SHALL display timestamped entries for:
  - LLM request (model, message count, tools available)
  - LLM response (finish reason, tokens, tool calls count)
  - Tool call start (server, tool name, args)
  - Tool result (duration, size)

#### Scenario: Trace timestamp format
- **GIVEN** trace mode is enabled
- **WHEN** an event is logged
- **THEN** it SHALL be prefixed with `[HH:MM:SS.mmm]` timestamp

#### Scenario: Trace indicators
- **GIVEN** trace mode is enabled
- **WHEN** displaying requests and responses
- **THEN** requests SHALL use `▶` prefix and responses SHALL use `◀` prefix

### Requirement: No-Color Mode

The system SHALL support disabling ANSI colors for CI/CD compatibility.

#### Scenario: No-color flag
- **GIVEN** `ot-bench run --no-color`
- **WHEN** output is displayed
- **THEN** it SHALL contain no ANSI escape codes

#### Scenario: NO_COLOR environment variable
- **GIVEN** `NO_COLOR` environment variable is set
- **WHEN** output is displayed
- **THEN** it SHALL contain no ANSI escape codes

### Requirement: Scenario/Task Terminology

The system SHALL use Scenario/Task terminology in all CLI output.

#### Scenario: CLI progress events
- **GIVEN** a benchmark runs
- **WHEN** progress is displayed
- **THEN** it SHALL use "Scenario:" and "Task:" labels

#### Scenario: CLI options
- **GIVEN** the user wants to filter by scenario or task
- **WHEN** using CLI options
- **THEN** `--scenario` and `--task` flags SHALL be available

### Requirement: Console Reporter

The system SHALL use a dedicated reporter class for console output.

#### Scenario: Reporter event handling
- **GIVEN** a benchmark event occurs
- **WHEN** the event is passed to ConsoleReporter
- **THEN** it SHALL format and display the event according to the current output mode

#### Scenario: Output modes
- **GIVEN** the `--output-format` option
- **WHEN** set to `compact`, `normal`, or `verbose`
- **THEN** the reporter SHALL adjust output detail level accordingly

#### Scenario: Theme consistency
- **GIVEN** console output is rendered
- **WHEN** colors are applied
- **THEN** they SHALL use consistent Rich markup styles:
  - Headers: `bold cyan`
  - Success: `green`
  - Error: `red`
  - Muted: `dim`
  - Emphasis: `bold`

### Requirement: Benchmark Logging Spans

The system SHALL use consistent span naming for traceability.

#### Scenario: Scenario-level spans
- **GIVEN** a scenario starts or completes
- **WHEN** logged
- **THEN** it SHALL use `span: "scenario.start"` or `span: "scenario.complete"`

#### Scenario: Task-level spans
- **GIVEN** a task starts or completes
- **WHEN** logged
- **THEN** it SHALL use `span: "task.start"` or `span: "task.complete"`

#### Scenario: LLM spans
- **GIVEN** an LLM request or response occurs
- **WHEN** logged
- **THEN** it SHALL use `span: "llm.request"` or `span: "llm.response"`

#### Scenario: Tool spans
- **GIVEN** a tool call or result occurs
- **WHEN** logged
- **THEN** it SHALL use `span: "tool.call"` or `span: "tool.result"`

#### Scenario: Server connection spans
- **GIVEN** connecting to an MCP server
- **WHEN** logged
- **THEN** it SHALL use `span: "server.connect"` with server name and tool count

### Requirement: Final Output Formatting

The system SHALL provide clear visual separation for benchmark results.

#### Scenario: Results separator
- **GIVEN** benchmark results are ready to display
- **WHEN** the results table is rendered
- **THEN** it SHALL be preceded by a DOUBLE box separator with "BENCHMARK RESULTS" header

#### Scenario: Results table
- **GIVEN** benchmark results are displayed
- **WHEN** rendering the summary
- **THEN** it SHALL use Rich's `Panel` with `box.DOUBLE` for visual emphasis

#### Scenario: Totals summary
- **GIVEN** benchmark results are displayed
- **WHEN** the table is complete
- **THEN** it SHALL show a totals line with aggregated tokens, calls, and cost

---

<!-- Section: Browser CLI Logging -->

### Requirement: Browser Session Logging

The system SHALL log browser session lifecycle events.

#### Scenario: Session start logging
- **GIVEN** a browser session is initialized
- **WHEN** the session starts
- **THEN** it SHALL log:
  - `span: "browse.session.start"`
  - `url`: Initial URL
  - `headless`: Boolean for headless mode
  - `viewport`: Viewport dimensions

#### Scenario: Session stop logging
- **GIVEN** a browser session is active
- **WHEN** the session ends
- **THEN** it SHALL log:
  - `span: "browse.session.stop"`
  - `duration`: Session duration in seconds
  - `pagesVisited`: Count of pages navigated

### Requirement: Navigation Logging

The system SHALL log page navigation events.

#### Scenario: Page navigation success
- **GIVEN** a navigation request is made
- **WHEN** navigation completes successfully
- **THEN** it SHALL log:
  - `span: "browse.navigate"`
  - `url`: Target URL
  - `status`: HTTP status code
  - `loadTime`: Page load time in seconds
  - `duration`: Navigation duration

#### Scenario: Navigation failure
- **GIVEN** a navigation request is made
- **WHEN** navigation fails
- **THEN** it SHALL log:
  - `span: "browse.navigate"`
  - `url`: Target URL
  - `status: "FAILED"`
  - `errorType`: Error class name
  - `errorMessage`: Error details

### Requirement: Screenshot Logging

The system SHALL log screenshot capture events.

#### Scenario: Screenshot capture
- **GIVEN** a screenshot request is made
- **WHEN** the screenshot is captured
- **THEN** it SHALL log:
  - `span: "browse.screenshot"`
  - `path`: Output file path
  - `width`: Image width
  - `height`: Image height
  - `size`: File size in bytes
  - `duration`: Capture duration

### Requirement: Element Interaction Logging

The system SHALL log element interactions.

#### Scenario: Element find
- **GIVEN** an element lookup is performed
- **WHEN** the lookup completes
- **THEN** it SHALL log:
  - `span: "browse.element.find"`
  - `selector`: CSS or XPath selector
  - `found`: Boolean indicating success
  - `count`: Number of matching elements

#### Scenario: Element click
- **GIVEN** a click action is performed
- **WHEN** the click completes
- **THEN** it SHALL log:
  - `span: "browse.element.click"`
  - `selector`: Element selector
  - `success`: Boolean indicating success

#### Scenario: Element type
- **GIVEN** text input is performed
- **WHEN** the input completes
- **THEN** it SHALL log:
  - `span: "browse.element.type"`
  - `selector`: Element selector
  - `length`: Character count (not the actual text)

### Requirement: State Persistence Logging

The system SHALL log browser state save/load operations.

#### Scenario: State save
- **GIVEN** browser state is saved
- **WHEN** the save completes
- **THEN** it SHALL log:
  - `span: "browse.state.save"`
  - `path`: State file path
  - `cookies`: Cookie count
  - `localStorage`: Local storage key count

#### Scenario: State load
- **GIVEN** browser state is restored
- **WHEN** the load completes
- **THEN** it SHALL log:
  - `span: "browse.state.load"`
  - `path`: State file path
  - `success`: Boolean indicating success
