# Design: add-onetool-util

**Proposal:** `proposal.md`
**Tasks:** `tasks.md`

---

## Architectural Overview

### System Context

`onetool-util` is a standalone MCP server that can operate in two modes:

1. **Standalone mode** - Direct MCP server, ~30K tokens, standard MCP protocol
2. **Proxied mode** - Via onetool-mcp frontend, ~2K tokens, code execution paradigm

```
┌─────────────────────────────────────────────────────────┐
│                    Claude Code Client                    │
└─────────────────┬───────────────────────────────────────┘
                  │
        ┌─────────┴──────────┐
        │                    │
   Standalone           Proxied Mode
   Mode (Direct)        (via onetool-mcp)
        │                    │
        │         ┌──────────▼──────────┐
        │         │   onetool-mcp       │
        │         │   (frontend)        │
        │         └──────────┬──────────┘
        │                    │
        │         ┌──────────▼──────────┐
        └────────►│   onetool-util      │
                  │   (backend)         │
                  │                     │
                  │ Packs:              │
                  │ - file   (18 tools) │
                  │ - excel  (30 tools) │
                  │ - convert (5 tools) │
                  │ - brave   (6 tools) │
                  │ - ground  (5 tools) │
                  └─────────────────────┘
```

### Design Principles

1. **Complete Independence**
   - No knowledge of onetool-mcp
   - Works as standalone MCP server
   - Standard MCP protocol only
   - No special parent-child relationship

2. **Code Reuse via Library**
   - Depends on `onetool-common` for shared code
   - Config loading, logging, utilities
   - No code duplication
   - Versioned dependency

3. **Tool Integrity**
   - Tools extracted verbatim from onetool-mcp
   - Only import paths change
   - Behavior preserved exactly
   - Tests verify equivalence

4. **Clean Boundaries**
   - Self-contained package
   - Own config file
   - Own logging
   - Own dependencies

---

## Component Design

### 1. Server Architecture

```python
# src/otutil/server.py

from fastmcp import FastMCP
from otcommon.config import load_config
from otcommon.logging import setup_logging
from otutil.tools import file, excel, convert, brave, ground

def create_server(config_path: str, secrets_path: str | None = None) -> FastMCP:
    """Create and configure the MCP server."""

    # Load config using onetool-common
    config = load_config(config_path, secrets_path)

    # Setup logging using onetool-common
    setup_logging(
        level=config.get("log_level", "INFO"),
        log_file=config.get("log_file"),
        backend_name="onetool-util"
    )

    # Create FastMCP server
    mcp = FastMCP(
        name="onetool-util",
        instructions="""
        OneTool Utilities Server

        General-purpose utility tools for file operations, Excel manipulation,
        document conversion, web search, and AI-powered grounding search.

        Available packs:
        - file: Read, write, edit, delete, copy, move, list, search files
        - excel: Create, read, write Excel workbooks, formulas, tables
        - convert: Convert PDF, Word, PowerPoint, Excel to markdown
        - brave: Web search using Brave Search API
        - ground: AI-powered search with sources using Google Grounding

        All tools accept keyword arguments only.
        """
    )

    # Inject mcp instance into tool modules for @tool_wrapper
    file.mcp = mcp
    excel.mcp = mcp
    convert.mcp = mcp
    brave.mcp = mcp
    ground.mcp = mcp

    # Tools auto-register via @tool_wrapper decorators

    return mcp


def main() -> None:
    """Run the MCP server."""
    import typer
    from pathlib import Path

    app = typer.Typer()

    @app.command()
    def serve(
        config: Path = typer.Option(
            Path.home() / ".onetool" / "util.yaml",
            "--config",
            "-c",
            help="Path to config file"
        ),
        secrets: Path | None = typer.Option(
            None,
            "--secrets",
            "-s",
            help="Path to secrets file"
        ),
    ) -> None:
        """Start the onetool-util MCP server."""
        mcp = create_server(str(config), str(secrets) if secrets else None)
        mcp.run(transport="stdio")

    app()


if __name__ == "__main__":
    main()
```

**Design decisions:**

- **FastMCP Framework**: Proven, lightweight, standard
- **Config-driven**: All settings externalized
- **Dependency Injection**: mcp instance injected into tool modules
- **Clean Entry Point**: Simple, testable server factory

---

### 2. Tool Registration Pattern

