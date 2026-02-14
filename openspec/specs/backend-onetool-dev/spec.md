# backend-onetool-dev Specification

## Purpose
TBD - created by archiving change add-onetool-dev. Update Purpose after archive.
## Requirements
### Requirement: onetool-dev Backend Server

The `onetool-dev` package SHALL provide a standalone MCP server containing developer tools extracted from the onetool-mcp monolith.

**Acceptance Criteria:**
- Package name: `onetool-dev` on PyPI
- Python module: `otdev` (PEP 8 compliant, no underscores)
- Invocation: `uvx onetool-dev` or `onetool-dev` (if installed)
- FastMCP server with stdio transport
- Support for `--config` flag to specify configuration file
- Default config location: `~/.onetool/dev.yaml`
- Private GitHub repository: `github.com/beycom/onetool-dev`

#### Scenario: Standalone Installation and Startup

**Given** a user wants to use developer tools without the full onetool-mcp frontend
**When** they run `uvx onetool-dev`
**Then** the onetool-dev MCP server starts successfully
**And** exposes ~30+ developer tools via MCP protocol
**And** can be configured via Claude Code's .mcp.json

#### Scenario: Proxied Mode via onetool-mcp

**Given** onetool-mcp is configured with backend_servers section
**And** onetool-dev is listed as a backend server
**When** onetool-mcp starts and initializes backends
**Then** onetool-dev backend is started as a subprocess
**And** tools are discovered and proxied through onetool-mcp
**And** ~95% token savings compared to standalone mode (15-20K→2K tokens)

---

### Requirement: Database Operations Pack (db)

The `db` pack SHALL provide database operations for SQL querying and schema inspection.

**Acceptance Criteria:**
- Pack name: `db`
- Module: `otdev.tools.db`
- Functions: query, schema_inspect, execute, tables, columns (minimum)
- Dependency: sqlalchemy>=2.0.0
- Support for multiple database engines (sqlite, postgresql, mysql)
- Configuration: default_engine, connection_timeout

#### Scenario: Query Execution

**Given** a user has a SQLite database at path `/tmp/test.db`
**When** they call `db.query(connection_string="sqlite:////tmp/test.db", query="SELECT * FROM users")`
**Then** the query executes successfully
**And** returns results as structured data (list of dicts or DataFrame)

#### Scenario: Schema Inspection

**Given** a user wants to understand database structure
**When** they call `db.schema_inspect(connection_string="...")`
**Then** the function returns table names, column names, types, and constraints
**And** provides a human-readable schema summary

---

### Requirement: Code Search Pack (ripgrep)

The `ripgrep` pack SHALL provide fast code search capabilities using the `rg` CLI.

**Acceptance Criteria:**
- Pack name: `ripgrep`
- Module: `otdev.tools.ripgrep`
- Functions: search, count, files, types (minimum)
- Dependency: `rg` CLI binary must be installed on system
- Support for regex patterns, glob filters, file type filters
- Configuration: max_results, default_context

#### Scenario: Code Pattern Search

**Given** a user wants to find all occurrences of "def process" in Python files
**When** they call `ripgrep.search(pattern="def process", glob="*.py", path=".")`
**Then** the function returns matching files with line numbers and context
**And** results are limited to max_results if configured

#### Scenario: File Type Listing

**Given** a user wants to know what file types are supported
**When** they call `ripgrep.types()`
**Then** the function returns a list of supported file types (py, js, rust, etc.)

---

### Requirement: Web Fetching Pack (web)

The `web` pack SHALL provide web content fetching and extraction capabilities.

**Acceptance Criteria:**
- Pack name: `web`
- Module: `otdev.tools.web` (renamed from web_fetch for consistency)
- Functions: fetch, extract (minimum)
- Dependencies: trafilatura>=2.0.0, httpx>=0.28.0
- Configuration: timeout, user_agent
- Support for HTML extraction to markdown/text

#### Scenario: Fetch Web Content

**Given** a user wants to fetch content from a URL
**When** they call `web.fetch(url="https://example.com")`
**Then** the function fetches the content via HTTP
**And** extracts main content using trafilatura
**And** returns cleaned text or markdown

#### Scenario: Custom User Agent

**Given** a user wants to specify a custom user agent
**When** they configure `web.user_agent = "MyBot/1.0"` in config
**Then** all web requests use the custom user agent header

---

### Requirement: Package Information Pack (package)

The `package` pack SHALL provide package information from npm, PyPI, and model registries.

**Acceptance Criteria:**
- Pack name: `package`
- Module: `otdev.tools.package`
- Functions: npm, pypi, models, audit, version (minimum)
- Dependency: httpx>=0.28.0
- Configuration: cache_ttl for caching package info
- Support for npm, PyPI, Hugging Face model registry

#### Scenario: NPM Package Information

**Given** a user wants to get information about an npm package
**When** they call `package.npm(package_name="react")`
**Then** the function fetches package metadata from npm registry
**And** returns version, description, dependencies, downloads

#### Scenario: PyPI Package Information

