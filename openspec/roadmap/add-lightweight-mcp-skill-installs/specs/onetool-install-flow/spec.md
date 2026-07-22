## MODIFIED Requirements

### Requirement: Bootstrap installer script

OneTool SHALL ship a POSIX shell bootstrap script (`scripts/install.sh`) and a
PowerShell bootstrap script (`scripts/install.ps1`) that wrap `uv`, select an
installable OneTool component composition, and run only the post-install setup
required by that composition. PyInstaller-style single-binary packaging remains
rejected because the MCP worker pool resolves PEP 723 dependencies through `uv`
and a frozen binary cannot express the optional-component model.

Both scripts SHALL, in order:

1. Detect the host platform.
2. Check whether `uv` is already on `PATH`; if not, install it with the official
   uv installer and make it available for the remainder of the script.
3. If `ONETOOL_EXTRAS` is set, validate and select that exact comma-separated
   extras list without prompting.
4. Otherwise, if a controlling terminal is available, prompt for MCP (`mcp`, the
   default), Skill (`skill`), MCP + Skill (`mcp,skill`), or Complete
   (`mcp,util,dev,skill`). If no controlling terminal is available, select `mcp`.
5. Run `uv tool install 'onetool-mcp[<extras>]'` for the resolved selection.
6. For a selection containing the MCP runtime, run `onetool init --config
   <config-dir>`, then `onetool init mcp-config --config
   <config-dir>/onetool.yaml`, and print `onetool init validate` guidance.
7. For a Skill-only selection, skip MCP initialization and print `onetool skill
   --help` plus the Skill quick-start command as the next step.

`<config-dir>` SHALL default to a platform-appropriate home-relative path and
remain overridable through `ONETOOL_CONFIG_DIR`. `uv tool install` SHALL remain the
documented manual installation path; the bootstrap remains the recommended guided
path rather than a replacement for uv.

#### Scenario: uv already installed

- **GIVEN** `uv` is already on `PATH`
- **WHEN** either bootstrap script runs
- **THEN** it SHALL skip the uv installer step
- **AND** it SHALL proceed to component selection

#### Scenario: uv missing

- **GIVEN** `uv` is not on `PATH`
- **WHEN** either bootstrap script runs
- **THEN** it SHALL install uv through the official installer before attempting
  `uv tool install`
- **AND** the script's own `PATH` SHALL be updated for the same process

#### Scenario: Interactive MCP default

- **GIVEN** `ONETOOL_EXTRAS` is not set
- **AND** a controlling terminal is available
- **WHEN** the user accepts the default selection
- **THEN** the script SHALL run `uv tool install 'onetool-mcp[mcp]'`
- **AND** it SHALL continue through MCP initialization and client configuration

#### Scenario: Interactive Skill selection

- **GIVEN** `ONETOOL_EXTRAS` is not set
- **AND** a controlling terminal is available
- **WHEN** the user selects Skill
- **THEN** the script SHALL run `uv tool install 'onetool-mcp[skill]'`
- **AND** it SHALL not create an MCP config directory or print MCP client config

#### Scenario: Interactive MCP and Skill selection

- **GIVEN** a controlling terminal is available
- **WHEN** the user selects MCP + Skill
- **THEN** the script SHALL run `uv tool install 'onetool-mcp[mcp,skill]'`
- **AND** it SHALL complete MCP post-install setup
- **AND** it SHALL print Skill quick-start guidance

#### Scenario: Interactive complete selection

- **GIVEN** a controlling terminal is available
- **WHEN** the user selects Complete
- **THEN** the script SHALL run
  `uv tool install 'onetool-mcp[mcp,util,dev,skill]'`

#### Scenario: Piped script uses controlling terminal

- **GIVEN** the POSIX script is invoked through `curl -LsSf <url> | sh`
- **AND** the process has a controlling terminal
- **WHEN** component selection begins
- **THEN** the script SHALL read the selection from the controlling terminal even
  though standard input is the script pipe

#### Scenario: Non-interactive default

- **GIVEN** `ONETOOL_EXTRAS` is not set
- **AND** no controlling terminal is available
- **WHEN** either bootstrap script runs
- **THEN** it SHALL select `mcp` without prompting
- **AND** it SHALL run `uv tool install 'onetool-mcp[mcp]'`