```python
# src/otutil/tools/file.py

from otcommon.tools import tool_wrapper
from otcommon.config import get_tool_config
from pydantic import BaseModel

pack = "file"

# MCP instance injected by server.py
mcp = None


class FileConfig(BaseModel):
    """Configuration for file pack."""
    allowed_dirs: list[str] = ["."]
    exclude_patterns: list[str] = [".git", "node_modules"]
    max_file_size: int = 10_000_000
    backup_on_write: bool = True


def _get_config() -> FileConfig:
    """Get file pack configuration."""
    return get_tool_config("file", FileConfig)


@tool_wrapper(mcp)
def read(*, path: str) -> str:
    """Read file contents.

    Args:
        path: Path to file relative to working directory

    Returns:
        File contents as string

    Raises:
        FileNotFoundError: If file doesn't exist
        PermissionError: If file not in allowed directories
    """
    config = _get_config()
    # ... implementation
```

**Design decisions:**

- **Decorator Pattern**: Clean, minimal boilerplate
- **Pydantic Config**: Type-safe configuration models
- **Lazy Config Loading**: Only load when tool called
- **Consistent Interface**: All tools follow same pattern

**Tool registration flow:**

```
1. server.py creates mcp instance
2. server.py imports tool modules (file, excel, etc.)
3. server.py injects: file.mcp = excel.mcp = ... = mcp
4. @tool_wrapper decorators register functions with mcp
5. All tools now available via MCP protocol
```

---

### 3. Configuration Architecture

```yaml
# ~/.onetool/util.yaml

version: 1.0.0

# Logging configuration
log_level: INFO
log_file: ~/.onetool/logs/onetool-util.log

# Tool-specific configuration
file:
  allowed_dirs: ["."]
  exclude_patterns: [".git", "node_modules", "__pycache__"]
  max_file_size: 10000000  # 10 MB
  backup_on_write: true

excel:
  max_file_size: 100000000  # 100 MB
  default_sheet: "Sheet1"

convert:
  default_format: markdown
  max_workers: 4
  output_dir: "./output"

brave:
  timeout: 30
  max_results: 10
  api_key: ${secrets.brave.api_key}  # Reference to secrets

ground:
  timeout: 30
  max_sources: 5
  model: gemini-2.0-flash-exp
  api_key: ${secrets.google.api_key}  # Reference to secrets
```

```yaml
# ~/.onetool/secrets.yaml (shared across backends)

brave:
  api_key: "BSA..."

google:
  api_key: "AI..."
```

**Configuration loading:**

```python
# In server.py
config = load_config(
    config_path="~/.onetool/util.yaml",
    secrets_path="~/.onetool/secrets.yaml"  # Optional
)

# otcommon.config handles:
# 1. YAML parsing
# 2. ${secrets.key.path} expansion
# 3. Environment variable expansion: ${env.VAR_NAME}
# 4. Deep merge with defaults
# 5. Pydantic validation
```

**Environment variable fallback:**

```bash
# Can override via environment
export BRAVE_API_KEY="BSA..."
export GEMINI_API_KEY="AI..."

# Config can reference:
brave:
  api_key: ${env.BRAVE_API_KEY}
```

**Design decisions:**

- **Separate config file**: Clean separation from core
- **Secrets separation**: Security best practice
- **Variable expansion**: Flexible credential management
- **Tool namespaces**: Each pack has own config section

---

### 4. Dependency Management

```toml
# pyproject.toml

[project]
name = "onetool-util"
version = "1.0.0"
requires-python = ">=3.11"
dependencies = [
    # Core framework
    "fastmcp>=2.14.0,<3.0.0",
    "onetool-common>=0.1.0,<1.0.0",

    # File and Excel
    "openpyxl>=3.1.0",

    # Document conversion
    "pymupdf>=1.24.0",
    "python-docx>=1.1.0",
    "python-pptx>=1.0.0",
    "pillow>=10.0.0",

    # Search APIs
    "google-genai>=0.8.0",
    "httpx>=0.28.0",
    "trafilatura>=2.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.24.0",
    "ruff>=0.9.0",
    "mypy>=1.13.0",
    "types-pyyaml",
]

[project.scripts]
onetool-util = "otutil.cli:main"

[tool.uv.sources]
# Development: local editable install
onetool-common = { path = "../onetool-common", editable = true }

# Production: PyPI version constraint
# (uv uses [project.dependencies] when not in dev mode)
```

**Dependency isolation strategy:**

```
Process 1: onetool-mcp (frontend)
  └─ fastmcp, pydantic, pyyaml
  └─ ~50 MB, lightweight

Process 2: onetool-util (backend)
  └─ fastmcp, onetool-common
  └─ pymupdf (20 MB), openpyxl, google-genai
  └─ ~120 MB, isolated

Result: No dependency conflicts possible
```

