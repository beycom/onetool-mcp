# OneTool MCP

MCP server with single `run` tool for LLM Python code execution.

## Source

- `src/ot/` - Core (executor, config, logging, inter-tool API)
- `src/ot_tools/` - Tools (db, excel, web, file)
- `src/onetool/` - MCP server CLI
- `src/bench/` - Benchmark CLI

## Config

- `pyproject.toml` - deps, scripts, tools
- `justfile` - dev tasks (`just check`, `just demo-*`)
- `AGENTS_RULES.md` - coding/testing rules
