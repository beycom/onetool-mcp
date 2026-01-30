## ADDED Requirements

### Requirement: Output Format Control

The system SHALL support a `__format__` magic variable to control result serialisation.

#### Scenario: Default format (compact JSON)
- **GIVEN** code that returns a dict without setting `__format__`
- **WHEN** the result is serialised
- **THEN** it SHALL use compact JSON with no whitespace

#### Scenario: Explicit json format
- **GIVEN** code that sets `__format__ = "json"` and returns a dict
- **WHEN** the result is serialised
- **THEN** it SHALL use compact JSON (same as default)

#### Scenario: Human-readable JSON format
- **GIVEN** code that sets `__format__ = "json_h"` and returns a dict
- **WHEN** the result is serialised
- **THEN** it SHALL use JSON with 2-space indentation

#### Scenario: YAML flow format
- **GIVEN** code that sets `__format__ = "yml"` and returns a dict
- **WHEN** the result is serialised
- **THEN** it SHALL use YAML flow style (inline collections)

#### Scenario: Human-readable YAML format
- **GIVEN** code that sets `__format__ = "yml_h"` and returns a dict
- **WHEN** the result is serialised
- **THEN** it SHALL use YAML block style with proper indentation

#### Scenario: Markdown format for list-of-dicts
- **GIVEN** code that sets `__format__ = "md"` and returns a list of dicts
- **WHEN** the result is serialised
- **THEN** it SHALL render as a markdown table

#### Scenario: Markdown format for single dict
- **GIVEN** code that sets `__format__ = "md"` and returns a single dict
- **WHEN** the result is serialised
- **THEN** it SHALL render as a markdown key-value list

#### Scenario: Markdown format for list
- **GIVEN** code that sets `__format__ = "md"` and returns a plain list
- **WHEN** the result is serialised
- **THEN** it SHALL render as a markdown bullet list

#### Scenario: Raw format
- **GIVEN** code that sets `__format__ = "raw"` and returns any value
- **WHEN** the result is serialised
- **THEN** it SHALL use Python `str()` conversion

#### Scenario: String passthrough unchanged
- **GIVEN** code that returns a string (regardless of `__format__` setting)
- **WHEN** the result is serialised
- **THEN** the string SHALL be returned unchanged

#### Scenario: Invalid format ignored
- **GIVEN** code that sets `__format__` to an unknown value
- **WHEN** the result is serialised
- **THEN** it SHALL fall back to default compact JSON
