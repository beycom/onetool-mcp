# Creating Tools

**One file. One pack. Instant availability.**

No registration. No configuration. Drop a Python file, restart the server, call your functions.

## Tool Types

OneTool supports two types of tools:

| Type          | Location           | Execution         | Use Case                   |
|---------------|--------------------| ------------------|----------------------------|
| **Internal**  | `src/ot_tools/`    | In-process        | Bundled tools with OneTool |
| **Extension** | `.onetool/tools/`  | Worker subprocess | User-created tools         |

**Extension tools** (covered below) run in-process using `ot.*` imports. For tools requiring dependency isolation, use PEP 723 headers to run as standalone subprocesses (no onetool imports).

If you're creating a tool for your project, follow the **Extension** pattern.

## File Structure

Each tool file follows this structure:

```python
"""Tool module docstring.

Brief description of what the tool does.
Requirements (e.g., "Requires MY_API_KEY in secrets.yaml").
"""

from __future__ import annotations

# Pack declaration MUST be before other imports
pack = "mytools"

# Export only these functions as tools
__all__ = ["search", "fetch", "batch"]

from typing import Any, Literal

from ot.config.secrets import get_secret
from ot.logging import LogSpan
```

## Pack Declaration

The `pack` variable enables dot notation:

```python
pack = "brave"  # Exposes brave.search(), brave.news()
pack = "web"    # Exposes web.fetch(), web.fetch_batch()
```

**Important**: The pack declaration must appear before other imports (except `from __future__`).

## Export Control

Use `__all__` to declare which functions are exposed as tools:

```python
__all__ = ["search", "fetch", "batch"]  # Only these become tools
```

Without `__all__`, imported functions would be incorrectly exposed as tools.

## Function Signatures

**All tool functions MUST use keyword-only arguments:**

```python
# CORRECT
def search(
    *,
    query: str,
    count: int = 10,
) -> str:
    """Search for items."""
    ...

# WRONG - will cause runtime errors
def search(query: str, count: int = 10) -> str:
    ...
```

## Docstring Format

All public tool functions MUST include complete docstrings:

```python
def search(
    *,
    query: str,
    count: int = 10,
) -> str:
    """Search for items.

    Args:
        query: The search query string
        count: Number of results (1-20, default: 10)

    Returns:
        Formatted search results

    Example:
        mytools.search(query="python async", count=5)
    """
```

## Logging with LogSpan

All public tool functions must use LogSpan:

```python
from ot.logging import LogSpan

def search(*, query: str) -> list[dict]:
    """Search for items."""
    with LogSpan(span="mytools.search", query=query) as s:
        results = do_search(query)
        s.add("resultCount", len(results))
        return results  # Return native type directly
```

## Error Handling

Return error messages as strings, don't raise exceptions:

```python
def search(*, query: str) -> str:
    with LogSpan(span="mytools.search", query=query) as s:
        api_key = get_secret("MY_API_KEY")
        if not api_key:
            s.add("error", "no_api_key")
            return "Error: MY_API_KEY not configured"

        try:
            result = call_api(query)
            return result  # Return native type directly
        except APIError as e:
            s.add("error", str(e))
            return f"API error: {e}"
```

## Lazy Imports for Optional Dependencies

Tools with optional dependencies must use **lazy imports** inside functions, not at module level. This ensures the tool module loads successfully even when the dependency is not installed - the error only occurs when the user calls a function that needs it.

**Wrong** - fails at module load:

```python
# Module level import - BREAKS tool loading if duckdb not installed
import duckdb

def search(*, query: str) -> str:
    conn = duckdb.connect(":memory:")
    ...
```

**Correct** - lazy import inside function:

```python
def search(*, query: str) -> str:
    """Search using DuckDB."""
    try:
        import duckdb
    except ImportError as e:
        raise ImportError(
            "duckdb is required for search. Install with: pip install duckdb"
        ) from e

    conn = duckdb.connect(":memory:")
    ...
```

For type hints, use `TYPE_CHECKING`:

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from openai import OpenAI

def _get_client() -> "OpenAI":
    """Get OpenAI client with lazy import."""
    try:
        from openai import OpenAI
    except ImportError as e:
        raise ImportError(
            "openai is required. Install with: pip install openai"
        ) from e
    return OpenAI(api_key=get_secret("OPENAI_API_KEY"))
