# serve-output-sanitization Specification

## Purpose

Protects against indirect prompt injection by sanitizing tool outputs that may contain malicious payloads designed to trick the LLM into executing unintended commands.

## Requirements

### Requirement: Trigger Pattern Sanitisation

The system SHALL sanitise trigger patterns in tool outputs to prevent indirect prompt injection.

#### Scenario: OneTool trigger pattern
- **GIVEN** tool output containing `__ot file.delete(path="x")`
- **WHEN** sanitisation is applied
- **THEN** it SHALL be replaced with `[REDACTED:trigger] file.delete(path="x")`

#### Scenario: MCP trigger-like pattern
- **GIVEN** tool output containing `mcp__onetool__run(command="...")`
- **WHEN** sanitisation is applied
- **THEN** the `mcp__onetool__run` token SHALL be replaced with `[REDACTED:trigger]`

#### Scenario: Short run trigger pattern
- **GIVEN** tool output containing `__r file.write(path="x", content="y")`
- **WHEN** sanitisation is applied
- **THEN** `__r` SHALL be replaced with `[REDACTED:trigger]`

#### Scenario: Removed REPL marker is not sanitized
- **GIVEN** tool output containing `>>> file.write(path="x", content="y")` (or any `>>> pack.tool(` form)
- **WHEN** sanitisation is applied
- **THEN** `>>>` SHALL NOT be treated as a OneTool trigger

#### Scenario: Case sensitivity
- **GIVEN** tool output containing `__OT` or `__Ot` (mixed case)
- **WHEN** sanitisation is applied
- **THEN** case-insensitive matching SHALL be used

#### Scenario: Multiple occurrences
- **GIVEN** tool output containing multiple trigger patterns
- **WHEN** sanitisation is applied
- **THEN** all occurrences SHALL be replaced

### Requirement: Boundary Tag Pattern Sanitisation

The system SHALL sanitise boundary tag patterns to prevent escape and confusion attacks.

#### Scenario: Closing tag pattern
- **GIVEN** tool output containing `</external-content-abc123>`
- **WHEN** sanitisation is applied
- **THEN** it SHALL be replaced with `[REDACTED:tag]`

#### Scenario: Opening tag pattern
- **GIVEN** tool output containing `<external-content-abc123>`
- **WHEN** sanitisation is applied
- **THEN** it SHALL be replaced with `[REDACTED:tag]`

### Requirement: GUID-Tagged Content Boundaries

The system SHALL wrap sanitised content in GUID-tagged boundaries.

#### Scenario: Content wrapping (default/raw)
- **GIVEN** sanitised tool output, source identifier, and no format or `raw` format
- **WHEN** boundary wrapping is applied
- **THEN** output SHALL be wrapped as:

  ```text
  <external-content-{id} source="{source}">
  {sanitised_content}
  </external-content-{id}>
  ```

#### Scenario: Content wrapping (YAML format)
- **GIVEN** sanitised tool output and format `yml` or `yml_h`
- **WHEN** boundary wrapping is applied
- **THEN** output SHALL use hash-comment boundaries:

  ```text
  # <external-content-{id} source="{source}">
  {sanitised_content}
  # </external-content-{id}>
  ```

#### Scenario: Content wrapping (JSON format)
- **GIVEN** sanitised tool output and format `json` or `json_h`
- **WHEN** boundary wrapping is applied
- **THEN** output SHALL use block-comment boundaries (not strict JSON; for LLM consumption):

  ```text
  /* <external-content-{id} source="{source}"> */
  {sanitised_content}
  /* </external-content-{id}> */
  ```

#### Scenario: ID uniqueness
- **GIVEN** multiple tool outputs in the same session
- **WHEN** each output is wrapped
- **THEN** each SHALL have a unique ID (4 hex chars from UUIDv4)

#### Scenario: Source attribution
- **GIVEN** tool output with source identifier
- **WHEN** boundary wrapping is applied
- **THEN** source attribute SHALL be included in the opening tag

#### Scenario: Empty content
- **GIVEN** empty string content
- **WHEN** sanitisation is applied
- **THEN** it SHALL return wrapped empty content (boundaries still apply)

### Requirement: Sanitisation Control

The system SHALL support enabling/disabling sanitisation via magic variable.

#### Scenario: Enabled via magic variable
- **GIVEN** code that sets `__sanitize__ = True`
- **WHEN** the result is returned
- **THEN** sanitisation SHALL be applied with boundary wrapping

#### Scenario: Disabled via magic variable
- **GIVEN** code that sets `__sanitize__ = False`
- **WHEN** the result is returned
- **THEN** sanitisation SHALL NOT be applied

#### Scenario: Default behaviour
- **GIVEN** code that does not set `__sanitize__`
- **WHEN** the result is returned
- **THEN** sanitisation SHALL follow the `security.sanitize.enabled` config setting (enabled by default)

### Requirement: Sanitisation Visibility

The system SHALL make sanitisation visible to aid debugging.

#### Scenario: Redacted markers
- **GIVEN** content with trigger patterns that were sanitised
- **WHEN** the LLM receives the result
- **THEN** `[REDACTED:trigger]` markers SHALL be visible
