# tool-chat-ops Specification

## Purpose

Defines telemetry ingest, annotation capture, and v3 reporting behavior for the `chat_ops` (`co`) tool pack.

## Requirements

### Requirement: Canonical signal table naming

The chat-ops schema SHALL use `event_signals` as the canonical table for extracted recommendation signals.

#### Scenario: Schema creation
- **WHEN** chat-ops schema is initialized
- **THEN** an `event_signals` table SHALL exist
- **AND** legacy `signals` table naming SHALL NOT be used

### Requirement: Report entrypoint naming

The chat-ops reporting entrypoint SHALL be `report_excel`.

#### Scenario: Report invocation
- **WHEN** a user calls `chat_ops.report_excel(...)` or `co.report_excel(...)`
- **THEN** report generation SHALL execute through the pack implementation
- **AND** the call SHALL return the final export payload after workbook generation completes

#### Scenario: Legacy entrypoint invocation
- **WHEN** a caller attempts `chat_ops.report(...)` or `co.report(...)`
- **THEN** the call SHALL fail explicitly

### Requirement: Report queries read v3 tables

Signals reporting queries SHALL read from `event_signals`.

#### Scenario: Signals query source
- **WHEN** report generation includes the signals raw tab
- **THEN** rows SHALL be selected from `event_signals`

### Requirement: Clean command/tool/invocation table contract

The chat-ops v3 projections SHALL separate shell commands, non-shell tool calls, and invocation intents.

#### Scenario: Shell command projection
- **WHEN** shell-wrapper tool calls are ingested
- **THEN** shell command rows SHALL be available in `event_commands`
- **AND** shell-wrapper rows SHALL NOT remain in `event_tool_calls`

#### Scenario: Invocation projection
- **WHEN** user text includes invocation prefixes
- **THEN** `event_invocations` SHALL contain only slash and dollar invocation types


### Requirement: YAML summary and narrative reporting

The pack SHALL expose `report_summary` and `report_llm` entrypoints that produce YAML artifacts from structured session payloads.

#### Scenario: Summary report generation
- **WHEN** a user calls `chat_ops.report_summary(...)` or `co.report_summary(...)`
- **THEN** the tool SHALL write a YAML report with deterministic metrics/evidence per session
- **AND** sessions SHALL be ordered chronologically (oldest to newest)

#### Scenario: Narrative report generation
- **WHEN** a user calls `chat_ops.report_llm(...)` or `co.report_llm(...)`
- **THEN** the tool SHALL consume structured summary payloads (not raw event dumps)
- **AND** write a YAML narrative report artifact

#### Scenario: Missing llm config for required llm report
- **WHEN** `report_llm(...)` is called without configured `llm_model`
- **THEN** the tool SHALL fail with a clear actionable error
