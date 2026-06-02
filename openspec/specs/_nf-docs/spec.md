# docs Specification

## Purpose
Defines the structure, format, and completeness requirements for all OneTool documentation — `docs/`, `dev/`, and tool reference pages. Covers MkDocs site configuration, section organisation, tool reference format, plugin guides, and the GitHub Pages deployment pipeline.
## Requirements
### Requirement: Getting Started Documentation

The project SHALL provide getting started documentation in `docs/learn/`.

#### Scenario: Quickstart guide
- **GIVEN** a new user
- **WHEN** they read `learn/quickstart.md`
- **THEN** they can install with `uv tool install onetool-mcp`
- **AND** they can make their first tool call within 2 minutes

#### Scenario: Detailed installation
- **GIVEN** a user needing platform-specific setup
- **WHEN** they read `learn/installation.md`
- **THEN** they find instructions for `uv tool install`
- **AND** they find MCP configuration examples

#### Scenario: Configuration reference
- **GIVEN** a user configuring OneTool
- **WHEN** they read `learn/configuration.md`
- **THEN** they find all config options documented

### Requirement: CLI Reference Documentation

The project SHALL provide CLI reference at `docs/reference/cli/`.

#### Scenario: CLI overview
- **GIVEN** a user looking for CLI help
- **WHEN** they read `reference/cli/index.md`
- **THEN** they find documentation for `onetool` and `bench`

#### Scenario: Individual CLI docs
- **GIVEN** a specific CLI (onetool, bench)
- **WHEN** the user reads its doc
- **THEN** they find commands, options, and examples

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
- **THEN** they find content organized for: Learn, Reference, Extending

#### Scenario: Section descriptions
- **GIVEN** each section reference
- **WHEN** the user reads it
- **THEN** they understand what content that section contains

#### Scenario: Hero section displayed
- **GIVEN** the home page
- **WHEN** a user views it
- **THEN** they see a hero section with logo, tagline, and call-to-action buttons

---

### Requirement: Tools Reference

The project SHALL document all tools at `docs/reference/tools/`.

#### Scenario: Tool index
- **GIVEN** a user at `reference/tools/index.md`
- **WHEN** they scan the page
- **THEN** they find a table of all packs with links to individual docs
- **AND** they find a link to the generated Tool Index

#### Scenario: Generated Tool Index
- **GIVEN** a user at `reference/tools/tool-index.md`
- **WHEN** they scan the page
- **THEN** they find a generated compact list of all tool signatures
- **AND** each listed tool includes a short inline description

#### Scenario: Generated docs developer tooling
- **GIVEN** a developer runs generated documentation commands
- **WHEN** Tool Index generation, generated block synchronization, or docs registry checks execute
- **THEN** reusable implementation SHALL live in importable developer modules
- **AND** script entrypoints SHALL remain thin command wrappers
- **AND** docs registry checks SHALL validate `reference/tools/index.md` against runtime registry metadata

#### Scenario: Individual tool docs
- **GIVEN** each tool pack
- **WHEN** the user reads its doc
- **THEN** they find: purpose tagline, highlights, functions table, key parameters table, requires, examples, source

#### Scenario: ot pack documented
- **GIVEN** the `ot.*` pack
- **WHEN** a user reads `reference/tools/ot_core.md`
- **THEN** they find docs for ot.tools, ot.config

### Requirement: How-to Guides

The project SHALL provide task-oriented guides in `docs/learn/`.

#### Scenario: Explicit calls guide
- **GIVEN** a user wanting to understand explicit invocation
- **WHEN** they read `learn/explicit-calls.md`
- **THEN** they learn how to use the `__run` trigger

#### Scenario: Security guide
- **GIVEN** a user concerned about security
- **WHEN** they read `learn/security.md`
- **THEN** they find security layers, AST validation, and path boundaries

#### Scenario: Comparison guide
- **GIVEN** a user evaluating OneTool
- **WHEN** they read `learn/comparison.md`
- **THEN** they find token savings and cost comparisons