```

## Extension Tools

Extension tools run in-process and use `ot.*` imports:

```python
"""Tool module docstring."""

from __future__ import annotations

pack = "mytool"
__all__ = ["search"]

from ot.config.secrets import get_secret
from ot.logging import LogSpan

def search(*, query: str) -> list[dict]:
    """Search for items."""
    with LogSpan(span="mytool.search", query=query) as s:
        api_key = get_secret("MY_API_KEY")
        # ... make API call ...
        s.add("resultCount", len(results))
        return results
```

### Isolated Tools (PEP 723)

For tools requiring dependency isolation, use PEP 723 headers. These run as standalone subprocesses with **no onetool imports**:

```python
# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx>=0.27.0"]
# ///
"""Isolated tool - runs via uv run with own dependencies."""

import sys
import json

pack = "mytool"
__all__ = ["search"]

def search(*, query: str) -> str:
    """Search for items."""
    import httpx
    response = httpx.get(f"https://api.example.com/search?q={query}")
    return response.text

# JSON-RPC stdin loop for subprocess communication
if __name__ == "__main__":
    for line in sys.stdin:
        req = json.loads(line)
        func = globals()[req["function"]]
        try:
            result = func(**req["kwargs"])
            print(json.dumps({"result": result, "error": None}))
        except Exception as e:
            print(json.dumps({"result": None, "error": str(e)}))
        sys.stdout.flush()
```

**⚠️ Critical:** All imports must be declared in the PEP 723 `dependencies` list. If you import a module without declaring it, the subprocess will crash with `ModuleNotFoundError`.

Run `uv run your_tool.py` locally to verify all imports resolve.

## Configuration Access

Tools can define a `Config` class that is automatically discovered and validated:

```python
from pydantic import BaseModel, Field

from ot.config import get_tool_config

# Define config schema - discovered automatically by the registry
class Config(BaseModel):
    timeout: float = Field(default=30.0, ge=1.0, le=120.0)

def search(*, query: str, timeout: float | None = None) -> str:
    if timeout is None:
        config = get_tool_config("mytool", Config)
        timeout = config.timeout
    # ...
```

The `Config` class is discovered from your tool file automatically - no need to modify `loader.py`.

## Path Resolution

Tools work with two path contexts:

| Context | Use For | Relative To |
|---------|---------|-------------|
| **Project paths** | Reading/writing project files | `OT_CWD` (working directory) |
| **Config paths** | Loading config assets (templates, etc.) | Config directory (`.onetool/`) |

### Path Prefixes

Path functions support prefixes to override the default base:

| Prefix    | Meaning                   | Use Case                       |
|-----------|---------------------------|--------------------------------|
| `~`       | Home directory            | Cross-project shared files     |
| `CWD/`    | Project working directory | Tool I/O files                 |
| `GLOBAL/` | `~/.onetool/`             | Global config/logs             |
| `OT_DIR/` | Active `.onetool/`        | Project-first, global fallback |

```python
from ot.paths import resolve_cwd_path, resolve_ot_path

# Default: relative to project directory
output = resolve_cwd_path("output/report.txt")

# Prefix overrides base
global_log = resolve_cwd_path("GLOBAL/logs/app.log")  # ~/.onetool/logs/app.log
template = resolve_ot_path("templates/default.mmd")    # .onetool/templates/default.mmd
```

### Project Paths (Reading/Writing Files)

When reading or writing files in the user's project, resolve paths relative to the project working directory:

```python
from ot.paths import resolve_cwd_path