**Design decisions:**

- **Semantic versioning**: `>=x.y.0,<x+1.0.0` for stability
- **Editable dev install**: Fast iteration with onetool-common
- **Heavy deps isolated**: pymupdf, google-genai only in util backend
- **Process isolation**: Each backend has own Python environment

---

### 5. Logging Architecture

```python
# In server.py
from otcommon.logging import setup_logging, LogSpan

setup_logging(
    level=config.get("log_level", "INFO"),
    log_file=config.get("log_file", "~/.onetool/logs/onetool-util.log"),
    backend_name="onetool-util"
)

# In tools
from otcommon.logging import LogSpan

def convert_pdf(*, path: str) -> str:
    with LogSpan("convert.pdf", path=path):
        # ... conversion logic
        return result
```

**Log output format:**

```json
{
  "timestamp": "2026-02-14T10:30:45.123Z",
  "level": "INFO",
  "backend": "onetool-util",
  "pack": "convert",
  "operation": "pdf",
  "path": "document.pdf",
  "duration_ms": 1234,
  "status": "success"
}
```

**Design decisions:**

- **Structured logging**: JSON format for parsing
- **Contextual metadata**: Backend, pack, operation
- **Performance tracking**: LogSpan for automatic timing
- **Separate log file**: `~/.onetool/logs/onetool-util.log`

---

### 6. Error Handling Strategy

```python
# In tools
from otcommon.logging import logger

@tool_wrapper(mcp)
def read(*, path: str) -> str:
    """Read file contents."""
    config = _get_config()

    try:
        # Validate path against allowed directories
        if not _is_path_allowed(path, config.allowed_dirs):
            logger.error(f"Path not allowed: {path}")
            raise PermissionError(
                f"Path '{path}' not in allowed directories: {config.allowed_dirs}"
            )

        # Read file
        content = Path(path).read_text()
        logger.info(f"Read file: {path} ({len(content)} bytes)")
        return content

    except FileNotFoundError:
        logger.error(f"File not found: {path}")
        raise

    except Exception as e:
        logger.error(f"Failed to read file: {path}", exc_info=True)
        raise RuntimeError(f"Failed to read {path}: {e}") from e
```

**Error handling principles:**

1. **Fail fast**: Validate inputs early
2. **Clear messages**: User-friendly error descriptions
3. **Log context**: Include relevant metadata
4. **Preserve stack traces**: Chain exceptions with `from e`
5. **Graceful degradation**: One tool fails, others work

**API key missing example:**

```python
# In brave.py
def _get_api_key() -> str:
    """Get Brave API key from config or environment."""
    config = _get_config()

    api_key = config.api_key or os.getenv("BRAVE_API_KEY")

    if not api_key:
        raise ValueError(
            "Brave API key not configured. Set in config:\n"
            "  brave:\n"
            "    api_key: YOUR_KEY\n"
            "Or environment variable: BRAVE_API_KEY"
        )

    return api_key
```

---

### 7. Testing Architecture

```python
# tests/conftest.py

import pytest
from pathlib import Path
from otutil.server import create_server

@pytest.fixture
def test_config_path(tmp_path: Path) -> Path:
    """Create temporary config file for testing."""
    config = tmp_path / "util.yaml"
    config.write_text("""
version: 1.0.0
log_level: DEBUG
file:
  allowed_dirs: ["."]
  max_file_size: 1000000
""")
    return config


@pytest.fixture
def mcp_server(test_config_path: Path):
    """Create MCP server instance for testing."""
    return create_server(str(test_config_path))


@pytest.fixture
def mock_brave_api(monkeypatch):
    """Mock Brave Search API responses."""
    def mock_request(*args, **kwargs):
        return {
            "web": {
                "results": [
                    {"title": "Test", "url": "https://example.com", "description": "Test result"}
                ]
            }
        }

    monkeypatch.setattr("otutil.tools.brave._make_request", mock_request)
```

**Test organization:**

```
tests/
├── conftest.py              # Shared fixtures
├── test_sanity.py           # Smoke tests (imports, server start)
└── test_tools/
    ├── test_file.py         # File operations (18 tests)
    ├── test_excel.py        # Excel manipulation (30 tests)
    ├── test_convert.py      # Document conversion (5 tests)
    ├── test_brave.py        # Brave search (6 tests, mocked)
    └── test_ground.py       # Grounding search (5 tests, mocked)
```

**Test markers:**

