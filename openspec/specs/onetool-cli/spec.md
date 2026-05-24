# onetool CLI Specification

## Purpose

Defines the main `onetool` CLI. Provides the MCP server entry point, the `init` subcommand group for configuration management, the `kb` subcommand group for knowledge base management, and the `direct` subcommand group for direct tool execution.

---

## Requirements

### Requirement: CLI Entry Point

The system SHALL provide a `onetool` CLI command with an explicit `serve`
runtime command for root MCP server startup. `onetool serve` SHALL default to
stdio transport and SHALL support Streamable HTTP root mode through
`--transport http`.

#### Scenario: Explicit stdio root invocation
- **GIVEN** the package is installed
- **WHEN** `onetool serve --config /path/to/onetool.yaml` is executed
- **THEN** it SHALL start the MCP server over stdio

#### Scenario: Explicit HTTP root invocation
- **GIVEN** the package is installed
- **WHEN** `onetool serve --transport http --config /path/to/onetool.yaml` is
  executed with optional host, port, and path options
- **THEN** it SHALL start the same OneTool MCP server over Streamable HTTP
- **AND** the public transport value `http` SHALL map internally to FastMCP's
  `streamable-http` transport
- **AND** it SHALL use the same config, secrets, lifespan, proxy startup, Direct
  API startup, stats, telemetry, and shutdown behavior as stdio root mode

#### Scenario: Transport short option
- **WHEN** `onetool serve -t http -c /path/to/onetool.yaml` is executed
- **THEN** it SHALL behave the same as `--transport http --config
  /path/to/onetool.yaml`

#### Scenario: HTTP root defaults
- **WHEN** `onetool serve --transport http` is started without host, port, or
  path overrides
- **THEN** the bind host SHALL default to loopback
- **AND** the bind port SHALL default to `8767`
- **AND** the MCP endpoint path SHALL default to `/mcp`

#### Scenario: HTTP root explicit broad bind
- **WHEN** Streamable HTTP root mode is started with `--host 0.0.0.0`
- **THEN** the server SHALL bind to `0.0.0.0`
- **AND** startup logs SHALL include an explicit warning that the bind address is
  not loopback

#### Scenario: Root callback compatibility warning
- **WHEN** `onetool --config /path/to/onetool.yaml` starts stdio root mode
- **THEN** it SHALL continue to start the MCP server over stdio
- **AND** it SHALL print a warning recommending `onetool serve --config
  /path/to/onetool.yaml`

#### Scenario: Removed serve-http command
- **WHEN** `onetool serve-http` is executed
- **THEN** the CLI SHALL fail through normal unknown-command handling

#### Scenario: Startup config validation failure
- **GIVEN** `onetool --config /path/to/onetool.yaml` is launched by an MCP client
- **AND** config loading fails before the MCP handshake
- **WHEN** the process exits
- **THEN** stderr SHALL include a compact config error diagnostic
- **AND** `<config-dir>/logs/serve.log` SHALL record the config path and error message

#### Scenario: Termination signal
- **GIVEN** the stdio or HTTP MCP server process receives SIGINT or SIGTERM
- **WHEN** the signal is handled
- **THEN** the process SHALL unwind through normal server shutdown
- **AND** FastMCP lifespan cleanup SHALL be able to close proxied transports
- **AND** the Direct API sidecar SHALL be stopped if it is running

#### Scenario: Help output
- **GIVEN** `onetool --help` is executed
- **WHEN** help is displayed
- **THEN** it SHALL list available options and subcommands with descriptions
- **AND** subcommands SHALL be grouped under labelled panels: `CLI`, `Runtime`,
  `Direct`, `Configuration`, and `Knowledge Base` where applicable

#### Scenario: Version flag
- **GIVEN** `onetool --version` is executed
- **WHEN** executed
- **THEN** it SHALL display the package version

### Requirement: direct subcommand group

The `onetool` CLI SHALL provide a `direct` subcommand group for sending commands to an already-running MCP-owned direct API.

#### Scenario: direct group in help

- **WHEN** `onetool --help` is run
- **THEN** a `direct` entry SHALL appear under a `Direct` panel in the help output
- **AND** `Configuration` and `Knowledge Base` panels SHALL also be present, grouping `init` and `kb` respectively

#### Scenario: direct group help

- **WHEN** `onetool direct --help` is run
- **THEN** it SHALL list `run` as the only available direct subcommand

### Requirement: Child Runtime Command