### Requirement: Extension Documentation

The project SHALL provide user-facing extension docs at `docs/learn/extending/`.

#### Scenario: Extension overview
- **GIVEN** a user wanting to build tools at `learn/extending/index.md`
- **WHEN** they read it
- **THEN** they find an overview of extension options and quick start

#### Scenario: Extension tool guide
- **GIVEN** a user creating an extension tool
- **WHEN** they read `learn/extending/extension-tools.md`
- **THEN** they find the full guide for building in-process tools

#### Scenario: Extension guide scope
- **GIVEN** a user needing extension guidance
- **WHEN** they read `learn/extending/extension-tools.md`
- **THEN** they find the supported extension workflow
- **AND** user docs SHALL NOT reference nonexistent guide pages

### Requirement: Internal Documentation

The project SHALL provide contributor docs at `dev/`.

#### Scenario: Contributor overview
- **GIVEN** a contributor at `dev/index.md`
- **WHEN** they read it
- **THEN** they find links to architecture, testing, logging, and CLI patterns

#### Scenario: Internal tool creation
- **GIVEN** a contributor creating a bundled tool
- **WHEN** they read `dev/project/guides/creating-tools.md`
- **THEN** they find the guide for tools in `src/ottools/`

#### Scenario: Testing and logging
- **GIVEN** a contributor debugging or writing tests
- **WHEN** they look for help
- **THEN** they find `dev/practices/testing.md` and `dev/practices/logging.md`

### Requirement: Directory Index Files

Documentation subdirectories SHALL use index.md files for section landing pages; navigation SHALL be handled by `mkdocs.yml`.

#### Scenario: Subdirectory structure
- **GIVEN** a documentation subdirectory (e.g., `learn/`, `reference/`)
- **WHEN** checked
- **THEN** it MAY contain an index.md for section introduction
- **AND** section navigation SHALL be handled by `mkdocs.yml` nav structure

#### Scenario: CLI reference directory
- **GIVEN** the `reference/cli/` directory
- **WHEN** checked
- **THEN** it contains an index.md with CLI overview

#### Scenario: Tools reference directory
- **GIVEN** the `reference/tools/` directory
- **WHEN** checked
- **THEN** it contains an index.md with tools overview table

---

### Requirement: Documentation Site Generation

The project SHALL use MkDocs Material to generate a static documentation site from `docs/`.

#### Scenario: Local development server
- **GIVEN** a developer with docs dependencies installed
- **WHEN** they run `just docs-serve`
- **THEN** a local server starts at `http://127.0.0.1:8000`
- **AND** changes to markdown files trigger hot reload

#### Scenario: Production build
- **GIVEN** the docs source in `docs/`
- **WHEN** `just docs-build` is run
- **THEN** a static site is generated in `dist/site/`
- **AND** the build fails on warnings when using `--strict`

#### Scenario: Manual deployment
- **GIVEN** a built documentation site
- **WHEN** `just docs-deploy` is run
- **THEN** the site is deployed to the `gh-pages` branch

### Requirement: Documentation Site Features

The generated documentation site SHALL provide enhanced navigation, search, and theming.

#### Scenario: Theme toggle
- **GIVEN** a user on the documentation site
- **WHEN** they click the theme toggle
- **THEN** the site switches between auto, light, and dark modes
- **AND** their preference is remembered

#### Scenario: Navigation tabs
- **GIVEN** a user on the documentation site
- **WHEN** they view any page
- **THEN** they see top-level navigation tabs
- **AND** tabs remain sticky when scrolling

#### Scenario: Feedback widget
- **GIVEN** a user on any documentation page
- **WHEN** they scroll to the bottom
- **THEN** they see a feedback widget with thumbs up/down
- **AND** feedback is sent to analytics

#### Scenario: Typography
- **GIVEN** the documentation site
- **WHEN** rendered
- **THEN** body text uses system fonts (Google Fonts disabled)
- **AND** code blocks use system monospace fonts

### Requirement: GitHub Pages Deployment

