# _nf-observability Specification

## Purpose

Defines product-level observability requirements for operating and debugging
OneTool. These requirements describe the runtime information users and operators
can observe, not the internal logging APIs used to produce it.
## Requirements
### Requirement: Structured Runtime Events

OneTool SHALL emit structured runtime events for significant operations so users
can diagnose behavior from logs without parsing free-form prose.

#### Scenario: Operation event shape
- **GIVEN** a OneTool runtime operation is logged
- **WHEN** the log record is written
- **THEN** it SHALL include an event or span name
- **AND** operation status where available
- **AND** contextual fields relevant to the operation

#### Scenario: Single-line runtime logs
- **GIVEN** a structured runtime event contains multiline values
- **WHEN** it is written to a text log file
- **THEN** one logical event SHALL occupy one physical log line

### Requirement: Runtime Attribution

Logs SHALL distinguish processes and runtime modes when multiple OneTool
processes or transports may be active.

#### Scenario: Process attribution
- **GIVEN** a OneTool process emits runtime logs
- **WHEN** records are written
- **THEN** each record SHALL include the process id
- **AND** a stable process-scoped MCP identifier where available

#### Scenario: Runtime mode attribution
- **GIVEN** OneTool starts in stdio, HTTP, Direct API, or proxy-related runtime paths
- **WHEN** lifecycle events are logged
- **THEN** records SHALL identify the runtime mode and relevant bind or target details

### Requirement: Lifecycle Visibility

OneTool SHALL log lifecycle transitions for root MCP runtime, Direct API sidecar,
stats persistence, and external MCP proxy connections.

#### Scenario: Startup visibility
- **GIVEN** OneTool runtime startup completes
- **WHEN** startup logs are written
- **THEN** records SHALL include runtime transport, config path where available, and registered tool count

#### Scenario: Shutdown visibility
- **GIVEN** OneTool runtime shutdown starts
- **WHEN** shutdown logs are written
- **THEN** records SHALL include cleanup results for active runtime components

#### Scenario: Proxy visibility
- **GIVEN** an external MCP proxy server connects, fails, restarts, disables, or shuts down
- **WHEN** the event is logged
- **THEN** the record SHALL identify the server name, operation, status, and connected tool count when known

### Requirement: Execution Diagnostics

OneTool SHALL log execution diagnostics for MCP `run` calls and direct tool
execution without exposing unbounded payloads by default.

#### Scenario: Run execution record
- **GIVEN** an MCP `run(command=...)` call is processed
- **WHEN** execution completes or fails
- **THEN** logs SHALL include command type, duration, status, and result size where available

#### Scenario: Snippet execution record
- **GIVEN** a snippet invocation expands to generated Python
- **WHEN** execution is logged at normal verbosity
- **THEN** logs SHALL identify the original snippet invocation and summary metadata
- **AND** expanded generated code SHALL not be included at normal verbosity

#### Scenario: Error diagnostics
- **GIVEN** an operation fails
- **WHEN** the failure is logged
- **THEN** records SHALL include error type, error message, operation context, and elapsed duration where available

### Requirement: Sensitive Data Protection

Observability output SHALL avoid exposing secrets or unbounded user data by
default.

#### Scenario: Credential masking
- **GIVEN** a logged value contains URL credentials or secret-like values known to OneTool
- **WHEN** the log record is rendered
- **THEN** credentials SHALL be masked or omitted

#### Scenario: Bounded default logging
- **GIVEN** a log field contains a large command, response, path, URL, or query
- **WHEN** default logging renders the field
- **THEN** the value SHALL be truncated or summarized

#### Scenario: Verbose opt-in
- **GIVEN** a user explicitly enables verbose logging
- **WHEN** log records are rendered
- **THEN** truncation MAY be disabled for diagnostic fields
- **AND** secret masking SHALL still apply

#### Scenario: Secret-shaped literal masking in any field
- **GIVEN** a logged field of any name (including `command`, `preparedCode`, or `error`) contains a
  secret-shaped literal — an API key (`sk-...`), a GitHub token (`ghp_...`/`gho_...`/
  `github_pat_...`), a Slack token (`xoxb-...`/`xoxp-...`), an AWS access key (`AKIA...`), a
  `password=`/`token=`/`secret=`/`api_key=` style assignment, or a credentialed connection string
  (`postgres://user:pass@host`, etc.)
- **WHEN** the log record is rendered, regardless of whether the value passes through a span-based log
  (`LogSpan`) or a direct `logger.debug(LogEntry(...))` call
- **THEN** the secret-shaped literal SHALL be replaced with a `[REDACTED:<kind>]` marker
- **AND** this masking SHALL apply even though the field name does not contain "url" and the value
  does not start with `http://`/`https://`

#### Scenario: Redaction applies to both LogSpan and direct LogEntry logging paths
- **GIVEN** `runner.py`'s `LogSpan(span="runner.execute", command=..., ...)` block and its nested
  `logger.debug(LogEntry(event="runner.execute.prepared", preparedCode=..., ...))` call, where the
  command or prepared code contains an inlined secret literal (e.g. `token="sk-abc123..."` instead of
  a `${VAR}` reference)
- **WHEN** either log record is emitted
- **THEN** the secret literal SHALL be redacted in both the `LogSpan`-produced record and the
  directly-logged `LogEntry` record — there SHALL NOT be a logging path that bypasses redaction

### Requirement: Configurable Log Level

Users SHALL be able to control runtime log verbosity.

#### Scenario: Log level override
- **GIVEN** the user configures a supported log level
- **WHEN** OneTool emits logs
- **THEN** records below that level SHALL be suppressed

#### Scenario: Debug diagnostics
- **GIVEN** debug logging is enabled
- **WHEN** OneTool performs configuration, discovery, proxy, or execution work
- **THEN** additional diagnostic records MAY be emitted for troubleshooting

### Requirement: Usage And Cost Visibility

When OneTool performs LLM-backed work, observability records SHALL expose usage
and cost metadata when providers return enough information to do so.

#### Scenario: Token usage
- **GIVEN** an LLM-backed operation completes with token usage metadata
- **WHEN** the operation is logged or reported
- **THEN** input, output, and total token counts SHALL be available

#### Scenario: Cost estimate
- **GIVEN** model pricing is known for an LLM-backed operation
- **WHEN** cost metadata is reported
- **THEN** the estimate SHALL identify the model and estimated cost

