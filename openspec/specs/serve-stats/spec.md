# serve-stats Specification

## Purpose

Runtime statistics collection for OneTool, tracking run-level and tool-level metrics to measure efficiency and estimate context/time savings from tool consolidation.
## Requirements
### Requirement: Statistics Collection

The server SHALL collect runtime statistics in JSONL format with unified run-level and tool-level records.

#### Scenario: Record successful run
- **GIVEN** stats collection is enabled
- **WHEN** a `run()` call completes successfully
- **THEN** a JSONL record SHALL be appended with: `type="run"`, timestamp, client, chars_in, chars_out, duration_ms, success=true

#### Scenario: Record failed run
- **GIVEN** stats collection is enabled
- **WHEN** a `run()` call fails with an error
- **THEN** a JSONL record SHALL be appended with: `type="run"`, timestamp, client, chars_in, chars_out, duration_ms, success=false, error_type

#### Scenario: Stats disabled
- **GIVEN** `stats.enabled: false` in configuration
- **WHEN** a `run()` call completes
- **THEN** no stats record SHALL be created

### Requirement: Statistics Configuration

The server SHALL support configuration for statistics collection.

#### Scenario: Default configuration
- **GIVEN** no stats configuration specified
- **WHEN** the server starts
- **THEN** stats SHALL be enabled with defaults:
  - persist_path: "{log_dir}/stats.jsonl"
  - flush_interval_seconds: 30
  - context_per_call: 30000
  - time_overhead_per_call_ms: 4000
  - telemetry.enabled: true

#### Scenario: Stats file location
- **GIVEN** default configuration
- **WHEN** stats are flushed
- **THEN** records SHALL be written to `stats.jsonl` in the log directory

### Requirement: Statistics Aggregation

The stats reader SHALL aggregate metrics into summary statistics.

#### Scenario: Summary metrics
- **GIVEN** recorded stats
- **WHEN** stats are aggregated
- **THEN** summary SHALL include: total_calls, success_count, error_count, success_rate, total_duration_ms

#### Scenario: Period filtering
- **GIVEN** `period="day"` parameter
- **WHEN** stats are loaded
- **THEN** only records from the last 24 hours SHALL be included

### Requirement: HTML Report Display

The HTML report SHALL display summary cards and tool breakdown.

#### Scenario: Summary cards
- **GIVEN** aggregated stats
- **WHEN** HTML report is generated
- **THEN** summary cards SHALL display: Total Calls, Success Rate, Est. Savings

#### Scenario: Est. Savings display
- **GIVEN** aggregated stats with calculated savings
- **WHEN** HTML report is generated
- **THEN** Est. Savings card SHALL display dollar amount and coffee equivalent
- **AND** coffee equivalent SHALL use $5 per coffee (hardcoded)
- **EXAMPLE** "$12.50 (2.5 coffees)"

#### Scenario: Tool breakdown table
- **GIVEN** execution-level tool stats
- **WHEN** HTML report is generated
- **THEN** table SHALL display per-tool metrics from execution tracking
- **AND** table SHALL NOT contain "code" or "unknown" categories

### Requirement: Execution-Level Tool Tracking

The server SHALL track actual tool invocations using a unified stats writer.

#### Scenario: Track tool call
- **GIVEN** a command executes any tool (e.g., `brave.search(query="test")`)
- **WHEN** the tool dispatch completes
- **THEN** a JSONL record SHALL be appended with: `type="tool"`, timestamp, client, tool name, duration_ms, success

#### Scenario: Track tool error
- **GIVEN** a tool call raises an exception
- **WHEN** the tool dispatch fails
- **THEN** a JSONL record SHALL include: success=false, error_type

#### Scenario: Multiple tools in single run
- **GIVEN** a multi-line command that calls multiple tools
- **WHEN** the command executes
- **THEN** separate tool records SHALL be created for each tool call
- **AND** one run-level record SHALL be created for the overall run

### Requirement: Savings Estimation

The stats reader SHALL estimate context and time savings using the per-call overhead model.

#### Scenario: Context savings calculation
- **GIVEN** 100 run-level stats records
- **AND** `context_per_call: 30000` in configuration
- **WHEN** stats are aggregated
- **THEN** `context_saved` SHALL equal 100 * 30000 = 3,000,000

#### Scenario: Dollar savings calculation
- **GIVEN** context savings calculated
- **AND** model pricing configured
- **WHEN** stats are aggregated
- **THEN** `savings_usd` SHALL be calculated from context overhead cost

#### Scenario: Coffee equivalent
- **GIVEN** `savings_usd` calculated
- **WHEN** displayed in HTML report
- **THEN** coffee count SHALL equal `savings_usd / 5.0`

