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
- **AND** `<config-dir>/runtime/logs/serve.log` SHALL record the config path and error message

#### Scenario: Startup failure when --secrets file does not exist
- **GIVEN** `onetool serve --config /path/to/onetool.yaml --secrets /path/to/missing-secrets.yaml` is executed (or the equivalent root `onetool --config ... --secrets ...` invocation)
- **AND** `/path/to/missing-secrets.yaml` does not exist on disk
- **WHEN** the process starts
- **THEN** it SHALL exit with a non-zero status before the MCP handshake
- **AND** stderr SHALL print an actionable message that names the missing secrets path and points at `onetool init` (e.g. `Secrets file not found: /path/to/missing-secrets.yaml`)
- **AND** `<config-dir>/runtime/logs/serve.log` SHALL record the same error
- **AND** this is distinct from omitting `--secrets` entirely, which SHALL continue to start the server with no secrets loaded and no error (secrets remain optional when the flag is not passed at all)

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

### Requirement: Runtime Mode Documentation

The user-facing CLI documentation SHALL describe the runtime modes consistently.

#### Scenario: Runtime mode table
- **WHEN** users read the CLI documentation
- **THEN** they SHALL find a comparison of `stdio`, `http`, and `direct`
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

---

> **Terminology:** The **config dir** is the directory that contains `onetool.yaml`. All materialised files are written to this directory.

### Requirement: Init Guided Setup

The `onetool init` command SHALL guide users through selective config file materialisation rather than bulk-copying all templates.

The primary interface is `onetool init` (uses current directory) or `onetool init -c <path>` for an explicit path. No mandatory flags are required.

`--config` / `-c` uses suffix detection to determine intent:
- Path ending in `.yaml` or `.yml` → treated as the config file path; parent directory is the config dir
- Any other path → treated as the config directory; `onetool.yaml` is written inside it

A `--force` flag SHALL be available. In non-interactive (non-TTY) mode it SHALL be required to overwrite an existing `onetool.yaml`; without it, a second `onetool init` run against an already-initialized config path SHALL be a no-op. In interactive (TTY) mode `--force` SHALL skip the existing overwrite-confirmation prompt and proceed directly to overwriting.

Existing files that ARE overwritten (via TTY confirmation or `--force`) SHALL be backed up to `<filename>.bak` (or `<filename>.bak1`, `<filename>.bak2`, etc. to avoid collisions) before being overwritten, and a warning SHALL be printed.

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

#### Scenario: diagram.yaml editable template directory
- **GIVEN** the user selects `diagram.yaml` during init
- **WHEN** init materialises `diagram.yaml`
- **THEN** it SHALL also copy packaged diagram templates into `templates/diagram/` under the config dir
- **AND** if `templates/diagram/` already exists it SHALL be backed up using the standard `.bak` scheme before overwriting

#### Scenario: Conflict handling
- **GIVEN** a file already exists in the target directory
- **WHEN** `onetool init` would overwrite it
- **THEN** the existing file SHALL be renamed to `<filename>.bak` (incrementing to `.bak1`, `.bak2`, etc. if needed)
- **AND** a warning SHALL be printed naming both the original and backup paths
- **AND** the new file SHALL be written to the original path

#### Scenario: Minimal output config
- **GIVEN** the user does not select any extensions during init (or stdin is not a TTY and the target does not already exist)
- **WHEN** init completes
- **THEN** the generated `onetool.yaml` SHALL contain only `version: 2` with no `include:` section

#### Scenario: Non-interactive re-run is a no-op by default
- **GIVEN** `onetool init --config <path>` was already run and `<path>` exists
- **AND** stdin is not a TTY
- **AND** `--force` is not passed
- **WHEN** `onetool init --config <path>` is run again
- **THEN** it SHALL exit with status 0
- **AND** it SHALL NOT modify, back up, or overwrite `<path>` or any other file
- **AND** it SHALL print a message stating the config already exists and that `--force` overwrites it

#### Scenario: Non-interactive re-run with --force overwrites
- **GIVEN** `onetool init --config <path>` was already run and `<path>` exists
- **AND** stdin is not a TTY
- **WHEN** `onetool init --config <path> --force` is run
- **THEN** the existing `<path>` SHALL be backed up per the standard `.bak` scheme
- **AND** a new minimal `onetool.yaml` SHALL be written to `<path>`

#### Scenario: Interactive re-run with --force skips the confirmation prompt
- **GIVEN** `onetool init --config <path>` was already run and `<path>` exists
- **AND** stdin is a TTY
- **WHEN** `onetool init --config <path> --force` is run
- **THEN** it SHALL NOT prompt "onetool.yaml already exists. Overwrite?"
- **AND** it SHALL proceed directly to the extension checkbox TUI and overwrite `<path>` (with the standard `.bak` backup) once confirmed

#### Scenario: Successful init prints the validate hint
- **GIVEN** `onetool init` completes successfully (interactive or non-interactive) and writes or would have written `onetool.yaml` to `<path>`
- **WHEN** the command finishes
- **THEN** it SHALL print a hint recommending `onetool init validate --config <path>` as the next step

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