The documentation site SHALL deploy automatically to GitHub Pages.

#### Scenario: Automatic deployment on push
- **GIVEN** changes pushed to the main branch
- **WHEN** the changes include files in `docs/` or `mkdocs.yml`
- **THEN** the GitHub Actions workflow builds the site
- **AND** deploys it to the `gh-pages` branch
- **AND** GitHub Pages serves the updated content

#### Scenario: PR validation
- **GIVEN** a pull request with documentation changes
- **WHEN** the PR is created or updated
- **THEN** the workflow runs lint checks
- **AND** deployment is skipped (only on main branch)

### Requirement: Documentation Build Configuration

The project SHALL maintain MkDocs configuration in `mkdocs.yml`.

#### Scenario: Configuration location
- **GIVEN** the repository root
- **WHEN** checked for MkDocs config
- **THEN** `mkdocs.yml` exists with site configuration

#### Scenario: Navigation structure
- **GIVEN** the `mkdocs.yml` configuration
- **WHEN** the `nav` section is read
- **THEN** it defines navigation matching the `docs/` directory structure
- **AND** all existing documentation pages are included

#### Scenario: Markdown extensions
- **GIVEN** the `mkdocs.yml` configuration
- **WHEN** the `markdown_extensions` section is read
- **THEN** it enables: toc, admonition, attr_list, tables
- **AND** it enables pymdownx extensions for code highlighting and tabs

### Requirement: Tool Documentation Format

Individual tool documentation files SHALL follow a standardised format.

#### Scenario: Required sections
- **GIVEN** a tool documentation file at `docs/reference/tools/{tool}.md`
- **WHEN** the file is structured
- **THEN** it SHALL include in order:
  1. Title (H1): Tool name
  2. Purpose tagline (bold): What it does, not how it differs
  3. Description: 1-2 sentences of functionality
  4. Highlights section: Feature list without comparisons
  5. Functions section: Table of functions with descriptions
  6. Key Parameters section: Table with Parameter, Type, Description columns
  7. Requires section: Dependencies and API key requirements
  8. Examples section: Python code examples
  9. Source section: Link to API or service documentation

#### Scenario: Optional sections
- **GIVEN** a tool documentation file
- **WHEN** tool-specific content is needed
- **THEN** it MAY include after Examples:
  - Configuration section: YAML config examples (if tool has config)
  - Based on / Inspired by section: Attribution (if applicable)

#### Scenario: Prohibited sections
- **GIVEN** a tool documentation file
- **WHEN** describing the tool
- **THEN** it SHALL NOT include:
  - "Differences from upstream" sections
  - "Comparison" sections
  - Feature comparisons to other implementations

### Requirement: Tool Documentation Highlights

The Highlights section SHALL describe features positively without upstream comparisons.

#### Scenario: Highlight format
- **GIVEN** a Highlights section
- **WHEN** listing features
- **THEN** each highlight SHALL:
  - Describe what the tool does (not what it differs from)
  - Use action-oriented language
  - Focus on user-facing capability

#### Scenario: Prohibited language
- **GIVEN** a Highlights section
- **WHEN** describing features
- **THEN** it SHALL NOT use:
  - "Unlike upstream..."
  - "Compared to..."
  - "Original MCP..."
  - "Differences include..."

### Requirement: Tool Documentation Tables

Functions and Key Parameters sections SHALL use table format.

#### Scenario: Functions table
- **GIVEN** a Functions section
- **WHEN** documenting functions
- **THEN** it SHALL use a table with columns: Function, Description
- **AND** Function column SHALL show `pack.function(params)` format

#### Scenario: Key Parameters table
- **GIVEN** a Key Parameters section
- **WHEN** documenting parameters
- **THEN** it SHALL use a table with columns: Parameter, Type, Description
- **AND** Type column SHALL show the Python type (str, int, bool, etc.)

### Requirement: Tool Documentation Attribution

Tool documentation SHALL include attribution sections based on the tool's derivation level.

