# tool-conventions Specification Delta

## MODIFIED Requirements

### Requirement: Output Formatting

Tools SHALL format output consistently.

#### Scenario: Empty results
- **GIVEN** a query returns no results
- **WHEN** formatting output
- **THEN** it SHALL return `"No results found."` or similar

#### Scenario: JSON format for structured data
- **GIVEN** structured data output (lists, dicts, nested structures)
- **WHEN** formatting for LLM consumption
- **THEN** it SHALL use JSON format with compact separators
- **AND** it SHALL use `json.dumps(data, ensure_ascii=False, separators=(',', ':'))`

#### Scenario: Pretty JSON for metadata
- **GIVEN** complex metadata output (file info, table info)
- **WHEN** readability is prioritised over compactness
- **THEN** it MAY use `json.dumps(data, ensure_ascii=False, indent=2)`

#### Scenario: Result truncation
- **GIVEN** output exceeds max length
- **WHEN** truncating
- **THEN** it SHALL append truncation indicator (e.g., "... (truncated)")

#### Scenario: Centralised formatter
- **GIVEN** a tool returning structured data
- **WHEN** formatting the result
- **THEN** it SHOULD use `format_result()` from `ot.utils.format`
- **AND** the helper SHALL handle both compact and pretty modes

---

## ADDED Requirements

### Requirement: Format Helper Module

A centralised format helper SHALL provide consistent JSON output formatting.

#### Scenario: Module location
- **GIVEN** the format helper module
- **WHEN** locating it
- **THEN** it SHALL be at `src/ot/utils/format.py`

#### Scenario: Compact mode
- **GIVEN** `format_result(data)` is called without arguments
- **WHEN** data is a list or dict
- **THEN** it SHALL return JSON with no whitespace: `{"key":"value"}`

#### Scenario: Pretty mode
- **GIVEN** `format_result(data, compact=False)` is called
- **WHEN** data is a list or dict
- **THEN** it SHALL return JSON with 2-space indentation

#### Scenario: Unicode handling
- **GIVEN** data contains non-ASCII characters
- **WHEN** formatted
- **THEN** it SHALL preserve Unicode (not escape to `\uXXXX`)
