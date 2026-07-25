# _nf-docs Specification

## Purpose

Defines product-level documentation requirements for OneTool users. These
requirements cover discoverability, accuracy, and disclosure for public
documentation that users rely on when installing, configuring, invoking,
extending, and operating OneTool.
## Requirements
### Requirement: User Onboarding Documentation

OneTool SHALL provide user-facing onboarding documentation that enables a new
user to install OneTool, configure a client, and make a first tool call.

#### Scenario: Quick start path
- **GIVEN** a new user reading public documentation
- **WHEN** they follow the quick start
- **THEN** they SHALL find installation instructions
- **AND** a minimal MCP client configuration
- **AND** a first successful `run(command=...)` or `__onetool` invocation example

#### Scenario: Configuration entry point
- **GIVEN** a user configuring OneTool
- **WHEN** they read public configuration documentation
- **THEN** they SHALL find the current `onetool.yaml` sections and command-line config options
- **AND** the documented behavior SHALL match the current configuration specs

### Requirement: Public CLI Reference

OneTool SHALL document user-facing CLI commands, options, outputs, and failure
modes.

#### Scenario: Runtime command reference
- **GIVEN** a user needs to start OneTool
- **WHEN** they read CLI reference documentation
- **THEN** they SHALL find `onetool serve` options for stdio and HTTP runtime modes
- **AND** direct execution commands SHALL be documented separately from root MCP runtime commands

#### Scenario: Knowledge-base command reference
- **GIVEN** a user operates knowledge bases through the CLI
- **WHEN** they read CLI reference documentation
- **THEN** they SHALL find the supported `onetool kb` commands and their required arguments

### Requirement: Tool Reference Accuracy

OneTool SHALL provide public reference documentation for bundled tool packs that
matches the current runtime interface.

#### Scenario: Tool pack index
- **GIVEN** a user browsing tool documentation
- **WHEN** they open the tool reference index
- **THEN** they SHALL find all bundled packs grouped by availability or extra
- **AND** each pack entry SHALL identify its public tool functions

#### Scenario: Individual tool documentation
- **GIVEN** a user reads an individual tool pack page
- **WHEN** the page describes callable functions
- **THEN** signatures, required parameters, output shapes, dependencies, and examples SHALL match the current runtime interface

#### Scenario: Missing dependency disclosure
- **GIVEN** a tool requires an API key, optional package, external service, or browser
- **WHEN** the user reads that tool's reference page
- **THEN** the requirement SHALL be disclosed before examples that depend on it

#### Scenario: Generated help doc links resolve
- **GIVEN** `ot.help()` or `ot.tool_info()` generates a documentation URL for a pack from its `doc_slug`
- **WHEN** a user follows that URL
- **THEN** it SHALL resolve to the pack's published reference page (`https://onetool.beycom.online/reference/tools/<doc_slug>/`) and SHALL NOT 404
- **AND** the `doc_slug` value SHALL equal the pack's page filename as listed in `mkdocs.yml`'s nav (e.g. `db` for `db.md`, `webfetch` for `webfetch.md`)

#### Scenario: db.query security documentation matches the real default
- **GIVEN** a user reads `docs/reference/tools/db.md`'s Security section
- **WHEN** the section describes query execution
- **THEN** it SHALL NOT claim queries are read-only by default
- **AND** it SHALL state that `db.query()` executes any valid SQL (SELECT, INSERT, UPDATE, DELETE, DDL) under AUTOCOMMIT isolation by default
- **AND** if an opt-in `read_only=True` parameter exists on `db.query()` at documentation time, it SHALL be documented as a best-effort advisory check that rejects statements which do not look like a single read-only query, not as a security boundary

#### Scenario: db.query return-shape documentation matches the implementation
- **GIVEN** a user reads `db.query()`'s docstring `Returns:` section
- **WHEN** the query is a SELECT
- **THEN** the documented return shape SHALL match the actual return value: a dict with `rows`, `row_count`, and `truncated` keys (not "a list of dicts")

#### Scenario: package.audit documentation matches its real signature and behavior
- **GIVEN** a user reads `docs/reference/tools/package.md`'s Functions table
- **WHEN** the table describes `package.audit`
- **THEN** it SHALL list `path` (not `packages`) as the parameter, matching `package.audit(*, path: str = ".", registry: str | None = None)`
- **AND** it SHALL describe the function as a version-staleness check against a manifest file, and SHALL NOT call it a "security audit" or otherwise imply CVE/vulnerability scanning