### Requirement: Init MCP Config

The `onetool init mcp-config` command SHALL print ready-to-paste MCP client configuration with fully resolved, absolute paths — never placeholder paths.

`onetool init mcp-config [--client claude-code|claude-desktop|cursor|vscode] [--config PATH] [--secrets PATH]`:
- `--config` / `-c` uses the same suffix-detection resolution as `onetool init` (`.yaml`/`.yml` → file path; otherwise → directory containing `onetool.yaml`); defaults to `onetool.yaml` in the current directory. The resolved path SHALL always be printed as an absolute path.
- `--secrets` / `-s` defaults to `secrets.yaml` in the resolved config directory.
- `--client` selects one client's output. If omitted, output for all four supported clients SHALL be printed in sequence, each under its own heading.
- The `command` field in every printed config SHALL be the absolute path to the `onetool` executable as resolved via `PATH` lookup at the time the command runs, not the bare string `"onetool"`, unless `onetool` cannot be found on `PATH` — in which case the bare string SHALL be used and a warning printed to stderr.
- If the resolved secrets path does not exist on disk, `--secrets <path>` SHALL be omitted from the printed `args` array (an absent secrets file must not be baked into a config that will fail at server startup), and a stderr note SHALL point at `onetool init` to create it.
- If the resolved `onetool.yaml` config path does not exist on disk, the command SHALL still print the resolved (future) path, and SHALL print a stderr warning that `onetool init --config <path>` has not been run yet.
- All JSON output SHALL be written to stdout; warnings and headings SHALL be written so that a single `--client` invocation's JSON block can be copy-pasted directly.

#### Scenario: Claude Code output format
- **WHEN** `onetool init mcp-config --client claude-code --config ~/.onetool/onetool.yaml` is run
- **THEN** it SHALL print a JSON object with a top-level `mcpServers` key containing an `onetool` entry
- **AND** the entry's `command` SHALL be the resolved absolute path to the `onetool` executable
- **AND** the entry's `args` SHALL be `["serve", "--config", "<absolute path to ~/.onetool/onetool.yaml>", "--secrets", "<absolute path to ~/.onetool/secrets.yaml>"]` when `secrets.yaml` exists at that location
- **AND** it SHALL also print the equivalent `claude mcp add onetool -- <resolved onetool path> serve --config <resolved config path> --secrets <resolved secrets path>` one-liner
- **AND** it SHALL name the target file (`~/.claude/mcp.json`, or project `.mcp.json`) the JSON block should be merged into

#### Scenario: Claude Desktop output format
- **WHEN** `onetool init mcp-config --client claude-desktop --config ~/.onetool/onetool.yaml` is run
- **THEN** it SHALL print the same `mcpServers`-keyed JSON shape as Claude Code
- **AND** it SHALL name the OS-specific target file path for the platform the command is run on (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS, `%APPDATA%\Claude\claude_desktop_config.json` on Windows, `~/.config/claude-desktop/claude_desktop_config.json` on Linux)
- **AND** it SHALL note that the printed block must be merged into that file's existing `mcpServers` key, not used to replace the whole file

#### Scenario: Cursor output format
- **WHEN** `onetool init mcp-config --client cursor --config ~/.onetool/onetool.yaml` is run
- **THEN** it SHALL print the same `mcpServers`-keyed JSON shape as Claude Code
- **AND** it SHALL name `.cursor/mcp.json` (project-scoped, relative to the current working directory) as the primary target, and mention `~/.cursor/mcp.json` as the global alternative

#### Scenario: VS Code output format
- **WHEN** `onetool init mcp-config --client vscode --config ~/.onetool/onetool.yaml` is run
- **THEN** it SHALL print a JSON object with a top-level `servers` key (not `mcpServers`) containing an `onetool` entry
- **AND** the entry SHALL include `"type": "stdio"` in addition to `command` and `args`
- **AND** it SHALL name `.vscode/mcp.json` (workspace-scoped) as the primary target, and mention the user profile `mcp.json` as the global alternative

#### Scenario: No --client prints all four
- **WHEN** `onetool init mcp-config --config ~/.onetool/onetool.yaml` is run without `--client`
- **THEN** output SHALL include one heading + JSON block per supported client (`claude-code`, `claude-desktop`, `cursor`, `vscode`) in that order

#### Scenario: Resolved onetool command path
- **GIVEN** `onetool` resolves via `PATH` lookup to `/Users/example/.local/bin/onetool`
- **WHEN** any `onetool init mcp-config` invocation runs
- **THEN** every printed `command` field SHALL be `/Users/example/.local/bin/onetool`, not the bare string `onetool`

#### Scenario: Missing secrets file is omitted, not guessed
- **GIVEN** the resolved secrets path `~/.onetool/secrets.yaml` does not exist on disk
- **WHEN** `onetool init mcp-config --config ~/.onetool/onetool.yaml` is run
- **THEN** the printed `args` array SHALL NOT include `--secrets`
- **AND** stderr SHALL print a note that `secrets.yaml` was not found and that `onetool init` creates it

