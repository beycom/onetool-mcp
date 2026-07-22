## ADDED Requirements

### Requirement: Lightweight facade installation

The base `onetool-mcp` distribution SHALL install the `onetool` CLI facade without
installing the MCP runtime or Skill component dependency sets.

#### Scenario: Bare distribution installs only the facade

- **WHEN** `uv tool install onetool-mcp` completes in a clean environment
- **THEN** the `onetool` executable SHALL be available
- **AND** `onetool --help` and `onetool --version` SHALL succeed
- **AND** the MCP runtime and Skill component distributions SHALL not be installed

#### Scenario: Facade reports no installed components

- **GIVEN** only the base `onetool-mcp` distribution is installed
- **WHEN** component status is requested
- **THEN** MCP and Skill SHALL both be reported as not installed
- **AND** the output SHALL show the exact `[mcp]` and `[skill]` installation commands

### Requirement: MCP component extra

The `onetool-mcp[mcp]` extra SHALL install a complete runnable MCP component and
SHALL NOT install the Skill component unless `[skill]` is also selected.

#### Scenario: MCP-only installation

- **WHEN** `uv tool install 'onetool-mcp[mcp]'` completes in a clean environment
- **THEN** `onetool serve`, `onetool init`, `onetool direct`, and `onetool kb`
  SHALL be available
- **AND** the MCP server SHALL pass its installed-wheel startup smoke test
- **AND** `onetool skill` SHALL not be registered

### Requirement: Skill component extra

The `onetool-mcp[skill]` extra SHALL install the Skill component without installing
the MCP runtime or MCP-only dependency set.

#### Scenario: Skill-only installation

- **WHEN** `uv tool install 'onetool-mcp[skill]'` completes in a clean environment
- **THEN** `onetool skill` SHALL be available
- **AND** Skill build and install smoke tests SHALL succeed
- **AND** FastMCP, MCP, and the OneTool MCP runtime distribution SHALL not be
  installed

#### Scenario: Skill-only invocation does not import MCP dependencies

- **GIVEN** only the `[skill]` component is installed
- **WHEN** `onetool skill --help` or a Skill command is invoked
- **THEN** execution SHALL not import or require an MCP runtime module

### Requirement: Composable extras

OneTool extras SHALL compose through normal package dependency resolution without
changing the behavior of either selected component.

#### Scenario: MCP and Skill installation

- **WHEN** `uv tool install 'onetool-mcp[mcp,skill]'` completes
- **THEN** the same `onetool` executable SHALL expose both MCP commands and the
  `skill` command group
- **AND** no component SHALL install a competing `onetool` console script

#### Scenario: Utility packs imply MCP

- **WHEN** `[util]` is selected without explicitly listing `[mcp]`
- **THEN** the MCP runtime and utility pack dependencies SHALL be installed
- **AND** utility packs SHALL be available to the MCP server

#### Scenario: Developer packs imply MCP

- **WHEN** `[dev]` is selected without explicitly listing `[mcp]`
- **THEN** the MCP runtime and developer pack dependencies SHALL be installed
- **AND** developer packs SHALL be available to the MCP server

#### Scenario: Complete explicit composition

- **WHEN** `uv tool install 'onetool-mcp[mcp,util,dev,skill]'` completes
- **THEN** MCP base, utility, developer, and Skill capabilities SHALL all be
  available from one `onetool` executable

#### Scenario: All extra composition

- **WHEN** `uv tool install 'onetool-mcp[all]'` completes
- **THEN** it SHALL install the same component set as
  `onetool-mcp[mcp,util,dev,skill]`

### Requirement: Component registration failures

The facade SHALL fail closed when installed components cannot be composed safely.

#### Scenario: Duplicate command registration

- **WHEN** two installed components register the same component or root command
  name
- **THEN** the CLI SHALL exit non-zero before command execution
- **AND** the error SHALL identify both conflicting distributions

#### Scenario: Incompatible component API

- **WHEN** an installed component declares an unsupported facade API version
- **THEN** the CLI SHALL exit non-zero with an actionable command to reinstall or
  upgrade the incompatible component set

#### Scenario: Broken installed component

- **WHEN** a registered component fails during loading
- **THEN** the CLI SHALL report that component as broken rather than treating it as
  absent
- **AND** it SHALL preserve the original failure as diagnostic context

### Requirement: Published-wheel dependency isolation

Release verification SHALL prove component isolation using built wheels installed
into clean environments.

#### Scenario: Skill wheel excludes MCP footprint

- **WHEN** release wheels are installed with only `[skill]`
- **THEN** package metadata and the installed distribution inventory SHALL contain
  no dependency path to the MCP runtime, FastMCP, or MCP

#### Scenario: MCP wheel excludes Skill footprint

- **WHEN** release wheels are installed with only `[mcp]`
- **THEN** package metadata and the installed distribution inventory SHALL contain
  no dependency path to the Skill component
