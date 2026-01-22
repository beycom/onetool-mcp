# onetool CLI Specification

## Purpose

Defines the main `onetool` CLI for configuration management utilities. Provides commands for upgrading config files, checking dependencies, and displaying current configuration.

---

## Requirements

### Requirement: CLI Entry Point

The system SHALL provide a `onetool` CLI command.

#### Scenario: CLI invocation
- **GIVEN** the package is installed
- **WHEN** `onetool` is executed
- **THEN** it SHALL display available subcommands

#### Scenario: Help output
- **GIVEN** `onetool --help` is executed
- **WHEN** help is displayed
- **THEN** it SHALL list all available subcommands with descriptions

---

### Requirement: Config Display

The system SHALL display the current configuration.

#### Scenario: Show merged config
- **GIVEN** `onetool config show` is executed
- **WHEN** configuration files exist
- **THEN** it SHALL display the merged configuration as YAML
- **AND** indicate which values came from which source (default, file, env)

#### Scenario: Show config path
- **GIVEN** `onetool config path` is executed
- **WHEN** executed
- **THEN** it SHALL display the resolved config file path

#### Scenario: Validate config
- **GIVEN** `onetool config validate` is executed
- **WHEN** a config file exists
- **THEN** it SHALL validate the configuration against the schema
- **AND** report any errors or warnings

---

### Requirement: Config Upgrade

The system SHALL support upgrading config files to newer schema versions.

#### Scenario: Upgrade config file
- **GIVEN** `onetool config upgrade` is executed
- **WHEN** an older config version is detected
- **THEN** it SHALL migrate settings to the current schema
- **AND** create a backup of the original file

#### Scenario: Dry run upgrade
- **GIVEN** `onetool config upgrade --dry-run` is executed
- **WHEN** an older config version is detected
- **THEN** it SHALL display what changes would be made
- **AND** NOT modify any files

#### Scenario: No upgrade needed
- **GIVEN** `onetool config upgrade` is executed
- **WHEN** the config is already at the current version
- **THEN** it SHALL report that no upgrade is needed

---

### Requirement: Dependency Check

The system SHALL check tool dependencies and report their status.

#### Scenario: Check all dependencies
- **GIVEN** `onetool check` is executed
- **WHEN** tools have external dependencies
- **THEN** it SHALL check each dependency (ripgrep, playwright, etc.)
- **AND** report status as available, missing, or outdated

#### Scenario: Check specific tool
- **GIVEN** `onetool check --tool ripgrep` is executed
- **WHEN** the tool has dependencies
- **THEN** it SHALL check only that tool's dependencies

#### Scenario: Install missing dependencies
- **GIVEN** `onetool check --install` is executed
- **WHEN** dependencies are missing
- **THEN** it SHALL attempt to install them
- **AND** report success or failure for each

---

### Requirement: Version Information

The system SHALL display version information.

#### Scenario: Show version
- **GIVEN** `onetool version` is executed
- **WHEN** executed
- **THEN** it SHALL display:
  - Package version
  - Python version
  - Installation path

#### Scenario: Version flag
- **GIVEN** `onetool --version` is executed
- **WHEN** executed
- **THEN** it SHALL display the package version
