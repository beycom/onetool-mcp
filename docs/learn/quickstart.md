# Quickstart

**30 seconds to install. 2 minutes to first tool call.**

## 1. Install

```bash
uv tool install onetool-mcp
```

Or with pip:

```bash
pip install onetool-mcp
```

## 2. Connect to Claude Code

Add to `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "onetool": {
      "command": "ot-serve"
    }
  }
}
```

## 3. Use It

```python
__ot brave.search(query="AI news")
```

That's it. One tool, unlimited capabilities.

---

**Next**: [Installation](installation.md) (all platforms) | [Configuration](configuration.md) | [Tools Reference](../reference/tools/index.md)
