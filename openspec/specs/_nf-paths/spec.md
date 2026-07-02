# _nf-paths Specification

## Purpose

Defines product-level path, storage, and workspace boundary requirements for
OneTool. These requirements describe where user-visible configuration, runtime
state, generated files, and tool-owned data live, and how user-supplied paths are
resolved.

## Requirements

### Requirement: Explicit Project Working Directory

OneTool SHALL support an explicit effective project working directory for
project-relative operations.

#### Scenario: Default project directory
- **GIVEN** no project working directory override is set
- **WHEN** a tool resolves a project-relative path
- **THEN** the path SHALL resolve relative to the current process working directory

#### Scenario: Environment project directory
- **GIVEN** the user sets `OT_CWD` to a project path
- **WHEN** a tool resolves a project-relative path
- **THEN** the path SHALL resolve relative to that project path

#### Scenario: No parent walking
- **GIVEN** a command runs inside a nested directory
- **WHEN** OneTool resolves project or config paths
- **THEN** it SHALL NOT search parent directories for implicit config files

### Requirement: Active OneTool Directory

OneTool SHALL keep active configuration and config-scoped runtime data under a
known `.onetool` directory selected by config path, explicit option, or the
global default.

#### Scenario: Config file parent
- **GIVEN** config is loaded from `/project/.onetool/onetool.yaml`
- **WHEN** config-relative paths are resolved
- **THEN** they SHALL resolve relative to `/project/.onetool`

#### Scenario: Global default
- **GIVEN** no project-specific OneTool directory is selected
- **WHEN** OneTool uses the global default
- **THEN** config and config-scoped runtime data SHALL live under `~/.onetool`

### Requirement: Directory Ownership

The active OneTool directory SHALL separate user configuration, runtime
artifacts, tool-owned data, editable templates, and custom tools.

#### Scenario: Standard directories
- **GIVEN** an active OneTool directory is initialized
- **WHEN** files are materialized
- **THEN** custom tools SHALL live under `tools/`
- **AND** logs, stats, sessions, and reports SHALL live under `runtime/`
- **AND** tool-owned config-scoped data stores SHALL live under `data/`
- **AND** editable templates SHALL live under `templates/`

#### Scenario: Config root files
- **GIVEN** root config files such as `onetool.yaml`, `secrets.yaml`, or included YAML files are materialized
- **WHEN** they are written by supported initialization flows
- **THEN** they SHALL be placed at the active OneTool directory root unless a command explicitly targets another path

### Requirement: User Path Resolution

OneTool SHALL resolve user-supplied paths predictably.

#### Scenario: Relative project path
- **GIVEN** a tool accepts a project file path such as `docs/report.md`
- **WHEN** the path is resolved for project I/O
- **THEN** it SHALL resolve relative to the effective project working directory

#### Scenario: Relative config path
- **GIVEN** a config field accepts a config-scoped path such as `runtime/logs`
- **WHEN** the path is resolved
- **THEN** it SHALL resolve relative to the active OneTool directory

#### Scenario: Absolute path
- **GIVEN** a user supplies an absolute path
- **WHEN** OneTool resolves it
- **THEN** the absolute path SHALL be used as-is

#### Scenario: Home path
- **GIVEN** a user supplies a path beginning with `~`
- **WHEN** OneTool resolves it
- **THEN** `~` SHALL expand to the user's home directory

#### Scenario: Environment variables in path strings
- **GIVEN** a path string contains `${VAR}`
- **WHEN** the path is resolved as a path
- **THEN** `${VAR}` SHALL NOT be expanded unless the specific feature explicitly documents runtime variable expansion

### Requirement: Project-Local State Ownership

Tool state that is intended to follow a project SHALL live under the effective
project directory, not under global config-scoped storage.

#### Scenario: Project-local tool state
- **GIVEN** a tool stores project-local state for a project
- **WHEN** state is written
- **THEN** it SHALL be written under `{CWD}/.onetool/state/<pack>/`

#### Scenario: No legacy project state fallback
- **GIVEN** project-local state exists only in an unsupported legacy location
- **WHEN** current tool state is read
- **THEN** OneTool SHALL NOT silently read that legacy location as a fallback

### Requirement: Initialization And Backup Safety

Initialization flows SHALL avoid destructive overwrites of user-owned
configuration.

#### Scenario: First initialization
- **GIVEN** the target OneTool directory does not exist
- **WHEN** initialization runs
- **THEN** the supported directory structure SHALL be created
- **AND** editable template config files SHALL be materialized

#### Scenario: Existing file backup
- **GIVEN** initialization would write a file that already exists
- **WHEN** the file is replaced by a supported initialization flow
- **THEN** the existing file SHALL first be backed up with an incrementing `.bak` suffix

### Requirement: Packaged Template Availability

OneTool SHALL ship the templates needed to initialize and operate the default
configuration.

#### Scenario: Default templates available
- **GIVEN** OneTool is installed
- **WHEN** initialization or include fallback needs packaged templates
- **THEN** default config, prompt, snippet, server, and supported tool template resources SHALL be available from the installed package

#### Scenario: Secret templates are not live secrets
- **GIVEN** packaged template resources include secret placeholders
- **WHEN** they are materialized for user editing
- **THEN** they SHALL be template files or copied placeholders, not real secret values