**Given** a user wants to get information about a PyPI package
**When** they call `package.pypi(package_name="fastapi")`
**Then** the function fetches package metadata from PyPI
**And** returns version, description, author, license, keywords

---

### Requirement: Documentation Search Pack (context7)

The `context7` pack SHALL provide documentation search via Context7 API.

**Acceptance Criteria:**
- Pack name: `context7`
- Module: `otdev.tools.context7`
- Functions: search, doc (minimum)
- Dependency: httpx>=0.28.0
- Configuration: api_key from environment variable or config
- Required: CONTEXT7_API_KEY environment variable

#### Scenario: Documentation Search

**Given** a user has a valid Context7 API key
**And** the API key is set in environment or config
**When** they call `context7.search(query="React hooks")`
**Then** the function searches Context7 documentation
**And** returns relevant documentation snippets with sources

#### Scenario: Missing API Key

**Given** a user does not have CONTEXT7_API_KEY configured
**When** they call any context7 function
**Then** the function raises a clear error message
**And** instructs user how to obtain and configure API key

---

### Requirement: Diagram Rendering Pack (diagram)

The `diagram` pack SHALL provide diagram rendering for mermaid, plantuml, d2, and gantt.

**Acceptance Criteria:**
- Pack name: `diagram`
- Module: `otdev.tools.diagram`
- Functions: render, mermaid, plantuml, d2, gantt (minimum)
- Dependency: jinja2>=3.1.0
- Configuration: default_format, output_dir
- Support for multiple output formats (png, svg, pdf)

#### Scenario: Render Mermaid Diagram

**Given** a user has a mermaid diagram definition
**When** they call `diagram.mermaid(code="graph TD; A-->B; B-->C", format="png")`
**Then** the function renders the mermaid diagram to PNG
**And** returns the file path to the rendered image
**And** saves to output_dir if configured

#### Scenario: Gantt Chart Generation

**Given** a user wants to create a project timeline
**When** they call `diagram.gantt(tasks=[...], format="svg")`
**Then** the function generates a gantt chart in SVG format
**And** includes task names, start dates, end dates, dependencies

---

### Requirement: Chrome DevTools Utilities Pack (devtools_util)

The `devtools_util` pack SHALL provide browser automation utilities via Chrome DevTools MCP server.

**Acceptance Criteria:**
- Pack name: `devtools_util`
- Module: `otdev.tools.devtools_util`
- Functions: inject, scan, clear, highlight, guide (minimum)
- Dependencies: devtools MCP server must be running
- Configuration: browser_launch_timeout
- Uses shared `_inject_base` module for browser injection

#### Scenario: Inject Annotation Script

**Given** a user wants to annotate elements on a web page
**And** devtools MCP server is running
**When** they call `devtools_util.inject_annotations()`
**Then** the function loads inject.js into the current page
**And** enables user/Claude annotations with Ctrl+I / Cmd+I

#### Scenario: Highlight Element

**Given** annotation script is loaded in the page
**When** they call `devtools_util.highlight_element(selector=".btn", label="Click here")`
**Then** the specified element is highlighted with the label
**And** the annotation is visible in the browser

---

### Requirement: Playwright Utilities Pack (playwright_util)

The `playwright_util` pack SHALL provide browser automation utilities via Playwright MCP server.

**Acceptance Criteria:**
- Pack name: `playwright_util`
- Module: `otdev.tools.playwright_util`
- Functions: inject, scan, clear, highlight, guide (minimum)
- Dependencies: playwright MCP server must be running
- Configuration: browser_launch_timeout
- Uses shared `_inject_base` module for browser injection

#### Scenario: Guide User Through Multi-Step Task

**Given** a user wants guidance for a multi-step browser task
**And** playwright MCP server is running
**When** they call `playwright_util.guide_user(task="Fill login form", steps=[...])`
**Then** the function provides step-by-step visual guidance
**And** highlights elements for each step
**And** waits for user completion before proceeding

#### Scenario: Scan Annotations

**Given** user or Claude have added annotations to the page
**When** they call `playwright_util.scan_annotations()`
**Then** the function reads all annotation labels
**And** returns structured data with selectors and labels

---

### Requirement: Shared Browser Injection Module (_inject_base)

The `_inject_base` module SHALL provide shared browser injection logic for devtools_util and playwright_util.

**Acceptance Criteria:**
- Module: `otdev.tools._inject_base`
- Provides base classes/functions for browser element annotation
- Shared between devtools_util and playwright_util packs
- No pack name (internal shared module)
- Handles inject.js script loading and management

#### Scenario: Shared Injection Logic

**Given** devtools_util or playwright_util needs to inject scripts
**When** they import and use _inject_base utilities
**Then** the injection logic is consistent across both packs
**And** code is not duplicated between devtools_util and playwright_util

---

### Requirement: Configuration and Logging

The onetool-dev backend SHALL support configuration loading and structured logging.

**Acceptance Criteria:**
- Uses `otcommon.config` for configuration loading
- Default config path: `~/.onetool/dev.yaml`
- Support for environment variable expansion in config
- Uses `otcommon.logging` for structured logging
- Default log file: `~/.onetool/logs/onetool-dev.log`
- Log level configurable via config: DEBUG, INFO, WARNING, ERROR
- All tools use `LogSpan` for operation tracking

