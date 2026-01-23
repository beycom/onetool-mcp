## ADDED Requirements

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
  - `ot-serve.yaml`, `ot-bench.yaml`, `ot-browse.yaml`
  - `prompts.yaml`, `snippets.yaml`, `servers.yaml`, `diagram.yaml`
  - `secrets.yaml` (template)
  - `diagram-templates/` subdirectory

#### Scenario: Bundled configs in development mode
- **GIVEN** OneTool is installed in editable mode (`uv tool install -e .`)
- **WHEN** `get_bundled_config_dir()` is called
- **THEN** it SHALL return the path to `src/ot/config/defaults/`
- **AND** the configs SHALL be usable without rebuilding

### Requirement: Global Directory Bootstrap

The `ensure_global_dir` function SHALL seed from bundled package resources.

#### Scenario: First run bootstrap
- **GIVEN** `~/.onetool/` does not exist
- **WHEN** `ensure_global_dir()` is called
- **THEN** it SHALL create `~/.onetool/`
- **AND** copy YAML configs from bundled defaults
- **AND** copy `diagram-templates/` subdirectory
- **AND** print creation messages to stderr

#### Scenario: Subsequent runs no-op
- **GIVEN** `~/.onetool/` already exists
- **WHEN** `ensure_global_dir()` is called
- **THEN** it SHALL return the existing path without modifications

#### Scenario: Quiet mode
- **GIVEN** `~/.onetool/` does not exist
- **WHEN** `ensure_global_dir(quiet=True)` is called
- **THEN** it SHALL create the directory without printing messages

## MODIFIED Requirements

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
- **AND** the global directory SHALL be seeded from bundled defaults

#### Scenario: Secondary CLIs require global config
- **GIVEN** `~/.onetool/` does not exist
- **WHEN** `ot-bench` or `ot-browse` starts
- **THEN** it SHALL print an error message directing the user to run `ot-serve --help`
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
