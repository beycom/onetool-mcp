# bench-logging Specification

## Purpose

Defines CLI output, verbose/trace modes, and console reporter for bench.

---

## Requirements

### Requirement: CLI Verbose Mode

The system SHALL provide detailed CLI output for debugging.

#### Scenario: Verbose tool calls
- **GIVEN** `bench run --verbose`
- **WHEN** a tool is called
- **THEN** it SHALL display:
  - Tool name with `→` prefix
  - Full arguments (formatted JSON with syntax highlighting)
  - Result with `←` prefix
  - Character count of result

#### Scenario: Verbose server connections
- **GIVEN** `bench run --verbose`
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
- **GIVEN** `bench run --trace`
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
- **GIVEN** `bench run --no-color`
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

### Requirement: Benchmark Span Naming

Benchmark CLI spans SHALL follow the `bench.{component}.{action}` naming convention.

#### Scenario: Tool call spans
- **GIVEN** the benchmark harness invokes an MCP tool
- **WHEN** the call is logged
- **THEN** the span SHALL be named `bench.tool_call`

#### Scenario: LLM call spans
- **GIVEN** the benchmark harness calls an LLM
- **WHEN** the call is logged
- **THEN** the span SHALL be named `bench.llm_call`

#### Scenario: Server connection spans
- **GIVEN** the benchmark connects to MCP servers
- **WHEN** the connection is logged
- **THEN** the span SHALL be named `bench.servers.connect`