#### Scenario: webfetch docstring examples are copy-paste runnable
- **GIVEN** a user copies an `Example:` line from `webfetch.fetch()` or `webfetch.fetch_batch()`'s docstring
- **WHEN** they run it against a correctly configured OneTool environment
- **THEN** it SHALL NOT raise `TypeError` for passing a keyword-only parameter (`url`, `urls`) positionally

#### Scenario: whiteboard draw() shape documentation is internally consistent
- **GIVEN** a user reads `whiteboard.draw()`'s docstring
- **WHEN** the "Shapes:" section states what `id["Label"]` produces
- **THEN** it SHALL NOT claim rectangle is the "only supported shape" in a way that contradicts the same docstring's `shape:` inline-style-prop documentation (which allows changing an element's rendered shape to diamond or ellipse)
- **AND** it SHALL instead describe rectangle as the DSL-literal creation default, overridable via the `shape:` prop

#### Scenario: chrome/play util docs disclose their relationship to the proxied server
- **GIVEN** a user reads `chrome-util.md` or `play-util.md`
- **WHEN** they look for how the pack relates to the underlying proxied MCP server (`chrome_devtools` / `playwright`)
- **THEN** the page SHALL state that the pack is a thin annotation/highlight layer over that proxied server (not a replacement for it)
- **AND** SHALL state that the proxied server's own tools remain available under its proxy name (or the name set via the pack's `server=` override) for everything outside annotation/highlighting

### Requirement: Security And Privacy Disclosure

OneTool SHALL document security and privacy behavior that affects user trust,
local data, network calls, and telemetry.

#### Scenario: Security model documented
- **GIVEN** a user evaluating OneTool security
- **WHEN** they read public security documentation
- **THEN** they SHALL find the code validation, path boundary, secret handling, and proxy trust boundaries that apply at runtime

#### Scenario: Telemetry disclosure
- **GIVEN** anonymous telemetry is enabled by default
- **WHEN** a user reads public documentation or README material
- **THEN** the telemetry event contents and opt-out mechanisms SHALL be disclosed

#### Scenario: Root-level proxy env broadcast disclosed
- **GIVEN** a user configures root-level `env:` in `onetool.yaml`
- **WHEN** they read the External MCP Servers configuration documentation
- **THEN** they SHALL find that root-level `env:` values are merged into the environment of **every** proxied stdio server, including third-party servers, and SHALL find guidance to prefer per-server `env:` for values that should not be shared across servers

### Requirement: Extension Documentation

OneTool SHALL document the supported user-facing extension workflow for adding
custom tools.

#### Scenario: Extension workflow
- **GIVEN** a user wants to add a custom tool
- **WHEN** they read extension documentation
- **THEN** they SHALL find the supported file placement, pack declaration, callable function shape, configuration, and reload workflow

#### Scenario: Third-party tool usage
- **GIVEN** a user wants to use a tool from another local project
- **WHEN** they read extension documentation
- **THEN** they SHALL find how to point `tools_dir` at that tool source
- **AND** how secrets or API keys are supplied for that tool

### Requirement: Documentation Consistency

Public documentation SHALL not advertise commands, config keys, tool names, or
runtime modes that are absent from the current product.

#### Scenario: Removed or unsupported surface omitted
- **GIVEN** a CLI command, config key, or tool function is not part of the current product
- **WHEN** public documentation is rendered or published
- **THEN** it SHALL NOT be presented as supported behavior

#### Scenario: Examples use real supported surfaces
- **GIVEN** public examples in docs or README material
- **WHEN** a user copies an example into a correctly configured OneTool environment
- **THEN** the example SHALL target real commands, packs, functions, and parameters

### Requirement: Undersold Capability Surfacing

Pack reference documentation SHALL call out high-value, non-obvious
capabilities in each page's Highlights section, not only in the Functions
table, so a reader skimming the page does not miss them.

#### Scenario: ot.help ask mode surfaced
- **GIVEN** a user reads `docs/reference/tools/ot_core.md`
- **WHEN** they scan the Highlights section
- **THEN** they SHALL find a bullet describing `ot.help(ask=...)`'s natural-language question mode over the deterministic help text

#### Scenario: ctx.ask surfaced
- **GIVEN** a user reads `docs/reference/tools/ot_context.md`
- **WHEN** they scan the Highlights section
- **THEN** they SHALL find a bullet describing `ctx.ask()`'s multi-question LLM retrieval over stored content

### Requirement: Installation Prerequisites Accuracy

Installation documentation SHALL state the Python version floor and package
manager that match `pyproject.toml`'s `requires-python` value, and SHALL
state both prerequisites explicitly before any install command.

#### Scenario: Python version matches pyproject.toml
- **GIVEN** `pyproject.toml` declares `requires-python = ">=3.12"`
- **WHEN** a user reads `docs/learn/installation.md` or `README.md`
- **THEN** every stated Python version requirement SHALL read `3.12+` (or `>= 3.12`), not `3.11`

