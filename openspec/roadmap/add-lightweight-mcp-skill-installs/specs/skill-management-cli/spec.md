## ADDED Requirements

### Requirement: Skill command namespace

When the Skill component is installed, OneTool SHALL expose its public command
surface under the `onetool skill` group.

#### Scenario: Skill group help

- **GIVEN** `onetool-mcp[skill]` is installed
- **WHEN** `onetool skill --help` is executed
- **THEN** it SHALL list the complete stable Skill command inventory
- **AND** it SHALL include at least `build` and `install`

#### Scenario: Build a skill repository

- **GIVEN** a valid Skill authoring repository
- **WHEN** `onetool skill build` is executed
- **THEN** it SHALL compile the repository according to the merged stable Skill
  build contract

#### Scenario: Install declared skills

- **GIVEN** a valid project skill manifest
- **WHEN** `onetool skill install` is executed
- **THEN** it SHALL install the declared skills according to the merged stable
  Skill install and lockfile contracts

### Requirement: Skill CLI operates independently from MCP

The Skill command group SHALL operate without an installed or configured OneTool
MCP runtime.

#### Scenario: Build without MCP

- **GIVEN** only `onetool-mcp[skill]` is installed
- **WHEN** `onetool skill build` is run against a valid repository
- **THEN** it SHALL complete without an MCP config file, MCP process, or MCP Python
  dependency

#### Scenario: Install without MCP

- **GIVEN** only `onetool-mcp[skill]` is installed
- **WHEN** `onetool skill install` is run for a valid project
- **THEN** it SHALL complete without starting or configuring an MCP server

### Requirement: No legacy Skill CLI aliases

The integrated Skill component SHALL expose only its OneTool-owned package,
command, configuration, state, and manifest names.

#### Scenario: Removed standalone command

- **WHEN** the integrated component release is installed
- **THEN** it SHALL not install a `oneskill` executable
- **AND** users SHALL invoke the component through `onetool skill`

#### Scenario: Removed names fail normally

- **WHEN** a removed pre-integration configuration key, environment variable, file
  name, or command spelling is used
- **THEN** it SHALL fail through the current discovery, validation, or unknown-command
  path
- **AND** it SHALL not be accepted as an alias or fallback

### Requirement: Skill management remains a host CLI capability

Skill building and installation SHALL run as explicit host CLI operations and
SHALL NOT be exposed as MCP tools.

#### Scenario: Skill commands absent from MCP registry

- **WHEN** the MCP tool registry is inspected with both MCP and Skill components
  installed
- **THEN** it SHALL contain no tool that builds, installs, updates, imports, or
  mutates agent skills on behalf of `onetool skill`
