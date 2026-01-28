<p align="center" markdown>
  <img src="assets/onetool-logo.png" alt="OneTool" width="400">
</p>

**Don't enumerate tools. Execute code.**

MCP doesn't scale. Connect 5 servers: 55K tokens burned. Connect 10+: 100K+ tokens gone before you say hello. OneTool fixes this.

**98.7% fewer tokens. Same accuracy. 10x lower cost.**

---

## Get Started

- **[Quickstart](getting-started/quickstart.md)** - Running in 2 minutes
- **[Installation](getting-started/installation.md)** - All platforms
- **[Configuration](getting-started/configuration.md)** - YAML schema
- **[Security](getting-started/security.md)** - Security model and policies

## Learn

- **[Features](features.md)** - What's in OneTool
- **[Why OneTool](intro/index.md)** - The problem and solution
- **[Guides](guides/explicit-calls.md)** - How-to guides
- **[Examples](examples/index.md)** - Demo project

## Reference

- **[Tools](reference/tools/index.md)** - 15+ built-in packs
- **[CLIs](reference/cli/index.md)** - ot-serve, ot-bench

## Extend

- **[Creating Tools](extending/creating-tools.md)** - Drop a file, get a pack
- **[Creating CLIs](extending/creating-clis.md)** - Build command-line tools

---

## Built-in Packs

**Search & Web**: `brave` (web, news, local, image, video), `ground` (Google grounded), `web` (fetch, extract)

**Documentation**: `context7` (library docs), `code` (semantic search), `ripgrep` (fast grep)

**Data**: `db` (SQL queries), `excel` (spreadsheets), `llm` (transform)

**Utilities**: `package` (npm, PyPI versions), `ot` (meta tools)

---

## How It Works

```python
__ot brave.search(query="AI trends 2026")
```

One prefix. Direct execution. No tool definitions. No tool selection loops.
