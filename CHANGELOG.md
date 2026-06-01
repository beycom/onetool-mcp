# Changelog

## [2.2.2] - 2026-04-03

### Fix
- **Installation** — `onetool-pack` is now bundled directly into the wheel; no separate package install required on new machines

---

## [2.2.1] - 2026-04-03

### CLI: `onetool direct`
Agent harnesses can invoke tools via subprocess or HTTP rather than MCP. `onetool direct` is the stable shell contract for that pattern — same tool calls, zero MCP overhead, structured JSON output.
- **`direct run`** — execute any tool call from the shell or a script; routes to a running host automatically, falls back to in-process; accepts stdin or a `.py` file
- **`direct repl`** — interactive REPL with tab completion, history, and persistent pack state across lines
- **`direct start / stop / restart / status / logs`** — manage a persistent HTTP execution host as a daemon; packs load once and state survives across calls; `start` blocks until the host is ready
- **`direct list / search / help`** — discover and inspect tools without opening a session

### Whiteboard
- **Persistent sessions** — canvas state is now backed by a file; your whiteboard survives server restarts and browser reconnections without losing work
- **Live updates** — incremental changes are pushed to the browser as they happen, rather than requiring a full page refresh

### Tool Improvements
- **`brave`** — `sources_only=True` returns just the source URLs without full result bodies
- **`webfetch`** — `format='html'` returns raw HTML instead of extracted text, useful for scraping structured markup
- **`tavily`** — `max_sources` cap controls how many sources are fetched in deep research mode
- **`ctx.slice()`** — integer offsets now accepted in addition to line ranges

### Configuration
- **Env var overrides** — `OT_LOG_LEVEL`, `OT_LOG_DIR`, and `OT_COMPACT_MAX_LENGTH` can now be set without touching `onetool.yaml`; log lines include full timestamps

### Deployment
- **Docker** — official `Dockerfile` for containerised deployments

---

## [2.2.0] - 2026-04-01

### New Tool Packs
- **`knowledge`** `[util]` — index local markdown directories into a searchable knowledge base; semantic search, full-text search, and RRF-merged results; knowledge packs for sharing curated content

### mem Improvements
- **`mem.ask()`** — ask a natural-language question across all memories; returns ranked, cited excerpts
- **`mem.inspect()`** — detailed view of a single memory entry with metadata
- **`mem.query()`** — structured query across memories with flexible filters

### ctx Improvements
- **File-based store** — replaced SQLite store with a file-based store; results are now addressable by handle
- **New tools**: `ctx.toc()`, `ctx.slice()`, `ctx.grep()`, `ctx.query()`, `ctx.append()` — navigate and extract from large stored outputs without re-running tools

### Configuration
- **Top-level `llm:` config** — set `llm.base_url`, `llm.model`, `llm.api_key`, and `llm.embedding_model` once in `onetool.yaml`; all LLM-using tools (`mem`, `ot_image`, `ot_llm`, `knowledge`) inherit these as defaults

### Changed
- **`chrome_devtools`** renamed from `chrome-devtools` — update any `servers:` config referencing the old name
- **Whiteboard driver** migrated from Playwright to pydoll
- **`worktree` pack removed** — use git directly or a dedicated worktree workflow

---

## [2.1.1] - 2026-03-10

### Changed
- **`ctx` returns a content string** — responses now return a single `content` string instead of a `lines` list, making results directly usable in prompts and tool chains without joining; large queries are capped via `ask_max_bytes`; SQL filters run faster

---

## [2.1.0] - 2026-03-06

### New Tool Packs
- **`ot_context`** (`ctx`) — TTL-expiring SQLite+FTS5 store; write, search, grep, and navigate large tool outputs across tool calls without filling the context window
- **`ot_image`** (`img`) — image analysis via a dedicated vision model in a separate API session; zero host tokens; substantially more accurate than direct attachment for structured extraction

### Whiteboard Improvements
- **`wb.layout()`** — ELK.js auto-layout with five algorithms (`layered`, `stress`, `mrtree`, `radial`, `force`) and full directional control
- **`wb.align()`** — align selected shapes (left, right, center, top, bottom, middle)
- **Auto-size shapes** — shapes resize from label content automatically
- **Chained edge syntax** — `A --> B --> C --> D` in a single DSL line
- **`wb.read_scene()`** — read current canvas state back as structured data

### Excel Improvements
- **Multi-sheet `create`** — create workbooks with multiple named sheets in one call
- **`datetime` serialization fixed** — dates round-trip correctly

---

## [2.0.1] - 2026-03-01

### Documentation
- Updated README: added all v2 tool packs, install extras, fixed broken links

---

## [2.0.0] - 2026-03-01

### Highlights
- **Live Whiteboard** — draw architecture diagrams and flowcharts with a Mermaid-compatible DSL, powered by Excalidraw
- **Three Search Engines** — Brave, Google (Ground), and Tavily; each with batch support and AI-synthesised answer summaries
- **Browser Annotations** — highlight page elements and guide users through workflows via Chrome DevTools or Playwright
- **Interactive Setup** — `onetool init` opens a TUI to configure extensions; no manual YAML editing to get started
- **Encrypted Secrets** — age-encrypted `secrets.yaml` backed by your OS keychain
- **Leaner Install** — optional `[util]` and `[dev]` extras; install only the dependencies you need

