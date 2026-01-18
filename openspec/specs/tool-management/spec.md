# tool-management Specification

## Purpose

Defines CLI commands for installing, updating, and managing external tools.
## Requirements
### Requirement: Tool Installation

The system SHALL provide `ot tool add <source>` to install tools from various sources.

#### Scenario: Add from local path
- **WHEN** a user runs `ot tool add ./my_tool/tool.py`
- **THEN** the tool is copied to `~/.onetool/tools/<namespace>/`
- **AND** the tool becomes available for use

#### Scenario: Add from git repository
- **WHEN** a user runs `ot tool add https://github.com/user/ot-excel-tool`
- **THEN** the repository is cloned to `~/.onetool/tools/<namespace>/`
- **AND** the tool becomes available for use

#### Scenario: Add from registry
- **WHEN** a user runs `ot tool add excel`
- **THEN** the tool is fetched from the onetool registry (future)
- **AND** installed to `~/.onetool/tools/<namespace>/`

### Requirement: Tool Removal

The system SHALL provide `ot tool remove <name>` to uninstall tools.

#### Scenario: Remove installed tool
- **WHEN** a user runs `ot tool remove mytool`
- **THEN** the tool is removed from `~/.onetool/tools/`
- **AND** any running worker for that tool is shut down

### Requirement: Tool Update

The system SHALL provide `ot tool update [name]` to update installed tools.

#### Scenario: Update single tool
- **WHEN** a user runs `ot tool update mytool`
- **AND** the tool was installed from git
- **THEN** the latest version is pulled

#### Scenario: Update all tools
- **WHEN** a user runs `ot tool update --all`
- **THEN** all installed tools are updated from their sources

#### Scenario: Update local tool
- **WHEN** a user runs `ot tool update mytool`
- **AND** the tool was installed from a local path
- **THEN** the tool is re-copied from the original source path

### Requirement: Tool Listing

The system SHALL provide `ot tool list` to show installed tools and their status.

#### Scenario: List tools
- **WHEN** a user runs `ot tool list`
- **THEN** a table is displayed with columns: NAME, SOURCE, STATUS
- **AND** status shows "active", "idle", or not running

### Requirement: Tool Information

The system SHALL provide `ot tool info <name>` to show detailed tool information.

#### Scenario: Show tool info
- **WHEN** a user runs `ot tool info brave`
- **THEN** the output shows: functions, dependencies, source location

### Requirement: Tool Testing

The system SHALL provide `ot tool test <name>` to run a tool's test suite.

#### Scenario: Run tool tests
- **WHEN** a user runs `ot tool test mytool`
- **AND** the tool has a tests directory
- **THEN** the tests are executed
- **AND** results are displayed

