# OneTool MCP

MCP server with single `run` tool for LLM Python code execution.

## Source

- `src/ot/` - Core (executor, config, logging)
- `src/ot_tools/` - Tools (db, excel, web, file)
- `src/ot_sdk/` - Tool SDK
- `src/ot_serve/` - MCP server CLI
- `src/ot_bench/` - Benchmark CLI

## Config

- `pyproject.toml` - deps, scripts, tools
- `justfile` - dev tasks (`just check`, `just demo-*`)
- `AGENTS_RULES.md` - coding/testing rules
