# paths Specification

## Purpose

Defines path resolution for OneTool configuration and working directories. Provides `get_effective_cwd()` for consistent working directory resolution across all CLIs, supporting the `OT_CWD` environment variable for explicit project targeting.
## Requirements
### Requirement: Effective CWD Resolution

The paths module SHALL provide a function to get the effective working directory.

#### Scenario: Default cwd
- **GIVEN** no `OT_CWD` environment variable
- **WHEN** `get_effective_cwd()` is called
- **THEN** it SHALL return `Path.cwd()`

#### Scenario: OT_CWD override
- **GIVEN** `OT_CWD=demo` environment variable
- **WHEN** `get_effective_cwd()` is called
- **THEN** it SHALL return `Path("demo").resolve()`

#### Scenario: Absolute OT_CWD
- **GIVEN** `OT_CWD=/path/to/project` environment variable
- **WHEN** `get_effective_cwd()` is called
- **THEN** it SHALL return `Path("/path/to/project")`

### Requirement: Standard Config Resolution

All config loaders SHALL use a standard resolution order.

#### Scenario: Resolution order
- **GIVEN** a CLI needs to load its config
- **WHEN** no explicit path is provided
- **THEN** it SHALL resolve in order:
  1. Environment variable (e.g., `OT_SERVE_CONFIG`)
  2. `get_effective_cwd() / ".onetool" / "<cli>.yaml"`
  3. `~/.onetool/<cli>.yaml`
  4. Built-in defaults

#### Scenario: Project config takes precedence
- **GIVEN** config exists at both `cwd/.onetool/ot-serve.yaml` and `~/.onetool/ot-serve.yaml`
- **WHEN** the config is resolved
- **THEN** the project config SHALL be used

### Requirement: .env Loading

The `load_env` function SHALL load from `.onetool/` directories as a fallback mechanism.

#### Scenario: .env resolution order
- **GIVEN** the application starts
- **WHEN** `load_env()` is called
- **THEN** it SHALL load `~/.onetool/.env` first
- **AND** then load `get_effective_cwd()/.onetool/.env` to override
- **AND** log a deprecation warning if .env files are found
- **NOTE** secrets.yaml is the preferred mechanism for API keys

#### Scenario: Project .env overrides global
- **GIVEN** `OT_API_KEY=global` in `~/.onetool/.env`
- **AND** `OT_API_KEY=project` in `cwd/.onetool/.env`
- **WHEN** `load_env()` is called
- **THEN** `OT_API_KEY` SHALL equal "project"

#### Scenario: Deprecation warning
- **GIVEN** a `.env` file exists in `~/.onetool/` or `cwd/.onetool/`
- **WHEN** `load_env()` is called
- **THEN** it SHALL log a warning suggesting migration to `secrets.yaml`

---

### Requirement: No Tree Walking

The paths module SHALL NOT walk parent directories to find config files.

#### Scenario: Use explicit cwd
- **GIVEN** a user wants to run from a subdirectory
- **WHEN** they set `OT_CWD=/path/to/project`
- **THEN** all config resolution SHALL use that path
- **AND** no parent directory walking SHALL occur

### Requirement: Config-Relative Path Resolution

The paths module SHALL provide functions for resolving paths relative to a config file.

#### Scenario: Resolve relative path
- **GIVEN** config directory `/project/.onetool/`
- **AND** relative path `../shared/prompts.yaml`
- **WHEN** path is resolved
- **THEN** result SHALL be `/project/shared/prompts.yaml`

#### Scenario: Resolve absolute path
- **GIVEN** any config directory
- **AND** absolute path `/etc/onetool/prompts.yaml`
- **WHEN** path is resolved
- **THEN** result SHALL be `/etc/onetool/prompts.yaml` (unchanged)

#### Scenario: Resolve path with tilde
- **GIVEN** any config directory
- **AND** path `~/prompts.yaml`
- **WHEN** path is resolved
- **THEN** `~` SHALL expand to home directory

#### Scenario: No environment variable expansion in paths
- **GIVEN** any config directory
- **AND** path `${CONFIG_DIR}/prompts.yaml`
- **WHEN** path is resolved
- **THEN** `${CONFIG_DIR}` SHALL NOT be expanded
- **AND** the literal path `${CONFIG_DIR}/prompts.yaml` SHALL be used
- **NOTE** Use `~` for home directory, not `${HOME}`

### Requirement: Project Path Resolution for Tools

The paths module SHALL provide a function for tools to resolve paths relative to the project working directory.

#### Scenario: Resolve relative path from project
- **GIVEN** `OT_CWD=/project`
- **AND** relative path `diagrams/flow.svg`
- **WHEN** path is resolved with `get_project_path("diagrams/flow.svg")`
- **THEN** result SHALL be `/project/diagrams/flow.svg`

#### Scenario: Absolute path unchanged
- **GIVEN** any project directory
- **AND** absolute path `/tmp/output.svg`
- **WHEN** path is resolved with `get_project_path("/tmp/output.svg")`
- **THEN** result SHALL be `/tmp/output.svg` (unchanged)

#### Scenario: Tilde expansion
- **GIVEN** any project directory
- **AND** path `~/diagrams/flow.svg`
- **WHEN** path is resolved with `get_project_path("~/diagrams/flow.svg")`
- **THEN** `~` SHALL expand to home directory