```python
@pytest.mark.smoke
def test_import_all_modules():
    """Smoke test: All modules import successfully."""
    from otutil.tools import file, excel, convert, brave, ground
    assert file.pack == "file"
    assert excel.pack == "excel"

@pytest.mark.unit
def test_file_read(tmp_path: Path):
    """Unit test: file.read() returns content."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("Hello, world!")

    from otutil.tools import file
    result = file.read(path=str(test_file))

    assert result == "Hello, world!"

@pytest.mark.tools
@pytest.mark.parametrize("format", ["pdf", "word", "powerpoint"])
def test_convert_formats(format: str, mock_convert):
    """Tool test: convert.auto() detects format."""
    from otutil.tools import convert
    result = convert.auto(path=f"test.{format}")
    assert "markdown" in result.lower()
```

**Design decisions:**

- **Pytest framework**: Industry standard
- **Mocked APIs**: No real API calls in tests
- **Tmp paths**: Isolated file operations
- **Markers**: Categorize tests (smoke, unit, tools, integration)
- **Fixtures**: Reusable test setup

---

## Data Flow Diagrams

### Standalone Mode

```
┌────────────┐
│ Claude Code│
└──────┬─────┘
       │ MCP Request: tools/list
       ▼
┌─────────────────┐
│  onetool-util   │
│   (FastMCP)     │
└──────┬──────────┘
       │ Returns: 64 tools (~30K tokens)
       ▼
┌────────────┐
│ Claude Code│ Receives full tool list
└────────────┘
```

### Proxied Mode

```
┌────────────┐
│ Claude Code│
└──────┬─────┘
       │ MCP Request: tools/list
       ▼
┌─────────────────┐
│  onetool-mcp    │ Returns: 1 tool ("run")
│   (Frontend)    │ (~2K tokens)
└──────┬──────────┘
       │
       │ User: __ot file.read(path="test.txt")
       ▼
┌─────────────────┐
│   Executor      │ Parse Python code
│                 │ Resolve "file.read"
└──────┬──────────┘
       │
       │ Call tool: file.read(path="test.txt")
       ▼
┌─────────────────┐
│  Proxy Manager  │ Route to onetool-util backend
└──────┬──────────┘
       │ MCP tool call via stdio
       ▼
┌─────────────────┐
│  onetool-util   │ Execute file.read(path="test.txt")
│   (Backend)     │
└──────┬──────────┘
       │ Return: "file contents..."
       ▼
┌─────────────────┐
│  onetool-mcp    │ Return to executor
└──────┬──────────┘
       │ Return: {"result": "file contents..."}
       ▼
┌────────────┐
│ Claude Code│ Receives result
└────────────┘
```

---

## Trade-offs and Decisions

### Trade-off 1: Standalone vs Integrated

**Decision:** Support both modes (dual-mode)

**Rationale:**
- **Flexibility**: Users choose based on needs
- **No forced dependency**: Can use without onetool-mcp
- **Token efficiency**: Proxied mode saves 95% tokens
- **Independence**: Backend doesn't know about frontend

**Cost:** Slightly more complex implementation

---

### Trade-off 2: Tool Registration Pattern

**Options:**
1. Manual `@mcp.tool()` for each function (60+ decorators)
2. Bulk module scanner (automatic discovery)
3. `@tool_wrapper()` decorator pattern (onetool-xero approach)

**Decision:** Option 3 - `@tool_wrapper()` decorator

**Rationale:**
- **Proven**: Works in onetool-xero
- **Declarative**: Tools self-describe
- **Flexible**: Easy to customize per tool
- **Maintainable**: Less boilerplate than manual

**Cost:** Requires mcp injection into modules

---

### Trade-off 3: Config File Location

**Options:**
1. `~/.one-util/util.yaml` (separate directory)
2. `~/.onetool/onetool-util.yaml` (full name)
3. `~/.onetool/util.yaml` (short name)

**Decision:** Option 3 - `~/.onetool/util.yaml`

**Rationale:**
- **Consistency**: All backends in `~/.onetool/`
- **Brevity**: Short names easier to reference
- **Namespace**: Backend prefix implied by directory

**Migration:** Established convention from onetool-common

---

### Trade-off 4: Python Module Naming

**Options:**
1. `onetool_util` (matches package name)
2. `ot_util` (shorter)
3. `otutil` (no underscores, PEP 8)

**Decision:** Option 3 - `otutil`

**Rationale:**
- **PEP 8 compliant**: Prefer `sklearn` over `scikit_learn`
- **Consistency**: Matches `otcommon`, `otxero`
- **Clean imports**: `from otutil.tools import file`

