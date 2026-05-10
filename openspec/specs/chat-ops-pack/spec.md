# chat-ops-pack Specification

## Purpose

Defines the `chat_ops` (`co`) tool-pack contract for telemetry ingest, projection rebuild, annotation writes, and Excel reporting.

## Requirements

### Requirement: Pack registration and alias

The system SHALL expose `chat_ops` with alias `co`.

#### Scenario: Alias invocation
- **WHEN** a user calls `co.ingest(...)`
- **THEN** the call SHALL resolve to `chat_ops.ingest(...)` with identical behavior

### Requirement: Tool surface

The pack SHALL expose `ingest`, `report_excel`, `note`, and `rebuild`.

#### Scenario: Report via tool call
- **WHEN** a user calls `co.report_excel(...)`
- **THEN** report generation SHALL execute fully through the pack tool implementation

### Requirement: Synchronous ingest and report completion

`ingest` and `report_excel` SHALL complete the requested work before returning.

#### Scenario: Ingest returns final counters
- **WHEN** `co.ingest(...)` is called
- **THEN** the tool SHALL return final ingest counters for each selected provider

#### Scenario: report_excel returns final export payload
- **WHEN** `co.report_excel(...)` is called
- **THEN** the tool SHALL generate the workbook and return its final export payload

### Requirement: YAML configuration for chat ops

The system SHALL support `tools.chat_ops` configuration in `onetool.yaml` for storage defaults, provider parsing defaults, analysis rules, and reporting defaults.

#### Scenario: Defaults loaded from config
- **WHEN** `tools.chat_ops` defines storage/provider/reporting defaults
- **THEN** `co.ingest(...)` and `co.report_excel(...)` SHALL use those defaults when call arguments are omitted

#### Scenario: Invalid configuration rejected
- **WHEN** `tools.chat_ops` contains invalid types or unsupported enum values
- **THEN** config loading SHALL fail with a clear validation error naming the invalid field

### Requirement: Pluggable provider parsing

The system SHALL support provider-specific parser modules selected from config.

#### Scenario: Configured parser selected
- **WHEN** `tools.chat_ops.providers.<name>.parser_file` is configured
- **THEN** ingest SHALL load that parser module and route parsing through `parse_line(...)`

### Requirement: Annotation writes and extraction

The system SHALL provide explicit annotation writes through `co.note(type=..., message=...)` and SHALL extract annotation rows from recorded note tool calls.

#### Scenario: Note write
- **WHEN** a user calls `co.note(type='summary', message='Summary text')`
- **THEN** an annotation row SHALL be stored with type `summary`

#### Scenario: Tool-call annotation extracted
- **WHEN** ingested events include a `co.note`/`chat_ops.note` function call
- **THEN** projection SHALL create an `event_annotations` row from the call arguments

### Requirement: Marker parsing removed

The system SHALL NOT treat bracket markers or free-form `$co ...` text as annotations.

#### Scenario: Marker ignored
- **WHEN** text includes `[title=...]`, `[summary=...]`, or `[note=...]`
- **THEN** no annotation rows SHALL be created from those markers

### Requirement: Regex-based category and signal rules

Category and signal extraction SHALL use ordered regex rules from `tools.chat_ops.analysis`.

#### Scenario: First category match wins
- **WHEN** multiple category rules match a turn
- **THEN** the first matching rule SHALL define the task category

#### Scenario: Signal rows emitted
- **WHEN** event content matches a configured signal rule
- **THEN** an `event_signals` row SHALL be created with evidence metadata

### Requirement: Unconfigured signal fallback

Ingest SHALL apply a non-empty baseline signal-rule set when no signal rules are configured.

#### Scenario: Baseline rules applied
- **WHEN** ingest runs with empty signal rule configuration
- **THEN** baseline signal extraction SHALL still be active

### Requirement: Command/tool/invocation layer separation

Projection SHALL keep shell command execution, non-shell tool-call lifecycle, and invocation intent in separate layers.

#### Scenario: Shell wrapper tool calls
- **WHEN** ingest sees shell-wrapper tool calls (for example `exec_command`)
- **THEN** command details SHALL be represented in `event_commands`
- **AND** those shell-wrapper calls SHALL NOT be retained in `event_tool_calls`

#### Scenario: Invocation intent rows
- **WHEN** ingest extracts invocation intent from user text
- **THEN** only slash and dollar invocation types SHALL be written to `event_invocations`

### Requirement: v3 reporting data source

`report_excel` SHALL read from v3 relational/projection tables.

#### Scenario: Signals tab source
- **WHEN** report generation includes signals data
- **THEN** the query SHALL read from `event_signals`


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
