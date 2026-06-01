# OneTool MCP - Project Structure Map

MCP server with single `run` tool for LLM Python code execution.

---

## Source Code Structure

### Core Framework (`src/ot/`)

Core execution engine, configuration, logging, and inter-tool API.

| Module | Purpose | Key Files |
|--------|---------|-----------|
| `executor/` | Code execution engine | `runner.py`, `validator.py`, `tool_loader.py` |
| `config/` | Configuration management | `loader.py`, `models.py`, `secrets.py` |
| `logging/` | LogSpan structured logging | `span.py`, `entry.py`, `format.py` |
| `registry/` | AST-based tool discovery | `registry.py`, `parser.py`, `models.py` |
| `meta/` | Metadata, health, and introspection helpers | `_help.py`, `_stats.py`, `_config_health.py` |
| `proxy/` | External MCP server support | `manager.py` |

### Base Tool Packs (`src/ottools/`)

Built-in core packs bundled with base install.

| Pack | Description |
|------|-------------|
| `ot_forge.py` | Extension scaffolding and validation |
| `ot_image.py` | Image loading, inspection, generation, and lifecycle helpers |
| `ot_llm.py` | LLM-powered transformation tools |
| `ot_secrets.py` | Secret management utilities |
| `ot_servers.py` | External MCP server management |
| `ot_timer.py` | Named stopwatch timers |
| `server.py` | MCP server metadata/resources |
| `skills.py` | Skills loading and lookup |

### MCP Server and CLI

FastMCP server runtime lives in `src/ot/`; the installed `onetool` command lives in `src/onetool/`.

| File | Purpose |
|------|---------|
| `src/ot/server.py` | FastMCP server runtime and single `run` tool |
| `src/onetool/cli.py` | `onetool` CLI entry point and commands |
| `src/onetool/cli_commands/` | CLI command implementations |

### Benchmark Harness (`packages/onetool-bench/src/bench/`)

Performance benchmarking CLI (internal, not distributed with `onetool-mcp`).

| File | Purpose |
|------|---------|
| `cli.py` | Benchmark CLI |
| `run.py` | Benchmark execution entry |
| `harness/runner.py` | Scenario/task execution loop |
| `reporter.py` | Console and summary reporting |

### Dev Extras (`src/otdev/`) — optional `[dev]`

Tool packs for developer-focused features. Installed via `pip install onetool-mcp[dev]`.

| Pack | Description |
|------|-------------|
| `tools/arch.py` | Architecture model export and validation |
| `tools/chrome_util.py` | Chrome utility operations |
| `tools/context7.py` | Context7 documentation lookup |
| `tools/db.py` | Database operations (SQLAlchemy) |
| `tools/diagram.py` | Diagram generation (Kroki) |
| `tools/excalidraw.py` | Excalidraw scene generation and export |
| `tools/package.py` | Package version checking |
| `tools/play_util.py` | Playwright utility operations |
| `tools/ripgrep.py` | Fast code search |
| `tools/webfetch.py` | Web scraping (trafilatura) |

### Util Extras (`src/otutil/`) — optional `[util]`

Tool packs for document and file utilities. Installed via `pip install onetool-mcp[util]`.

| Pack | Description |
|------|-------------|
| `tools/brave.py` | Brave web search |
| `tools/convert.py` | Document conversion (PDF/DOCX/PPTX→MD) |
| `tools/ctx.py` | Context store operations |
| `tools/excel.py` | Excel file handling |
| `tools/file.py` | File operations |
| `tools/ground.py` | Gemini grounding search |
| `tools/knowledge.py` | Knowledge extraction utilities |
| `tools/mem.py` | Persistent memory tools |
| `tools/tavily.py` | Tavily AI search and URL extraction |

---

## Configuration Files

| File | Purpose | Key Sections |
|------|---------|--------------|
| `pyproject.toml` | Dependencies, scripts, tools | `[project]`, `[tool.ruff]`, `[tool.pytest]` |
| `justfile` | Dev commands | `install`, `check`, `test`, `dev` |
| `onetool.yaml` | OneTool config (optional) | Tool-specific settings |

---

## Tests

Tests mirror the source package structure:

| Source package | Test root |
|----------------|-----------|
| `src/ot/`, `src/onetool/` | `tests/` |
| `src/ottools/` | `tests/ottools/` |
| `src/otdev/` | `tests/otdev/` |
| `src/otutil/` | `tests/otutil/` |

Each test root has the same layout:

| Sub-directory | Test Type | Markers |
|---------------|-----------|---------|
| `smoke/` | Fast sanity checks | `@pytest.mark.smoke` |
| `unit/` | Unit tests | `@pytest.mark.unit` |
| `integration/` | Integration tests | `@pytest.mark.integration` |
| `slow/` | Long-running tests | `@pytest.mark.slow` |

**Component markers:** `core`, `bench`, `serve`, `tools`

**Rule:** Always place tests under the root that matches the source package.
A test for `src/otdev/tools/webfetch.py` → `tests/otdev/unit/tools/test_webfetch.py`.

---

## Documentation

| Directory | Purpose | Audience |
|-----------|---------|----------|
| `dev/` | Developer documentation | Contributors, AI agents |
| `docs/` | User-facing docs | End users |
| `openspec/` | Specifications | Contributors |

---

## Developer Resources

| File | Purpose |
|------|---------|
| `dev/agents/hints.md` | Quick reference for agents |
| `dev/agents/project-map.md` | This file - project structure |
| `dev/practices/commit-scopes.md` | Conventional commit scopes |
| `dev/practices/git.md` | Git workflow, branches, tags |
| `CLAUDE.md` | Instructions for Claude Code |
| `README.md` | Project overview |

---

## Work in Progress

| Directory | Purpose |
|-----------|---------|
| `wip/test-results/` | Sanity test outputs |
| `wip/issues/` | Issues found during testing |
| `wip/consult/` | Consultation findings |
| `wip/bench/` | Benchmark results |

---

## Quick Navigation

**Need to modify:**
- Base tool pack → `src/ottools/<pack>.py`
- Extra tool pack → `src/otdev/tools/<pack>.py` or `src/otutil/tools/<pack>.py`
- Core executor → `src/ot/executor/runner.py`
- MCP server runtime → `src/ot/server.py`
- onetool CLI → `src/onetool/cli.py`
- Tests → `tests/otdev/`, `tests/ottools/`, `tests/otutil/`, or `tests/` (match source package)
- Specs → `openspec/specs/<feature>/spec.md`

**Need to understand:**
- Architecture → `dev/project/arch/index.md`
- How to create tools → `dev/project/guides/tool-development.md`
- Testing guide → `dev/practices/testing.md`
- Git workflow → `dev/practices/git.md`
