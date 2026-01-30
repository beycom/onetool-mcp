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
- **THEN** it SHALL return valid=False with error "Dangerous builtin 'exec' is not allowed (matches 'exec')"

#### Scenario: Eval call blocked
- **GIVEN** code containing `eval("expression")`
- **WHEN** validate_python_code() is called with check_security=True
- **THEN** it SHALL return valid=False with error "Dangerous builtin 'eval' is not allowed (matches 'eval')"

#### Scenario: Dynamic import blocked
- **GIVEN** code containing `__import__("module")`
- **WHEN** validate_python_code() is called with check_security=True
- **THEN** it SHALL return valid=False with error "Dangerous builtin '__import__' is not allowed (matches '__import__')"

#### Scenario: Compile blocked
- **GIVEN** code containing `compile("code", "", "exec")`
- **WHEN** validate_python_code() is called with check_security=True
- **THEN** it SHALL return valid=False with error "Dangerous builtin 'compile' is not allowed (matches 'compile')"

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

### Requirement: Configurable Security Patterns

The system SHALL support configurable security patterns via ot-serve.yaml.

#### Scenario: Custom blocked patterns
- **GIVEN** configuration with:

  ```yaml
  security:
    blocked:
      - my_dangerous.*
  ```

- **WHEN** code containing `my_dangerous.func()` is validated
- **THEN** it SHALL return valid=False with error
- **AND** built-in default blocked patterns SHALL still apply

#### Scenario: Security disabled
- **GIVEN** configuration with `security.enabled: false`
- **WHEN** code containing dangerous patterns is validated
- **THEN** security checks SHALL be skipped
- **AND** only syntax validation SHALL occur

#### Scenario: Default patterns used
- **GIVEN** no security configuration in ot-serve.yaml
- **WHEN** code is validated
- **THEN** built-in default patterns SHALL be used

#### Scenario: Additive configuration
- **GIVEN** configuration with only custom patterns
- **WHEN** patterns are loaded
- **THEN** custom patterns SHALL be merged with defaults
- **AND** defaults SHALL NOT be replaced
- **RATIONALE** Prevents accidental removal of critical security patterns

#### Scenario: Allow list exemption
- **GIVEN** configuration with:

  ```yaml
  security:
    allow:
      - open
  ```

- **WHEN** code containing `open()` is validated
- **THEN** it SHALL pass without warning (exempted from defaults)

### Requirement: Wildcard Pattern Matching

The system SHALL support fnmatch wildcards in security patterns.

#### Scenario: Asterisk wildcard
- **GIVEN** blocked pattern `subprocess.*`
- **WHEN** code containing `subprocess.run()` or `subprocess.Popen()` is validated
- **THEN** both SHALL be blocked

#### Scenario: Question mark wildcard
- **GIVEN** blocked pattern `os.exec?`
- **WHEN** code containing `os.execl()` is validated
- **THEN** it SHALL be blocked
- **AND** `os.execve()` SHALL NOT be blocked (more than one char)

#### Scenario: Exact match fallback
- **GIVEN** blocked pattern `os.system` (no wildcards)
- **WHEN** code containing `os.system()` is validated
- **THEN** exact match SHALL be used (fast path)

#### Scenario: Error message includes pattern
- **GIVEN** code blocked by wildcard pattern `subprocess.*`
- **WHEN** error is reported
- **THEN** message SHALL include both the function name and the matched pattern
- **EXAMPLE** "subprocess.check_output is not allowed (matches 'subprocess.*')"

### Requirement: Four-Level Security Pattern Categories

The system SHALL support four categories of security patterns with automatic type detection.

#### Scenario: Blocked patterns
- **GIVEN** `blocked: [exec, eval, subprocess.*, os.system]`
- **WHEN** code uses these patterns
- **THEN** validation SHALL fail with error
- **AND** execution SHALL be denied

#### Scenario: Ask patterns
- **GIVEN** `ask: [requests.*, urllib.*]`
- **WHEN** code uses these patterns
- **THEN** validation SHALL return `requires_confirmation=True`
- **AND** the caller SHALL prompt the user for confirmation before execution
- **AND** if denied, execution SHALL be blocked

#### Scenario: Warned patterns
- **GIVEN** `warned: [subprocess, os, open, pickle.*]`
- **WHEN** code uses these patterns
- **THEN** validation SHALL pass with warning
- **AND** warning SHALL be logged

#### Scenario: Allow patterns
- **GIVEN** `allow: [open]`
- **WHEN** code uses these patterns
- **THEN** validation SHALL pass without warning
- **AND** pattern SHALL be exempt from warned/ask defaults

#### Scenario: Pattern precedence
- **GIVEN** a pattern appears in multiple categories
- **WHEN** validation occurs
- **THEN** precedence SHALL be: `blocked` > `ask` > `warned` > `allow`
- **EXAMPLE** If `open` is in both `blocked` and `allow`, it SHALL be blocked

#### Scenario: Pattern type detection
- **GIVEN** patterns without dots (e.g., `exec`, `subprocess`)
- **WHEN** pattern matching occurs
- **THEN** they SHALL match builtin calls AND import statements
- **AND** patterns with dots (e.g., `subprocess.*`) SHALL match qualified calls only
