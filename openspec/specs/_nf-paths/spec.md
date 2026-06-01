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
- **WHEN** `onetool` starts
- **THEN** it SHALL call `ensure_global_dir()` to bootstrap the global directory
- **AND** the global directory SHALL be seeded from global templates (not bundled defaults)

#### Scenario: Secondary CLIs require global config
- **GIVEN** `~/.onetool/` does not exist
- **WHEN** `bench` starts
- **THEN** it SHALL print an error message directing the user to run `onetool init`
- **AND** exit with non-zero status

### Requirement: Directory Structure

The active OneTool config directory SHALL use a subdirectory structure to organise files by purpose.

#### Scenario: Standard subdirectories
- **GIVEN** an active OneTool config directory
- **WHEN** the directory structure is created or validated
- **THEN** it SHALL contain these subdirectories:
  - `tools/` - Custom tool packs
  - `runtime/` - Logs, stats, sessions, and reports
  - `data/` - Tool-owned config-scoped data stores
  - `templates/` - Editable template overrides

#### Scenario: Config files at config root
- **GIVEN** config files like `onetool.yaml`, `secrets.yaml`, `snippets.yaml`
- **WHEN** they are created or looked up
- **THEN** they SHALL be in the active config directory

#### Scenario: Logs in runtime logs subdirectory
- **GIVEN** log files are written
- **WHEN** the log directory is resolved
- **THEN** logs SHALL be written to the `runtime/logs/` subdirectory

#### Scenario: Stats in runtime stats subdirectory
- **GIVEN** statistics are persisted
- **WHEN** the stats file is resolved
- **THEN** stats SHALL be written to the `runtime/stats/` subdirectory

### Requirement: Standard Config Resolution

Config loaders SHALL use an explicit config-file model with flat config directories.

#### Scenario: Resolution order
- **GIVEN** a CLI needs to load its config
- **WHEN** no explicit path is provided
- **THEN** it SHALL resolve in order:
  1. Environment variable (e.g., `ONETOOL_CONFIG`)
  2. CLI argument such as `--config`
  3. User-selected default such as `~/.onetool/<cli>.yaml`
  4. Built-in defaults only where the loader explicitly supports packaged defaults

#### Scenario: Config directory is the config file parent
- **GIVEN** config is loaded from `/project/.onetool/onetool.yaml`
- **WHEN** relative OT_DIR paths are resolved
- **THEN** they SHALL resolve relative to `/project/.onetool/`

#### Scenario: Bundled fallback when no config exists
- **GIVEN** no config exists in project or global directories
- **WHEN** the config is resolved
- **THEN** bundled defaults from `get_bundled_config_dir()` SHALL be used

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
- **WHEN** path is resolved with `resolve_cwd_path("diagrams/flow.svg")`
- **THEN** result SHALL be `/project/diagrams/flow.svg`

#### Scenario: Absolute path unchanged
- **GIVEN** any project directory
- **AND** absolute path `/tmp/output.svg`
- **WHEN** path is resolved with `resolve_cwd_path("/tmp/output.svg")`
- **THEN** result SHALL be `/tmp/output.svg` (unchanged)

#### Scenario: Tilde expansion
- **GIVEN** any project directory
- **AND** path `~/diagrams/flow.svg`
- **WHEN** path is resolved with `resolve_cwd_path("~/diagrams/flow.svg")`
- **THEN** `~` SHALL expand to home directory

#### Scenario: CWD prefix in resolve_cwd_path
- **GIVEN** `OT_CWD=/project`
- **AND** path `CWD/output.txt`
- **WHEN** `resolve_cwd_path("CWD/output.txt")` is called
- **THEN** result SHALL be `/project/output.txt`

### Requirement: Path Prefixes

SDK path functions SHALL support prefixes to override the default base.

#### Scenario: CWD prefix
- **GIVEN** path `CWD/output.txt`
- **WHEN** resolved with any SDK path function (even `resolve_ot_path`)
- **THEN** the path SHALL resolve relative to the project working directory

#### Scenario: GLOBAL prefix
- **GIVEN** path `GLOBAL/logs/app.log`
- **WHEN** resolved with any SDK path function
- **THEN** the path SHALL resolve relative to `~/.onetool/`

#### Scenario: OT_DIR prefix
- **GIVEN** path `OT_DIR/templates/flow.mmd`
- **WHEN** resolved with any SDK path function (even `resolve_cwd_path`)
- **THEN** the path SHALL resolve relative to the active .onetool directory

### Requirement: tools_dir Resolution

The `tools_dir` configuration SHALL resolve relative paths against OT_DIR.

#### Scenario: Relative tools_dir pattern
- **GIVEN** config with `tools_dir: ["tools/*.py"]`
- **AND** config loaded from `/project/.onetool/onetool.yaml`
- **WHEN** tool files are discovered
- **THEN** the pattern SHALL resolve to `/project/.onetool/tools/*.py`

