# Project Context

## Purpose

OneTool is an MCP server exposing a single `run` tool for AI-assisted development. It addresses MCP's token bloat (~150K tokens for multiple tools) by moving execution to a cheap LLM.

**Architecture**: `run request` → `LLM codegen` → `Host exec` → `Return` (~2K tokens, 1 call)

## What It Provides

**CLIs**: `ot-serve` (MCP server), `ot-bench` (benchmarks), `ot-browse` (browser TUI)

**Built-in tools** in `src/ot_tools/`: `brave.*` (search), `web.*` (fetch), `ground.*` (Gemini), `context7.*` (docs), `code.*` (semantic search), `llm.*` (transform), `page.*` (browser), `db.*` (database), `package.*` (versions), `ripgrep.*` (grep)

## Tech Stack

Python 3.11+, FastMCP, OpenAI SDK (OpenRouter), Typer, Pydantic, YAML config

## Conventions

- **Code**: Type hints, Google-style docstrings, Ruff linting
- **Testing**: pytest markers (`smoke`, `unit`, `integration`) + component markers (`core`, `serve`, `bench`, `browse`)
- **Git**: Feature branches `feature/[change-id]`, conventional commits

## Configuration

**Resolution order**: `OT_<CLI>_CONFIG` env var → `cwd/.onetool/<cli>.yaml` → `~/.onetool/<cli>.yaml` → defaults

**Working directory**: Set `OT_CWD` to override the effective working directory (e.g., `OT_CWD=demo ot-serve`).

**Locations**:
- Project configs: `<project>/.onetool/*.yaml`
- Global configs: `~/.onetool/*.yaml`
- Bundled defaults: `src/ot/config/defaults/` (packaged with wheel)
- Secrets: `secrets.yaml` (ot-serve) and `bench-secrets.yaml` (ot-bench) in `.onetool/`

**Variable expansion**: `${VAR}` in config files reads from `secrets.yaml` only (not environment variables). Use `${VAR:-default}` for defaults. Paths support `~` expansion only.

**Subprocess environment**: stdio MCP servers inherit only `PATH` plus explicit `env:` values from config. Use `${VAR}` in env section for pass-through (secrets first, then os.environ).

Config includes `version` field for migrations.

## Tool Development

1. Create `src/ot_tools/<name>.py` with `pack = "<name>"` and `__all__`
2. Use `LogSpan` for logging
3. Declare dependencies via `__onetool_requires__ = {"secrets": [...], "system": [...]}`
4. Add spec to `openspec/specs/tool-<name>/spec.md`

See `docs/ot-tools.md` for full guide.

## Dependencies

**Required**: Python 3.11+, uv, FastMCP

**Optional**: Brave API (`brave.*`), Context7 API (`context7.*`), Gemini API (`ground.*`), Playwright (`ot-browse`), ripgrep (`ripgrep.*`)

## OpenSpec Workflow

Changes follow: Proposal → Specs → Tasks → Apply → Archive. See `openspec/AGENTS.md`.

## References

- [Anthropic: Code Execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp) - 98.7% token reduction
- [Anthropic: Advanced Tool Use](https://www.anthropic.com/engineering/advanced-tool-use)

---

*Last Updated: 2026-01-11*
