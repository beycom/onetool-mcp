# Proposal: add-onetool-dev

**Status:** Draft
**Created:** 2026-02-14
**Depends on:** add-onetool-common (completed)
**Parallel with:** add-onetool-util (completed)

---

## Summary

Create `onetool-dev` as a standalone MCP server containing developer tools extracted from `onetool-mcp`. This is the third phase of the v2.0 modular architecture refactor, running in parallel with Proposal 2 (onetool-util).

**What:**
- Create new repository: `github.com/beycom/onetool-dev` (private)
- Extract 8 tool packs (~30+ tools) from `onetool-mcp/src/ot_tools/`:
  - `db.py` - Database operations (SQL query, schema inspect)
  - `ripgrep.py` - Fast code search (search, count, files, types)
  - `web_fetch.py` - Web content fetching and extraction
  - `package.py` - Package information (npm, pypi, models, audit, version)
  - `context7.py` - Documentation search via Context7 API
  - `diagram.py` - Diagram rendering (mermaid, plantuml, d2, gantt)
  - `devtools_util.py` - Chrome DevTools browser utilities
  - `playwright_util.py` - Playwright browser utilities
  - `_inject_base.py` - Shared browser injection logic
- Build on `onetool-common` shared library for config, logging, and utilities
- Publish to PyPI as `onetool-dev` (but keep GitHub repo private initially)
- Support dual-mode operation: standalone MCP server OR proxied via onetool-mcp

**Why:**
- **Dependency isolation** - Developer dependencies (sqlalchemy, jinja2, trafilatura) isolated to dev backend
- **Fault isolation** - Dev backend crashes don't affect other backends or core
- **Selective installation** - Users install only if they need developer tools
- **Token efficiency** - When proxied, ~95% reduction (15-20K→2K tokens)
- **Independent development** - Dev backend evolves without coordinating with core

**Scope:**
- ✅ New repository and package structure
- ✅ Tool extraction and adaptation
- ✅ FastMCP server implementation
- ✅ Configuration and logging setup
- ✅ Tests and quality checks
- ✅ Documentation and examples
- ❌ NOT included: onetool-mcp refactor (separate proposal)
- ❌ NOT included: Backend management CLI (separate proposal)

---

## Context

### Completed Work

**Proposal 1: add-onetool-common (✅ Complete)**
- Created `onetool-common` shared library (github.com/beycom/onetool-common)
- Provides: config loading, logging, path resolution, HTTP helpers, CLI boilerplate, batch processing, path security, factory utilities
- Template available for new backends in `onetool-common/template/`
- Proven pattern with onetool-xero refactoring

**Proposal 2: add-onetool-util (✅ Complete)**
- Created first backend server for utility tools
- Extracted 5 packs (~64 tools): file, excel, convert, brave, ground
- Established backend server pattern
- Applied learnings: PEP 8 naming (`otutil`), E402 lint exceptions, simplified config, comprehensive smoke tests
- All 7/7 smoke tests passing, linting and tests passing

### This Proposal

**Proposal 3: add-onetool-dev (This)**
- Second backend server to be extracted
- Developer tools focus (database, search, web, packages, docs, diagrams, browser automation)
- Runs in parallel with Proposal 2 - independent backends
- Paves the way for Proposal 4 (onetool-mcp refactor)

### Related Work

- **v2.0 refactor roadmap:** `wip/consult/v2-refactor.md`
- **Architecture decisions:** `wip/consult/one-servers.md`
- **Migration plan:** `wip/consult/one-server-migration.md`
- **Reference implementation:** `onetool-util` (completed)

### Learnings from onetool-util