#### Scenario: Absolute tools_dir pattern
- **GIVEN** config with `tools_dir: ["/opt/tools/*.py"]`
- **WHEN** tool files are discovered
- **THEN** the pattern SHALL be used as-is

### Requirement: Bundled Config Directory

The paths module SHALL provide access to bundled default configuration files.

#### Scenario: Get bundled config directory
- **GIVEN** OneTool is installed as a package
- **WHEN** `get_bundled_config_dir()` is called
- **THEN** it SHALL return the path to `ot/config/global_templates/` within the installed package
- **AND** the path SHALL be accessible via `importlib.resources`

#### Scenario: Bundled directory contents
- **GIVEN** the bundled config directory exists
- **WHEN** its contents are listed
- **THEN** it SHALL contain:
  - `onetool.yaml`, `bench.yaml` (minimal working configs)
  - `prompts.yaml`, `snippets.yaml`, `servers.yaml`, `diagram.yaml`
  - `arch-templates/` and `diagram-templates/` packaged resource subdirectories
- **NOTE** `secrets.yaml` is NOT in bundled defaults; it is in global templates only

#### Scenario: Bundled configs in development mode
- **GIVEN** OneTool is installed in editable mode (`uv tool install -e .`)
- **WHEN** `get_bundled_config_dir()` is called
- **THEN** it SHALL return the path to `src/ot/config/global_templates/`
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
  - `onetool.yaml` (commented template with all options)
  - `snippets.yaml` (example snippets as comments)
  - `servers.yaml` (supported browser MCP integration templates)
  - `secrets-template.yaml` (API key placeholders, copied as `secrets.yaml`)
  - `bench.yaml` (bench config template)
  - `bench-secrets-template.yaml` (bench secrets, copied as `bench-secrets.yaml`)

#### Scenario: Template files avoid gitignore
- **GIVEN** secrets files are gitignored (`**/secrets.yaml`)
- **WHEN** templates are packaged
- **THEN** secrets templates SHALL be named `*-template.yaml`
- **AND** they SHALL be copied without the `-template` suffix to the active config directory root

### Requirement: Template File Discovery

The paths module SHALL provide a function to list template files.

#### Scenario: Get template files
- **GIVEN** global templates directory exists
- **WHEN** `get_template_files()` is called
- **THEN** it SHALL return a list of (source_path, dest_name) tuples
- **AND** dest_name SHALL have `-template` suffix stripped

### Requirement: File Backup

The paths module SHALL provide a function to create numbered backups.

#### Scenario: First backup
- **GIVEN** file `secrets.yaml` exists
- **WHEN** `create_backup(Path("secrets.yaml"))` is called
- **THEN** it SHALL create `secrets.yaml.bak`

#### Scenario: Subsequent backups
- **GIVEN** `secrets.yaml` and `secrets.yaml.bak` exist
- **WHEN** `create_backup(Path("secrets.yaml"))` is called
- **THEN** it SHALL create `secrets.yaml.bak.1`

#### Scenario: Numbered backup sequence
- **GIVEN** `secrets.yaml.bak` through `secrets.yaml.bak.5` exist
- **WHEN** `create_backup(Path("secrets.yaml"))` is called
- **THEN** it SHALL create `secrets.yaml.bak.6`

### Requirement: Global Directory Bootstrap

The `ensure_global_dir` function SHALL seed from global templates into the `config/` subdirectory.

#### Scenario: First run bootstrap
- **GIVEN** `~/.onetool/` does not exist
- **WHEN** `ensure_global_dir()` is called
- **THEN** it SHALL create `~/.onetool/`
- **AND** create the `tools/` subdirectory
- **AND** copy YAML configs from global templates to the config directory root
- **AND** rename `*-template.yaml` files to remove the suffix (e.g., `secrets-template.yaml` → `secrets.yaml`)
- **AND** copy only explicit editable template directories to `templates/arch/` and `templates/diagram/`
- **AND** NOT copy package-only resource directories such as `skills/`, `tool_templates/`, or `__pycache__/`
- **AND** print creation messages to stderr

#### Scenario: Subsequent runs no-op
- **GIVEN** `~/.onetool/` already exists
- **WHEN** `ensure_global_dir()` is called
- **THEN** it SHALL return the existing path without modifications

#### Scenario: Quiet mode
- **GIVEN** `~/.onetool/` does not exist
- **WHEN** `ensure_global_dir(quiet=True)` is called
- **THEN** it SHALL create the directory structure without printing messages

#### Scenario: Force reset
- **GIVEN** `~/.onetool/` already exists with customized files
- **WHEN** `ensure_global_dir(force=True)` is called
- **THEN** it SHALL ensure subdirectories exist
- **AND** overwrite template files in `config/` with fresh copies
- **AND** print reset messages to stderr

#### Scenario: Re-running init (conflict handling)
- **GIVEN** a user wants to re-initialise a config directory
- **WHEN** `onetool init -c <dir>` is called and files already exist
- **THEN** existing files SHALL be automatically backed up to `file.bak` (incrementing to `.bak1`, `.bak2`, etc.)
- **AND** new files SHALL be written to the original paths

