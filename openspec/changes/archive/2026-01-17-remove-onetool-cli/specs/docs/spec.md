# docs Spec Delta

## MODIFIED Requirements

### Requirement: Getting Started Documentation

The project SHALL provide getting started documentation in `docs/getting-started/`.

#### Scenario: Quickstart guide
- **GIVEN** a new user
- **WHEN** they read `getting-started/quickstart.md`
- **THEN** they can install with `uv tool install onetool-mcp`
- **AND** they can make their first tool call within 2 minutes

#### Scenario: Detailed installation
- **GIVEN** a user needing platform-specific setup
- **WHEN** they read `getting-started/installation.md`
- **THEN** they find instructions for `uv tool install` and `pip install`
- **AND** they find MCP configuration examples

#### Scenario: Configuration reference
- **GIVEN** a user configuring OneTool
- **WHEN** they read `getting-started/configuration.md`
- **THEN** they find all config options documented

### Requirement: CLI Reference Documentation

The project SHALL provide CLI reference at `docs/reference/cli/`.

#### Scenario: CLI overview
- **GIVEN** a user looking for CLI help
- **WHEN** they read `reference/cli/index.md`
- **THEN** they find documentation for `ot-serve` and `ot-bench`

#### Scenario: Individual CLI docs
- **GIVEN** a specific CLI (ot-serve, ot-bench)
- **WHEN** the user reads its doc
- **THEN** they find commands, options, and examples

#### Scenario: Beta CLIs separated
- **GIVEN** experimental CLIs (ot-browse)
- **WHEN** a user looks for them
- **THEN** they find them in `docs/beta/` with stability warnings