def save_output(*, content: str, output_file: str = "output.txt") -> str:
    """Save content to a file in the project."""
    # Resolves relative to OT_CWD (project directory)
    path = resolve_cwd_path(output_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return f"Saved to {path}"
```

**Behaviour:**

- Relative paths → resolved relative to `OT_CWD` (or `cwd` if not set)
- Absolute paths → used unchanged
- `~` → expanded to home directory
- Prefixes (`CWD/`, `GLOBAL/`, `OT_DIR/`) → override the default base

### Config Paths (Loading Assets)

When loading configuration assets like templates, schemas, or reference files defined in config, resolve paths relative to the config directory:

```python
from ot.config import get_tool_config
from ot.paths import resolve_ot_path

def get_template(*, name: str) -> str:
    """Load a template from config."""
    config = get_tool_config("mytool")
    templates = getattr(config, "templates", {}) or {}
    if name not in templates:
        return f"Template not found: {name}"

    # Resolves relative to config directory (.onetool/)
    template_file = templates[name].get("file", "")
    path = resolve_ot_path(template_file)

    if path.exists():
        return path.read_text()
    return f"Template file not found: {template_file}"
```

**Behaviour:**

- Relative paths → resolved relative to config directory
- Absolute paths → used unchanged
- `~` → expanded to home directory
- Prefixes (`CWD/`, `GLOBAL/`, `OT_DIR/`) → override the default base

### Main Process Tools

For tools running in the main process (not workers), use `ot.paths`:

```python
from ot.paths import get_effective_cwd, expand_path

def list_files(*, directory: str = ".") -> str:
    """List files in a directory."""
    # get_effective_cwd() returns OT_CWD or Path.cwd()
    base = get_effective_cwd()
    target = base / directory
    # ...
```

### Summary

| Function             | Import From | Resolves Relative To           |
|----------------------|-------------|--------------------------------|
| `resolve_cwd_path()` | `ot.paths`  | Project directory (`OT_CWD`)   |
| `resolve_ot_path()`  | `ot.paths`  | Config directory (`.onetool/`) |
| `get_effective_cwd()`| `ot.paths`  | Returns project directory      |
| `expand_path()`      | `ot.paths`  | Only expands `~`               |

## Attribution & Licensing

When creating tools based on or inspired by external projects, follow this three-tier attribution model:

| Level | When to Use | Source Header | License File | Tool Doc |
|-------|-------------|---------------|--------------|----------|
| **Based on** | Code derived or ported from upstream | Required | Required in `licenses/` | Include "Based on" section |
| **Inspired by** | Similar functionality, independent code | Required | Not required | Include "Inspired by" section |
| **Original** | Clean room implementation, API wrappers | Optional `API docs:` | Not required | No attribution section |

### Source Header Format

Add attribution to the module docstring:

```python
# Based on (code derived from upstream)
"""Database operations via SQLAlchemy.

Based on mcp-alchemy by Rui Machado (MPL-2.0).
https://github.com/runekaagaard/mcp-alchemy
"""

# Inspired by (independent implementation)
"""Secure file operations with configurable boundaries.

Inspired by fast-filesystem-mcp by efforthye (Apache 2.0).
https://github.com/efforthye/fast-filesystem-mcp
"""

# Original (API wrapper or clean room)
"""Web search via Brave Search API.

API docs: https://api.search.brave.com/app/documentation
"""
```

### License File Requirements

For "Based on" tools, include the upstream license:

1. Copy the upstream LICENSE file to `licenses/{project-name}-LICENSE`
2. Use the exact project name from the source header
3. Example: `licenses/mcp-alchemy-LICENSE` for database tool

### Documentation Requirements

| Level | Tool Doc Attribution |
|-------|---------------------|
| Based on | Add "## Based on" section at end with project link, author, license |
| Inspired by | Add "## Inspired by" section at end with project link, author, license |
| Original | No attribution section; include "## Source" linking to API docs |

## Checklist

- [ ] Module docstring with description
- [ ] `pack = "..."` before imports
- [ ] `__all__ = [...]` listing exports
- [ ] All functions use keyword-only arguments (`*,`)
- [ ] Complete docstrings with Args, Returns, Example
- [ ] LogSpan logging for all operations
- [ ] Error handling returning strings
- [ ] Secrets in `secrets.yaml`
- [ ] Dependencies in `pyproject.toml` or PEP 723 (all imports declared)
- [ ] Extension tools tested with `uv run src/ot_tools/your_tool.py`
- [ ] Attribution level determined (Based on / Inspired by / Original)
- [ ] Source header matches attribution level
- [ ] License file in `licenses/` (if "Based on")
- [ ] Tool doc attribution section matches source header

## Architecture

```text
src/
├── ot/           # Core library (config, logging, paths, utils)
├── ot_tools/     # Built-in tools (auto-discovered)
├── onetool/      # CLI: onetool
└── bench/        # CLI: bench
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