### New Tool Packs
- **`whiteboard`** `[dev]` — live Excalidraw canvas with Mermaid-compatible DSL; screenshot and save results. Short alias: `wb`
- **`tavily`** `[util]` — AI-native search with batch queries, URL extraction, and deep research mode
- **`chrome_util` / `play_util`** `[dev]` — visual browser annotations via Chrome DevTools or Playwright
- **`worktree`** `[dev]` *(beta)* — isolated git worktrees for parallel agent tasks; commit, rebase, and clean up automatically
- **`ot_secrets`** — age encryption for `secrets.yaml`; audit, rotate, and check keychain status
- **`ot_forge`** — scaffold new tool packs with correct structure, type hints, and docstrings
- **`ot_timer`** — named timers that persist across tool calls for profiling workflows

### New Features
- **Interactive `onetool init`** — TUI checkbox interface to select extensions; backs up existing config automatically
- **Slim prompts** — system prompt under 25 lines, freeing token budget for actual work
- **`>>>` trigger prefix** — new recommended invocation style (replaces `__ot`)
- **Smarter `ot.result()`** — `tail`, `search`, `context`, `progress`, and `next_query` params for navigating large outputs
- **Bundled skills** — curated guides for Chrome DevTools, Playwright, and more via `ot.skills()`
- **`ot_secrets` encryption** — transparent age/keyring decryption at load time
- **Short pack aliases** — all verbose pack names have short aliases (e.g. `whiteboard→wb`, `webfetch→wf`, `ripgrep→rg`)

### Improved Packs
- **`file`** — `grep` with `.gitignore` awareness, `read_batch`, `slice`, `slice_batch`, and `toc` for markdown navigation
- **`mem`** — `grep` for fast regex search across memory content with context lines
- **`context7`** — updated to v2 API with better library resolution and semantic reranking
- **`diagram`** — `get_playground_url()` generates shareable Kroki playground links

### Breaking Changes
- **Explicit config flags** — `--config` and `--secrets` must now be passed to the server; no implicit discovery
- **Config version** — add `version: 2` to `onetool.yaml`; v1 configs are rejected with a clear error
- **Config location** — moved from `~/.onetool/config/` to `~/.onetool/` (flat layout)
- **User-defined skills removed** — use bundled skills via `ot.skills()` instead
- **`__ot` prefix deprecated** — use `>>>` in saved prompts and documentation

### Install Extras

| Extra    | Packs                                                                 |
| -------- | --------------------------------------------------------------------- |
| `[util]` | brave, convert, excel, file, ground, mem, tavily                      |
| `[dev]`  | context7, db, diagram, package, ripgrep, webfetch, worktree, whiteboard, chrome_util, play_util |
| `[all]`  | Everything                                                            |

---

## [1.1.0] - 2026-02-18

### Added
- `[util]` extra: file, excel, convert, brave, ground tool packs
- `[dev]` extra: db, ripgrep, web, diagram, package, context7 tool packs
- `[all]` convenience extra installs everything
- `--secrets` flag on `onetool serve`
- `file` tool: dry_run, symlinks, include_hidden, recursive delete, encoding options

### Changed
- Global config location: `~/.onetool/onetool.yaml` (was `~/.onetool/config/onetool.yaml`)
- Server starts with defaults if no config found — `onetool init` no longer required
- `[file]` standalone extra folded into `[util]`

## [1.0.2] - 2026-02-16

### Highlights
- add automatic tool name aliasing for non-Python-friendly names
- add devtools_util and playwright_util browser annotation packs; add chrome devtools guide

### Fixed
- expand env vars from secrets for stdio MCP servers; add inherit_env option

## [1.0.1] - 2026-02-10

### Highlights
- **Mem Tool** - 11-13x faster than accessing files directly and improved user experience
- **Agent Hints** - Agents now can get help on using OneTool via add ot.agent_hints()
- **Timer Pack** - Timer tool pack to measure elapsed time
- **Dev Docs** - Architecture, coding standards, etc now all documented for agents and contributors

### Changes
- add mem.grep regex search; update prompts and guides

## [1.0.0] - 2026-02-09

### Highlights
- **Stop Context Rot** - 98.7% token reduction (150K to 2K)
- **Explicit Calls** - Five trigger prefixes, three invocation styles
- **Configurable Everything** - Per-tool timeouts, limits, behavior
- **Batteries Included** - 15+ packs, 100+ tools ready to use
- **Security First** - AST validation, configurable policies, path boundaries

### Changes
- add persistent memory tool
- fix github mcp by implementing streamable HTTP transport
- add proxy server discovery and instructions. Enable chrome-devtools and github mcp by default
- add transform_file and data param
- remove code_search tool
- remove timed tool