#### Scenario: Based on attribution
- **GIVEN** a tool derived from upstream code
- **WHEN** the source header says "Based on"
- **THEN** the doc SHALL include a "Based on" section at the end
- **AND** it SHALL link to the upstream repository
- **AND** it SHALL name the author and license type

#### Scenario: Inspired by attribution
- **GIVEN** a tool with independent code inspired by another project
- **WHEN** the source header says "Inspired by"
- **THEN** the doc SHALL include an "Inspired by" section at the end
- **AND** it SHALL link to the inspiring project
- **AND** it SHALL name the author and license type

#### Scenario: Original tool
- **GIVEN** a clean room implementation or API wrapper
- **WHEN** no attribution is in the source header
- **THEN** the doc SHALL NOT include an attribution section
- **AND** the "Source" section SHALL link to the API documentation

### Requirement: Tool Documentation Source Section

All tool documentation SHALL include a Source section.

#### Scenario: API-based tools
- **GIVEN** a tool that wraps an external API
- **WHEN** documenting the source
- **THEN** the Source section SHALL link to the API documentation
- **NOT** to any upstream implementation repository

#### Scenario: Library-based tools
- **GIVEN** a tool that uses a library (e.g., SQLAlchemy)
- **WHEN** documenting the source
- **THEN** the Source section SHALL link to the library documentation

### Requirement: Plugin Development Documentation

The documentation SHALL include a plugin development guide for building standalone tools in separate repositories.

#### Scenario: Minimal plugin structure documented

- **WHEN** a developer reads the plugin guide
- **THEN** they SHALL find the minimal structure: a single Python file with `pack` declaration
- **AND** a local `.onetool/` directory for development configuration

#### Scenario: Local development configuration documented

- **WHEN** a developer sets up their plugin project
- **THEN** the guide SHALL explain creating `.onetool/onetool.yaml` with `tools_dir` pointing to the plugin source
- **AND** `.onetool/secrets.yaml` for any required API keys
- **AND** optionally `.onetool/bench.yaml` for benchmark testing

#### Scenario: Configuration for consumers documented

- **WHEN** a user wants to use a third-party plugin
- **THEN** the guide SHALL explain adding the plugin path to their project or global `tools_dir`
- **AND** glob patterns SHALL be documented (e.g., `~/plugins/myproject/src/*.py`)

#### Scenario: Extension tool pattern documented

- **WHEN** a plugin requires isolated dependencies
- **THEN** the guide SHALL explain the PEP 723 header pattern
- **AND** include the required `worker_main()` call
- **AND** reference the `ot_sdk` exports

#### Scenario: Plugin testing approach documented

- **WHEN** a developer needs to test their plugin
- **THEN** the guide SHALL explain testing without a full OneTool installation
- **AND** describe the direct function call approach

### Requirement: About Page

The project SHALL provide about pages under `docs/about/`.

#### Scenario: About content
- **GIVEN** a user reading `docs/about/index.md` and `docs/about/about-onetool.md`
- **WHEN** they view the page
- **THEN** they find project information, authors, and license details

---

### Requirement: Learn Section

The project SHALL provide learning materials in `docs/learn/`.

#### Scenario: Learn section structure
- **GIVEN** a user navigating to the Learn section
- **WHEN** they read `docs/learn/index.md`
- **THEN** they find a brief introduction to the learning materials
- **AND** navigation to subsections is handled by the nav sidebar

#### Scenario: Consolidated guides
- **GIVEN** the learn section
- **WHEN** checked
- **THEN** it contains quickstart, installation, configuration, security, explicit-calls, and comparison
- **AND** extending documentation is in `learn/extending/`

### Requirement: Extending Subsection

The project SHALL provide task-oriented extension documentation in `docs/learn/extending/`.

#### Scenario: Extending landing page
- **GIVEN** a user navigating to `docs/learn/extending/index.md`
- **WHEN** they read it
- **THEN** they find a brief overview of extension documentation
- **AND** links to the extension tool guide

### Removed: Public Server Reference Guides

The project SHALL provide curated MCP server setup guides as public reference pages.