1. **PEP 8 module naming** - Use `otdev` (no underscores), not `ot_dev` or `one_dev`
2. **E402 lint exception** - Tool files have pack/metadata before imports (intentional pattern)
3. **Simplified config** - Don't implement complex config schemas initially, tools use defaults
4. **Config singleton** - Use `otcommon.config.get_config()` for thread-safe config access
5. **Batch utilities** - Use `otcommon.batch.parallel_map()` for concurrent operations
6. **Path security** - Use `otcommon.pathsec.validate_path()` for safe file access
7. **Type ignores** - Add `# type: ignore[attr-defined]` for MCP injection pattern
8. **Comprehensive tests** - 7 smoke tests minimum (imports, server creation, CLI)
9. **Standard files** - pyproject.toml, justfile, CLAUDE.md, README.md, server.json, CHANGELOG.md, .gitleaks.toml, .markdownlint.json
10. **Template structure** - Follow `onetool-common/template/` exactly

---

## Objectives

### Primary Goals

1. **Create standalone backend server**
   - Repository structure following onetool-common template
   - FastMCP server with ~30+ tools from 8 packs
   - Standard `--config` CLI interface
   - Dual-mode: standalone OR proxied operation

2. **Extract and adapt tools**
   - Move tools from onetool-mcp with minimal changes
   - Update imports: `ot.config` → `otcommon.config`, etc.
   - Preserve all existing functionality and behavior
   - Maintain test coverage

3. **Publish and distribute**
   - PyPI package: `onetool-dev`
   - GitHub repository (private): `github.com/beycom/onetool-dev`
   - Invocation: `uvx onetool-dev --config ~/.onetool/dev.yaml`
   - Documentation and examples

### Success Criteria

- ✅ `just check` passes (lint, typecheck, test)
- ✅ Standalone mode: Starts as MCP server, responds to tool calls
- ✅ Config: Loads from `~/.onetool/dev.yaml`
- ✅ Tools: All ~30+ tools work identically to onetool-mcp v1.x
- ✅ Tests: All smoke tests pass (minimum 7)
- ✅ Docs: README, tool reference, configuration guide
- ✅ Quality: Matches onetool-common standards (ruff, mypy, pytest)
- ✅ Private repo: GitHub repository created as private

---

## Design

### Repository Structure

```
onetool-dev/
├── pyproject.toml              # Python package definition
├── justfile                    # Build and test commands
├── CLAUDE.md                   # Agent instructions
├── README.md                   # User documentation
├── CHANGELOG.md                # Version history
├── .mcp.json                   # Local MCP testing config
├── server.json                 # MCP server metadata
├── .gitleaks.toml              # Secret scanning config
├── .markdownlint.json          # Markdown linting config
├── src/
│   └── otdev/                  # Python module (PEP 8: no underscores)
│       ├── __init__.py         # Package metadata, version
│       ├── server.py           # FastMCP server entry point
│       ├── cli.py              # Typer CLI (serve, version commands)
│       └── tools/
│           ├── db.py           # Database operations pack
│           ├── ripgrep.py      # Code search pack
│           ├── web.py          # Web fetch pack (renamed from web_fetch)
│           ├── package.py      # Package info pack
│           ├── context7.py     # Documentation search pack
│           ├── diagram.py      # Diagram rendering pack
│           ├── devtools_util.py  # DevTools utilities pack
│           ├── playwright_util.py # Playwright utilities pack
│           └── _inject_base.py   # Shared browser injection logic
├── tests/
│   ├── conftest.py             # Test fixtures
│   ├── test_sanity.py          # Import and startup smoke tests (7 minimum)
│   └── test_tools/
│       ├── test_db.py
│       ├── test_ripgrep.py
│       ├── test_web.py
│       ├── test_package.py
│       ├── test_context7.py
│       ├── test_diagram.py
│       ├── test_devtools_util.py
│       └── test_playwright_util.py
├── openspec/                   # OpenSpec documentation
│   └── project.md              # Project context
└── dev/
    └── agents/
        ├── hints.md            # Quick reference for agents
        └── project-map.md      # Detailed project structure
```

### Python Module Naming

Following PEP 8 and onetool-util pattern:

- **Package name (PyPI):** `onetool-dev` (kebab-case)
- **Python module:** `otdev` (no underscores, like `sklearn`, `bs4`)
- **Import style:** `from otdev.tools import db, ripgrep`

