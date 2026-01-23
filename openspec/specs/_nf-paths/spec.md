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

#### Scenario: CLI bootstrap on first run
- **GIVEN** `~/.onetool/` does not exist
- **WHEN** `ot-serve` starts
- **THEN** it SHALL call `ensure_global_dir()` to bootstrap the global directory
- **AND** the global directory SHALL be seeded from global templates (not bundled defaults)

#### Scenario: Secondary CLIs require global config
- **GIVEN** `~/.onetool/` does not exist
- **WHEN** `ot-bench` or `ot-browse` starts
- **THEN** it SHALL print an error message directing the user to run `ot-serve init`
- **AND** exit with non-zero status

### Requirement: Standard Config Resolution

All config loaders SHALL use a standard resolution order.

#### Scenario: Resolution order
- **GIVEN** a CLI needs to load its config
- **WHEN** no explicit path is provided
- **THEN** it SHALL resolve in order:
  1. Environment variable (e.g., `OT_SERVE_CONFIG`)
  2. `get_effective_cwd() / ".onetool" / "<cli>.yaml"`
  3. `~/.onetool/<cli>.yaml`
  4. Built-in defaults (from bundled configs)

#### Scenario: Project config takes precedence
- **GIVEN** config exists at both `cwd/.onetool/ot-serve.yaml` and `~/.onetool/ot-serve.yaml`
- **WHEN** the config is resolved
- **THEN** the project config SHALL be used

#### Scenario: Bundled fallback when no config exists
- **GIVEN** no config exists in project or global directories
- **WHEN** the config is resolved
- **THEN** bundled defaults from `get_bundled_config_dir()` SHALL be used

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

### Requirement: Bundled Config Directory

The paths module SHALL provide access to bundled default configuration files.

#### Scenario: Get bundled config directory
- **GIVEN** OneTool is installed as a package
- **WHEN** `get_bundled_config_dir()` is called
- **THEN** it SHALL return the path to `ot/config/defaults/` within the installed package
- **AND** the path SHALL be accessible via `importlib.resources`

#### Scenario: Bundled directory contents
- **GIVEN** the bundled config directory exists
- **WHEN** its contents are listed
- **THEN** it SHALL contain:
  - `ot-serve.yaml`, `ot-bench.yaml`, `ot-browse.yaml` (minimal working configs)
  - `prompts.yaml`, `snippets.yaml`, `servers.yaml`, `diagram.yaml`
  - `diagram-templates/` subdirectory
- **NOTE** `secrets.yaml` is NOT in bundled defaults; it is in global templates only

#### Scenario: Bundled configs in development mode
- **GIVEN** OneTool is installed in editable mode (`uv tool install -e .`)
- **WHEN** `get_bundled_config_dir()` is called
- **THEN** it SHALL return the path to `src/ot/config/defaults/`
- **AND** the configs SHALL be usable without rebuilding

### Requirement: Global Templates Directory

The paths module SHALL provide access to global template configuration files for user customization.

#### Scenario: Get global templates directory
- **GIVEN** OneTool is installed as a package
- **WHEN** `get_global_templates_dir()` is called
- **THEN** it SHALL return the path to `ot/config/global_templates/` within the installed package
- **AND** the path SHALL be accessible via `importlib.resources`

#### Scenario: Global templates directory contents
- **GIVEN** the global templates directory exists
- **WHEN** its contents are listed
- **THEN** it SHALL contain:
  - `ot-serve.yaml` (commented template with all options)
  - `snippets.yaml` (example snippets as comments)
  - `servers.yaml` (example MCP server configs as comments)
  - `secrets-template.yaml` (API key placeholders, copied as `secrets.yaml`)
  - `ot-bench.yaml` (bench config template)
  - `bench-secrets-template.yaml` (bench secrets, copied as `bench-secrets.yaml`)

#### Scenario: Template files avoid gitignore
- **GIVEN** secrets files are gitignored (`**/secrets.yaml`)
- **WHEN** templates are packaged
- **THEN** secrets templates SHALL be named `*-template.yaml`
- **AND** they SHALL be copied without the `-template` suffix to `~/.onetool/`

### Requirement: Global Directory Bootstrap

The `ensure_global_dir` function SHALL seed from global templates (not bundled defaults).

#### Scenario: First run bootstrap
- **GIVEN** `~/.onetool/` does not exist
- **WHEN** `ensure_global_dir()` is called
- **THEN** it SHALL create `~/.onetool/`
- **AND** copy YAML configs from global templates
- **AND** rename `*-template.yaml` files to remove the suffix (e.g., `secrets-template.yaml` → `secrets.yaml`)
- **AND** NOT copy subdirectories (diagram-templates stays in bundled defaults)
- **AND** print creation messages to stderr

#### Scenario: Subsequent runs no-op
- **GIVEN** `~/.onetool/` already exists
- **WHEN** `ensure_global_dir()` is called
- **THEN** it SHALL return the existing path without modifications

#### Scenario: Quiet mode
- **GIVEN** `~/.onetool/` does not exist
- **WHEN** `ensure_global_dir(quiet=True)` is called
- **THEN** it SHALL create the directory without printing messages

#### Scenario: Force reset
- **GIVEN** `~/.onetool/` already exists with customized files
- **WHEN** `ensure_global_dir(force=True)` is called
- **THEN** it SHALL overwrite all template files with fresh copies
- **AND** print reset messages to stderr

#### Scenario: CLI init reset command
- **GIVEN** a user wants to reset their global config
- **WHEN** `ot-serve init reset` is called
- **THEN** it SHALL prompt for confirmation
- **AND** call `ensure_global_dir(force=True)` if confirmed

