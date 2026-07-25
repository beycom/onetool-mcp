## ADDED Requirements

### Requirement: Harness commands in the OneTool CLI
The `onetool` CLI SHALL expose Claude Code and Codex launcher commands as top-level
commands.

#### Scenario: Harness commands in help
- **WHEN** `onetool --help` is executed
- **THEN** `claude` and `codex` SHALL appear under a labelled harness/code panel
- **AND** existing Runtime, Direct, Configuration, and Knowledge Base groups SHALL
  remain available

#### Scenario: Claude command help
- **WHEN** `onetool claude --help` is executed
- **THEN** it SHALL document the optional model, permission, config, dry-run, and
  argument-passthrough behavior
- **AND** it SHALL state that all routes use CLIProxyAPI

#### Scenario: Codex command help
- **WHEN** `onetool codex --help` is executed
- **THEN** it SHALL document the optional model, permission, config, dry-run, and
  argument-passthrough behavior
- **AND** it SHALL state that all routes use CLIProxyAPI

### Requirement: Code management group
The `onetool` CLI SHALL provide a `code` group for interactive selection and
CLIProxyAPI support operations.

#### Scenario: Interactive picker
- **WHEN** `onetool code` is executed in a TTY without a subcommand
- **THEN** it SHALL prompt for harness, compatible model, and permission mode
- **AND** show the resolved proxy route before launch

#### Scenario: Non-TTY picker
- **WHEN** `onetool code` is executed without a subcommand and stdin is not a TTY
- **THEN** it SHALL fail with usage showing the explicit `onetool claude` and
  `onetool codex` forms

#### Scenario: Management commands
- **WHEN** `onetool code --help` is executed
- **THEN** it SHALL list `setup`, `login`, `models`, `status`, `doctor`, `config`,
  and `proxy` operations

#### Scenario: Proxy subgroup
- **WHEN** `onetool code proxy --help` is executed
- **THEN** it SHALL list `start`, `stop`, `restart`, `status`, `models`, and `logs`
- **AND** CLIProxyAPI operations SHALL not be exposed as an ambiguous top-level
  `onetool proxy` group

### Requirement: Harness config path resolution
Harness and code commands SHALL resolve a OneTool configuration deterministically
without changing the explicit config contract of `onetool serve`.

#### Scenario: Explicit config
- **WHEN** `--config` or `-c` is provided to a harness/code command
- **THEN** that path SHALL be used and validated

#### Scenario: Project config
- **WHEN** no explicit config is provided and `.onetool/onetool.yaml` exists under
  the effective current project
- **THEN** that project config SHALL be used

#### Scenario: User config
- **WHEN** no explicit or project config exists and the standard user OneTool
  config exists
- **THEN** the standard user config SHALL be used

#### Scenario: Config not found
- **WHEN** no config can be resolved
- **THEN** the command SHALL fail with the checked locations and an actionable
  `onetool init` command

#### Scenario: Serve remains explicit
- **WHEN** `onetool serve` is executed
- **THEN** its existing explicit runtime configuration requirements SHALL remain
  unchanged

### Requirement: Harness config management commands
The CLI SHALL expose paths and effective configuration without exposing secrets.

#### Scenario: Config path
- **WHEN** `onetool code config path` is executed
- **THEN** it SHALL print the resolved `onetool.yaml` and optional materialised
  harness include path

#### Scenario: Config show
- **WHEN** `onetool code config show` is executed
- **THEN** it SHALL render effective typed harness configuration
- **AND** secret values, generated private config content, OAuth identities, and
  proxy keys SHALL be omitted or redacted

#### Scenario: Setup materialises harness config
- **WHEN** interactive `onetool init` or `onetool code setup` offers optional
  configuration files
- **THEN** users SHALL be able to materialise `harness.yaml` through the normal
  include and backup behavior

### Requirement: CLI errors and exit behavior
Harness/code commands SHALL use actionable, redacted errors and meaningful exit
statuses.

#### Scenario: Validation error
- **WHEN** harness configuration is invalid
- **THEN** the CLI SHALL exit non-zero before proxy mutation or harness launch
- **AND** identify the config path and invalid field

#### Scenario: External command fails
- **WHEN** setup, OAuth, or proxy management delegates to an external command that
  exits unsuccessfully
- **THEN** OneTool SHALL preserve a non-zero outcome and show a bounded diagnostic
- **AND** it SHALL not echo the complete secret-bearing environment

#### Scenario: User cancels interactive selection
- **WHEN** the user cancels the interactive picker
- **THEN** OneTool SHALL exit without starting the proxy or harness and without
  changing config