The `onetool` CLI SHALL provide a restricted `child` command for worker MCP
access that forwards `run` calls to the parent Direct API.

#### Scenario: Child requires parent URL and auth directory
- **WHEN** `onetool child` is executed
- **THEN** it SHALL require `--url <parent-direct-url>`
- **AND** it SHALL require `--ot-dir <parent-ot-dir>`
- **AND** `--ot-dir` SHALL identify the parent OneTool directory containing
  `mcp-direct/auth.key`

#### Scenario: Child rejects missing ot-dir
- **WHEN** `onetool child --url <parent-direct-url>` is executed without
  `--ot-dir`
- **THEN** it SHALL fail before starting the child MCP server
- **AND** the error SHALL explain that child mode needs the parent OneTool
  directory to use the parent Direct API auth key

#### Scenario: Child rejects relative ot-dir
- **WHEN** `onetool child --url <parent-direct-url> --ot-dir .onetool` is
  executed
- **THEN** it SHALL fail before starting the child MCP server
- **AND** the error SHALL explain that `--ot-dir` must be absolute after `~`
  expansion

#### Scenario: Child exposes only run
- **WHEN** the child MCP server starts
- **THEN** it SHALL expose only the restricted `run` tool
- **AND** each `run` call SHALL forward to the parent Direct API URL
- **AND** forwarded requests SHALL be signed with the key from the explicit
  parent `--ot-dir`

### Requirement: Runtime Mode Documentation

The user-facing CLI documentation SHALL describe the runtime modes consistently.

#### Scenario: Runtime mode table
- **WHEN** users read the CLI documentation
- **THEN** they SHALL find a comparison of `stdio`, `http`, `direct`, and
  `child`
- **AND** the table SHALL describe purpose, transport, auth, port or bind,
  config, entry point, and when to use each mode

#### Scenario: Stdio recommended
- **WHEN** users read local MCP setup documentation
- **THEN** stdio SHALL be presented as the default and recommended local MCP
  setup

#### Scenario: HTTP container configuration
- **WHEN** users read containerized client documentation
- **THEN** Streamable HTTP root mode SHALL be documented with a pure MCP client
  URL config and no command or args

#### Scenario: HTTP smoke coverage
- **WHEN** automated smoke coverage starts Streamable HTTP root mode
- **THEN** it SHALL connect with a Streamable HTTP MCP client
- **AND** it SHALL list tools and verify the `run` tool is present
- **AND** it SHALL call `run` successfully over Streamable HTTP

---

> **Terminology:** The **config dir** is the directory that contains `onetool.yaml`. All materialised files are written to this directory.

### Requirement: Init Guided Setup

The `onetool init` command SHALL guide users through selective config file materialisation rather than bulk-copying all templates.

The primary interface is `onetool init` (uses current directory) or `onetool init -c <path>` for an explicit path. No mandatory flags are required.

`--config` / `-c` uses suffix detection to determine intent:
- Path ending in `.yaml` or `.yml` → treated as the config file path; parent directory is the config dir
- Any other path → treated as the config directory; `onetool.yaml` is written inside it

Existing files in the target directory SHALL be backed up to `<filename>.bak` (or `<filename>.bak1`, `<filename>.bak2`, etc. to avoid collisions) before being overwritten, and a warning SHALL be printed.

#### Scenario: Init with no flags (interactive)
- **GIVEN** `onetool init` or `onetool init -c <path>` is run
- **AND** stdin is a TTY
- **WHEN** init runs
- **THEN** it SHALL first prompt the user to confirm or edit the resolved config file path (e.g. `Config file: onetool.yaml`)
  - The default shown is the fully-resolved `config_path`; pressing enter accepts it; typing a new path overrides it
  - Ctrl+C at this prompt cancels without writing any files
- **AND** it SHALL display a checkbox multi-select TUI listing all available extensions:
  - `prompts.yaml`, `servers.yaml`, `security.yaml`, `diagram.yaml`, `snippets.yaml`
- **AND** materialise only the extensions selected by the user
- **AND** write an `onetool.yaml` that includes only the materialised YAML files
- **AND** if the user cancels (Ctrl+C) at the checkbox, exit with code 0 without writing any files

#### Scenario: diagram.yaml sidecar directory
- **GIVEN** the user selects `diagram.yaml` during init
- **WHEN** init materialises `diagram.yaml`
- **THEN** it SHALL also copy the `diagram-templates/` directory from package templates into the config dir alongside `diagram.yaml`
- **AND** if `diagram-templates/` already exists it SHALL be backed up using the standard `.bak` scheme before overwriting

