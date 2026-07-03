## MODIFIED Requirements

### Requirement: Statistics Collection

The server SHALL collect runtime statistics in JSONL format with unified run-level and tool-level records. Where a record includes `error_type`, the value SHALL be the actual exception type name that caused the failure, not a generic wrapper type introduced by an intermediate error-handling layer.

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

#### Scenario: error_type reflects the real exception type
- **GIVEN** command execution raises a specific exception type (e.g. `KeyError`) inside user/tool code
- **AND** that exception is subsequently wrapped by an intermediate error-handling layer (e.g. re-raised as a generic execution-error wrapper) before reaching the stats writer
- **WHEN** the failed-run JSONL record is written
- **THEN** `error_type` SHALL be `"KeyError"` (the original exception's type name)
- **AND** it SHALL NOT be the intermediate wrapper's type name (e.g. `"ValueError"`) unless the original exception actually was that type

### Requirement: Execution-Level Tool Tracking

The server SHALL track actual tool invocations using a unified stats writer. Where a tool-level record includes `error_type`, the value SHALL be the actual exception type name that caused the tool call to fail.

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

#### Scenario: Tool error_type reflects the real exception type
- **GIVEN** a tool call raises a specific exception type (e.g. `KeyError`) that is subsequently wrapped by an intermediate error-handling layer before reaching the stats writer
- **WHEN** the failed-tool JSONL record is written
- **THEN** `error_type` SHALL be the original exception's type name, not the intermediate wrapper's type name
