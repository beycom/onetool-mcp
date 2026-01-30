<p align="center">
  <img src="docs/assets/onetool-logo.png" alt="OneTool" width="400">
</p>

<p align="center">
  <em>One tool to rule them all, one tool to find them, one tool to bring them all, and in the development bind them.</em>
</p>

<p align="center">
  <a href="https://pypi.org/project/onetool-mcp/"><img alt="PyPI" src="https://img.shields.io/pypi/v/onetool-mcp"></a>
  <a href="https://github.com/beycom/onetool-mcp/blob/main/LICENSE"><img alt="License" src="https://img.shields.io/badge/license-GPLv3-blue"></a>
  <a href="https://www.python.org/"><img alt="Python" src="https://img.shields.io/badge/python-3.11%2B-blue"></a>
</p>

> **v1.0.0 Pre-Release** - API stable, actively tested.

OneTool is a local-first MCP server that exposes a single `run` tool for code execution, giving your AI assistant access to unlimited capabilities through one interface.

## The Problem

Connect 5 MCP servers and you've burned 55K tokens before the conversation starts. Connect 10+ and you're at 100K tokens. Your AI gets worse as you add more tools - that's not a bug, it's how context windows work.

## The Solution

**98.7% fewer tokens. Same accuracy. 10x lower cost.**

Instead of loading 50 separate tool schemas, you write Python directly:

```python
__ot brave.search(query="AI trends 2026")
```

No JSON schema parsing. No tool selection loops. No hoping the model guesses correctly. You write explicit code to call APIs - deterministic, visible, no hidden magic.

Based on [Anthropic's research](https://www.anthropic.com/engineering/code-execution-with-mcp), which found token usage dropped from 150,000 to 2,000 when presenting tools as code APIs.

## Core Capabilities

- **30-second setup** - Install with uv or pip
- **Drop-in extensibility** - Add a Python file, get a new pack
- **AST security** - All code validated before execution
- **Benchmark harness** - Test LLM + MCP combinations with `bench`

## Batteries Included with 100+ Tools

See [Tool Reference](docs/tool-reference.md) for the complete list of packs and tools.

## Installation

```bash
uv tool install onetool-mcp
```

Or with pip: `pip install onetool-mcp`

**With optional dependencies** (for convert, excel, code search):

```bash
uv tool install onetool-mcp \
  --with pymupdf --with python-docx --with python-pptx \
  --with openpyxl --with Pillow --with duckdb --with openai
```

Add to Claude Code (`~/.claude/settings.json`):

```json
{
  "mcpServers": {
    "onetool": {
      "command": "onetool"
    }
  }
}
```

## Extending

Drop a Python file, get a pack. No registration, no config:

```python
# tools/mytool.py
pack = "mytool"

def search(*, query: str) -> str:
    """Search for something."""
    return f"Results for: {query}"
```

## Why this approach

LLMs write Python instead of parsing JSON schemas. You see what's being called. 2K tokens instead of 150K. Adding your own packs is just dropping in a file.

## Documentation

- [Why OneTool](docs/intro/index.md) - The problem and our solution
- [Getting Started](docs/getting-started/quickstart.md) - 2-minute setup
- [Tools Reference](docs/reference/tools/index.md) - All built-in tools
- [Extending](docs/extending/index.md) - Create your own tools

## References

- [Code Execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp) - Anthropic Engineering
- [Context Rot](https://research.trychroma.com/context-rot) - Chroma Research

## Licensing

**GPLv3** - Will transition to **MIT** at v2.0. Contribute via PRs to help us get there.

## Support

If you use or like this project, please consider buying me a coffee:

[![Ko-fi](https://img.shields.io/badge/Ko--fi-Buy%20me%20a%20coffee-ff5e5b?logo=ko-fi)](https://ko-fi.com/beycom)