**Cost:** Slight learning curve (package vs module name differs)

---

## Security Considerations

### Path Traversal Protection

```python
# In file.py
def _is_path_allowed(path: str, allowed_dirs: list[str]) -> bool:
    """Check if path is within allowed directories."""
    resolved = Path(path).resolve()

    for allowed_dir in allowed_dirs:
        allowed_path = Path(allowed_dir).resolve()

        try:
            resolved.relative_to(allowed_path)
            return True
        except ValueError:
            continue

    return False
```

**Protection against:**
- `../../../etc/passwd` - Path traversal
- Symlink attacks
- Absolute paths outside allowed dirs

---

### API Key Security

**Best practices:**
1. **Never log API keys**
2. **Store in secrets file** (not main config)
3. **Use environment variables** as fallback
4. **Mask in error messages**

```python
# GOOD
logger.info("Brave search completed", query=query)

# BAD
logger.info(f"Using API key: {api_key}")  # Leaks secret!
```

---

### Dependency Security

**Scanning:**
- `.gitleaks.toml` - Prevent secret commits
- GitHub Dependabot - Automated dependency updates
- `uv audit` - Check for known vulnerabilities

**Supply chain:**
- Pin dependencies with version constraints
- Review dependency tree: `uv tree`
- Prefer well-maintained packages (pymupdf, openpyxl)

---

## Performance Characteristics

### Memory Usage

**Package size:** ~120 MB (including dependencies)

**Runtime memory:**
- Base: 30 MB (Python interpreter)
- Loaded modules: 50 MB (openpyxl, pymupdf)
- Active operations: 10-40 MB (depends on file size)
- **Total:** ~90-120 MB typical

**Lazy loading:**
- Tools loaded on first use
- Heavy deps (pymupdf) only if convert tools used

---

### Latency

**Standalone mode:**
- Server startup: ~800ms (load pymupdf, openpyxl)
- Tool call overhead: ~10-50ms (FastMCP)
- Total: Tool execution + 10-50ms

**Proxied mode:**
- Proxy routing: 5-15ms
- IPC (stdio): 10-30ms
- Tool execution: (same as standalone)
- **Total:** Tool execution + 15-45ms

**Tool execution times (typical):**
- `file.read`: 1-5ms (small files)
- `excel.read`: 10-100ms (workbook size)
- `convert.pdf`: 500-2000ms (page count)
- `brave.search`: 200-800ms (API call)
- `ground.search`: 1000-3000ms (AI processing)

---

### Scalability

**Concurrent operations:**
- FastMCP handles async I/O
- Convert pack uses ThreadPoolExecutor (max_workers=4)
- File/Excel operations thread-safe

**Resource limits:**
- Max file size: 10 MB (file pack)
- Max Excel size: 100 MB (excel pack)
- Configurable in util.yaml

---

## Deployment Architecture

### Installation Methods

**1. Direct install (standalone):**
```bash
uv tool install onetool-util
```

**2. Via onetool (proxied):**
```bash
onetool install onetool-util
```

**3. Development (editable):**
```bash
cd onetool-util
uv sync
uv run onetool-util
```

---

### MCP Client Configuration

**Standalone mode:**
```json
{
  "mcpServers": {
    "onetool-util": {
      "command": "uvx",
      "args": ["onetool-util", "--config", "~/.onetool/util.yaml"]
    }
  }
}
```

**Proxied mode:**
```json
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

---

## Future Extensibility

### Adding New Tools

**Process:**
1. Add tool function to appropriate pack (e.g., `file.py`)
2. Add `@tool_wrapper(mcp)` decorator
3. Update `__all__` export
4. Write tests in `test_tools/test_file.py`
5. Document in README

**No changes needed to:**
- Server setup
- Config structure
- Tool registration

---

### Tool Pack Migration

**If a tool needs to move to another backend:**

1. Remove from `otutil/tools/`
2. Add to new backend (e.g., `otdev/tools/`)
3. Update imports in new backend
4. Tests follow the tool
5. Update docs

**Clean break** - No backwards compatibility shims

---

## Conclusion

This design establishes `onetool-util` as:

1. **Standalone MCP server** - Works independently, no onetool-mcp required
2. **Dual-mode capable** - Supports both standalone and proxied operation
3. **Well-architected** - Clean separation of concerns, testable, maintainable
4. **Dependency-isolated** - Heavy deps don't affect other backends
5. **User-friendly** - Simple config, clear errors, good docs
6. **Extensible** - Easy to add tools, packs, features

**Ready for implementation** following `tasks.md` checklist.
