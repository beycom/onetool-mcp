# backend-onetool-util Specification

## Purpose
TBD - created by archiving change add-onetool-util. Update Purpose after archive.
## Requirements
### Requirement: Repository Structure

The `onetool-util` backend MUST be implemented as a standalone Python package with the following structure:

- Package name (PyPI): `onetool-util`
- Python module: `otutil` (PEP 8 compliant, no underscores)
- Repository: `github.com/beycom/onetool-util`
- Entry point: `onetool-util` command via CLI

#### Scenario: User installs onetool-util

```bash
# Standalone installation
$ uvx onetool-util --version
onetool-util 1.0.0

# Check available tools
$ uvx onetool-util --config ~/.onetool/util.yaml
# Server starts and exposes 64 tools via MCP protocol
```

---

### Requirement: Tool Packs

The backend MUST provide 5 tool packs with the following tools:

**file pack** (18 tools):
- read, write, edit, delete, copy, move, list, tree, search, info, and 8 more operations

**excel pack** (30 tools):
- create, read, write, add_sheet, cell_range, formula, formulas, tables, and 22 more operations

**convert pack** (5 tools):
- pdf, word, powerpoint, excel, auto (document to markdown conversion)

**brave pack** (6 tools):
- search, news, local, image, video, search_batch (Brave Search API)

**ground pack** (5 tools):
- search, search_batch, dev, docs, reddit (Google Grounding API)

#### Scenario: User calls file operations

```python
# Via onetool-mcp proxy
__ot file.read(path="test.txt")
# Returns: "file contents..."

__ot file.write(path="output.txt", content="Hello, world!")
# Returns: {"path": "output.txt", "bytes_written": 13}
```

#### Scenario: User converts documents

```python
# Convert PDF to markdown
__ot convert.pdf(path="document.pdf")
# Returns: "# Document Title\n\nContent in markdown..."

# Auto-detect format
__ot convert.auto(path="presentation.pptx")
# Returns: markdown conversion of PowerPoint slides
```

#### Scenario: User performs web search

```python
# Brave search
__ot brave.search(query="python asyncio tutorial", max_results=5)
# Returns: [{"title": "...", "url": "...", "description": "..."}]

# Grounding search with sources
__ot ground.search(query="latest Python release")
# Returns: "Python 3.13 released... [Sources: python.org, ...]"
```

---

### Requirement: Dual-Mode Operation

The backend MUST support two operational modes:

1. **Standalone mode** - Direct MCP server accessible via standard MCP protocol
2. **Proxied mode** - Backend server loaded via onetool-mcp frontend for code execution

#### Scenario: Standalone mode operation

```json
// ~/.claude/mcp.json
{
  "mcpServers": {
    "onetool-util": {
      "command": "uvx",
      "args": ["onetool-util", "--config", "~/.onetool/util.yaml"]
    }
  }
}
```

User can directly call 64 tools via MCP protocol. Token usage: ~30K tokens for tool definitions.

#### Scenario: Proxied mode operation

```json
// ~/.claude/mcp.json
{
  "mcpServers": {
    "onetool": {
      "command": "uvx",
      "args": ["onetool"]
    }
  }
}
```

```yaml
# ~/.onetool/onetool.yaml
backend_servers:
  onetool-util:
    command: uvx
    args: ["onetool-util", "--config", "~/.onetool/util.yaml"]
    enabled: true
    lazy: true
```

User calls tools via Python code execution. Token usage: ~2K tokens (single `run` tool). 95% reduction.

---

### Requirement: Configuration System

The backend MUST support configuration via YAML file at `~/.onetool/util.yaml` with the following structure:

- `log_level`: Logging verbosity (INFO, DEBUG, ERROR)
- `log_file`: Path to log file (default: `~/.onetool/logs/onetool-util.log`)
- Tool-specific config sections: `file`, `excel`, `convert`, `brave`, `ground`

#### Scenario: User configures file pack

```yaml
# ~/.onetool/util.yaml
version: 1.0.0

file:
  allowed_dirs: [".", "~/Documents"]
  exclude_patterns: [".git", "node_modules"]
  max_file_size: 10000000
  backup_on_write: true
```

File operations respect allowed directories and create backups before writes.

#### Scenario: User configures API keys

```yaml
# ~/.onetool/secrets.yaml
brave:
  api_key: "BSA..."

google:
  api_key: "AI..."
```

```yaml
# ~/.onetool/util.yaml
brave:
  api_key: ${secrets.brave.api_key}

ground:
  api_key: ${secrets.google.api_key}
```

Secrets loaded from separate file and expanded via `${secrets.key.path}` syntax.

---

### Requirement: Dependency on onetool-common

The backend MUST depend on `onetool-common>=0.1.0,<1.0.0` and use it for:

- Configuration loading with YAML includes, deep merge, and secrets expansion
- Logging setup with structured JSON output and LogSpan timing
- Path resolution for `~/.onetool/` global directory
- HTTP client helpers for API calls

#### Scenario: Backend loads configuration using onetool-common

```python
from otcommon.config import load_config

config = load_config(
    config_path="~/.onetool/util.yaml",
    secrets_path="~/.onetool/secrets.yaml"
)

# Config loaded with:
# - YAML parsing
# - ${secrets.key} expansion
# - ${env.VAR} environment variable expansion
# - Pydantic validation
```

---

### Requirement: Tool Registration Pattern

The backend MUST use the `@tool_wrapper()` decorator pattern for tool registration:

- Tools decorated with `@tool_wrapper(mcp)` from `otcommon.tools`
- MCP instance injected by server.py into tool modules
- Tools auto-register when module imported

#### Scenario: Tool registration flow

```python
# src/otutil/tools/file.py
from otcommon.tools import tool_wrapper

mcp = None  # Injected by server.py

@tool_wrapper(mcp)
def read(*, path: str) -> str:
    """Read file contents."""
    # Implementation...
```

```python
# src/otutil/server.py
from fastmcp import FastMCP
from otutil.tools import file, excel

mcp = FastMCP(name="onetool-util")

# Inject mcp instance
file.mcp = excel.mcp = mcp

# Tools auto-register via decorators
```

---

### Requirement: Testing and Quality

The backend MUST maintain the following quality standards:

- `just check` passes (lint with ruff, typecheck with mypy, test with pytest)
- Test coverage for all tool packs
- Smoke tests for server startup and tool imports
- Integration tests for end-to-end MCP communication

#### Scenario: Developer runs quality checks

```bash
$ cd onetool-util
$ just check

Lint: ✓ (ruff)
Typecheck: ✓ (mypy)
Test: ✓ (pytest - 64 tests passed)

All checks passed!
```

---

### Requirement: Documentation

The backend MUST provide:

- README.md with installation, quick start, and tool reference
- Configuration guide with examples
- API documentation for all 64 tools
- Examples for common use cases
- Agent documentation (dev/agents/hints.md, dev/agents/project-map.md)

#### Scenario: User reads documentation

```bash
$ cat README.md
# onetool-util

General-purpose utility tools for file operations, Excel, document
conversion, and search.

