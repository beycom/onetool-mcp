# serve-skills Specification

## Purpose

Defines the `ot.skills()` API for listing and retrieving bundled skill content at runtime. Skills are Markdown files stored in `global_templates/skills/` and returned on-demand to avoid embedding large reference content in the always-on MCP prompt.

## Requirements

### Requirement: Skills Listing

The system SHALL provide an `ot.skills()` function that lists available bundled skills.

#### Scenario: List all skills
- **WHEN** `ot.skills()` is called with no arguments
- **THEN** it SHALL return a formatted list of all bundled skills
- **AND** each entry SHALL include the skill name and description

#### Scenario: Min info level
- **WHEN** `ot.skills(info="min")` is called
- **THEN** it SHALL return skill names only

#### Scenario: Default info level
- **WHEN** `ot.skills(info="default")` is called
- **THEN** it SHALL return skill name and description for each entry

#### Scenario: Filter by pattern
- **WHEN** `ot.skills(pattern="devtools")` is called
- **THEN** it SHALL return only skills whose name contains "devtools"

#### Scenario: Full info level
- **WHEN** `ot.skills(info="full")` is called
- **THEN** it SHALL return name, description, tags, and source path for each skill

#### Scenario: Invalid info level
- **WHEN** `ot.skills(info="list")` is called
- **THEN** it SHALL raise a ValueError indicating valid levels are `min`, `default`, and `full`

#### Scenario: No skills match pattern
- **WHEN** `ot.skills(pattern="nonexistent")` is called
- **THEN** it SHALL return a message indicating no skills matched

### Requirement: Skill Content Retrieval

The system SHALL return the full body of a named skill via `ot.skills(name=...)`.

#### Scenario: Retrieve bundled skill
- **WHEN** `ot.skills(name="ot-ref")` is called
- **THEN** it SHALL return the full Markdown body of the skill (below the frontmatter)
- **AND** the body SHALL reflect the currently running server version

#### Scenario: Unknown skill name
- **WHEN** `ot.skills(name="does-not-exist")` is called
- **THEN** it SHALL return an error message listing available skill names

#### Scenario: Bundled skill content location
- **WHEN** a bundled skill is requested
- **THEN** it SHALL be read from `global_templates/skills/<name>.md`
- **AND** frontmatter (between `---` markers) SHALL be parsed and excluded from the returned body

### Requirement: Bundled Skill Set

The system SHALL bundle an initial set of skills for on-demand discovery and server guides.

#### Scenario: ot-ref skill bundled
- **WHEN** `ot.skills()` is called
- **THEN** `ot-ref` SHALL be listed

#### Scenario: ot-ref direct run discoverability
- **WHEN** bundled `ot-ref` frontmatter is parsed
- **THEN** its description SHALL include trigger terms for `__run`, MCP `run`, direct pack calls, and run-vs-local-script decisions

#### Scenario: ot-ref advanced reference scope
- **WHEN** `ot.skills(name="ot-ref")` is called
- **THEN** the returned body SHALL include advanced recovery, proxy handling, security, output, and ctx guidance
- **AND** it SHALL open with guidance that it applies when a OneTool `__run`/MCP run request needs advanced recovery or decision-boundary help
- **AND** it SHALL include parameter prefix matching and readable discovery hints
- **AND** it SHALL NOT be the only place where normal invocation modes are documented
- **AND** its content SHALL include error recovery patterns, security allowlist guidance, output format/sanitisation controls, multi-step patterns, pack extras, and parameter traps

#### Scenario: ot-chrome-devtools-mcp skill bundled
- **WHEN** `ot.skills()` is called
- **THEN** `ot-chrome-devtools-mcp` SHALL be listed
- **AND** its content SHALL cover the Chrome DevTools MCP server tools, connection modes, and usage patterns

#### Scenario: ot-playwright-mcp skill bundled
- **WHEN** `ot.skills()` is called
- **THEN** `ot-playwright-mcp` SHALL be listed
- **AND** its content SHALL cover the Playwright MCP server tools and usage patterns

#### Scenario: ot-github-mcp skill bundled
- **WHEN** `ot.skills()` is called
- **THEN** `ot-github-mcp` SHALL be listed
- **AND** its content SHALL cover the GitHub MCP server tools and usage patterns
