# bench-tui Specification

## Purpose

Defines the TUI favorites mode and harness configuration file for ot-bench.

---

## Requirements

### Requirement: TUI Favorites Mode

The harness CLI SHALL support an interactive TUI mode for selecting benchmark files from favorites.

#### Scenario: Launch TUI mode

- **WHEN** user runs `ot-bench run --tui`
- **THEN** an interactive picker displays configured favorites
- **AND** user can select a benchmark to run

#### Scenario: Favorite file selection

- **GIVEN** a favorite with `path` pointing to a YAML file
- **WHEN** user selects that favorite
- **THEN** the benchmark runs with that file

#### Scenario: Favorite directory selection

- **GIVEN** a favorite with `path` pointing to a directory
- **WHEN** user selects that favorite
- **THEN** a sub-picker displays all YAML files in that directory
- **AND** user can select a specific file to run

#### Scenario: Directory scanning rules

- **GIVEN** a favorite directory is selected
- **WHEN** scanning for files
- **THEN** it recursively finds `*.yaml` and `*.yml` files
- **AND** excludes hidden directories (`.git`, `.venv`, etc.)
- **AND** displays relative paths in the picker

#### Scenario: Description from file metadata

- **GIVEN** a YAML benchmark file with a `description` field
- **WHEN** displaying in the picker
- **THEN** the description is shown alongside the name

#### Scenario: No favorites configured

- **GIVEN** no favorites in ot-bench.yaml
- **WHEN** user runs `ot-bench run --tui`
- **THEN** a message indicates no favorites are configured

### Requirement: Harness Configuration File

The harness CLI SHALL support a configuration file for CLI settings including favorites.

#### Scenario: Config file location

- **WHEN** no config path specified
- **THEN** looks for ot-bench.yaml in `config/` directory
- **OR** uses OT_BENCH_CONFIG environment variable

#### Scenario: Favorites configuration

- **GIVEN** a config file with favorites
- **WHEN** the CLI loads configuration
- **THEN** each favorite has:
  - `name`: Display name in picker (required)
  - `path`: File path or directory (required)

#### Scenario: Favorites config format

- **GIVEN** ot-bench.yaml
- **WHEN** favorites are defined
- **THEN** favorites are specified as:

  ```yaml
  favorites:
    - name: features
      path: demo/bench/features.yaml
    - name: all-bench
      path: demo/bench/
  ```
