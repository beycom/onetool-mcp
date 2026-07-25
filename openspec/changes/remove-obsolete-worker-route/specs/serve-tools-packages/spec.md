## ADDED Requirements

### Requirement: Configured Extension In-Process Execution

OneTool SHALL load configured extension files in-process through the same local
pack loading route regardless of inline script comment metadata.

#### Scenario: Configured extension loads in-process

- **GIVEN** a configured extension with a valid pack and exported function
- **WHEN** the tool registry loads and the function is called
- **THEN** OneTool imports and executes the extension in the server process
- **AND** the extension has access to the installed OneTool runtime

#### Scenario: Inline script metadata is inert

- **GIVEN** a configured extension containing a syntactically valid PEP 723
  comment block
- **WHEN** the tool registry loads the extension
- **THEN** the comment block does not change execution routing
- **AND** OneTool does not parse it, install dependencies, or spawn a subprocess

#### Scenario: Missing extension dependency

- **GIVEN** a configured extension imports a dependency absent from the
  installed OneTool environment
- **WHEN** the tool registry loads the extension
- **THEN** the extension fails through the normal in-process module-load error
  path
- **AND** unrelated valid packs remain available
