# tool-scaffold Specification

## Purpose

Provides the scaffold pack for creating extension and isolated tools from templates. Enables users to quickly scaffold new tools with proper structure for in-process or subprocess execution.
## Requirements
### Requirement: List Templates Function

The scaffold pack SHALL provide a `templates()` function to list available extension templates.

#### Scenario: List available templates
- **WHEN** `scaffold.templates()` is called
- **THEN** it returns a formatted list of template names and descriptions
- **AND** templates are read from `src/ot/config/defaults/tool_templates/`

#### Scenario: Empty template directory
- **WHEN** the template directory does not exist or is empty
- **THEN** it returns "No templates found"

### Requirement: Create Extension Function

The scaffold pack SHALL provide a `create()` function to scaffold new extensions from templates.

#### Scenario: Create project extension
- **WHEN** `scaffold.create(name="mypack")` is called
- **THEN** it creates `.onetool/tools/mypack/mypack.py`
- **AND** uses the default "extension" template (in-process, full `ot.*` access)
- **AND** substitutes `{{pack}}`, `{{function}}`, `{{description}}` placeholders

#### Scenario: Create global extension
- **WHEN** `scaffold.create(name="mypack", scope="global")` is called
- **THEN** it creates `~/.onetool/tools/mypack/mypack.py`

#### Scenario: Custom function name
- **WHEN** `scaffold.create(name="mypack", function="search")` is called
- **THEN** the generated file has `def search(...)` instead of `def run(...)`

#### Scenario: Custom template
- **WHEN** `scaffold.create(name="mypack", template="custom")` is called
- **THEN** it uses `tool_templates/custom.py` if it exists
- **AND** returns error if template not found

#### Scenario: Extension already exists
- **WHEN** `scaffold.create(name="mypack")` is called
- **AND** `.onetool/tools/mypack/mypack.py` already exists
- **THEN** it returns an error message without overwriting

#### Scenario: Next steps guidance
- **WHEN** an extension is successfully created
- **THEN** the return value includes guidance on editing, validating, reloading, and calling the new function

### Requirement: List Extensions Function

The scaffold pack SHALL provide an `extensions()` function to show loaded extensions.

#### Scenario: List loaded extensions
- **WHEN** `scaffold.extensions()` is called
- **THEN** it returns all extension files loaded from `tools_dir` config
- **AND** shows full path to each file

#### Scenario: No extensions loaded
- **WHEN** no extension files are configured in `tools_dir`
- **THEN** it returns a message indicating no extensions are loaded

### Requirement: Validate Extension Function

The scaffold pack SHALL provide a `validate()` function for pre-reload validation.

#### Scenario: Valid extension
- **WHEN** `scaffold.validate(path="/path/to/extension.py")` is called
- **AND** the extension has valid syntax and required structure
- **THEN** it returns "Validation PASSED" with any warnings

#### Scenario: Syntax error
- **WHEN** `scaffold.validate(path="/path/to/extension.py")` is called
- **AND** the file has a Python syntax error
- **THEN** it returns an error with line number and message

#### Scenario: Missing required structure
- **WHEN** `scaffold.validate(path="/path/to/extension.py")` is called
- **AND** the file is missing `pack` or `__all__`
- **THEN** it returns "Validation FAILED" with errors

#### Scenario: Missing JSON-RPC loop for isolated tools
- **WHEN** `scaffold.validate(path="/path/to/tool.py")` is called
- **AND** the file has PEP 723 dependencies but no inline JSON-RPC loop
- **THEN** it returns "Validation FAILED" with error about missing JSON-RPC loop

#### Scenario: Warn about deprecated ot_sdk imports
- **WHEN** `scaffold.validate(path="/path/to/tool.py")` is called
- **AND** the file imports from `ot_sdk`
- **THEN** it includes a DEPRECATED warning in the result

#### Scenario: Best practices warnings
- **WHEN** `scaffold.validate(path="/path/to/extension.py")` is called
- **AND** the file violates best practices (pack after imports, missing logging)
- **THEN** it includes warnings in the result but still passes

### Requirement: Extension Template Structure

The extension template SHALL include all required components for in-process execution with full onetool access.

#### Scenario: Extension template uses ot.* imports
- **WHEN** the extension template is used
- **THEN** the generated file imports from `ot.logging`, `ot.config`
- **AND** optionally shows `ot.tools` import in comments for inter-tool calling

#### Scenario: Extension template does not use worker_main
- **WHEN** the extension template is used
- **THEN** the generated file does NOT have `worker_main()` or `if __name__` block
- **AND** executes in-process like bundled tools

#### Scenario: Extension template includes logging
- **WHEN** the extension template is used
- **THEN** the generated function uses `with LogSpan(...) as s:` pattern
- **AND** imports `LogSpan` from `ot.logging`

### Requirement: Isolated Template Structure

The isolated template SHALL include all required components for subprocess execution with external dependencies.

#### Scenario: Isolated template is fully standalone
- **WHEN** the isolated template is used
- **THEN** the generated file has NO onetool imports
- **AND** implements JSON-RPC loop inline using only stdlib

#### Scenario: Isolated template has PEP 723 header
- **WHEN** the isolated template is used
- **THEN** the generated file has a valid `# /// script` metadata block
- **AND** includes `requires-python` and `dependencies` fields

#### Scenario: Isolated template main loop
- **WHEN** the isolated template is used
- **THEN** the generated file has `if __name__ == "__main__":` with JSON-RPC loop
- **AND** reads from stdin and writes to stdout as JSON

### Requirement: Template Location

Extension templates SHALL be stored in the bundled config defaults directory.

#### Scenario: Template discovery
- **WHEN** scaffold functions look for templates
- **THEN** they use `get_bundled_config_dir() / "tool_templates"` to find the directory
- **AND** templates are bundled with the onetool package

#### Scenario: Template file naming
- **WHEN** a template is referenced
- **THEN** the file name is `<template>.py` in the tool_templates directory

