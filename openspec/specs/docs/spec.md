# docs Specification

## Purpose
TBD - created by archiving change add-project-docs. Update Purpose after archive.
## Requirements
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

### Requirement: README Documentation Section

The README.md SHALL be concise with links to documentation.

#### Scenario: README structure
- **GIVEN** the README.md
- **WHEN** a user reads it
- **THEN** they find: What (1-2 lines), Why (2-3 lines), Quick Install (3 lines), Links

#### Scenario: README length
- **GIVEN** the README.md
- **WHEN** measured
- **THEN** it is under 100 lines

### Requirement: Documentation Landing Page

The project SHALL provide a landing page at `docs/index.md`.

#### Scenario: Navigation structure
- **GIVEN** a user at `docs/index.md`
- **WHEN** they scan the page
- **THEN** they find links organized by: Getting Started, Guides, Reference, Examples, Beta, Extending

#### Scenario: Section descriptions
- **GIVEN** each section link
- **WHEN** the user reads it
- **THEN** they understand what content that section contains

### Requirement: Tools Reference

The project SHALL document all tools at `docs/reference/tools/`.

#### Scenario: Tool index
- **GIVEN** a user at `reference/tools/index.md`
- **WHEN** they scan the page
- **THEN** they find a table of all namespaces with links to individual docs

#### Scenario: Individual tool docs
- **GIVEN** each tool namespace
- **WHEN** the user reads its doc
- **THEN** they find: purpose, functions, parameters, and examples

#### Scenario: ot namespace documented
- **GIVEN** the `ot.*` namespace
- **WHEN** a user reads `reference/tools/ot.md`
- **THEN** they find docs for ot.tools, ot.push, ot.config

### Requirement: How-to Guides

The project SHALL provide task-oriented guides at `docs/guides/`.

#### Scenario: Explicit calls guide
- **GIVEN** a user wanting to understand explicit invocation
- **WHEN** they read `guides/explicit-calls.md`
- **THEN** they learn how to use the `__ot` prefix

#### Scenario: Prompting guide
- **GIVEN** a user optimizing their prompts
- **WHEN** they read `guides/prompting-best-practices.md`
- **THEN** they find patterns, anti-patterns, and snippet usage

#### Scenario: Database queries guide
- **GIVEN** a user working with databases
- **WHEN** they read `guides/database-queries.md`
- **THEN** they find db.* workflow examples and best practices

### Requirement: Examples Section

The project SHALL provide examples at `docs/examples/`.

#### Scenario: Examples index
- **GIVEN** a user at `examples/index.md`
- **WHEN** they scan the page
- **THEN** they find recipes organized by category: web, code, data

#### Scenario: Recipe format
- **GIVEN** an example recipe
- **WHEN** the user reads it
- **THEN** they find: goal, code snippet, expected output

### Requirement: Beta Features Documentation

The project SHALL document experimental features at `docs/beta/`.

#### Scenario: Beta index
- **GIVEN** a user at `beta/index.md`
- **WHEN** they read it
- **THEN** they see a stability warning and list of beta features

#### Scenario: Beta feature docs
- **GIVEN** a beta feature (ot-browse, page-view, browser-inspector)
- **WHEN** the user reads its doc
- **THEN** they find minimal docs with explicit "may change" warnings

### Requirement: Developer Documentation

The project SHALL provide developer docs at `docs/extending/`.

#### Scenario: Contributing overview
- **GIVEN** a contributor at `extending/index.md`
- **WHEN** they read it
- **THEN** they find how to: create tools, create CLIs, run tests

#### Scenario: Tool creation guide
- **GIVEN** a developer creating a new tool
- **WHEN** they read `extending/creating-tools.md`
- **THEN** they find the full guide from ot-tools.md

#### Scenario: Testing and logging
- **GIVEN** a developer debugging
- **WHEN** they look for help
- **THEN** they find testing.md and logging.md in extending/

### Requirement: Directory Index Files

Every documentation directory SHALL have an index.md file.

#### Scenario: All directories indexed
- **GIVEN** a documentation directory
- **WHEN** checked
- **THEN** it contains an index.md

#### Scenario: Index content
- **GIVEN** an index.md
- **WHEN** read
- **THEN** it describes the section and links to its contents

