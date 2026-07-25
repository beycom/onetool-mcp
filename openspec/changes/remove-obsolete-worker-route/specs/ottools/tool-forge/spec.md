## MODIFIED Requirements

### Requirement: Validate Extension Function

The ot_forge pack SHALL provide a `validate_ext()` function for pre-reload
validation of the current in-process extension structure.

#### Scenario: Valid extension

- **WHEN** `ot_forge.validate_ext(path="/path/to/extension.py")` is called
- **AND** the extension has valid syntax and required structure
- **THEN** it returns "Validation PASSED" with any warnings

#### Scenario: Syntax error

- **WHEN** `ot_forge.validate_ext(path="/path/to/extension.py")` is called
- **AND** the file has a Python syntax error
- **THEN** it returns an error with line number and message

#### Scenario: Missing required structure

- **WHEN** `ot_forge.validate_ext(path="/path/to/extension.py")` is called
- **AND** the file is missing `pack` or `__all__`
- **THEN** it returns "Validation FAILED" with errors

#### Scenario: Best practices warnings

- **WHEN** `ot_forge.validate_ext(path="/path/to/extension.py")` is called
- **AND** the file violates best practices (pack after imports, missing logging)
- **THEN** it includes warnings in the result but still passes
