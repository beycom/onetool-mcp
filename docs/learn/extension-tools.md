# Extension Tools

**Build tools in your own repository. No OneTool source required.**

Extension tools run in-process with full access to OneTool's logging, config, secrets, and inter-tool calling APIs. This is the recommended approach for most tools.

## Quick Reference

- Define `pack = "name"` and exported keyword-only functions.
- Use `@tool` only when you need its optional metadata; exported functions are
  discovered without it.
- Use OneTool APIs for config, secrets, logging, and calling other tools.
- Validate/reload quickly during development with Forge and `ot.reload()`.

## Minimal Structure

An extension needs just one file:

```
my-extension/
└── src/
    └── mytool.py    # One file. That's it.
```

### The Tool File

```python
# src/mytool.py
pack = "mytool"
__all__ = ["search"]

def search(*, query: str) -> str:
    """Search for items.

    Args:
        query: The search query

    Returns:
        Search results
    """
    return f"Found: {query}"
```

That's the minimum. One file with a `pack` declaration and exported functions.

## Function Requirements

### Keyword-Only Arguments

All tool functions MUST use keyword-only arguments:

```python
# CORRECT
def search(*, query: str, count: int = 10) -> str:
    """Search for items."""
    ...

# WRONG - will cause runtime errors
def search(query: str, count: int = 10) -> str:
    ...
```

### Docstrings

All public tool functions MUST include complete docstrings:

```python
def search(*, query: str, count: int = 10) -> str:
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

### Error Handling

Return error messages as strings, don't raise exceptions:

```python
def search(*, query: str) -> str:
    api_key = get_secret("MY_API_KEY")
    if not api_key:
        return "Error: MY_API_KEY not configured"

    try:
        result = call_api(query)
        return result
    except APIError as e:
        return f"API error: {e}"
```

## OneTool APIs

Extension tools have access to OneTool's APIs:

| Import | Purpose |
|--------|---------|
| `from ot.logging import LogSpan` | Structured logging context manager |
| `from ot.config import get_secret` | Access secrets from `secrets.yaml` |
| `from ot.config import get_tool_config` | Access tool config from `onetool.yaml` |
| `from ot.tools import call_tool` | Call another tool by name |
| `from ot.tools import get_pack` | Get a pack for multiple calls |
| `from ot.paths import resolve_cwd_path` | Resolve paths relative to project directory |

### Complete Example

```python
"""Tool with OneTool API access."""

from __future__ import annotations

pack = "mytool"

import httpx

__all__ = ["fetch"]

from ot.config import get_secret, get_tool_config
from ot.logging import LogSpan

_client = httpx.Client(timeout=30.0, follow_redirects=True)

def fetch(*, url: str) -> str:
    """Fetch a URL.

    Args:
        url: URL to fetch

    Returns:
        Page content

    Example:
        mytool.fetch(url="https://www.wikipedia.org/")
    """
    with LogSpan(span="mytool.fetch", url=url) as s:
        # Access secrets
        api_key = get_secret("MY_API_KEY")

        # Access config
        timeout = get_tool_config("mytool", "timeout", 30.0)

        response = _client.get(url)
        s.add(status=response.status_code)
        return response.text
```

### Logging with LogSpan

Use LogSpan for structured logging:

```python
from ot.logging import LogSpan

def search(*, query: str) -> list[dict]:
    """Search for items."""
    with LogSpan(span="mytools.search", query=query) as s:
        results = do_search(query)
        s.add("resultCount", len(results))
        return results
```

### Inter-Tool Calling

Extension tools can call other tools:

```python
from ot.tools import call_tool, get_pack

# Call a single tool
result = call_tool("ot_llm.transform", input=text, prompt="Summarize")

# Get a pack for multiple calls
brave = get_pack("brave")
results = brave.search(query="python tutorials")
```

## Local Development Setup

For development, create a `.onetool/` directory in your extension repository:

```
my-extension/
├── .onetool/
│   ├── onetool.yaml         # Server config (tools_dir, etc.)
│   └── secrets.yaml         # API keys for testing
└── src/
    └── mytool.py
