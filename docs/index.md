<figure markdown="span">
  ![OneTool](assets/onetool-logo.png){ width="400" }
</figure>

<!-- [![PyPI version](https://img.shields.io/pypi/v/onetool-mcp.svg)](https://pypi.org/project/onetool-mcp/) -->
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://github.com/beycom/onetool-mcp/blob/main/LICENSE)

**Don't enumerate tools. Execute code.**

MCP doesn't scale. Each MCP server costs ~$30/month in wasted tokens. OneTool fixes this.

**[96% fewer tokens. 24x lower cost. Improved accuracy.](learn/comparison.md)**

---

## Get Started

- **[Quickstart](learn/quickstart.md)** - Running in 2 minutes
- **[Installation](learn/installation.md)** - All platforms
- **[Configuration](learn/configuration.md)** - YAML schema
- **[Security](learn/security.md)** - Security model and policies

## Learn

- **[Features](features.md)** - What's in OneTool
- **[Guides](learn/explicit-calls.md)** - How-to guides
- **[Examples](learn/examples.md)** - Demo project

## Reference

- **[Tools](reference/tools/index.md)** - Batteries Included with 100+ Tools
- **[CLIs](reference/cli/onetool.md)** - onetool, bench

## Extend

- **[Creating Tools](extending/creating-tools.md)** - Drop a file, get a pack
- **[Creating CLIs](extending/creating-clis.md)** - Build command-line tools

---

## Batteries Included with 100+ Tools

See [Tool Reference](reference/tools/index.md) for the complete list of packs and tools.

---

## How It Works

```python
__ot brave.search(query="AI trends 2026")
```

One prefix. Direct execution. No tool definitions. No tool selection loops.