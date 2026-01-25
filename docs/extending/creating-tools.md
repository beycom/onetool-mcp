# Creating Tools

**One file. One pack. Instant availability.**

No registration. No configuration. Drop a Python file, restart the server, call your functions.

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

## Worker Tools

Tools with external dependencies run as isolated subprocesses using PEP 723:

```python
# /// script
# requires-python = ">=3.11"
# dependencies = ["some-library>=1.0.0", "httpx>=0.27.0", "pyyaml>=6.0.0"]
# ///
"""Tool module docstring."""

from ot_sdk import get_config, get_secret, http, log, cache, worker_main

pack = "mytool"
__all__ = ["search"]

@cache(ttl=300)  # Cache results for 5 minutes
def search(*, query: str) -> list[dict]:
    """Search for items."""
    with log("mytool.search", query=query) as s:
        api_key = get_secret("MY_API_KEY")
        response = http.get(f"https://api.example.com/search?q={query}")
        results = response.json()
        s.add("resultCount", len(results))
        return results  # Return native type directly

if __name__ == "__main__":
    worker_main()
```

> **⚠️ Critical:** The `if __name__ == "__main__": worker_main()` block is **required** for any file with a PEP 723 header. Without it, the tool will fail with "Worker for X.py closed unexpectedly" because:
> 1. PEP 723 headers mark a tool as a worker (runs in subprocess)
> 2. Workers communicate via stdin/stdout JSON-RPC
> 3. `worker_main()` provides the stdin loop that handles requests
> 4. Without it, the subprocess starts, executes module-level code, and exits immediately
>
> If you have a PEP 723 header but don't need isolated dependencies, remove the header instead of adding `worker_main()`. This lets the tool run in-process.

**⚠️ Critical:** All imports must be declared in the PEP 723 `dependencies` list. Worker tools run in isolated environments where only declared dependencies are available. If you import a module (e.g., `from pydantic import BaseModel`) without declaring it in dependencies, the worker will crash with "Worker for X.py closed unexpectedly" due to `ModuleNotFoundError`.

**Common dependencies to include:**
- `pydantic>=2.0.0` - if using `BaseModel`, `Field`, validators
- `httpx>=0.27.0` - if using the SDK's `http` module
- `pyyaml>=6.0.0` - if using YAML serialization

Run `uv run src/ot_tools/your_tool.py` locally to verify all imports resolve before deployment.

### SDK Exports

The `ot_sdk` package provides these utilities for worker tools:

| Module | Purpose |
|--------|---------|
| `worker_main` | Main loop - dispatches JSON-RPC requests to functions |
| `get_config(key)` | Access configuration from `ot-serve.yaml` |
| `get_secret(key)` | Access secrets from `secrets.yaml` |
| `http` | Pre-configured httpx client with connection pooling |
| `log(span, **kwargs)` | Structured logging context manager |
| `cache(ttl=seconds)` | In-memory caching decorator with TTL |
| `get_project_path(path)` | Resolve paths relative to project directory |
| `get_config_path(path)` | Resolve paths relative to config directory |

### HTTP Client

The SDK provides a pre-configured httpx client:

```python
from ot_sdk import http

# Simple requests
response = http.get(url, params={}, headers={}, timeout=30)
response = http.post(url, json={}, headers={})

# Custom client for different settings
client = http.client(base_url="https://api.example.com", timeout=60)
response = client.get("/endpoint")
```

### Caching

Use the `@cache` decorator for expensive operations:

```python
from ot_sdk import cache

@cache(ttl=300)  # Cache for 5 minutes
def fetch_data(*, url: str) -> str:
    """Fetch and cache data."""
    return http.get(url).text

@cache(ttl=3600)  # Cache for 1 hour
def expensive_computation(*, input: str) -> str:
    """Cache expensive results."""
    return process(input)
```

### Worker Communication Protocol

Workers communicate via JSON-RPC over stdin/stdout:

```json
Request:  {"function": "name", "kwargs": {...}, "config": {...}, "secrets": {...}}
Response: {"result": ..., "error": null} or {"result": null, "error": "message"}
```

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

### Project Paths (Reading/Writing Files)

When reading or writing files in the user's project, resolve paths relative to the project working directory:

```python
from ot_sdk import get_project_path

def save_output(*, content: str, output_file: str = "output.txt") -> str:
    """Save content to a file in the project."""
    # Resolves relative to OT_CWD (project directory)
    path = get_project_path(output_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return f"Saved to {path}"
```

**Behaviour:**

- Relative paths → resolved relative to `OT_CWD` (or `cwd` if not set)
- Absolute paths → used unchanged
- `~` → expanded to home directory

### Config Paths (Loading Assets)

When loading configuration assets like templates, schemas, or reference files defined in config, resolve paths relative to the config directory:

```python
from ot_sdk import get_config, get_config_path

def get_template(*, name: str) -> str:
    """Load a template from config."""
    templates = get_config("tools.mytool.templates") or {}
    if name not in templates:
        return f"Template not found: {name}"

    # Resolves relative to config directory (.onetool/)
    template_file = templates[name].get("file", "")
    path = get_config_path(template_file)

    if path.exists():
        return path.read_text()
    return f"Template file not found: {template_file}"
```

**Behaviour:**

- Relative paths → resolved relative to config directory
- Absolute paths → used unchanged
- `~` → expanded to home directory

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

| Function | Import From | Resolves Relative To |
|----------|-------------|---------------------|
| `get_project_path()` | `ot_sdk` | Project directory (`OT_CWD`) |
| `get_config_path()` | `ot_sdk` | Config directory (`.onetool/`) |
| `get_effective_cwd()` | `ot.paths` | Returns project directory |
| `expand_path()` | `ot_sdk` | Only expands `~` |

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
- [ ] Worker tools tested with `uv run src/ot_tools/your_tool.py`
- [ ] Attribution level determined (Based on / Inspired by / Original)
- [ ] Source header matches attribution level
- [ ] License file in `licenses/` (if "Based on")
- [ ] Tool doc attribution section matches source header