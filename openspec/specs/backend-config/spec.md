# backend-config Specification

## Purpose
TBD - created by archiving change add-onetool-common. Update Purpose after archive.
## Requirements
### Requirement: Backend Configuration Convention
Backend servers SHALL use the shared `~/.onetool/` directory for configuration, with short config file names (e.g., `xero.yaml`, `dev.yaml`, `util.yaml`) and a standard `--config` CLI flag.

#### Scenario: Default config path
- **WHEN** `onetool-xero` is started without `--config`
- **THEN** it loads config from `~/.onetool/xero.yaml`

#### Scenario: Custom config path
- **WHEN** `onetool-xero --config /custom/path/xero.yaml` is started
- **THEN** it loads config from the specified path

#### Scenario: Config referenced from frontend
- **WHEN** `onetool.yaml` references a backend with `args: ["onetool-xero", "--config", "~/.onetool/xero.yaml"]`
- **THEN** the backend receives and uses the specified config path

### Requirement: Backend Logging Convention
Backend servers SHALL manage their own logging independently, using `onetool-common` logging helpers for consistent format, with logs written to `~/.onetool/logs/{backend-name}.log`.

#### Scenario: Default log location
- **WHEN** `onetool-xero` starts with default config
- **THEN** logs are written to `~/.onetool/logs/onetool-xero.log` with 10MB rotation

#### Scenario: Backend log independence
- **WHEN** multiple backends are running (onetool-xero, onetool-util)
- **THEN** each writes to its own log file with no shared state or aggregation

### Requirement: Backend Package Structure
Backend server packages SHALL follow a standard structure with `src/` layout, FastMCP server entry point, Typer CLI, and tool modules.

#### Scenario: Standard project layout
- **WHEN** a new backend `onetool-xero` is structured
- **THEN** it has `src/onetool_xero/server.py` (FastMCP), `src/onetool_xero/cli.py` (Typer), and tool modules under `src/onetool_xero/tools/`

#### Scenario: PyPI entry point
- **WHEN** `onetool-xero` is installed via pip/uvx
- **THEN** the `onetool-xero` command is available and starts the MCP server via stdio transport

### Requirement: Reference Project Template
The `onetool-common` package SHALL include a `template/` directory containing a reference project structure with placeholder files for scaffolding new backend server projects.

#### Scenario: Template contains standard project files
- **WHEN** a developer inspects `onetool-common/template/`
- **THEN** it contains `pyproject.toml`, `justfile`, `CLAUDE.md`, `README.md`, `.gitignore`, `.mcp.json`, `dev/agents/hints.md`, `openspec/project.md`, `src/{package}/server.py`, `src/{package}/cli.py`, and `tests/conftest.py`

#### Scenario: Template uses simple placeholders
- **WHEN** template files reference the project name
- **THEN** they use `{name}` (PyPI name), `{package}` (Python package), and `{description}` (one-line) placeholders that can be search-replaced

#### Scenario: Template produces working project
- **WHEN** template files are copied and placeholders replaced with actual values
- **THEN** `just check` (lint + typecheck + test) passes on the resulting project

### Requirement: onetool-xero Migration to onetool-common
The `onetool-xero` package SHALL be refactored to depend on `onetool-common` for config loading, logging, and path resolution, replacing its inline `ox.config`, `ox.logging`, and `ox.paths` modules.

#### Scenario: Config loading via common
- **WHEN** onetool-xero loads its configuration
- **THEN** it uses `onetool_common.config.load_config()` with its own `OneXeroConfig` Pydantic model

#### Scenario: Logging via common
- **WHEN** onetool-xero initialises logging
- **THEN** it uses `onetool_common.logging.configure_logging(name="onetool-xero")`

#### Scenario: Path resolution via common
- **WHEN** onetool-xero resolves its global directory
- **THEN** it uses `onetool_common.paths.get_global_dir()` returning `~/.onetool/`

#### Scenario: Existing tests pass
- **WHEN** onetool-xero is refactored to use onetool-common
- **THEN** all existing tests pass without modification to test assertions

#### Scenario: tool_wrapper from common
- **WHEN** onetool-xero registers tools in server.py
- **THEN** it imports `tool_wrapper` from `onetool_common.tools` instead of `ox.server`