#### Scenario: Prerequisites stated before install commands
- **GIVEN** a user opens `docs/learn/installation.md`
- **WHEN** they read the page
- **THEN** they SHALL find an explicit statement that both Python 3.12+ and `uv` are required, positioned before or alongside the recommended install command
- **AND** the recommended install command SHALL appear at or near the top of the page, ahead of the per-platform prerequisite-installation walkthrough

### Requirement: Package Install Command Accuracy

User-facing install hints SHALL reference the actual published PyPI package name. This applies to CLI output, docstrings, and docs that print or show an install command.

#### Scenario: kb scrape extra hint uses the real package name
- **GIVEN** `onetool kb crawl` (or any code path in `src/onetool/kb.py`) prints an install hint for the `[scrape]` extra because `crawl4ai` or Playwright is missing
- **WHEN** the hint is printed
- **THEN** it SHALL read `pip install 'onetool-mcp[scrape]'`, not `pip install 'onetool[scrape]'`

### Requirement: Canonical Tool Count Consistency

README.md SHALL state one consistent tool-count figure throughout the page,
approximately matching (rounded down from) the validated count published in
`docs/reference/tools/index.md`'s header (which `scripts/check_docs_registry.py`
keeps in sync with the runtime registry).

#### Scenario: Single figure used everywhere in README.md
- **GIVEN** README.md mentions the total tool count in more than one place
- **WHEN** a reader compares those mentions
- **THEN** every mention SHALL use the same number
- **AND** that number SHALL be less than or equal to the `docs/reference/tools/index.md` header's validated tool count at time of writing

### Requirement: README Introspection Row Completeness

README.md's `ot` pack row in the Tools table SHALL list `status` alongside
its other listed functions, since `ot.status()` is the quickstart
hello-world call.

#### Scenario: ot.status appears in the README ot row
- **GIVEN** a reader scans README.md's Tools table for the `ot` pack row
- **WHEN** they read the Tools column
- **THEN** `status` SHALL appear alongside `help`, `tools`, `stats`, `skills`

### Requirement: Consistent Missing-Dependency Guidance

Two code paths that detect the same missing Python dependency for encrypted secrets SHALL give the same actionable install guidance.

#### Scenario: keyring guidance matches across call sites
- **GIVEN** `keyring` is not installed
- **WHEN** either `ot/config/secrets.py`'s transparent-decrypt path or `ottools/ot_secrets.py`'s explicit `_require_keyring()` check raises its `ImportError`
- **THEN** both SHALL instruct `pip install keyring`, not a bare package reinstall

#### Scenario: pyrage guidance matches across call sites
- **GIVEN** `pyrage` is not installed
- **WHEN** either `ot/config/secrets.py`'s transparent-decrypt path or `ottools/ot_secrets.py`'s explicit `_require_pyrage()` check raises its `ImportError`
- **THEN** both SHALL instruct `pip install pyrage`, not a bare package reinstall

### Requirement: Marketing Claims Traceability

`claims.md`'s token-count and percentage-reduction figures SHALL trace exactly to the figures published in `docs/learn/comparison.md`, which they cite as their source, and SHALL be date-stamped to the dataset they were computed from.

#### Scenario: One-shot and multi-turn figures match the source
- **GIVEN** `claims.md` states one-shot and multi-turn token counts for the "reduction in token usage" claim
- **WHEN** those numbers are compared to `docs/learn/comparison.md`'s one-shot and 3-shot scenario tables
- **THEN** the token counts, percentages, and multiplier figures in `claims.md` SHALL be derived from (and match) `comparison.md`'s numbers, not an older or different dataset

#### Scenario: Dataset is date-stamped and harness location is disclosed
- **GIVEN** a reader of `claims.md` wants to know when and how the figures were measured
- **WHEN** they read the reduction-claim section
- **THEN** they SHALL find the measurement date (matching `comparison.md`'s "Measurements captured" date) and a note that the benchmark harness now lives outside this repository

### Requirement: Framework-vs-Product Positioning Disclosure

Public documentation SHALL explicitly contrast OneTool as an installed product against
framework-level building blocks (naming FastMCP Code Mode by name), so a prospective user can
answer "why not just use the framework feature" without leaving the docs.

The contrast SHALL state, at minimum, that: FastMCP is a toolkit for *building* MCP servers;
Code Mode / ProxyProvider / sandbox primitives are ingredients a developer must adopt and expose
themselves; a Claude Code / Cursor / Codex user gets none of that unless someone ships a server
around it; OneTool *is* that shipped server, pre-built, with 200+ curated tools, the
param/alias/snippet forgiveness layer, ctx handles, the prompt + skill that teach an LLM to drive
it, and rich config + security.

#### Scenario: Positioning contrast present in README

- **GIVEN** a user reading `README.md`
- **WHEN** they look for how OneTool differs from a framework capability like FastMCP Code Mode
- **THEN** they SHALL find an explicit "framework feature you'd have to build vs. a product you
  install" contrast that names FastMCP/Code Mode and lists OneTool's pre-built layers (curated
  tools, forgiveness layer, ctx handles, prompt+skill, config/security)