**Rationale:**
- PEP 8 discourages underscores in module names
- Matches onetool-util (`otutil`), onetool-common (`otcommon`), onetool-xero (`otxero`)
- Cleaner imports, better consistency

### Tool Pack Mapping

| Source File (onetool-mcp) | Target Module (onetool-dev) | Pack Name | Functions | Key Dependencies |
|---------------------------|----------------------------|-----------|-----------|------------------|
| `db.py` | `otdev.tools.db` | db | query, schema_inspect, execute, tables, columns | sqlalchemy |
| `ripgrep.py` | `otdev.tools.ripgrep` | ripgrep | search, count, files, types | rg CLI binary |
| `web_fetch.py` | `otdev.tools.web` | web | fetch, extract | trafilatura, httpx |
| `package.py` | `otdev.tools.package` | package | npm, pypi, models, audit, version | httpx |
| `context7.py` | `otdev.tools.context7` | context7 | search, doc | httpx (CONTEXT7_API_KEY) |
| `diagram.py` | `otdev.tools.diagram` | diagram | render, mermaid, plantuml, d2, gantt | jinja2 |
| `devtools_util.py` | `otdev.tools.devtools_util` | devtools_util | inject, scan, clear, highlight, guide | devtools MCP |
| `playwright_util.py` | `otdev.tools.playwright_util` | playwright_util | inject, scan, clear, highlight, guide | playwright MCP |
| `_inject_base.py` | `otdev.tools._inject_base` | (shared) | Base browser injection logic | — |

**Total:** ~8 packs, ~30+ tools

### Import Changes

**Before (in onetool-mcp):**
```python
from ot.config import get_tool_config, get_secret
from ot.logging import LogSpan
from ot.paths import resolve_cwd_path
from ot.http_client import http_get
from ot.utils.factory import lazy_client
```

**After (in onetool-dev):**
```python
from otcommon.config import get_config
from otcommon.logging import LogSpan
from otcommon.paths import resolve_path
from otcommon.http import get_client
from otcommon.factory import lazy_client
from otcommon.batch import parallel_map
from otcommon.pathsec import validate_path
```

**Scope:** ~30-40 import lines across 8 files

### Configuration

**Default config path:** `~/.onetool/dev.yaml`

**Minimal config structure:**
```yaml
version: 1

# Logging
log_level: INFO
log_file: ~/.onetool/logs/onetool-dev.log

# Tool-specific settings (optional)
db:
  default_engine: sqlite
  connection_timeout: 30

ripgrep:
  max_results: 1000
  default_context: 2

web:
  timeout: 30
  user_agent: "onetool-dev/1.0"

package:
  cache_ttl: 3600

context7:
  api_key: ${CONTEXT7_API_KEY}  # From env or secrets

diagram:
  default_format: png
  output_dir: /tmp/diagrams

devtools_util:
  browser_launch_timeout: 30

playwright_util:
  browser_launch_timeout: 30
```

**Secrets:** Environment variables or `~/.onetool/secrets.yaml`

### Dependencies

**pyproject.toml:**
```toml
[project]
name = "onetool-dev"
version = "1.0.0"
description = "Developer tools MCP server for database, search, web, packages, docs, and diagrams"
requires-python = ">=3.11"
dependencies = [
    # Core framework
    "fastmcp>=2.14.4,<3.0.0",
    "onetool-common>=0.1.0,<1.0.0",
    "typer>=0.12.0",
    "rich>=13.0.0",

    # Tool-specific dependencies
    "sqlalchemy>=2.0.0",      # db.py - database operations
    "jinja2>=3.1.0",          # diagram.py - template rendering
    "trafilatura>=2.0.0",     # web.py - web content extraction
    "httpx>=0.28.0",          # web, package, context7 - HTTP client
]
```