#### Scenario: Overridable extras

- **GIVEN** `ONETOOL_EXTRAS=skill` is set
- **WHEN** either bootstrap script runs
- **THEN** it SHALL not prompt for a component selection
- **AND** it SHALL run `uv tool install 'onetool-mcp[skill]'`

#### Scenario: Invalid extras override

- **GIVEN** `ONETOOL_EXTRAS` contains an empty, duplicate, or unsupported extra
- **WHEN** either bootstrap script validates the override
- **THEN** it SHALL exit non-zero before invoking `uv tool install`
- **AND** it SHALL list the supported extras

#### Scenario: Non-interactive init during MCP bootstrap

- **GIVEN** the script itself is supplied through a pipe
- **AND** the resolved selection contains MCP
- **WHEN** the `onetool init` step runs
- **THEN** `onetool init` SHALL take its non-interactive path unless its own
  terminal interaction is explicitly supported
- **AND** the closing message SHALL explain how to rerun guided MCP configuration

#### Scenario: MCP config printed at the end of MCP bootstrap

- **GIVEN** the resolved selection contains MCP
- **WHEN** the bootstrap completes successfully
- **THEN** it SHALL print the generated MCP client configuration and validation
  command

#### Scenario: Skill guidance printed at the end of Skill-only bootstrap

- **GIVEN** the resolved selection is Skill only
- **WHEN** the bootstrap completes successfully
- **THEN** it SHALL print `onetool skill --help` and the Skill quick-start command
- **AND** it SHALL not recommend MCP initialization

### Requirement: Repeatable first-run command sequence

Documentation SHALL present component selection and the matching first-run
sequence in an explicitly ordered, copy/paste-friendly form. MCP selections SHALL
use install, init, MCP client configuration, and validation; Skill-only selections
SHALL use install and Skill quick start without MCP setup. No install wrapper beyond
the bootstrap scripts SHALL be introduced.

#### Scenario: Recommended MCP sequence documented

- **WHEN** users read installation or quick-start documentation for MCP
- **THEN** they SHALL find the guided bootstrap or manual
  `uv tool install 'onetool-mcp[mcp]'` command followed by `onetool init`, MCP
  client configuration, and `onetool init validate`
- **AND** each step's expected output or effect SHALL be stated

#### Scenario: Recommended Skill sequence documented

- **WHEN** users read installation or quick-start documentation for Skill
- **THEN** they SHALL find the guided bootstrap or manual
  `uv tool install 'onetool-mcp[skill]'` command followed by `onetool skill`
  quick-start commands
- **AND** the sequence SHALL not require `onetool init` or an MCP client

#### Scenario: Combined installation documented

- **WHEN** users want MCP and Skill in one tool environment
- **THEN** documentation SHALL show `onetool-mcp[mcp,skill]` and the explicit
  complete `onetool-mcp[mcp,util,dev,skill]` composition

#### Scenario: Manual path still documented

- **WHEN** users read installation documentation
- **THEN** `uv tool install 'onetool-mcp[<extras>]'` SHALL remain a supported
  alternative to the bootstrap
- **AND** bare `uv tool install onetool-mcp` SHALL be identified as facade-only

#### Scenario: Init validate remains the MCP verification step

- **WHEN** documentation describes completing an MCP-containing setup
- **THEN** it SHALL point to `onetool init validate --config <path>`
- **AND** the same command SHALL be printed by MCP initialization

#### Scenario: Clean-machine MCP flow

- **GIVEN** a machine with no prior uv, OneTool, or OneTool config directory
- **WHEN** the documented MCP bootstrap sequence is followed without manual path
  edits
- **THEN** the MCP client SHALL connect to the `onetool` server successfully
- **AND** a first `ot.status()` call SHALL succeed

#### Scenario: Clean-machine Skill flow

- **GIVEN** a machine with no prior uv, OneTool, or MCP configuration
- **WHEN** the documented Skill-only bootstrap sequence is followed
- **THEN** `onetool skill --help` and the documented Skill smoke command SHALL
  succeed
- **AND** no MCP configuration SHALL be created
