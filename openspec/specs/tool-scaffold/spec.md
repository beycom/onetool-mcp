# tool-scaffold Specification

## Purpose

Provides the scaffold pack for creating extension tools from templates. Enables users to quickly scaffold new extensions with proper PEP 723 headers and worker patterns.
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
- **WHEN** `scaffold.create(pack="mypack")` is called
- **THEN** it creates `.onetool/tools/mypack/mypack_tools.py`
- **AND** uses the default "extension" template
- **AND** substitutes `{{pack}}`, `{{function}}`, `{{description}}` placeholders

#### Scenario: Create global extension
- **WHEN** `scaffold.create(pack="mypack", location="global")` is called
- **THEN** it creates `~/.onetool/tools/mypack/mypack_tools.py`

#### Scenario: Custom function name
- **WHEN** `scaffold.create(pack="mypack", function="search")` is called
- **THEN** the generated file has `def search(...)` instead of `def run(...)`

#### Scenario: Custom template
- **WHEN** `scaffold.create(pack="mypack", template="http")` is called
- **THEN** it uses `tool_templates/http.py` if it exists
- **AND** returns error if template not found

#### Scenario: Extension already exists
- **WHEN** `scaffold.create(pack="mypack")` is called
- **AND** `.onetool/tools/mypack/mypack_tools.py` already exists
- **THEN** it returns an error message without overwriting

#### Scenario: Next steps guidance
- **WHEN** an extension is successfully created
- **THEN** the return value includes guidance on editing, restarting, and calling the new function

### Requirement: List Extensions Function

The scaffold pack SHALL provide a `list_extensions()` function to show installed extensions.

#### Scenario: List project and global extensions
- **WHEN** `scaffold.list_extensions()` is called
- **THEN** it returns extensions from both `.onetool/tools/` and `~/.onetool/tools/`
- **AND** shows pack name and file path for each

#### Scenario: No extensions installed
- **WHEN** no extensions exist in either location
- **THEN** it returns "(none)" under "User extensions:"

### Requirement: Extension Template Structure

The default extension template SHALL include all required components for a working extension.

#### Scenario: Template includes PEP 723 header
- **WHEN** the extension template is used
- **THEN** the generated file has a valid `# /// script` metadata block
- **AND** includes `requires-python` and `dependencies` fields

#### Scenario: Template includes worker_main
- **WHEN** the extension template is used
- **THEN** the generated file has `if __name__ == "__main__": worker_main()`
- **AND** imports `worker_main` from `ot_sdk`

#### Scenario: Template includes logging
- **WHEN** the extension template is used
- **THEN** the generated function uses `with log(...) as s:` pattern
- **AND** imports `log` from `ot_sdk`

### Requirement: Template Location

Extension templates SHALL be stored in the bundled config defaults directory.

#### Scenario: Template discovery
- **WHEN** scaffold functions look for templates
- **THEN** they use `get_config_path("tool_templates")` to find the directory
- **AND** templates are bundled with the onetool package

#### Scenario: Template file naming
- **WHEN** a template is referenced
- **THEN** the file name is `<template>.py` in the tool_templates directory