**Lighter than onetool-util:**
- No pymupdf (large PDF library)
- No openpyxl (Excel library)
- No google-genai (AI search)
- Estimated size: ~80-100 MB (vs util's ~100-150 MB)

### FastMCP Server

**src/otdev/server.py:**
```python
"""FastMCP server for onetool-dev."""

from __future__ import annotations

from fastmcp import FastMCP

from otdev.tools import context7, db, devtools_util, diagram, package, playwright_util, ripgrep, web

_INSTRUCTIONS = """\
OneTool Developer Tools Server

Developer tools for database operations, code search, web fetching, package
information, documentation search, diagram rendering, and browser automation.

Available packs:
- db: SQL query, schema inspect, execute, tables, columns
- ripgrep: Fast code search with rg
- web: Web content fetching and extraction
- package: Package info from npm, pypi, model registries
- context7: Documentation search via Context7 API
- diagram: Render mermaid, plantuml, d2, gantt diagrams
- devtools_util: Chrome DevTools browser automation utilities
- playwright_util: Playwright browser automation utilities

All tools accept keyword arguments only.
"""


def create_server() -> FastMCP:
    """Create and configure the MCP server.

    Returns:
        Configured FastMCP server instance

    Note:
        Configuration loading will be implemented when OneToolDevConfig
        schema is defined. Tools currently use default values.
    """

    # Create FastMCP server
    mcp = FastMCP(
        name="onetool-dev",
        instructions=_INSTRUCTIONS,
    )

    # Inject mcp instance into tool modules for @tool_wrapper
    db.mcp = mcp  # type: ignore[attr-defined]
    ripgrep.mcp = mcp  # type: ignore[attr-defined]
    web.mcp = mcp  # type: ignore[attr-defined]
    package.mcp = mcp  # type: ignore[attr-defined]
    context7.mcp = mcp  # type: ignore[attr-defined]
    diagram.mcp = mcp  # type: ignore[attr-defined]
    devtools_util.mcp = mcp  # type: ignore[attr-defined]
    playwright_util.mcp = mcp  # type: ignore[attr-defined]

    # Tools will auto-register via @tool_wrapper decorators when tools are loaded

    return mcp


def main() -> None:
    """Run the MCP server with stdio transport."""
    mcp = create_server()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
```

### CLI Interface

**src/otdev/cli.py:**
```python
"""CLI for onetool-dev."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from otdev import __version__

console = Console()

app = typer.Typer(
    name="onetool-dev",
    help="Developer tools MCP server",
    no_args_is_help=True,
    add_completion=False,
)


@app.command()
def serve() -> None:
    """Start the onetool-dev MCP server.

    Note:
        Configuration loading will be implemented when OneToolDevConfig
        schema is defined. Tools currently use default values.
    """
    from otdev.server import create_server

    # TODO: Add --config and --secrets options when config loading is implemented
    mcp = create_server()
    mcp.run(transport="stdio")


@app.command()
def version() -> None:
    """Show version information."""
    console.print(f"onetool-dev version {__version__}")


def cli() -> None:
    """Main CLI entry point."""
    app()


if __name__ == "__main__":
    cli()
```

### Testing Strategy

**Smoke tests (tests/test_sanity.py):**
```python
"""Smoke tests for onetool-dev - verify basic functionality."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.smoke
def test_import_package():
    """Test that the package can be imported."""
    import otdev

    assert otdev.__version__ == "1.0.0"
    assert otdev.__package_name__ == "onetool-dev"


@pytest.mark.smoke
def test_import_server():
    """Test that the server module can be imported."""
    from otdev.server import create_server

    assert callable(create_server)


@pytest.mark.smoke
def test_import_cli():
    """Test that the CLI module can be imported."""
    from otdev.cli import app, cli

    assert app is not None
    assert callable(cli)


@pytest.mark.smoke
def test_import_tool_modules():
    """Test that all tool modules can be imported."""
    from otdev.tools import context7, db, devtools_util, diagram, package, playwright_util, ripgrep, web

    # Check pack names
    assert db.pack == "db"
    assert ripgrep.pack == "ripgrep"
    assert web.pack == "web"
    assert package.pack == "package"
    assert context7.pack == "context7"
    assert diagram.pack == "diagram"
    assert devtools_util.pack == "devtools_util"
    assert playwright_util.pack == "playwright_util"


@pytest.mark.smoke
def test_server_creation():
    """Test that a server can be created without config."""
    from otdev.server import create_server

    # Should work without config (optional)
    server = create_server()

    assert server is not None
    assert server.name == "onetool-dev"


@pytest.mark.smoke
def test_server_creation_with_config(tmp_config: Path):
    """Test that a server can be created (config fixture for future use)."""
    from otdev.server import create_server

    # TODO: When config loading is implemented, pass config_path
    server = create_server()

    assert server is not None
    assert server.name == "onetool-dev"


@pytest.mark.smoke
def test_cli_version():
    """Test that CLI version command works."""
    from typer.testing import CliRunner

    from otdev.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["version"])

    assert result.exit_code == 0
    assert "1.0.0" in result.output
```

**Test fixtures (tests/conftest.py):**
```python
"""Test fixtures for onetool-dev."""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

import pytest


@pytest.fixture
def tmp_config(tmp_path: Path) -> Iterator[Path]:
    """Create a temporary config file for testing.

    Args:
        tmp_path: pytest's temporary directory fixture

    Yields:
        Path to temporary config file
    """
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """\
version: 1
log_level: INFO
"""
    )
    yield config_path
```

### Documentation

**README.md sections:**
1. Overview and purpose
2. Installation (`uvx onetool-dev`)
3. Configuration (`~/.onetool/dev.yaml`)
4. Available tools (8 packs, ~30+ tools)
5. Usage examples (standalone and proxied modes)
6. Development setup
7. Testing and quality checks
8. Contributing guidelines

**CLAUDE.md sections:**
1. Project context and purpose
2. Architecture (FastMCP server, tool packs)
3. Development workflow
4. Testing strategy
5. Quality standards
6. Tool reference (brief)

---

## Implementation Plan

### Phase 1: Project Setup (From Template)

1. **Initialize repository**
   - Create GitHub repo: `github.com/beycom/onetool-dev` (private)
   - Clone locally to `/Users/gavin/01-work-thor/projects/group-hobby/onetool-dev`
   - Copy template from `onetool-common/template/`

2. **Configure project files**
   - Update `pyproject.toml`: name, description, dependencies
   - Update `justfile`: project name
   - Update `CLAUDE.md`: project context
   - Update `README.md`: project description
   - Create `server.json` for MCP metadata
   - Create `CHANGELOG.md` with v1.0.0 initial release
   - Configure `.gitleaks.toml` and `.markdownlint.json`

3. **Setup Python package**
   - Create `src/otdev/__init__.py` with version and metadata
   - Create `src/otdev/server.py` with FastMCP server
   - Create `src/otdev/cli.py` with Typer CLI
   - Create `src/otdev/tools/` directory

4. **Setup testing**
   - Create `tests/conftest.py` with fixtures
   - Create `tests/test_sanity.py` with 7 smoke tests
   - Create `tests/test_tools/` directory

5. **Validation**
   - Run `uv sync` to install dependencies
   - Run `just check` to verify setup
   - Commit initial project structure

### Phase 2: Tool Extraction

For each tool pack:

1. **Copy source files**
   - Copy from `onetool-mcp/src/ot_tools/` to `onetool-dev/src/otdev/tools/`
   - Rename files: `web_fetch.py` → `web.py` (cleaner naming)

2. **Update imports**
   - Replace `ot.config` → `otcommon.config`
   - Replace `ot.logging` → `otcommon.logging`
   - Replace `ot.paths` → `otcommon.paths`
   - Replace `ot.http_client` → `otcommon.http`
   - Replace `ot.utils.factory` → `otcommon.factory`
   - Add `otcommon.batch`, `otcommon.pathsec` where beneficial

3. **Add E402 lint exception**
   - Update `pyproject.toml` to ignore E402 for tool files
   - Add comment explaining OneTool pattern

4. **Update tool metadata**
   - Ensure each tool file has `pack = "..."` declaration
   - Ensure each tool has `__all__` listing exported functions
   - Ensure each tool has `__ot_requires__` if it has dependencies

5. **Inject mcp in server.py**
   - Add mcp injection for each tool module
   - Add `# type: ignore[attr-defined]` comments

6. **Create basic tests**
   - Create `tests/test_tools/test_<pack>.py` for each pack
   - Start with import smoke tests
   - Add basic functionality tests where possible

7. **Validation**
   - Run `just lint` to check for issues
   - Run `just test` to verify tests pass
   - Manually test each tool pack if possible

### Tool Extraction Order

1. `ripgrep.py` → `otdev.tools.ripgrep` (simple, CLI wrapper)
2. `web_fetch.py` → `otdev.tools.web` (simple, HTTP + trafilatura)
3. `package.py` → `otdev.tools.package` (simple, HTTP APIs)
4. `context7.py` → `otdev.tools.context7` (simple, HTTP API)
5. `db.py` → `otdev.tools.db` (moderate, SQLAlchemy)
6. `diagram.py` → `otdev.tools.diagram` (moderate, Jinja2 + rendering)
7. `_inject_base.py` → `otdev.tools._inject_base` (shared utility)
8. `devtools_util.py` → `otdev.tools.devtools_util` (depends on _inject_base)
9. `playwright_util.py` → `otdev.tools.playwright_util` (depends on _inject_base)

### Phase 3: Configuration and Logging

1. **Config loading (simplified)**
   - For now, tools use default values
   - Add TODO comments for future config schema
   - Don't implement complex OneToolDevConfig yet

2. **Logging setup**
   - Use `otcommon.logging.configure_logging()`
   - Default log file: `~/.onetool/logs/onetool-dev.log`
   - Default level: INFO

3. **Config template**
   - Create example config in README.md
   - Document all available tool settings
   - Show secrets integration pattern

### Phase 4: Quality Assurance

1. **Linting**
   - Run `just lint` and fix all issues
   - Run `ruff check --fix` for auto-fixes
   - Address remaining issues manually

2. **Type checking**
   - Run `just typecheck`
   - Fix critical type errors in server.py, cli.py
   - Add `# type: ignore` for known patterns
   - Accept pre-existing tool type errors (can address later)

3. **Testing**
   - All 7 smoke tests must pass
   - Run `just test` to verify
   - Add tool-specific tests where feasible

4. **Documentation**
   - Complete README.md with all sections
   - Complete CLAUDE.md with project context
   - Update CHANGELOG.md with v1.0.0 details
   - Create dev/agents/hints.md and project-map.md

### Phase 5: Publication

1. **GitHub repository**
   - Push to `github.com/beycom/onetool-dev`
   - Verify repo is private
   - Add README, LICENSE, .gitignore

2. **PyPI package**
   - Build package: `uv build`
   - Publish to PyPI: `uv publish` (or test PyPI first)
   - Verify installation: `uvx onetool-dev --version`

3. **Documentation**
   - Update main project docs to reference onetool-dev
   - Add installation instructions
   - Add usage examples

4. **Final validation**
   - Install fresh via uvx
   - Test standalone mode
   - Test basic tool functionality
   - Verify all smoke tests pass

---

## Risks and Mitigations

### Risk 1: Import Path Breakage

**Risk:** Changing imports across ~30-40 lines in 8 files could introduce errors.

**Mitigation:**
- Mechanical find-and-replace (low risk)
- Run `just check` after each file change
- Keep onetool-util as reference for import patterns
- Test each tool pack individually

### Risk 2: Tool Behavior Regression

**Risk:** Tools behave differently in standalone backend vs onetool-mcp.

**Mitigation:**
- Copy tools verbatim, only change imports
- Preserve all functionality
- Smoke test each tool manually
- Keep onetool-mcp v1.x as reference

### Risk 3: Dependency Issues

**Risk:** Missing dependencies or version conflicts.

**Mitigation:**
- Copy dependency versions from onetool-mcp
- Test installation in clean venv
- Use `uv sync` for reproducible installs
- Document all required system dependencies (e.g., `rg` CLI)

### Risk 4: Browser Utility Integration

**Risk:** devtools_util and playwright_util depend on external MCP servers.

**Mitigation:**
- Document MCP server dependencies clearly
- Test with devtools and playwright MCPs installed
- Add graceful error handling if MCPs not available
- Include setup instructions in README

### Risk 5: Private Repository Management

**Risk:** Accidentally making private repo public.

**Mitigation:**
- Double-check repo visibility before creation
- Verify repo is private after creation
- Limit collaborator access
- Document why repo is private (learnings from onetool-util)

---

## Success Metrics

### Technical Metrics

- ✅ All 7 smoke tests passing
- ✅ `just check` passes (lint + typecheck + test)
- ✅ No critical mypy errors in server/cli code
- ✅ All tool packs importable
- ✅ FastMCP server starts successfully
- ✅ Config loads from `~/.onetool/dev.yaml`

### Quality Metrics

- ✅ Code coverage: >80% for server and cli modules
- ✅ Documentation: README and CLAUDE.md complete
- ✅ Consistent with onetool-common standards
- ✅ Consistent with onetool-util patterns

### Distribution Metrics

- ✅ PyPI package published
- ✅ GitHub repository created (private)
- ✅ Installation works: `uvx onetool-dev`
- ✅ Version command works: `onetool-dev version`

---

## Future Work

### Post-v1.0.0

1. **Config schema**
   - Define OneToolDevConfig Pydantic model
   - Implement config loading in server.py
   - Add --config and --secrets CLI options
   - Support config validation

2. **Tool enhancements**
   - Add more database operations
   - Enhance ripgrep with more options
   - Add web caching for fetch operations
   - Improve diagram rendering options

3. **Testing**
   - Add integration tests
   - Add tool-specific unit tests
   - Add performance benchmarks

4. **Documentation**
   - Add API reference
   - Add tutorial examples
   - Add troubleshooting guide

5. **Community**
   - Open source repository (make public)
   - Accept community contributions
   - Create contributor guide

---

## Dependencies

### Upstream Dependencies

- **onetool-common** (v0.1.0+) - Must be published to PyPI or available as editable install
- **FastMCP** (v2.14.4+) - MCP server framework
- **External CLIs** - `rg` (ripgrep) must be installed on system

### Downstream Dependencies

None - onetool-dev is a leaf backend server.

### Parallel Dependencies

- **onetool-util** - Can be developed in parallel (independent backends)
- **onetool-mcp** - Will depend on onetool-dev after refactor (Proposal 4)

---

## Open Questions

None - all decisions made based on onetool-util experience.

---

## Appendix

### Tool Count Breakdown

| Pack | Tools | Complexity | Dependencies |
|------|-------|------------|--------------|
| db | ~5 | Medium | sqlalchemy |
| ripgrep | ~4 | Low | rg CLI |
| web | ~2 | Low | trafilatura, httpx |
| package | ~6 | Low | httpx |
| context7 | ~2 | Low | httpx |
| diagram | ~5 | Medium | jinja2 |
| devtools_util | ~5 | Medium | devtools MCP |
| playwright_util | ~5 | Medium | playwright MCP |
| **Total** | **~34** | — | — |

### File Size Estimates

- Source code: ~15-20 KB per tool × 8 = ~120-160 KB
- Tests: ~5-10 KB per tool × 8 = ~40-80 KB
- Config/docs: ~20-30 KB
- **Total:** ~200-300 KB source

### Development Time Estimate

Based on onetool-util completion:

| Phase | Time Estimate |
|-------|---------------|
| Phase 1: Project setup | 0.5 day |
| Phase 2: Tool extraction | 1.0 day |
| Phase 3: Config/logging | 0.25 day |
| Phase 4: Quality assurance | 0.5 day |
| Phase 5: Publication | 0.25 day |
| **Total** | **~2.5 days** |

With Claude Code assistance, possibly faster.

---

**Status:** Ready for approval and implementation
**Next step:** Create tasks.md with detailed implementation tasks