#### Scenario: Conflict handling
- **GIVEN** a file already exists in the target directory
- **WHEN** `onetool init` would overwrite it
- **THEN** the existing file SHALL be renamed to `<filename>.bak` (incrementing to `.bak1`, `.bak2`, etc. if needed)
- **AND** a warning SHALL be printed naming both the original and backup paths
- **AND** the new file SHALL be written to the original path

#### Scenario: Minimal output config
- **GIVEN** the user does not select any extensions during init (or stdin is not a TTY)
- **WHEN** init completes
- **THEN** the generated `onetool.yaml` SHALL contain only `version: 2` with no `include:` section

### Requirement: Init Validate Source Reporting

The `onetool init validate` command SHALL report the source of each resolved include.

#### Scenario: Validate shows include sources
- **GIVEN** `onetool init validate` is run
- **AND** some includes are user-owned and some use package defaults
- **WHEN** validation output is displayed
- **THEN** each include SHALL be listed with its source tag:
  - `[user]` — loaded from the config dir (`config_path.parent/<path>`)
  - `[default]` — loaded from `global_templates/<path>`
  - `[missing]` — listed in `include:` but not found in either location
  - `[absolute]` — resolved from an absolute path
  - `[not listed]` — not in `include:`, not loaded
- **AND** the resolved file path SHALL be shown for each loaded include

#### Scenario: Validate suggests materialisation
- **GIVEN** an include using a package default (`[default]` source)
- **WHEN** validation output is shown
- **THEN** it SHALL include a hint suggesting how to materialise the file locally to customise it

---

### Requirement: KB Subcommand Group

The `onetool kb` subcommand group SHALL provide offline knowledge base management commands.

All commands call the implementation layer directly (not MCP wrappers) so they can emit real-time progress output.

Global options on the `kb` callback: `--config`/`-c` (path to onetool.yaml) and `--secrets`/`-s` (path to secrets file). Both auto-detect from CWD if omitted.

#### Commands

| Command | Description |
|---|---|
| `onetool kb index <project> [--path PATH] [--overwrite skip\|update]` | Index a project's scraped content into the knowledge database |
| `onetool kb reindex <db>` | Backfill missing embeddings |
| `onetool kb stats <db>` | Print chunk counts, embedding coverage, file size |
| `onetool kb info <db>` | Print DB metadata, path, version |
| `onetool kb export <db> --output PATH [--category CAT] [--topic TOPIC]` | Export all chunks (or filtered subset) to JSON |
| `onetool kb scrape <project> [--only ...] [--resume] [--debug] [--max-pages N] [--flat-files\|--no-flat-files]` | Crawl all sources in a scrape project |

#### Scenario: Index a project
- **GIVEN** `onetool kb index <project>` is run and `<project>` is configured under `tools.knowledge.kb`
- **WHEN** indexing completes
- **THEN** it SHALL print indexed count, skipped count, and link edges added
- If `--path` is supplied, it overrides the project's `output_base_dir`
- `--overwrite` accepts `skip` (default, skip existing entries) or `update` (re-index changed entries)

#### Scenario: Reindex missing embeddings
- **GIVEN** `onetool kb reindex <db>` is run
- **WHEN** reindexing completes
- **THEN** it SHALL print the number of embeddings generated

#### Scenario: Stats
- **GIVEN** `onetool kb stats <db>` is run
- **THEN** it SHALL print chunk counts by category, embedding coverage, and file size
- **AND** it SHALL print a `✓ Stats for '<name>'.` completion summary

#### Scenario: Info
- **GIVEN** `onetool kb info <db>` is run
- **THEN** it SHALL print the DB path, size, chunk count, and _meta content
- **AND** it SHALL print a `✓ Info for '<name>'.` completion summary

#### Scenario: Export
- **GIVEN** `onetool kb export <db> --output <path>` is run
- **THEN** it SHALL write all chunks (or filtered subset) to a JSON file and print the export count
- `--category` and `--topic` are optional filters

#### Scenario: Scrape a project
- **GIVEN** `onetool kb scrape <project>` is run and `<project>` exists in `tools.knowledge.kb` with a `scrape:` section
- **WHEN** scraping completes
- **THEN** it SHALL crawl all sources in insertion order and print per-source written/failed/skipped counts, then print `Report: <path>` for each source's `._run_report.json`

