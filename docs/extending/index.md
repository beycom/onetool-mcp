# Extending OneTool

**Drop a file. Get a pack. No registration.**

Adding tools to OneTool is trivial - create a Python file, declare a pack, and you're done.

## Developer Guides

| Guide | Description |
|-------|-------------|
| [Creating Tools](creating-tools.md) | Add custom tool functions |
| [Creating Plugins](plugins.md) | Build tools in separate repositories |
| [Creating CLIs](creating-clis.md) | Build command-line interfaces |
| [Testing](testing.md) | Test markers and organization |
| [Logging](logging.md) | Structured logging with LogSpan |

## Quick Start: Adding a Tool

1. Create a file in `src/ot_tools/`:

```python
# src/ot_tools/mytool.py
pack = "mytool"

__all__ = ["search"]

def search(*, query: str) -> str:
    """Search for items.

    Args:
        query: Search query

    Returns:
        Search results
    """
    return f"Results for: {query}"
```

2. Restart `ot-serve` - the tool is auto-discovered.

3. Use it:

```python
__ot mytool.search(query="test")
```

## Architecture

```
src/
├── ot/           # Core library
├── ot_sdk/       # SDK for extension tools
├── ot_tools/     # Built-in tools (auto-discovered)
├── ot_serve/     # CLI: ot-serve
└── ot_bench/     # CLI: ot-bench
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Install dev dependencies: `uv sync --group dev`
4. Make changes
5. Run tests: `uv run pytest`
6. Submit a pull request

## Code Style

- Format with `ruff format`
- Lint with `ruff check`
- Type check with `mypy`
