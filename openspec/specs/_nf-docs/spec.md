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
- **THEN** they find a table of all packs with links to individual docs

#### Scenario: Individual tool docs
- **GIVEN** each tool pack
- **WHEN** the user reads its doc
- **THEN** they find: purpose tagline, highlights, functions table, key parameters table, requires, examples, source

#### Scenario: ot pack documented
- **GIVEN** the `ot.*` pack
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
- **THEN** they find the full guide including attribution requirements

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

The generated documentation site SHALL provide navigation, search, and theming.

#### Scenario: Site navigation
- **GIVEN** a user visiting the documentation site
- **WHEN** they view any page
- **THEN** they see a sidebar with section navigation
- **AND** they see breadcrumbs showing current location
- **AND** they can navigate to any section without page reload

#### Scenario: Search functionality
- **GIVEN** a user on the documentation site
- **WHEN** they use the search bar
- **THEN** results appear instantly (client-side search)
- **AND** matching terms are highlighted in results

#### Scenario: Theme toggle
- **GIVEN** a user on the documentation site
- **WHEN** they click the theme toggle
- **THEN** the site switches between light and dark modes
- **AND** their preference is remembered

#### Scenario: Code blocks
- **GIVEN** a documentation page with code examples
- **WHEN** a user views the page
- **THEN** code blocks have syntax highlighting
- **AND** code blocks have a copy button

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
- **THEN** the guide SHALL explain creating `.onetool/ot-serve.yaml` with `tools_dir` pointing to the plugin source
- **AND** `.onetool/secrets.yaml` for any required API keys
- **AND** optionally `.onetool/ot-bench.yaml` for benchmark testing

#### Scenario: Configuration for consumers documented

- **WHEN** a user wants to use a third-party plugin
- **THEN** the guide SHALL explain adding the plugin path to their project or global `tools_dir`
- **AND** glob patterns SHALL be documented (e.g., `~/plugins/myproject/src/*.py`)

#### Scenario: Worker tool pattern documented

- **WHEN** a plugin requires isolated dependencies
- **THEN** the guide SHALL explain the PEP 723 header pattern
- **AND** include the required `worker_main()` call
- **AND** reference the `ot_sdk` exports

#### Scenario: Plugin testing approach documented

- **WHEN** a developer needs to test their plugin
- **THEN** the guide SHALL explain testing without a full OneTool installation
- **AND** describe the direct function call approach
