<p align="center">
  <img src="docs/assets/onetool-logo.png" alt="OneTool" width="400">
</p>

<p align="center">
  <em>One tool to rule them all, one tool to find them, one tool to bring them all, and in the development bind them.</em>
</p>

**Don't enumerate tools. Execute code.**

OneTool is a local-first MCP server that exposes a single `run` tool for code execution, giving your AI assistant access to unlimited capabilities through one interface.

## The Problem

Token bloat • Context rot • Tool sprawl • Guessing games • Schema overhead • Scaling limits

Connect 5 MCP servers: **55K tokens** consumed before conversation begins. Connect 10+: **100K+ tokens** burned. Your AI gets worse as you add more tools.

## The Solution

**98.7% fewer tokens. Same accuracy. 10x lower cost.**

Instead of loading 50 separate tool schemas, your LLM writes Python directly:

```python
__ot brave.search(query="AI trends 2026")
```

No JSON schema parsing. No tool selection loops. No hoping the model guesses correctly. You write explicit code to call APIs - deterministic, visible, no hidden magic.

Based on [Anthropic's research](https://www.anthropic.com/engineering/code-execution-with-mcp), which found token usage dropped from 150,000 to 2,000 when presenting tools as code APIs.

## Core Capabilities

- **10 built-in namespaces** - brave, web, context7, code, llm, db, package, ripgrep, excel, ot
- **30-second setup** - Install with uv or pip
- **Drop-in extensibility** - Add a Python file, get a new namespace
- **AST security** - All code validated before execution
- **Benchmark harness** - Test LLM + MCP combinations with `ot-bench`

## Installation

```bash
uv tool install onetool-mcp
```

Or with pip: `pip install onetool-mcp`

Add to Claude Code (`~/.claude/settings.json`):

```json
{
  "mcpServers": {
    "onetool": {
      "command": "ot-serve"
    }
  }
}
```

## What's Inside

**Namespaces** - brave (web search), web (fetch), context7 (library docs), code (semantic search), llm (transform), db (SQL), package (npm/PyPI), ripgrep (file search), excel (spreadsheets), ot (meta tools)

**CLIs** - `ot-serve` (MCP server), `ot-bench` (benchmark harness)

## Extending

Drop a Python file, get a namespace. No registration, no config:

```python
# tools/mytool.py
namespace = "mytool"

def search(*, query: str) -> str:
    """Search for something."""
    return f"Results for: {query}"
```

## Philosophy

- **Fight Context Rot** - 2K tokens instead of 150K
- **Code is King** - LLMs write Python, not JSON
- **Explicit Invocation** - You control what gets called
- **Batteries Included** - 10 namespaces ready, extensible by design

## Documentation

- [Why OneTool](docs/intro/index.md) - The problem and our solution
- [Getting Started](docs/getting-started/quickstart.md) - 2-minute setup
- [Tools Reference](docs/reference/tools/index.md) - All built-in tools
- [Extending](docs/extending/index.md) - Create your own tools

## References

- [Code Execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp) - Anthropic Engineering
- [Context Rot](https://research.trychroma.com/context-rot) - Chroma Research

## Licensing & Roadmap

**OneTool** is currently licensed under **GPLv3**. I have chosen this license for the early development phase to:

- **Prevent Fragmentation:** Ensure the community remains focused on a single, high-quality version.
- **Guarantee Reciprocity:** Ensure all early improvements are shared back with the project.

**The Future:** Once OneTool reaches a stable milestone (Target: Version 2.0), I intend to re-license the project under the **MIT License**. This will allow for maximum flexibility once the core architecture is established.

I kindly ask that you contribute via Pull Requests to the main repository rather than maintaining separate public forks to help reach that milestone faster.

## Telemetry

OneTool includes anonymous telemetry to help improve the project. **Telemetry is enabled by default.**

When enabled, OneTool collects:
- Server start events (version, tool count)
- Aggregated run stats (success/failure, duration, character counts)

OneTool **never** collects: code content, file paths, API responses, personal information, or IP addresses.

**Opt-out methods** (any of these disables telemetry):
- Set `telemetry.enabled: false` in configuration
- Set `DO_NOT_TRACK=1` environment variable
- Set `ONETOOL_TELEMETRY_DISABLED=1` environment variable

## Support

If you use or like this project, please consider buying me a coffee:

[![Ko-fi](https://img.shields.io/badge/Ko--fi-Buy%20me%20a%20coffee-ff5e5b?logo=ko-fi)](https://ko-fi.com/gavinlas)