# serve-code-validation Specification

## Purpose

Defines Python code validation for the run() tool. Includes syntax checking via AST parsing, security pattern detection for dangerous calls, and optional ruff linting for style warnings.
## Requirements
### Requirement: Syntax Validation

The system SHALL validate Python syntax before execution using AST parsing.

#### Scenario: Valid syntax
- **GIVEN** syntactically valid Python code
- **WHEN** validate_python_code() is called
- **THEN** it SHALL return ValidationResult with valid=True

#### Scenario: Invalid syntax
- **GIVEN** Python code with syntax errors
- **WHEN** validate_python_code() is called
- **THEN** it SHALL return ValidationResult with valid=False and error containing line number

#### Scenario: Syntax error message
- **GIVEN** code with syntax error on line 5
- **WHEN** validation fails
- **THEN** the error message SHALL include "Syntax error at line 5: {error message}"

### Requirement: Security Pattern Detection

The system SHALL detect and block dangerous code patterns.

#### Scenario: Exec call blocked
- **GIVEN** code containing `exec("code")`
- **WHEN** validate_python_code() is called with check_security=True
- **THEN** it SHALL return valid=False with error "Dangerous call: exec() not allowed"

#### Scenario: Eval call blocked
- **GIVEN** code containing `eval("expression")`
- **WHEN** validate_python_code() is called with check_security=True
- **THEN** it SHALL return valid=False with error "Dangerous call: eval() not allowed"

#### Scenario: Dynamic import blocked
- **GIVEN** code containing `__import__("module")`
- **WHEN** validate_python_code() is called with check_security=True
- **THEN** it SHALL return valid=False with error "Dangerous call: __import__() not allowed"

#### Scenario: Compile blocked
- **GIVEN** code containing `compile("code", "", "exec")`
- **WHEN** validate_python_code() is called with check_security=True
- **THEN** it SHALL return valid=False with error "Dangerous call: compile() not allowed"

#### Scenario: Open generates warning
- **GIVEN** code containing `open("file.txt")`
- **WHEN** validate_python_code() is called with check_security=True
- **THEN** it SHALL return valid=True with warning "Potentially unsafe function 'open'"
- **RATIONALE** File access is commonly needed by legitimate tools

#### Scenario: Security check disabled
- **GIVEN** code containing dangerous patterns
- **WHEN** validate_python_code() is called with check_security=False
- **THEN** it SHALL not check for dangerous patterns

### Requirement: AST-Based Function Parsing

The system SHALL parse function calls using AST instead of regex.

#### Scenario: Simple function call
- **GIVEN** code `search(query="test")`
- **WHEN** parse_function_call() is called
- **THEN** it SHALL return ("search", {"query": "test"})

#### Scenario: Nested function call
- **GIVEN** code `to_yaml(search(query="test"))`
- **WHEN** parse_function_call() is called
- **THEN** it SHALL detect this as Python code requiring full execution

#### Scenario: Multiple arguments
- **GIVEN** code `search(query="test", count=5, fresh=True)`
- **WHEN** parse_function_call() is called
- **THEN** it SHALL extract all keyword arguments with correct types

#### Scenario: Invalid function call
- **GIVEN** invalid syntax like `search(query=`
- **WHEN** parse_function_call() is called
- **THEN** it SHALL raise ValueError with clear error message

### Requirement: Optional Ruff Linting

The system SHALL optionally run ruff for style warnings.

#### Scenario: Ruff available
- **GIVEN** ruff is installed and lint_warnings=True
- **WHEN** lint_code() is called
- **THEN** it SHALL return list of warning strings

#### Scenario: Ruff not installed
- **GIVEN** ruff is not installed
- **WHEN** lint_code() is called
- **THEN** it SHALL return empty list (fail silently)

#### Scenario: Ruff timeout
- **GIVEN** ruff takes longer than 5 seconds
- **WHEN** lint_code() is called
- **THEN** it SHALL return empty list (fail silently)

#### Scenario: Warnings non-blocking
- **GIVEN** ruff returns warnings
- **WHEN** validation runs
- **THEN** warnings SHALL be included in ValidationResult but valid SHALL remain True

### Requirement: Validation Result Structure

The system SHALL return structured validation results.

#### Scenario: Result structure
- **GIVEN** any code input
- **WHEN** validate_python_code() is called
- **THEN** it SHALL return ValidationResult with: valid (bool), errors (list[str]), warnings (list[str])

#### Scenario: Multiple errors
- **GIVEN** code with multiple issues
- **WHEN** validate_python_code() is called
- **THEN** all errors SHALL be collected in the errors list

#### Scenario: Mixed errors and warnings
- **GIVEN** code with security issues and style warnings
- **WHEN** validate_python_code() is called
- **THEN** security issues SHALL be in errors, style issues in warnings

### Requirement: Security Pattern Detection (modified)

The system SHALL generate warnings for potentially unsafe but commonly-needed functions.

#### Scenario: Open generates warning (modified from "Open blocked")
- **GIVEN** code containing `open("file.txt")`
- **WHEN** validate_python_code() is called with check_security=True
- **THEN** it SHALL return valid=True with warning "Potentially unsafe function 'open'"
- **RATIONALE** File access is often required by legitimate tools. Warning is appropriate.
