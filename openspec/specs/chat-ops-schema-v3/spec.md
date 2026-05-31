# chat-ops-schema-v3 Specification

## Purpose
TBD - created by archiving change chat-ops-schema-v3-refactor. Update Purpose after archive.
## Requirements
### Requirement: Canonical Session-Turn-Event Backbone
The system SHALL persist chat telemetry using relational core tables `sessions`, `turns`, and `events`, where each `turns.session_id` references `sessions.session_id` and each `events` row references both `session_id` and `turn_id` for that same session.

#### Scenario: Event insert requires resolved parent session and turn
- **WHEN** ingest processes a raw provider record
- **THEN** it MUST resolve `session_id` and `turn_id` before inserting into `events`

#### Scenario: Referential integrity is enforced
- **WHEN** an `events` insert references a missing session or turn
- **THEN** the write MUST fail rather than storing an orphaned event

### Requirement: Deterministic Turn Assignment Contract
The parser SHALL assign each event to a turn using the defined precedence order: explicit turn context identifier, explicit event payload turn identifier, active parser-state turn, then synthetic turn creation.

#### Scenario: Explicit turn context takes precedence
- **WHEN** both parser state and turn-context identifiers are available
- **THEN** the parser MUST assign the event to the turn-context identifier

#### Scenario: Synthetic turns cover turn-less provider records
- **WHEN** no explicit or inferable turn identifier is available
- **THEN** ingest MUST create a synthetic turn and link the event to it

#### Scenario: Active turn state cannot cross session boundaries
- **WHEN** ingest resolves a different `session_id` than the prior event in the same source stream
- **THEN** it MUST NOT reuse previously active turn state from the prior session
- **AND** subsequent turn resolution MUST create or resolve a turn that belongs to the new session

### Requirement: Event Detail Composition Tables
The system SHALL store sparse or domain-specific event detail in compositional subtype tables keyed by `event_id` (for example `event_usage`, `event_commands`, `event_tool_calls`, `event_file_ops`, and related `event_*` tables), while preserving full source payload in `events.payload_json`.

#### Scenario: Usage data absent
- **WHEN** an event has no usage payload
- **THEN** no `event_usage` row MUST be created for that event

#### Scenario: Tool call details present
- **WHEN** an event includes tool-call details
- **THEN** projection MUST emit one canonical row in `event_tool_calls` per logical non-shell tool call key (`call_id`/`tool_use_id`)

#### Scenario: Tool call canonical merge precedence
- **WHEN** lifecycle fragments include call/start and terminal result records for the same logical call
- **THEN** canonical tool-call metadata (`tool_name`, `server`, `arguments_json`) MUST come from the start/call fragment when present
- **AND** canonical outcome fields (`status`, `result_json`, `error_text`) MUST come from the terminal result fragment when present

#### Scenario: Tool call canonical duration semantics
- **WHEN** both start/call and terminal result timestamps are available for a logical tool call
- **THEN** canonical `duration_ms` MUST represent total wall-clock start-to-end latency
- **AND** fragment durations MUST NOT be summed into canonical `duration_ms`

#### Scenario: Shell-wrapper calls are projected into event_commands
- **WHEN** a shell-wrapper tool call (for example `exec_command`) has canonical tool-call data but no matching `event_commands` row
- **THEN** projection MUST synthesize an `event_commands` row from tool-call arguments and result payload
- **AND** shell-wrapper tool calls MUST NOT remain in `event_tool_calls`

#### Scenario: Invocation table remains intent-only slash and dollar
- **WHEN** user text contains slash or dollar command prefixes
- **THEN** projection MUST emit only `slash` and `dollar` invocation types in `event_invocations`
- **AND** `skill` invocation rows MUST NOT be emitted

### Requirement: Ingest Tracking and Rebuild Observability
The system SHALL maintain ingest progress in `ingest_state` and run-level counters/status in `ingest_runs` for every ingest execution.

#### Scenario: Incremental ingest checkpoint update
- **WHEN** ingest advances through a source file
- **THEN** it MUST update that file's checkpoint fields in `ingest_state`

#### Scenario: Run completion counters
- **WHEN** ingest completes
- **THEN** `ingest_runs` MUST contain final inserted, skipped, duplicate, and error counters for the run

### Requirement: Materialized Session and Turn Metrics
The system SHALL populate and maintain projection tables `mv_turn_metrics` and `mv_session_metrics` derived from core and composition tables for report-facing analytics.

#### Scenario: Turn metrics refresh
- **WHEN** projection rebuild executes
- **THEN** each persisted turn MUST have one corresponding row in `mv_turn_metrics`
- **AND** `tool_calls_count` MUST count canonical logical tool calls rather than lifecycle fragments

#### Scenario: Session metrics refresh
- **WHEN** projection rebuild executes
- **THEN** each persisted session MUST have one corresponding row in `mv_session_metrics`

### Requirement: Clean-Break Reporting Surface
The chat-ops reporting tool surface SHALL expose `report_excel` as the report entrypoint and MUST NOT expose deprecated compatibility aliases for removed report contracts.

#### Scenario: Legacy report entrypoint invocation
- **WHEN** callers attempt to use removed report entrypoints
- **THEN** the system MUST fail explicitly instead of silently redirecting to new behavior

#### Scenario: Report generation against v3 tables
- **WHEN** `report_excel` is executed
- **THEN** report queries MUST read from v3 relational/projection tables rather than legacy schema names
