# tool-forge Specification

## Purpose

Provides the `ot_forge` pack for creating and validating in-process extension tools. All extensions use the single in-process `extension` template with full `ot.*` access.

## Requirements

### Requirement: Create Extension Function

The ot_forge pack SHALL provide a `create_ext()` function to create new extensions.

#### Scenario: Create project extension
- **WHEN** `ot_forge.create_ext(name="mypack")` is called
- **THEN** it creates an extension file in a path compatible with active `tools_dir` glob patterns
- **AND** uses the `extension` template (in-process, full `ot.*` access)
- **AND** substitutes `{{pack}}`, `{{function}}`, `{{description}}` placeholders

#### Scenario: Custom function name
- **WHEN** `ot_forge.create_ext(name="mypack", function="search")` is called
- **THEN** the generated file has `def search(...)` instead of `def run(...)`

#### Scenario: Extension already exists
- **WHEN** `ot_forge.create_ext(name="mypack")` is called
- **AND** the computed scaffold path already exists
- **THEN** it returns an error message without overwriting

#### Scenario: Common flat tools_dir compatibility
- **GIVEN** `tools_dir` contains `tools/*.py`
- **WHEN** `ot_forge.create_ext(name="mypack")` is called
- **THEN** it SHALL scaffold to `.onetool/tools/mypack.py` so `ot.reload()` can discover it immediately

#### Scenario: Next steps guidance
- **WHEN** an extension is successfully created
- **THEN** the return value includes guidance referencing `ot_forge.validate_ext`, `ot.reload()`, and the new function

### Requirement: Validate Extension Function

The ot_forge pack SHALL provide a `validate_ext()` function for pre-reload validation.

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

### Requirement: Extension Template Structure

The extension template SHALL include all required components for in-process execution with full onetool access.

#### Scenario: Extension template uses ot.* imports
- **WHEN** the extension template is used
- **THEN** the generated file imports from `ot.logging`, `ot.config`

#### Scenario: Extension template includes logging
- **WHEN** the extension template is used
- **THEN** the generated function emits structured runtime logs for the generated operation

### Requirement: Template Location

The extension template SHALL be stored in the bundled config defaults directory.

#### Scenario: Template discovery
- **WHEN** `create_ext()` looks for the template
- **THEN** it uses `get_global_templates_dir() / "tool_templates" / "extension.py"`

### Requirement: ot.packs() Extension Visibility

The `ot.packs()` function SHALL identify user extension packs and expose their file path.

#### Scenario: Extension pack marked in packs listing
- **WHEN** `ot.packs()` is called
- **AND** a user extension pack is loaded from `tools_dir`
- **THEN** the pack entry SHALL include `is_extension: true`
- **AND** SHALL include `path` with the full path to the extension file

#### Scenario: Built-in local pack not marked as extension
- **WHEN** `ot.packs()` is called
- **AND** a bundled local pack is listed (e.g. `ot`, `ripgrep`)
- **THEN** the pack entry SHALL NOT include `is_extension`
