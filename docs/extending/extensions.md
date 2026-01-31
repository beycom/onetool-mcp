# Creating Extensions

**Build tools in your own repository. No onetool source required.**

Extensions let you develop OneTool tools in separate repositories while using local configuration for development and testing.

## Tool Types

OneTool supports three types of tools:

| Type | Description | Template | Imports |
|------|-------------|----------|---------|
| **Bundled Tool** | Shipped with onetool | N/A (`src/ot_tools/`) | `from ot.*` |
| **Extension Tool** | User-built, no external deps | `extension` | `from ot.*` |
| **Isolated Tool** | User-built, external deps | `isolated` | None (standalone) |

**Extension tools** (recommended) run in-process and have full access to onetool's logging, config, and inter-tool calling APIs.

**Isolated tools** run in subprocesses with their own dependencies via PEP 723. They are fully standalone with no onetool imports.

## Minimal Structure

An extension needs just one file:

```
ot-mytool/
└── src/
    └── mytool.py    # One file. That's it.
```

### The tool file

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

## Local Development Setup

For development, create a `.onetool/` directory in your extension repository:

```
ot-mytool/
├── .onetool/
│   ├── onetool.yaml     # Server config (tools_dir, etc.)
│   ├── secrets.yaml      # API keys for testing
│   └── bench.yaml     # Benchmark harness config (optional)
├── demo.yaml             # Test scenarios (bench run demo.yaml)
└── src/
    └── mytool.py
```

### `.onetool/onetool.yaml`

Point `tools_dir` at your extension source:

```yaml
# .onetool/onetool.yaml
tools_dir:
  - ./src/*.py
```

Run `onetool` from your extension directory. It finds `.onetool/onetool.yaml` automatically.

### `.onetool/secrets.yaml`

Add API keys your tool needs during development:

```yaml
# .onetool/secrets.yaml
MY_API_KEY: "dev-key-for-testing"
```

### `.onetool/bench.yaml`

Configure the benchmark harness (model, evaluators, server definitions):

```yaml
# .onetool/bench.yaml
defaults:
  timeout: 60
  model: anthropic/claude-sonnet-4

servers:
  mytool:
    type: stdio
    command: onetool
```

### Test Scenario Files

Define test scenarios in a separate YAML file:

```yaml
# demo.yaml
scenarios:
  - name: "Basic search test"
    tasks:
      - name: "search:basic"
        server: mytool
        prompt: "Search for python tutorials using mytool.search"
```

Run tests with: `bench run demo.yaml`

## Running Locally

From your extension directory:

```bash
# Start the server with your local config
onetool

# In another terminal, run benchmarks
bench
```

The server discovers your tool from the local `tools_dir` configuration.

## Extension Tools (recommended)

Extension tools run in-process with full access to onetool's APIs:

```python
"""Tool with onetool access."""

from __future__ import annotations

pack = "mytool"

import httpx

__all__ = ["fetch"]

from ot.config import get_secret, get_tool_config
from ot.logging import LogSpan
# from ot.tools import call_tool, get_pack  # For inter-tool calling

_client = httpx.Client(timeout=30.0, follow_redirects=True)

def fetch(*, url: str) -> str:
    """Fetch a URL.

    Args:
        url: URL to fetch

    Returns:
        Page content

    Example:
        mytool.fetch(url="https://example.com")
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

### Extension Tool APIs

| Import | Purpose |
|--------|---------|
| `from ot.logging import LogSpan` | Structured logging context manager |
| `from ot.config import get_secret` | Access secrets from `secrets.yaml` |
| `from ot.config import get_tool_config` | Access tool config from `onetool.yaml` |
| `from ot.tools import call_tool` | Call another tool by name |
| `from ot.tools import get_pack` | Get a pack for multiple calls |
| `from ot.paths import resolve_cwd_path` | Resolve paths relative to project directory |

### Inter-Tool Calling

Extension tools can call other tools:

```python
from ot.tools import call_tool, get_pack

# Call a single tool
result = call_tool("llm.transform", input=text, prompt="Summarize")

# Get a pack for multiple calls
brave = get_pack("brave")
results = brave.search(query="python tutorials")
```

## Isolated Tools (for external dependencies)

If your tool needs external packages that aren't bundled with onetool, use an isolated tool with PEP 723 headers:

```python
# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy>=2.0.0"]
# ///
"""Tool with external dependencies."""

from __future__ import annotations

import json
import sys

import numpy as np

pack = "mytool"
__all__ = ["analyze"]

def analyze(*, data: list[float]) -> str:
    """Analyze numerical data.

    Args:
        data: List of numbers

    Returns:
        Analysis results

    Example:
        mytool.analyze(data=[1.0, 2.0, 3.0])
    """
    arr = np.array(data)
    return f"Mean: {arr.mean():.2f}, Std: {arr.std():.2f}"

# JSON-RPC main loop for subprocess communication
if __name__ == "__main__":
    _functions = {
        "analyze": analyze,
    }
    for line in sys.stdin:
        request = json.loads(line)
        func = _functions.get(request["function"])
        if func is None:
            print(json.dumps({"error": f"Unknown function: {request['function']}"}), flush=True)
            continue
        try:
            result = func(**request.get("kwargs", {}))
            print(json.dumps({"result": result}), flush=True)
        except Exception as e:
            print(json.dumps({"error": str(e)}), flush=True)
```

**Critical**: The `if __name__ == "__main__":` block with the JSON-RPC loop is required for isolated tools. Without it, the tool fails with "Worker closed unexpectedly".

### Isolated Tool Limitations

Isolated tools cannot:

- Access secrets (use environment variables instead)
- Access onetool config (hardcode values)
- Use structured logging
- Call other tools

This trade-off provides full dependency isolation and crash safety.

## Consumer Installation

When users want to use your extension, they add it to their `tools_dir`:

### Global installation

```yaml
# ~/.onetool/onetool.yaml
tools_dir:
  - ~/extensions/ot-mytool/src/*.py
```

### Project-specific

```yaml
# project/.onetool/onetool.yaml
tools_dir:
  - ~/extensions/ot-mytool/src/*.py
  - ./local-tools/*.py
```

Glob patterns work for selecting tool files.

## Testing Without Full Installation

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

## Creating Tools with Scaffold

Use the scaffold tool to generate new extensions:

```python
# Create an extension tool (in-process, recommended)
scaffold.create(name="my_tool", function="search")

# Create an isolated tool (subprocess, for external deps)
scaffold.create(name="numpy_tool", template="isolated")
```

Validate before reloading:

```python
scaffold.validate(path=".onetool/tools/my_tool/my_tool.py")
```

## Example: Extension with Implementation Modules

For larger extensions, organize implementation in a subpackage:

```
ot-convert/
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

def word(*, pattern: str, output_dir: str = "output") -> str:
    """Convert Word documents to markdown."""
    with LogSpan(span="convert.word", pattern=pattern) as s:
        return convert_word(pattern, output_dir)
```