```

### onetool.yaml

Point `tools_dir` at your extension source:

```yaml
# .onetool/onetool.yaml
tools_dir:
  - ./src/*.py
```

Run `onetool` from your extension directory. It finds
`.onetool/onetool.yaml` automatically.

### secrets.yaml

Add API keys your tool needs during development:

```yaml
# .onetool/secrets.yaml
MY_API_KEY: "dev-key-for-testing"
```

### Running Locally

From your extension directory:

```bash
# Start the server with your local config
onetool

```

## Configuration Access

Tools can define a `Config` class that is automatically discovered and validated:

```python
from pydantic import BaseModel, Field
from ot.config import get_tool_config

class Config(BaseModel):
    timeout: float = Field(default=30.0, ge=1.0, le=120.0)

def search(*, query: str, timeout: float | None = None) -> str:
    if timeout is None:
        config = get_tool_config("mytool", Config)
        timeout = config.timeout
    # ...
```

## Path Resolution

Tools work with two path contexts:

| Context | Use For | Relative To |
|---------|---------|-------------|
| **Project paths** | Reading/writing project files | `OT_CWD` (working directory) |
| **Config paths** | Loading config assets | Config directory (`.onetool/`) |

```python
from ot.paths import resolve_cwd_path, resolve_ot_path

# Relative to project directory
output = resolve_cwd_path("output/report.txt")

# Relative to config directory
template = resolve_ot_path("templates/default.mmd")
```

## Consumer Installation

When users want to use your extension, they add it to their `tools_dir`:

### Global Installation

```yaml
# ~/.onetool/onetool.yaml
tools_dir:
  - ~/extensions/my-extension/src/*.py
```

### Project-Specific

```yaml
# project/.onetool/onetool.yaml
tools_dir:
  - ~/extensions/my-extension/src/*.py
  - ./local-tools/*.py
```

## Testing Your Tools

Test your extension functions directly without running `onetool`:

```python
# test_mytool.py
from mytool import search

def test_search():
    result = search(query="python")
    assert "python" in result.lower()
```

Run with pytest:

```bash
cd src
python -m pytest ../test_mytool.py
```

## Creating Tools with Forge

Use the forge tool to generate new extensions:

```python
# Create an extension tool
ot_forge.create_ext(name="my_tool", function="search")
```

Validate before reloading:

```python
ot_forge.validate_ext(path=".onetool/tools/my_tool/my_tool.py")
```

Configured extensions run in the OneTool process. Install their dependencies
in the same OneTool environment; inline PEP 723 script blocks are treated as
ordinary comments and do not install packages or change execution routing.

## Larger Extensions

For larger extensions, organize implementation in a subpackage:

```
my-extension/
├── .onetool/
│   ├── onetool.yaml
│   └── secrets.yaml
├── src/
│   ├── convert.py           # Main tool file
│   └── _convert/            # Implementation modules
│       ├── __init__.py
│       ├── pdf.py
│       └── word.py
└── README.md
```

The main tool file imports from the implementation package:

```python
"""Document conversion tools."""

from __future__ import annotations

pack = "convert"
__all__ = ["pdf", "word"]

from ot.logging import LogSpan
from _convert import convert_pdf, convert_word

def pdf(*, pattern: str, output_dir: str = "output") -> str:
    """Convert PDF files to markdown."""
    with LogSpan(span="convert.pdf", pattern=pattern) as s:
        return convert_pdf(pattern, output_dir)
```

## Checklist

- [ ] `pack = "..."` before imports
- [ ] `__all__ = [...]` listing exports
- [ ] All functions use keyword-only arguments (`*,`)
- [ ] Complete docstrings with Args, Returns, Example
- [ ] Error handling returning strings (not raising exceptions)
- [ ] LogSpan logging for operations
- [ ] Secrets in `secrets.yaml`