#### Scenario: Scrape a subset with --only
- **GIVEN** `onetool kb scrape <project> --only "src-a,src-b"` is run
- **THEN** only the named sources are crawled; unknown names → error before any crawl starts

#### Scenario: Unknown project name
- **GIVEN** `onetool kb scrape <name>` is run and `<name>` is not in `tools.knowledge.kb`
- **THEN** the command SHALL exit with an error listing available project names

#### Scenario: Resume per source
- **GIVEN** `onetool kb scrape <project> --resume` is run
- **THEN** sources whose output dir contains `.state.json` SHALL resume; others start fresh

#### Scenario: Debug mode
- **GIVEN** `onetool kb scrape <project> --debug` is run
- **THEN** per-page debug artifacts (`cleaned.html`, `raw.html`, `screenshot.png`, `meta.json`) SHALL be written to `._debug/<slug>/` inside each source output dir

#### Scenario: Missing crawl4ai package
- **GIVEN** `onetool kb scrape` is run and `crawl4ai` is not installed
- **THEN** the command SHALL exit with: `"crawl4ai is required. Install with: pip install 'onetool[scrape]'"`

#### Scenario: Missing Playwright browser
- **GIVEN** `crawl4ai` is installed but Playwright Chromium browser is not
- **THEN** the command SHALL exit with: `"Playwright browser not found. Run: playwright install chromium"`

#### Scenario: Override max_pages at runtime
- **GIVEN** `onetool kb scrape <project> --max-pages 50` is run
- **THEN** each source SHALL stop writing pages once 50 pages are written, regardless of the configured `max_pages` value
- **AND** the `--max-pages` value applies to each source independently (i.e. each source may write up to 50 pages)

#### Scenario: max_pages hard limit enforced in BFS loop
- **WHEN** a BFS crawl is running and `max_pages` written pages are reached
- **THEN** the crawl loop SHALL break and no further pages SHALL be written, even if crawl4ai's strategy continues to yield results

---

### Requirement: kb scrape command
The `onetool kb` subcommand group SHALL include a `scrape` command that crawls a web source and writes `.md` + `.meta.yaml` pairs to an output directory.

#### Scenario: Named source crawl uses config output dir
- **WHEN** `onetool kb scrape mysite` is run and `mysite` is configured under `tools.knowledge.scrape.sources`
- **THEN** pages are crawled and files written to the source's configured `output_dir`, or `.onetool/scrape/mysite/` if `output_dir` is not set

#### Scenario: Named source with --output override
- **WHEN** `onetool kb scrape mysite --output /tmp/out` is run
- **THEN** files are written to `/tmp/out` regardless of the configured `output_dir`

#### Scenario: Ad-hoc URL requires --output
- **WHEN** `onetool kb scrape https://docs.example.com` is run without `--output`
- **THEN** the command SHALL exit with an error: `"--output is required for ad-hoc URL scrapes"`

#### Scenario: Ad-hoc URL with --output
- **WHEN** `onetool kb scrape https://docs.example.com --output /tmp/out` is run
- **THEN** pages are crawled and files written to `/tmp/out`

#### Scenario: Unknown named source raises error
- **WHEN** `onetool kb scrape unknown-source` is run and `unknown-source` is not in `tools.knowledge.scrape.sources`
- **THEN** the command SHALL exit with an error: `"No source 'unknown-source' in tools.knowledge.scrape.sources"`

#### Scenario: Resume flag
- **GIVEN** a prior crawl was interrupted
- **WHEN** `onetool kb scrape mysite --resume` is run
- **THEN** the crawl resumes from `.state.json` in the output directory

#### Scenario: --depth overrides config
- **WHEN** `onetool kb scrape mysite --depth 2` is run
- **THEN** the crawl uses `max_depth=2` regardless of the configured `depth`

#### Scenario: --max-pages overrides config
- **WHEN** `onetool kb scrape mysite --max-pages 100` is run
- **THEN** the crawl stops after 100 pages regardless of the configured `max_pages`

#### Scenario: Missing [scrape] extra
- **WHEN** `onetool kb scrape` is run and `crawl4ai` is not installed
- **THEN** the command SHALL exit with: `"crawl4ai is required. Install with: pip install 'onetool[scrape]'"`

#### Scenario: Summary printed on completion
- **WHEN** a crawl completes
- **THEN** the command SHALL print the count of pages written, failed, and skipped