#### Scenario: Missing config path still resolves, with a warning
- **GIVEN** `~/.onetool/onetool.yaml` does not exist on disk
- **WHEN** `onetool init mcp-config --config ~/.onetool/onetool.yaml` is run
- **THEN** the printed JSON SHALL still use the resolved absolute path `~/.onetool/onetool.yaml` (expanded to the user's home directory)
- **AND** stderr SHALL print a warning that `onetool init --config ~/.onetool/onetool.yaml` has not been run yet

#### Scenario: mcp-config appears in init help
- **WHEN** `onetool init --help` is run
- **THEN** `mcp-config` SHALL be listed as an available `init` subcommand alongside `validate`

### Requirement: Harness commands in the OneTool CLI

The `onetool` CLI SHALL expose Claude Code and Codex launcher commands.

#### Scenario: Commands in help
- **WHEN** `onetool --help` is executed
- **THEN** `claude` and `codex` SHALL appear in a labelled code-harness panel

#### Scenario: Claude harness help
- **WHEN** Claude command help is displayed
- **THEN** it SHALL describe exact model/shortcut, route, permission, config,
  presentation, dry-run, and `--` passthrough options

#### Scenario: Codex harness help
- **WHEN** Codex command help is displayed
- **THEN** it SHALL additionally describe an exact direct `--profile`/`-p` selector
- **AND** route and profile SHALL be mutually exclusive

### Requirement: Code helper group

The CLI SHALL provide a small `code` group for target selection and diagnostics.

#### Scenario: Interactive picker
- **WHEN** `onetool code` runs in a terminal without a subcommand
- **THEN** it SHALL select a configured harness, target, model, and permission mode
- **AND** it SHALL use the same resolver as explicit harness commands

#### Scenario: Helper commands
- **WHEN** `onetool code --help` is executed
- **THEN** it SHALL list models, status, doctor, and config
- **AND** it SHALL not list setup, proxy lifecycle, management, authentication, or
  login operations

#### Scenario: Non-interactive picker
- **WHEN** the picker is invoked without a terminal
- **THEN** it SHALL fail with the equivalent explicit command syntax

### Requirement: Launcher configuration resolution

Code commands SHALL resolve configuration deterministically without changing
`onetool serve` behavior.

#### Scenario: Resolution order
- **WHEN** a code command has no explicit config
- **THEN** it SHALL check the current project configuration before the standard user
  configuration

#### Scenario: Explicit config
- **WHEN** `--config` is supplied
- **THEN** it SHALL resolve to an existing regular file and only that checked path
  SHALL be used
- **AND** no directory expansion or fallback discovery SHALL occur

#### Scenario: Launcher secrets resolution
- **WHEN** a code command loads its resolved configuration
- **THEN** an explicit `--secrets` path SHALL take precedence
- **AND** otherwise an adjacent `secrets.yaml` SHALL be loaded when present
- **AND** absence of that adjacent file SHALL load no launcher secrets

#### Scenario: Missing config
- **WHEN** no configuration can be resolved
- **THEN** the command SHALL report checked paths and identify `onetool init` as the
  template installation workflow

#### Scenario: Serve remains unchanged
- **WHEN** `onetool serve` is executed
- **THEN** its existing explicit runtime configuration contract SHALL remain
  unchanged

### Requirement: Redacted local status and explicit diagnostics

Status, doctor, and config helpers SHALL remain within the thin-launcher boundary.

#### Scenario: Status
- **WHEN** `onetool code status` is executed
- **THEN** it SHALL report configured proxy routes and direct profiles, configured
  harness binaries, and proxy endpoint and named-secret presence when applicable
- **AND** it SHALL perform no HTTP request or version/help subprocess

#### Scenario: Doctor
- **WHEN** `onetool code doctor` is executed
- **THEN** it SHALL probe each configured harness executable once for required
  adapter capabilities
- **AND** it SHALL call `/v1/models` exactly once only when proxy routes are
  configured and their named secret is available
- **AND** a missing named proxy secret SHALL be reported without making that request
- **AND** it SHALL compare configured proxy launcher ids exactly against that
  inventory without exposing credentials

#### Scenario: Config display
- **WHEN** effective launcher configuration is shown
- **THEN** it SHALL show only the effective `code` section and resolved OneTool config
  path
- **AND** it SHALL omit secret values, top-level generation models, and generated
  private adapter content

#### Scenario: Models display
- **WHEN** `onetool code models` is executed
- **THEN** it SHALL enumerate configured proxy-route and direct-profile records and
  harness compatibility
- **AND** it SHALL not use or display top-level generation model records

### Requirement: Code routing template initialization

Interactive `onetool init` SHALL offer the code-routing extension template through
the standard extension installation workflow.

#### Scenario: Code routing selected
- **WHEN** a user selects `code-routing.yaml` during interactive initialization
- **THEN** OneTool SHALL copy the bundled template, back up a conflicting target,
  and add the extension include using the standard initialization behavior
