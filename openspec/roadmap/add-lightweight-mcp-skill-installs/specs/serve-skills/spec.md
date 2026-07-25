## MODIFIED Requirements

### Requirement: No OneTool-Owned Runtime Serving or Installer

The OneTool MCP runtime SHALL NOT expose a tool that lists, retrieves, builds, or
installs skill content. An independently installed OneTool Skill host CLI component
MAY build and install skills only through explicit `onetool skill` commands outside
the MCP request pipeline.

#### Scenario: No ot.skills tool

- **WHEN** the OneTool MCP tool registry is inspected
- **THEN** no tool named `ot.skills` SHALL be present

#### Scenario: No ot_forge.install_skills tool

- **WHEN** the OneTool MCP tool registry is inspected
- **THEN** no tool named `ot_forge.install_skills` SHALL be present

#### Scenario: No MCP installer machinery

- **WHEN** the MCP runtime source and registry are inspected
- **THEN** no MCP tool or server request path SHALL invoke the Skill component's
  build, install, update, import, or mutation operations

#### Scenario: Host Skill CLI remains separate

- **GIVEN** both MCP and Skill components are installed
- **WHEN** `onetool skill install` is executed by the user
- **THEN** it SHALL run as a host CLI operation
- **AND** it SHALL not call the local MCP server to perform the installation
