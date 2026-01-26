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

### Requirement: Directory Structure

The `.onetool/` directory SHALL use a subdirectory structure to organise files by purpose.

#### Scenario: Standard subdirectories
- **GIVEN** a `.onetool/` directory (global or project)
- **WHEN** the directory structure is created or validated
- **THEN** it SHALL contain these subdirectories:
  - `config/` - YAML configuration files
  - `logs/` - Application log files
  - `stats/` - Statistics data (stats.jsonl)
  - `sessions/` - Browser session state
  - `tools/` - Reserved for installed tool packs

#### Scenario: Config files in config subdirectory
- **GIVEN** config files like `ot-serve.yaml`, `secrets.yaml`, `snippets.yaml`
- **WHEN** they are created or looked up
- **THEN** they SHALL be in the `config/` subdirectory
- **AND** paths like `~/.onetool/config/ot-serve.yaml`

#### Scenario: Logs in logs subdirectory
- **GIVEN** log files are written
- **WHEN** the log directory is resolved
- **THEN** logs SHALL be written to the `logs/` subdirectory
- **AND** paths like `~/.onetool/logs/ot-serve.log`

#### Scenario: Stats in stats subdirectory
- **GIVEN** statistics are persisted
- **WHEN** the stats file is resolved
- **THEN** stats SHALL be written to the `stats/` subdirectory
- **AND** paths like `~/.onetool/stats/stats.jsonl`

### Requirement: Standard Config Resolution

All config loaders SHALL use a standard resolution order with subdirectory support.

#### Scenario: Resolution order
- **GIVEN** a CLI needs to load its config
- **WHEN** no explicit path is provided
- **THEN** it SHALL resolve in order:
  1. Environment variable (e.g., `OT_SERVE_CONFIG`)
  2. `get_effective_cwd() / ".onetool" / "config" / "<cli>.yaml"`
  3. `~/.onetool/config/<cli>.yaml`
  4. Built-in defaults (from bundled configs)

#### Scenario: Project config takes precedence
- **GIVEN** config exists at both `cwd/.onetool/config/ot-serve.yaml` and `~/.onetool/config/ot-serve.yaml`
- **WHEN** the config is resolved
- **THEN** the project config SHALL be used

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
- **AND** config loaded from `/project/.onetool/config/ot-serve.yaml`
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
- **AND** they SHALL be copied without the `-template` suffix to `~/.onetool/config/`

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
- **AND** create `config/`, `logs/`, `stats/`, `sessions/`, `tools/` subdirectories
- **AND** copy YAML configs from global templates to `config/`
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
- **THEN** it SHALL create the directory structure without printing messages

#### Scenario: Force reset
- **GIVEN** `~/.onetool/` already exists with customized files
- **WHEN** `ensure_global_dir(force=True)` is called
- **THEN** it SHALL ensure subdirectories exist
- **AND** overwrite template files in `config/` with fresh copies
- **AND** print reset messages to stderr

#### Scenario: CLI init reset command
- **GIVEN** a user wants to reset their global config
- **WHEN** `ot-serve init reset` is called
- **THEN** it SHALL prompt for each existing file before overwriting (default: Y)
- **AND** offer to create a backup before overwriting (default: Y)
- **AND** backups SHALL be numbered (`file.bak`, `file.bak.1`, `file.bak.2`, etc.)

#### Scenario: CLI init validate command
- **GIVEN** a user wants to validate config and view status
- **WHEN** `ot-serve init validate` is called
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
- **GIVEN** any context
- **WHEN** `get_global_dir()` is called
- **THEN** it SHALL return `~/.onetool/`

