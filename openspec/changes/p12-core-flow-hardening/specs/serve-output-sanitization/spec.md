## MODIFIED Requirements

### Requirement: Trigger Pattern Sanitisation

The system SHALL sanitise trigger patterns in tool outputs to prevent indirect prompt injection. The short `__ot` trigger token SHALL only be treated as a trigger when it appears in an invocation shape (optionally followed by whitespace and a dotted identifier, then an opening parenthesis) — not when it appears as a standalone word in prose.

#### Scenario: OneTool trigger pattern
- **GIVEN** tool output containing `__onetool file.delete(path="x")`
- **WHEN** sanitisation is applied
- **THEN** it SHALL be replaced with `[REDACTED:trigger] file.delete(path="x")`

#### Scenario: MCP trigger-like pattern
- **GIVEN** tool output containing `mcp__onetool__run(command="...")`
- **WHEN** sanitisation is applied
- **THEN** the `mcp__onetool__run` token SHALL be replaced with `[REDACTED:trigger]`

#### Scenario: Short run trigger pattern
- **GIVEN** tool output containing `__ot file.write(path="x", content="y")`
- **WHEN** sanitisation is applied
- **THEN** `__ot` SHALL be replaced with `[REDACTED:trigger]`

#### Scenario: Removed REPL marker is not sanitized
- **GIVEN** tool output containing `>>> file.write(path="x", content="y")` (or any `>>> pack.tool(` form)
- **WHEN** sanitisation is applied
- **THEN** `>>>` SHALL NOT be treated as a OneTool trigger

#### Scenario: Case sensitivity
- **GIVEN** tool output containing `__OT` or `__Ot` (mixed case), immediately followed by a call shape (e.g. `__OT file.delete()`)
- **WHEN** sanitisation is applied
- **THEN** case-insensitive matching SHALL be used

#### Scenario: Multiple occurrences
- **GIVEN** tool output containing multiple trigger patterns, each in a call shape
- **WHEN** sanitisation is applied
- **THEN** all occurrences SHALL be replaced

#### Scenario: Bare __ot token in prose is not redacted
- **GIVEN** tool output containing `"see __ot for details"` (no call shape follows `__ot`)
- **WHEN** sanitisation is applied
- **THEN** the text SHALL be returned unchanged
- **AND** `[REDACTED:trigger]` SHALL NOT appear in the output

#### Scenario: Case-insensitive bare token in prose is not redacted
- **GIVEN** tool output containing `"the __OT flag"` (no call shape follows `__OT`)
- **WHEN** sanitisation is applied
- **THEN** the text SHALL be returned unchanged
- **AND** `[REDACTED:trigger]` SHALL NOT appear in the output

#### Scenario: __ot followed by a dotted call is redacted
- **GIVEN** tool output containing `__ot.file.delete(path="x")` (no space, dotted attribute access)
- **WHEN** sanitisation is applied
- **THEN** `__ot` SHALL be replaced with `[REDACTED:trigger]`

## ADDED Requirements

### Requirement: Error Result Sanitisation Consistency

The system SHALL apply the same sanitisation treatment to first-party error text regardless of which layer of the `run` pipeline produced the error, so that error surfaces are not inconsistently boundary-wrapped/redacted in one path and left completely unsanitised in another.

#### Scenario: Preparation errors and execution errors are treated alike
- **GIVEN** a command that fails during preparation (e.g. an unknown pack reference)
- **AND** a different command that fails during execution (e.g. a runtime exception in tool code)
- **WHEN** each error is returned to the caller
- **THEN** both error texts SHALL receive the same sanitisation treatment (both sanitised the same way, or both left unsanitised the same way) — not one boundary-wrapped/trigger-redacted while the other is passed through completely raw