#### Scenario: Savings rationale
- **REASON** Each OneTool call consolidates operations that would otherwise require multiple MCP tool calls
- **AND** each traditional MCP call re-sends full context (~30K tokens) to the LLM
- **AND** each additional LLM round-trip adds ~4s latency
- **THEREFORE** savings = calls * overhead_per_call

### Requirement: Client Name Tracking

The server SHALL capture the MCP client name in all stats records.

#### Scenario: Client name from initialization
- **GIVEN** an MCP client connects with implementation info
- **WHEN** stats records are created
- **THEN** all records SHALL include the `client` field with the client implementation name

#### Scenario: Unknown client
- **GIVEN** no client implementation info is available
- **WHEN** stats records are created
- **THEN** the `client` field SHALL be "unknown"

### Requirement: JSONL Record Schema

Stats records SHALL follow a discriminated union schema based on the `type` field.

#### Scenario: Run record schema
- **GIVEN** a run-level event
- **WHEN** a record is written
- **THEN** the record SHALL contain:
  - `ts`: ISO 8601 timestamp
  - `type`: "run"
  - `client`: MCP client name
  - `chars_in`: Input character count
  - `chars_out`: Output character count
  - `duration_ms`: Execution time in milliseconds
  - `success`: Boolean
  - `error_type`: String or null

#### Scenario: Tool record schema
- **GIVEN** a tool-level event
- **WHEN** a record is written
- **THEN** the record SHALL contain:
  - `ts`: ISO 8601 timestamp
  - `type`: "tool"
  - `client`: MCP client name
  - `tool`: Fully qualified tool name (e.g., "brave.search")
  - `duration_ms`: Execution time in milliseconds
  - `success`: Boolean
  - `error_type`: String or null

### Requirement: Timed Tool Call Helper

The stats module SHALL provide a context manager for timing tool calls.

#### Scenario: Successful tool timing
- **GIVEN** code wrapped in `timed_tool_call(tool_name, client)`
- **WHEN** the code completes successfully
- **THEN** a tool stats record SHALL be created with success=true

#### Scenario: Failed tool timing
- **GIVEN** code wrapped in `timed_tool_call(tool_name, client)`
- **WHEN** the code raises an exception
- **THEN** a tool stats record SHALL be created with success=false, error_type
- **AND** the exception SHALL be re-raised

### Requirement: Telemetry

The server SHALL support remote telemetry via PostHog.

#### Scenario: Telemetry enabled by default
- **GIVEN** no telemetry configuration specified
- **WHEN** the server starts
- **THEN** anonymous telemetry data SHALL be sent to PostHog

#### Scenario: Telemetry disabled
- **GIVEN** `stats.telemetry.enabled: false` in configuration
- **WHEN** stats events occur
- **THEN** no telemetry data SHALL be sent

#### Scenario: DO_NOT_TRACK environment variable
- **GIVEN** `DO_NOT_TRACK=1` environment variable is set
- **WHEN** the server starts
- **THEN** telemetry SHALL be disabled regardless of configuration

#### Scenario: ONETOOL_TELEMETRY_DISABLED environment variable
- **GIVEN** `ONETOOL_TELEMETRY_DISABLED=1` environment variable is set
- **WHEN** the server starts
- **THEN** telemetry SHALL be disabled regardless of configuration

### Requirement: Telemetry Events

When telemetry is enabled, the server SHALL send specific events.

#### Scenario: Server started event
- **GIVEN** telemetry is enabled
- **WHEN** the server starts
- **THEN** a `server_started` event SHALL be sent with: version, tool_count

#### Scenario: Run completed event
- **GIVEN** telemetry is enabled
- **WHEN** a run completes
- **THEN** a `run_completed` event SHALL be sent with: chars_in, chars_out, duration_ms, success

#### Scenario: Tool executed event
- **GIVEN** telemetry is enabled
- **WHEN** a tool is executed
- **THEN** a `tool_executed` event SHALL be sent with: tool_name, duration_ms, success

### Requirement: Telemetry Data Privacy

Telemetry SHALL collect only anonymous, aggregated metrics.

#### Scenario: Anonymous identifier
- **GIVEN** telemetry is enabled
- **WHEN** events are sent
- **THEN** the distinct_id SHALL be an anonymous machine identifier
- **AND** no personal information SHALL be included

#### Scenario: No code or content
- **GIVEN** telemetry is enabled
- **WHEN** events are sent
- **THEN** no code, queries, file contents, or paths SHALL be included

#### Scenario: No credentials
- **GIVEN** telemetry is enabled
- **WHEN** events are sent
- **THEN** no API keys, passwords, or credentials SHALL be included