#### Scenario: Load Configuration

**Given** a user has created `~/.onetool/dev.yaml` with tool settings
**When** onetool-dev server starts
**Then** the configuration is loaded from the file
**And** tool-specific settings are applied
**And** secrets are expanded from environment variables

#### Scenario: Structured Logging

**Given** onetool-dev server is running
**When** any tool executes an operation
**Then** the operation is logged with LogSpan
**And** log entries include timestamp, level, pack, function, duration
**And** logs are written to ~/.onetool/logs/onetool-dev.log

---

### Requirement: Dual-Mode Operation

The onetool-dev backend SHALL support both standalone and proxied operation modes.

**Acceptance Criteria:**
- Standalone mode: Run directly via `uvx onetool-dev` or `onetool-dev`
- Proxied mode: Started by onetool-mcp as a backend subprocess
- No special knowledge of parent server required
- Standard MCP protocol in both modes
- Configuration passed via --config flag in both modes

#### Scenario: Standalone Mode Usage

**Given** a user wants to use only developer tools
**When** they configure Claude Code .mcp.json with onetool-dev directly
**Then** onetool-dev runs as a standalone MCP server
**And** exposes ~30+ tools via MCP protocol
**And** works with any MCP client (Claude Code, etc.)
**And** token usage is ~15-20K tokens (tool definitions)

#### Scenario: Proxied Mode Usage

**Given** a user has onetool-mcp configured as their MCP server
**And** onetool-dev is listed in backend_servers
**When** they use developer tools via onetool-mcp
**Then** calls are proxied to onetool-dev backend
**And** token usage is ~2K tokens (single run tool)
**And** code execution paradigm is available
**And** tools are callable via `__ot db.query(...)` syntax

---

### Requirement: Quality Standards

The onetool-dev backend SHALL meet quality standards for code, tests, and documentation.

**Acceptance Criteria:**
- Linting: Passes `ruff check` with E402 exception for tool files
- Formatting: Passes `ruff format --check`
- Type checking: Passes `mypy` with no critical errors in server/CLI code
- Testing: Minimum 7 smoke tests, all passing
- Test markers: smoke, unit, integration, tools
- Documentation: Complete README.md, CLAUDE.md, CHANGELOG.md
- Security: Passes gitleaks secret scanning
- Code coverage: >80% for server and CLI modules

#### Scenario: Linting Passes

**Given** the onetool-dev codebase
**When** running `just lint` or `ruff check src/ tests/`
**Then** all checks pass
**And** E402 errors are ignored for tool files (documented in pyproject.toml)

#### Scenario: All Smoke Tests Pass

**Given** the onetool-dev codebase
**When** running `pytest -m smoke` or `just test`
**Then** all 7 smoke tests pass:
  - test_import_package
  - test_import_server
  - test_import_cli
  - test_import_tool_modules
  - test_server_creation
  - test_server_creation_with_config
  - test_cli_version

---

### Requirement: PyPI Publication

The onetool-dev backend SHALL be published to PyPI for easy installation.

**Acceptance Criteria:**
- Package published to PyPI as `onetool-dev`
- Version: 1.0.0 (initial release)
- Installable via `uv tool install onetool-dev` or `uvx onetool-dev`
- Dependencies correctly specified in pyproject.toml
- Includes README.md in package description
- Includes LICENSE file (MIT)
- GitHub repository link in package metadata

#### Scenario: PyPI Installation

**Given** onetool-dev is published to PyPI
**When** a user runs `uvx onetool-dev --version`
**Then** the package installs automatically from PyPI
**And** displays version "1.0.0"
**And** includes all dependencies (onetool-common, fastmcp, etc.)

#### Scenario: Package Metadata

**Given** onetool-dev is on PyPI
**When** a user visits https://pypi.org/project/onetool-dev/
**Then** the page shows correct name, version, description
**And** includes link to GitHub repository
**And** lists all dependencies
**And** shows keywords: mcp, mcp-server, onetool, developer-tools

---

### Requirement: GitHub Repository (Private)

The onetool-dev backend SHALL have a private GitHub repository for collaboration.

**Acceptance Criteria:**
- Repository: `github.com/beycom/onetool-dev`
- Visibility: Private
- Includes: README.md, LICENSE, .gitignore
- Topics: mcp, mcp-server, onetool, developer-tools, database, search, diagrams
- Default branch: main
- Version tags: v1.0.0, etc.

#### Scenario: Repository Privacy

**Given** onetool-dev repository is created on GitHub
**When** checking repository visibility settings
**Then** the repository is marked as "Private"
**And** only authorized collaborators can access
**And** not listed in public search results

#### Scenario: Version Tagging

**Given** onetool-dev v1.0.0 is ready for release
**When** creating a git tag `git tag v1.0.0`
**And** pushing to GitHub `git push --tags`
**Then** the v1.0.0 tag appears on GitHub
**And** a GitHub release can be created from the tag

---

