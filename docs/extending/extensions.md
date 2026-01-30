# Creating Extensions

**Build tools in your own repository. No onetool source required.**

Extensions let you develop OneTool tools in separate repositories while using local configuration for development and testing.

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
│   ├── ot-serve.yaml     # Server config (tools_dir, etc.)
│   ├── secrets.yaml      # API keys for testing
│   └── ot-bench.yaml     # Benchmark harness config (optional)
├── demo.yaml             # Test scenarios (ot-bench run demo.yaml)
└── src/
    └── mytool.py
```

### `.onetool/ot-serve.yaml`

Point `tools_dir` at your extension source:

```yaml
# .onetool/ot-serve.yaml
tools_dir:
  - ./src/*.py
```

Run `ot-serve` from your extension directory. It finds `.onetool/ot-serve.yaml` automatically.

### `.onetool/secrets.yaml`

Add API keys your tool needs during development:

```yaml
# .onetool/secrets.yaml
MY_API_KEY: "dev-key-for-testing"
```

### `.onetool/ot-bench.yaml`

Configure the benchmark harness (model, evaluators, server definitions):

```yaml
# .onetool/ot-bench.yaml
defaults:
  timeout: 60
  model: anthropic/claude-sonnet-4

servers:
  mytool:
    type: stdio
    command: ot-serve
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

Run tests with: `ot-bench run demo.yaml`

## Running Locally

From your extension directory:

```bash
# Start the server with your local config
ot-serve

# In another terminal, run benchmarks
ot-bench
```

The server discovers your tool from the local `tools_dir` configuration.

## Extension Tools (with dependencies)

If your tool needs external packages, use PEP 723 headers and run as an isolated subprocess:

```python
# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx>=0.28.0"]
# ///
"""Tool with external dependencies."""

from __future__ import annotations

pack = "mytool"
__all__ = ["fetch"]

from ot_sdk import http, log, worker_main

def fetch(*, url: str) -> str:
    """Fetch a URL.

    Args:
        url: URL to fetch

    Returns:
        Page content
    """
    with log("mytool.fetch", url=url) as s:
        response = http.get(url)
        s.add(status=response.status_code)
        return response.text

if __name__ == "__main__":
    worker_main()
```

**Critical**: The `if __name__ == "__main__": worker_main()` block is required for any file with a PEP 723 header. Without it, the tool fails with "Worker closed unexpectedly".

### SDK Exports

The `ot_sdk` package provides utilities for extension tools:

| Export | Purpose |
|--------|---------|
| `worker_main` | Main loop - handles JSON-RPC requests |
| `get_config(key)` | Access configuration from `ot-serve.yaml` |
| `get_secret(key)` | Access secrets from `secrets.yaml` |
| `http` | Pre-configured httpx client |
| `log(span, **kwargs)` | Structured logging context manager |
| `cache(ttl=seconds)` | In-memory caching decorator |
| `resolve_cwd_path(path)` | Resolve paths relative to project directory |
| `resolve_ot_path(path)` | Resolve paths relative to config directory |

### Path Prefixes

Path functions support prefixes to override the default base:

| Prefix    | Meaning                  | Use Case                       |
|-----------|--------------------------|--------------------------------|
| `~`       | Home directory           | Cross-project shared files     |
| `CWD/`    | Project working directory| Tool I/O files                 |
| `GLOBAL/` | `~/.onetool/`            | Global config/logs             |
| `OT_DIR/` | Active `.onetool/`       | Project-first, global fallback |

```python
from ot_sdk import resolve_cwd_path, resolve_ot_path

# Default: relative to project directory
output = resolve_cwd_path("output/report.txt")

# Prefix overrides base
global_log = resolve_cwd_path("GLOBAL/logs/app.log")  # ~/.onetool/logs/app.log
template = resolve_ot_path("templates/default.mmd")    # .onetool/templates/default.mmd
```

## Consumer Installation

When users want to use your extension, they add it to their `tools_dir`:

### Global installation

```yaml
# ~/.onetool/ot-serve.yaml
tools_dir:
  - ~/extensions/ot-mytool/src/*.py
```

### Project-specific

```yaml
# project/.onetool/ot-serve.yaml
tools_dir:
  - ~/extensions/ot-mytool/src/*.py
  - ./local-tools/*.py
```

Glob patterns work for selecting tool files.

## Testing Without Full Installation

Test your extension functions directly without running `ot-serve`:

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

For extension tools, test the functions before adding `worker_main()`:

```python
# Test individual functions
from mytool import fetch

def test_fetch():
    # Mock http if needed
    result = fetch(url="https://example.com")
    assert result
```

## Example: Extension with Implementation Modules

For larger extensions, organize implementation in a subpackage:

```
ot-convert/
├── .onetool/
│   ├── ot-serve.yaml
│   └── secrets.yaml
├── src/
│   ├── convert.py           # Main tool file (worker)
│   └── _convert/            # Implementation modules
│       ├── __init__.py
│       ├── pdf.py
│       └── word.py
└── README.md
```

The main tool file imports from the implementation package:

```python
# /// script
# requires-python = ">=3.11"
# dependencies = ["pymupdf>=1.24.0", "python-docx>=1.1.0"]
# ///
"""Document conversion tools."""

from __future__ import annotations

pack = "convert"
__all__ = ["pdf", "word"]

from ot_sdk import get_project_path, log, worker_main

from _convert import convert_pdf, convert_word

def pdf(*, pattern: str, output_dir: str = "output") -> str:
    """Convert PDF files to markdown."""
    with log("convert.pdf", pattern=pattern) as s:
        return convert_pdf(pattern, output_dir)

def word(*, pattern: str, output_dir: str = "output") -> str:
    """Convert Word documents to markdown."""
    with log("convert.word", pattern=pattern) as s:
        return convert_word(pattern, output_dir)

if __name__ == "__main__":
    worker_main()
```