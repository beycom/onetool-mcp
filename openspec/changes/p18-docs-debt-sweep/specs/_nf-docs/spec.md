## MODIFIED Requirements

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
- **AND** if an opt-in `read_only=True` parameter exists on `db.query()` at documentation time, it SHALL be documented as the way to reject non-SELECT/EXPLAIN/PRAGMA statements

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

## ADDED Requirements

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