#### Scenario: CLI init validate command
- **GIVEN** a user wants to validate config and view status
- **WHEN** `onetool init validate` is called
- **THEN** it SHALL validate configuration files for syntax errors
- **AND** display (all sorted alphabetically with counts):
  - Global and project directory paths with existence status
  - Packs with total tool counts
  - Secret names (NOT values) with "set" indicator
  - Snippet names
  - Alias mappings
  - MCP server names

### Requirement: SDK Path Prefix Expansion

The SDK paths module SHALL support path prefixes for standardised resolution.

#### Scenario: Tilde prefix expansion
- **GIVEN** a path starting with `~`
- **WHEN** `resolve_path("~/file.txt")` is called
- **THEN** `~` SHALL expand to the user's home directory
- **AND** result SHALL be an absolute Path

#### Scenario: CWD prefix expansion
- **GIVEN** a path starting with `CWD`
- **WHEN** `resolve_path("CWD/file.txt")` is called
- **THEN** `CWD` SHALL expand to the effective working directory (OT_CWD)
- **AND** result SHALL be an absolute Path

#### Scenario: GLOBAL prefix expansion
- **GIVEN** a path starting with `GLOBAL`
- **WHEN** `resolve_path("GLOBAL/logs")` is called
- **THEN** `GLOBAL` SHALL expand to `~/.onetool/`
- **AND** result SHALL be an absolute Path

#### Scenario: OT_DIR prefix expansion
- **GIVEN** a path starting with `OT_DIR`
- **WHEN** `resolve_path("OT_DIR/logs")` is called
- **THEN** `OT_DIR` SHALL expand to the active .onetool directory
- **AND** result SHALL be an absolute Path

#### Scenario: OT_DIR project-first resolution
- **GIVEN** `CWD/.onetool/` exists
- **WHEN** `OT_DIR` prefix is expanded
- **THEN** it SHALL resolve to `CWD/.onetool/`

#### Scenario: OT_DIR global fallback
- **GIVEN** `CWD/.onetool/` does NOT exist
- **WHEN** `OT_DIR` prefix is expanded
- **THEN** it SHALL resolve to `~/.onetool/`

#### Scenario: Relative path with default base
- **GIVEN** a relative path without prefix
- **WHEN** `resolve_path("file.txt")` is called with default base
- **THEN** it SHALL resolve relative to CWD
- **AND** result SHALL be an absolute Path

#### Scenario: Relative path with OT_DIR base
- **GIVEN** a relative path without prefix
- **WHEN** `resolve_path("logs/app.log", base="OT_DIR")` is called
- **THEN** it SHALL resolve relative to OT_DIR
- **AND** result SHALL be an absolute Path

#### Scenario: Absolute path unchanged
- **GIVEN** an absolute path
- **WHEN** `resolve_path("/etc/config.yaml")` is called
- **THEN** it SHALL return the path unchanged

### Requirement: SDK Path Convenience Functions

The SDK paths module SHALL provide convenience wrappers for common resolution patterns.

#### Scenario: resolve_cwd_path for tool I/O
- **GIVEN** a path for tool input/output
- **WHEN** `resolve_cwd_path("output.txt")` is called
- **THEN** it SHALL be equivalent to `resolve_path("output.txt", base="CWD")`

#### Scenario: get_project_state_dir for project-local state
- **GIVEN** project-local runtime state belongs under the effective project working directory
- **WHEN** `otpack` resolves the default state file path
- **THEN** it SHALL use `get_project_state_dir(pack) / "state.yaml"`

#### Scenario: Project-local state is pack-owned
- **WHEN** `otpack` writes project-local state for pack `bridge`
- **THEN** it SHALL write under `{CWD}/.onetool/state/bridge/`
- **AND** it SHALL NOT read `{CWD}/.onetool/state.yaml` as a fallback

#### Scenario: resolve_ot_path for config assets
- **GIVEN** a path for config or logs
- **WHEN** `resolve_ot_path("logs/app.log")` is called
- **THEN** it SHALL be equivalent to `resolve_path("logs/app.log", base="OT_DIR")`

### Requirement: SDK Directory Getters

The SDK paths module SHALL provide functions to get directory paths.

#### Scenario: get_ot_dir returns active directory
- **GIVEN** `CWD/.onetool/` exists
- **WHEN** `get_ot_dir()` is called
- **THEN** it SHALL return `CWD/.onetool/`

#### Scenario: get_ot_dir fallback to global
- **GIVEN** `CWD/.onetool/` does NOT exist
- **WHEN** `get_ot_dir()` is called
- **THEN** it SHALL return `~/.onetool/`

#### Scenario: get_global_dir returns global
- **GIVEN** no override
- **WHEN** `get_global_dir()` is called
- **THEN** it SHALL return `~/.onetool/`