#### Scenario: Positioning contrast present in comparison docs

- **GIVEN** a user reading `docs/learn/comparison.md`
- **WHEN** they look for the product-vs-framework positioning
- **THEN** they SHALL find the same contrast (or a cross-reference to it) alongside the existing
  token/cost benchmark data

### Requirement: MCP Proxy Walkthrough Documentation

`docs/learn/` SHALL contain at least one walkthrough that documents the MCP-proxy story: any
MCP server configured under `servers:` in `onetool.yaml` becomes a callable Python namespace,
tool names are auto-aliased across naming conventions, and connections are controlled at runtime
through `ot_servers` (`srv`).

#### Scenario: Proxy namespace walkthrough exists

- **GIVEN** a user wants to understand how an external MCP server becomes callable as
  `server_name.tool_name(...)`
- **WHEN** they read `docs/learn/`
- **THEN** they SHALL find a walkthrough showing a `servers:` config entry and the resulting
  Python-namespace call, distinct from the tool-pack reference pages

#### Scenario: Name-aliasing documented with examples

- **GIVEN** a user calls a proxied tool using a different naming convention than the upstream
  server exposes (e.g. `listRepositories()` vs `list_repositories()` vs `list-repositories`)
- **WHEN** they read the proxy walkthrough
- **THEN** they SHALL find at least one worked example showing the same proxied call succeeding
  under snake_case, kebab-case, and camelCase spellings

#### Scenario: Runtime server control documented

- **GIVEN** a user wants to enable, disable, restart, or check the status of a configured proxy
  server without restarting OneTool
- **WHEN** they read the proxy walkthrough
- **THEN** they SHALL find the `ot_servers` (`srv`) tools (`enable`, `disable`, `restart`,
  `status`) documented with example calls

#### Scenario: chrome_util/play_util framed as proxy companions

- **GIVEN** a user reads the proxy walkthrough or the `chrome_util`/`play_util` reference pages
- **WHEN** they look for the relationship between OneTool's annotation helpers and the underlying
  proxied browser MCP server (`chrome_devtools`/`playwright`)
- **THEN** they SHALL find `chrome_util`/`play_util` explicitly described as thin companions over
  the proxy manager (the `server=` override pattern), meant to be used alongside the proxied
  server's own tools, not as a replacement for them

### Requirement: Capability Demonstration Content

OneTool SHALL ship a set of scripted, runnable demonstrations under `docs/learn/demos/`, each
built around one undersold capability, driven by `onetool direct run` invocations, and narrated
through a proxied voice MCP server. Each demo SHALL be able to run start-to-finish on a fresh
`[all]`-extras install.

#### Scenario: Demo directory exists with required launch scenarios

- **GIVEN** a user or release reviewer browses `docs/learn/demos/`
- **WHEN** they look for the launch-required demonstrations
- **THEN** they SHALL find runnable scripts for at least the three launch-priority scenarios: the
  forgiveness demo, the codebase-to-live-whiteboard demo, and the "we just committed our secrets
  file" demo

#### Scenario: Demo runs start-to-finish on a fresh install

- **GIVEN** a fresh `uv tool install 'onetool-mcp[all]'` environment with `onetool init` completed
- **WHEN** a demo script under `docs/learn/demos/` is executed
- **THEN** every `onetool direct run` invocation in the script SHALL exit `0`
- **AND** the script SHALL require no manual intervention beyond the documented one-time setup
  (starting the OneTool MCP process and registering the narrator MCP server)

#### Scenario: Demos are narrated through a proxied MCP server

- **GIVEN** a demo script that narrates its steps
- **WHEN** the script speaks a narration line
- **THEN** it SHALL do so by calling a proxied MCP server's tool (not a local/native TTS call
  outside OneTool), demonstrating the proxy story from the MCP Proxy Walkthrough requirement

#### Scenario: Demos double as manual release tests

- **GIVEN** a release reviewer runs every script under `docs/learn/demos/`
- **WHEN** all scripts complete without a non-zero exit code
- **THEN** that run SHALL constitute a passing manual release check for the capabilities each
  demo exercises

