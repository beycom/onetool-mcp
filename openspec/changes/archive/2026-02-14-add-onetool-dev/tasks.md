# Tasks: add-onetool-dev

**Proposal:** add-onetool-dev
**Status:** Draft
**Total tasks:** 103

---

## Phase 1: Project Setup (From Template) - 15 tasks

### Task 1.1: Create GitHub Repository
- [ ] Create private repository `github.com/beycom/onetool-dev`
- [ ] Add description: "Developer tools MCP server for database, search, web, packages, docs, and diagrams"
- [ ] Add topics: `mcp`, `mcp-server`, `onetool`, `developer-tools`, `database`, `search`, `diagrams`
- [ ] Set visibility to **private**
- [ ] Verify repository is private
- [ ] Clone repository locally to `/Users/gavin/01-work-thor/projects/group-hobby/onetool-dev`

### Task 1.2: Copy Template Structure
- [ ] Copy all files from `onetool-common/template/` to `onetool-dev/`
- [ ] Verify all template files copied successfully
- [ ] Create `.mcp.json` for local testing
- [ ] Create `server.json` for MCP metadata

### Task 1.3: Configure pyproject.toml
- [ ] Update `name = "onetool-dev"`
- [ ] Update `version = "1.0.0"`
- [ ] Update `description = "Developer tools MCP server for database, search, web, packages, docs, and diagrams"`
- [ ] Update `authors = [{ name = "Beycom", email = "dev@beycom.com" }]`
- [ ] Update `keywords = ["mcp", "mcp-server", "onetool", "developer-tools", "database", "search", "diagrams", "web", "packages"]`
- [ ] Set `requires-python = ">=3.11"`
- [ ] Update dependencies:
  - `fastmcp>=2.14.4,<3.0.0`
  - `onetool-common>=0.1.0,<1.0.0`
  - `typer>=0.12.0`
  - `rich>=13.0.0`
  - `sqlalchemy>=2.0.0`
  - `jinja2>=3.1.0`
  - `trafilatura>=2.0.0`
  - `httpx>=0.28.0`
- [ ] Update `[project.scripts]`: `onetool-dev = "otdev.cli:cli"`
- [ ] Update `[tool.hatch.build.targets.wheel]`: `packages = ["src/otdev"]`
- [ ] Update `[tool.ruff.lint]`: Add `ignore = ["E501", "B008", "UP047", "E402"]` with comment
- [ ] Update `[tool.ruff.lint.isort]`: `known-first-party = ["otdev"]`
- [ ] Update `[tool.mypy]`: `files = ["src/otdev"]`
- [ ] Update `[dependency-groups]` with dev dependencies:
  - `mypy>=1.19.1`
  - `pytest>=9.0.2`
  - `pytest-asyncio>=1.3.0`
  - `ruff>=0.14.14`
  - `types-pyyaml`
- [ ] Add `[tool.uv.sources]` for onetool-common editable install

### Task 1.4: Configure Project Files
- [ ] Update `justfile`: Replace `{name}` with `onetool-dev`, `{package}` with `otdev`
- [ ] Update `README.md`: Replace placeholders with project-specific content
- [ ] Update `CLAUDE.md`: Add project context for developer tools backend
- [ ] Create `CHANGELOG.md` with v1.0.0 initial release entry
- [ ] Update `.python-version` to `3.11`
- [ ] Verify `.gitignore` is configured correctly
- [ ] Configure `.gitleaks.toml` for secret scanning
- [ ] Configure `.markdownlint.json` for markdown linting

### Task 1.5: Create Python Package Structure
- [ ] Create `src/otdev/__init__.py`
- [ ] Add `__version__ = "1.0.0"` to `__init__.py`
- [ ] Add `__package_name__ = "onetool-dev"` to `__init__.py`
- [ ] Add package docstring to `__init__.py`
- [ ] Create `src/otdev/tools/` directory
- [ ] Create `src/otdev/tools/__init__.py`

### Task 1.6: Create FastMCP Server
- [ ] Create `src/otdev/server.py`
- [ ] Import FastMCP
- [ ] Import all tool modules (8 packs)
- [ ] Define `_INSTRUCTIONS` with server description
- [ ] Implement `create_server()` function
- [ ] Add mcp injection for all 8 tool modules with `# type: ignore[attr-defined]`
- [ ] Implement `main()` function
- [ ] Add `if __name__ == "__main__"` block

### Task 1.7: Create CLI Interface
- [ ] Create `src/otdev/cli.py`
- [ ] Import typer, rich, __version__
- [ ] Create Typer app with name="onetool-dev"
- [ ] Implement `serve()` command (simplified, no config loading yet)
- [ ] Implement `version()` command
- [ ] Implement `cli()` entry point function
- [ ] Add `if __name__ == "__main__"` block

### Task 1.8: Setup Testing Infrastructure
- [ ] Create `tests/` directory
- [ ] Create `tests/__init__.py`
- [ ] Create `tests/conftest.py` with `tmp_config` fixture
- [ ] Create `tests/test_tools/` directory
- [ ] Create `tests/test_tools/__init__.py`
- [ ] Configure pytest markers in `pyproject.toml`:
  - `smoke: Quick sanity checks`
  - `unit: Fast isolated tests`
  - `integration: End-to-end tests`
  - `tools: Tool implementation tests`

### Task 1.9: Create Smoke Tests
- [ ] Create `tests/test_sanity.py`
- [ ] Add `test_import_package()` - verify package imports and version
- [ ] Add `test_import_server()` - verify server module imports
- [ ] Add `test_import_cli()` - verify CLI module imports
- [ ] Add `test_import_tool_modules()` - verify all 8 tool modules import and have pack names
- [ ] Add `test_server_creation()` - verify server creates without config
- [ ] Add `test_server_creation_with_config()` - verify server creates with config fixture
- [ ] Add `test_cli_version()` - verify CLI version command works
- [ ] Mark all tests with `@pytest.mark.smoke`

### Task 1.10: Create OpenSpec Documentation
- [ ] Create `openspec/` directory
- [ ] Create `openspec/project.md` with basic project context
- [ ] Document project purpose and architecture
- [ ] Reference proposal and design documents

### Task 1.11: Create Agent Documentation
- [ ] Create `dev/` directory
- [ ] Create `dev/agents/` directory
- [ ] Create `dev/agents/hints.md` with quick reference:
  - Project structure
  - Common commands (`just check`, `just test`, etc.)
  - Tool pack locations
  - Import patterns
  - Testing strategy
- [ ] Create `dev/agents/project-map.md` with detailed structure:
  - Directory tree
  - Module descriptions
  - Dependency graph
  - Key files and their purposes

### Task 1.12: Configure Release Automation
- [ ] Create `server.json` with MCP metadata:
  - name: "onetool-dev"
  - version: "1.0.0"
  - description
  - entrypoint: "onetool-dev"
  - config schema (basic)
- [ ] Create `cliff.toml` for changelog generation
- [ ] Create `release.just` with release tasks
- [ ] Verify release automation is configured correctly

### Task 1.13: Install Dependencies
- [ ] Run `uv sync` to create virtual environment
- [ ] Verify all dependencies installed successfully
- [ ] Verify onetool-common editable install works
- [ ] Check for any dependency conflicts

### Task 1.14: Initial Validation
- [ ] Run `just lint` - should pass (no code yet)
- [ ] Run `just typecheck` - should pass (no code yet)
- [ ] Run `just test` - smoke tests should fail (no tools yet)
- [ ] Verify project structure matches template

### Task 1.15: Initial Commit
- [ ] Stage all project setup files
- [ ] Commit: "feat(init): initialize onetool-dev project structure"
- [ ] Push to GitHub
- [ ] Verify commit appears on GitHub
- [ ] Verify repository is still private

---

## Phase 2: Tool Extraction - 72 tasks (8 tools × 9 tasks each)

### 2.1: Extract ripgrep.py (Simple CLI Wrapper)

#### Task 2.1.1: Copy Source File
- [ ] Copy `onetool-mcp/src/ot_tools/ripgrep.py` to `onetool-dev/src/otdev/tools/ripgrep.py`
- [ ] Verify file copied successfully
- [ ] Check file size and line count matches

#### Task 2.1.2: Update Imports
- [ ] Replace `from ot.config import get_tool_config, get_secret` with `from otcommon.config import get_config`
- [ ] Replace `from ot.logging import LogSpan` with `from otcommon.logging import LogSpan`
- [ ] Replace `from ot.paths import resolve_cwd_path` with `from otcommon.paths import resolve_path`
- [ ] Add `from otcommon.batch import parallel_map` if beneficial for batch operations
- [ ] Add `from otcommon.pathsec import validate_path` for file path validation
- [ ] Verify all imports resolve correctly

#### Task 2.1.3: Update Configuration Access
- [ ] Replace `get_tool_config("ripgrep", ...)` with `get_config().get("ripgrep", {})`
- [ ] Replace `get_secret("...")` with `get_config().get("secrets", {}).get(...)`
- [ ] Update any hardcoded config paths to use `resolve_path()`
- [ ] Verify configuration access works

#### Task 2.1.4: Update Pack Metadata
- [ ] Verify `pack = "ripgrep"` declaration exists at top of file
- [ ] Verify `__all__` lists all exported functions
- [ ] Verify `__ot_requires__` declares dependencies if any
- [ ] Add comment: `# E402: Pack metadata must come before imports (OneTool pattern)`

#### Task 2.1.5: Register Tool in Server
- [ ] Import ripgrep in `src/otdev/server.py`
- [ ] Add `ripgrep.mcp = mcp  # type: ignore[attr-defined]` in `create_server()`
- [ ] Verify import order (alphabetical)
- [ ] Verify type ignore comment is present

#### Task 2.1.6: Create Tests
- [ ] Create `tests/test_tools/test_ripgrep.py`
- [ ] Add import smoke test
- [ ] Add pack name verification test
- [ ] Add basic functionality test (if feasible without rg CLI)
- [ ] Mark tests with `@pytest.mark.unit` or `@pytest.mark.tools`

#### Task 2.1.7: Update Smoke Tests
- [ ] Verify `test_import_tool_modules()` includes `ripgrep`
- [ ] Verify `assert ripgrep.pack == "ripgrep"` is present
- [ ] Run smoke tests to verify ripgrep imports correctly

#### Task 2.1.8: Lint and Type Check
- [ ] Run `just lint` - fix any issues in ripgrep.py
- [ ] Run `ruff check --fix src/otdev/tools/ripgrep.py` for auto-fixes
- [ ] Run `just typecheck` - address critical type errors
- [ ] Add `# type: ignore` for known patterns if needed

#### Task 2.1.9: Test and Validate
- [ ] Run `just test -k ripgrep` to test ripgrep-specific tests
- [ ] Run `just test -k smoke` to verify smoke tests pass
- [ ] Manually test ripgrep tools if possible (requires rg CLI)
- [ ] Commit: "feat(tools): extract ripgrep pack from onetool-mcp"

### 2.2: Extract web_fetch.py → web.py (Simple HTTP + Trafilatura)

#### Task 2.2.1: Copy and Rename Source File
- [ ] Copy `onetool-mcp/src/ot_tools/web_fetch.py` to `onetool-dev/src/otdev/tools/web.py`
- [ ] Verify file copied successfully
- [ ] Verify renamed to `web.py` (cleaner naming)

#### Task 2.2.2: Update Imports
- [ ] Replace `from ot.config import get_tool_config, get_secret` with `from otcommon.config import get_config`
- [ ] Replace `from ot.logging import LogSpan` with `from otcommon.logging import LogSpan`
- [ ] Replace `from ot.http_client import http_get` with `from otcommon.http import get_client`
- [ ] Add `from otcommon.factory import lazy_client` if needed
- [ ] Verify all imports resolve correctly

#### Task 2.2.3: Update Configuration Access
- [ ] Replace `get_tool_config("web", ...)` with `get_config().get("web", {})`
- [ ] Update timeout and user_agent configuration access
- [ ] Verify configuration access works

#### Task 2.2.4: Update Pack Metadata
- [ ] Update `pack = "web"` (was "web_fetch")
- [ ] Verify `__all__` lists all exported functions
- [ ] Verify `__ot_requires__` declares dependencies
- [ ] Add comment: `# E402: Pack metadata must come before imports (OneTool pattern)`

#### Task 2.2.5: Register Tool in Server
- [ ] Import web in `src/otdev/server.py`
- [ ] Add `web.mcp = mcp  # type: ignore[attr-defined]` in `create_server()`
- [ ] Verify import order (alphabetical)
- [ ] Verify type ignore comment is present

#### Task 2.2.6: Create Tests
- [ ] Create `tests/test_tools/test_web.py`
- [ ] Add import smoke test
- [ ] Add pack name verification test
- [ ] Add basic fetch test (mock HTTP response)
- [ ] Mark tests appropriately

#### Task 2.2.7: Update Smoke Tests
- [ ] Verify `test_import_tool_modules()` includes `web`
- [ ] Verify `assert web.pack == "web"` is present
- [ ] Run smoke tests to verify web imports correctly

#### Task 2.2.8: Lint and Type Check
- [ ] Run `just lint` - fix any issues in web.py
- [ ] Run `ruff check --fix src/otdev/tools/web.py`
- [ ] Run `just typecheck` - address critical type errors
- [ ] Add `# type: ignore` for known patterns if needed

#### Task 2.2.9: Test and Validate
- [ ] Run `just test -k web` to test web-specific tests
- [ ] Run `just test -k smoke` to verify smoke tests pass
- [ ] Manually test web tools if possible
- [ ] Commit: "feat(tools): extract web pack from onetool-mcp (was web_fetch)"

### 2.3: Extract package.py (Simple HTTP APIs)

#### Task 2.3.1: Copy Source File
- [ ] Copy `onetool-mcp/src/ot_tools/package.py` to `onetool-dev/src/otdev/tools/package.py`
- [ ] Verify file copied successfully

#### Task 2.3.2: Update Imports
- [ ] Replace ot imports with otcommon imports
- [ ] Replace `from ot.http_client` with `from otcommon.http`
- [ ] Add otcommon utilities where beneficial
- [ ] Verify all imports resolve correctly

#### Task 2.3.3: Update Configuration Access
- [ ] Replace `get_tool_config("package", ...)` with `get_config().get("package", {})`
- [ ] Update cache_ttl configuration access
- [ ] Verify configuration access works

#### Task 2.3.4: Update Pack Metadata
- [ ] Verify `pack = "package"` declaration exists
- [ ] Verify `__all__` lists all exported functions
- [ ] Verify `__ot_requires__` declares dependencies
- [ ] Add E402 comment if needed

#### Task 2.3.5: Register Tool in Server
- [ ] Import package in `src/otdev/server.py`
- [ ] Add `package.mcp = mcp  # type: ignore[attr-defined]`
- [ ] Verify import order
- [ ] Verify type ignore comment

#### Task 2.3.6: Create Tests
- [ ] Create `tests/test_tools/test_package.py`
- [ ] Add import smoke test
- [ ] Add pack name verification test
- [ ] Add basic functionality test (mock HTTP)
- [ ] Mark tests appropriately

#### Task 2.3.7: Update Smoke Tests
- [ ] Verify `test_import_tool_modules()` includes `package`
- [ ] Verify `assert package.pack == "package"`
- [ ] Run smoke tests

#### Task 2.3.8: Lint and Type Check
- [ ] Run `just lint` - fix issues
- [ ] Run `ruff check --fix src/otdev/tools/package.py`
- [ ] Run `just typecheck`
- [ ] Add type ignores if needed

#### Task 2.3.9: Test and Validate
- [ ] Run `just test -k package`
- [ ] Run `just test -k smoke`
- [ ] Manually test if possible
- [ ] Commit: "feat(tools): extract package pack from onetool-mcp"

### 2.4: Extract context7.py (Simple HTTP API)

#### Task 2.4.1: Copy Source File
- [ ] Copy `onetool-mcp/src/ot_tools/context7.py` to `onetool-dev/src/otdev/tools/context7.py`
- [ ] Verify file copied successfully

#### Task 2.4.2: Update Imports
- [ ] Replace ot imports with otcommon imports
- [ ] Replace `from ot.http_client` with `from otcommon.http`
- [ ] Replace `from ot.config import get_secret` with config access
- [ ] Verify all imports resolve correctly

#### Task 2.4.3: Update Configuration Access
- [ ] Replace `get_tool_config("context7", ...)` with `get_config().get("context7", {})`
- [ ] Replace `get_secret("CONTEXT7_API_KEY")` with env var or config
- [ ] Verify configuration access works

#### Task 2.4.4: Update Pack Metadata
- [ ] Verify `pack = "context7"` declaration exists
- [ ] Verify `__all__` lists all exported functions
- [ ] Verify `__ot_requires__` declares API key requirement
- [ ] Add E402 comment if needed

#### Task 2.4.5: Register Tool in Server
- [ ] Import context7 in `src/otdev/server.py`
- [ ] Add `context7.mcp = mcp  # type: ignore[attr-defined]`
- [ ] Verify import order
- [ ] Verify type ignore comment

#### Task 2.4.6: Create Tests
- [ ] Create `tests/test_tools/test_context7.py`
- [ ] Add import smoke test
- [ ] Add pack name verification test
- [ ] Add basic functionality test (mock API)
- [ ] Mark tests appropriately

#### Task 2.4.7: Update Smoke Tests
- [ ] Verify `test_import_tool_modules()` includes `context7`
- [ ] Verify `assert context7.pack == "context7"`
- [ ] Run smoke tests

#### Task 2.4.8: Lint and Type Check
- [ ] Run `just lint` - fix issues
- [ ] Run `ruff check --fix src/otdev/tools/context7.py`
- [ ] Run `just typecheck`
- [ ] Add type ignores if needed

#### Task 2.4.9: Test and Validate
- [ ] Run `just test -k context7`
- [ ] Run `just test -k smoke`
- [ ] Manually test if possible (requires API key)
- [ ] Commit: "feat(tools): extract context7 pack from onetool-mcp"

### 2.5: Extract db.py (Moderate - SQLAlchemy)

#### Task 2.5.1: Copy Source File
- [ ] Copy `onetool-mcp/src/ot_tools/db.py` to `onetool-dev/src/otdev/tools/db.py`
- [ ] Verify file copied successfully

#### Task 2.5.2: Update Imports
- [ ] Replace ot imports with otcommon imports
- [ ] Replace `from ot.utils.factory import lazy_client` with `from otcommon.factory import lazy_client`
- [ ] Add `from otcommon.pathsec import validate_path` for database file paths
- [ ] Verify all imports resolve correctly

#### Task 2.5.3: Update Configuration Access
- [ ] Replace `get_tool_config("db", ...)` with `get_config().get("db", {})`
- [ ] Update default_engine, connection_timeout config access
- [ ] Verify configuration access works

#### Task 2.5.4: Update Pack Metadata
- [ ] Verify `pack = "db"` declaration exists
- [ ] Verify `__all__` lists all exported functions
- [ ] Verify `__ot_requires__` declares sqlalchemy dependency
- [ ] Add E402 comment if needed

#### Task 2.5.5: Register Tool in Server
- [ ] Import db in `src/otdev/server.py`
- [ ] Add `db.mcp = mcp  # type: ignore[attr-defined]`
- [ ] Verify import order
- [ ] Verify type ignore comment

#### Task 2.5.6: Create Tests
- [ ] Create `tests/test_tools/test_db.py`
- [ ] Add import smoke test
- [ ] Add pack name verification test
- [ ] Add basic query test (in-memory SQLite)
- [ ] Mark tests appropriately

#### Task 2.5.7: Update Smoke Tests
- [ ] Verify `test_import_tool_modules()` includes `db`
- [ ] Verify `assert db.pack == "db"`
- [ ] Run smoke tests

#### Task 2.5.8: Lint and Type Check
- [ ] Run `just lint` - fix issues
- [ ] Run `ruff check --fix src/otdev/tools/db.py`
- [ ] Run `just typecheck`
- [ ] Add type ignores if needed

#### Task 2.5.9: Test and Validate
- [ ] Run `just test -k db`
- [ ] Run `just test -k smoke`
- [ ] Manually test with SQLite database
- [ ] Commit: "feat(tools): extract db pack from onetool-mcp"

### 2.6: Extract diagram.py (Moderate - Jinja2 + Rendering)

#### Task 2.6.1: Copy Source Files
- [ ] Copy `onetool-mcp/src/ot_tools/diagram.py` to `onetool-dev/src/otdev/tools/diagram.py`
- [ ] Copy `onetool-mcp/src/ot_tools/diagram.yaml` if it exists
- [ ] Verify files copied successfully

#### Task 2.6.2: Update Imports
- [ ] Replace ot imports with otcommon imports
- [ ] Replace `from ot.paths import resolve_cwd_path` with `from otcommon.paths import resolve_path`
- [ ] Add `from otcommon.pathsec import validate_path` for output file paths
- [ ] Verify all imports resolve correctly

#### Task 2.6.3: Update Configuration Access
- [ ] Replace `get_tool_config("diagram", ...)` with `get_config().get("diagram", {})`
- [ ] Update default_format, output_dir config access
- [ ] Verify configuration access works

#### Task 2.6.4: Update Pack Metadata
- [ ] Verify `pack = "diagram"` declaration exists
- [ ] Verify `__all__` lists all exported functions
- [ ] Verify `__ot_requires__` declares jinja2 dependency
- [ ] Add E402 comment if needed

#### Task 2.6.5: Register Tool in Server
- [ ] Import diagram in `src/otdev/server.py`
- [ ] Add `diagram.mcp = mcp  # type: ignore[attr-defined]`
- [ ] Verify import order
- [ ] Verify type ignore comment

#### Task 2.6.6: Create Tests
- [ ] Create `tests/test_tools/test_diagram.py`
- [ ] Add import smoke test
- [ ] Add pack name verification test
- [ ] Add basic rendering test (simple mermaid)
- [ ] Mark tests appropriately

#### Task 2.6.7: Update Smoke Tests
- [ ] Verify `test_import_tool_modules()` includes `diagram`
- [ ] Verify `assert diagram.pack == "diagram"`
- [ ] Run smoke tests

#### Task 2.6.8: Lint and Type Check
- [ ] Run `just lint` - fix issues
- [ ] Run `ruff check --fix src/otdev/tools/diagram.py`
- [ ] Run `just typecheck`
- [ ] Add type ignores if needed

#### Task 2.6.9: Test and Validate
- [ ] Run `just test -k diagram`
- [ ] Run `just test -k smoke`
- [ ] Manually test diagram rendering
- [ ] Commit: "feat(tools): extract diagram pack from onetool-mcp"

### 2.7: Extract _inject_base.py (Shared Browser Utility)

#### Task 2.7.1: Copy Source File
- [ ] Copy `onetool-mcp/src/ot_tools/_inject_base.py` to `onetool-dev/src/otdev/tools/_inject_base.py`
- [ ] Verify file copied successfully

#### Task 2.7.2: Update Imports
- [ ] Replace ot imports with otcommon imports
- [ ] Verify all imports resolve correctly
- [ ] Check for any MCP server proxy imports

#### Task 2.7.3: Update Configuration Access
- [ ] Update any configuration access to use `get_config()`
- [ ] Verify no hardcoded paths remain

#### Task 2.7.4: Update Module Metadata
- [ ] Verify `__all__` lists exported classes/functions
- [ ] Add module docstring explaining shared utilities
- [ ] Add E402 comment if pack metadata present

#### Task 2.7.5: Lint and Type Check
- [ ] Run `just lint` - fix issues
- [ ] Run `ruff check --fix src/otdev/tools/_inject_base.py`
- [ ] Run `just typecheck`
- [ ] Add type ignores if needed

#### Task 2.7.6: Create Basic Tests
- [ ] Create `tests/test_tools/test_inject_base.py`
- [ ] Add import smoke test
- [ ] Add basic functionality test if feasible
- [ ] Mark tests appropriately

#### Task 2.7.7: Test and Validate
- [ ] Run `just test -k inject`
- [ ] Run `just test -k smoke`
- [ ] Verify _inject_base imports correctly
- [ ] Commit: "feat(tools): extract _inject_base shared browser utilities"

### 2.8: Extract devtools_util.py (Depends on _inject_base)

#### Task 2.8.1: Copy Source File
- [ ] Copy `onetool-mcp/src/ot_tools/devtools_util.py` to `onetool-dev/src/otdev/tools/devtools_util.py`
- [ ] Verify file copied successfully

#### Task 2.8.2: Update Imports
- [ ] Replace ot imports with otcommon imports
- [ ] Update `from ot_tools._inject_base import ...` to `from otdev.tools._inject_base import ...`
- [ ] Verify all imports resolve correctly

#### Task 2.8.3: Update Configuration Access
- [ ] Replace `get_tool_config("devtools_util", ...)` with `get_config().get("devtools_util", {})`
- [ ] Update browser_launch_timeout config access
- [ ] Verify configuration access works

#### Task 2.8.4: Update Pack Metadata
- [ ] Verify `pack = "devtools_util"` declaration exists
- [ ] Verify `__all__` lists all exported functions
- [ ] Verify `__ot_requires__` declares devtools MCP dependency
- [ ] Add E402 comment if needed

#### Task 2.8.5: Register Tool in Server
- [ ] Import devtools_util in `src/otdev/server.py`
- [ ] Add `devtools_util.mcp = mcp  # type: ignore[attr-defined]`
- [ ] Verify import order
- [ ] Verify type ignore comment

#### Task 2.8.6: Create Tests
- [ ] Create `tests/test_tools/test_devtools_util.py`
- [ ] Add import smoke test
- [ ] Add pack name verification test
- [ ] Add basic functionality test (mock MCP server)
- [ ] Mark tests appropriately

#### Task 2.8.7: Update Smoke Tests
- [ ] Verify `test_import_tool_modules()` includes `devtools_util`
- [ ] Verify `assert devtools_util.pack == "devtools_util"`
- [ ] Run smoke tests

#### Task 2.8.8: Lint and Type Check
- [ ] Run `just lint` - fix issues
- [ ] Run `ruff check --fix src/otdev/tools/devtools_util.py`
- [ ] Run `just typecheck`
- [ ] Add type ignores if needed

#### Task 2.8.9: Test and Validate
- [ ] Run `just test -k devtools_util`
- [ ] Run `just test -k smoke`
- [ ] Manually test if possible (requires devtools MCP)
- [ ] Commit: "feat(tools): extract devtools_util pack from onetool-mcp"

### 2.9: Extract playwright_util.py (Depends on _inject_base)

#### Task 2.9.1: Copy Source File
- [ ] Copy `onetool-mcp/src/ot_tools/playwright_util.py` to `onetool-dev/src/otdev/tools/playwright_util.py`
- [ ] Verify file copied successfully

#### Task 2.9.2: Update Imports
- [ ] Replace ot imports with otcommon imports
- [ ] Update `from ot_tools._inject_base import ...` to `from otdev.tools._inject_base import ...`
- [ ] Verify all imports resolve correctly

#### Task 2.9.3: Update Configuration Access
- [ ] Replace `get_tool_config("playwright_util", ...)` with `get_config().get("playwright_util", {})`
- [ ] Update browser_launch_timeout config access
- [ ] Verify configuration access works

#### Task 2.9.4: Update Pack Metadata
- [ ] Verify `pack = "playwright_util"` declaration exists
- [ ] Verify `__all__` lists all exported functions
- [ ] Verify `__ot_requires__` declares playwright MCP dependency
- [ ] Add E402 comment if needed

#### Task 2.9.5: Register Tool in Server
- [ ] Import playwright_util in `src/otdev/server.py`
- [ ] Add `playwright_util.mcp = mcp  # type: ignore[attr-defined]`
- [ ] Verify import order
- [ ] Verify type ignore comment

#### Task 2.9.6: Create Tests
- [ ] Create `tests/test_tools/test_playwright_util.py`
- [ ] Add import smoke test
- [ ] Add pack name verification test
- [ ] Add basic functionality test (mock MCP server)
- [ ] Mark tests appropriately

#### Task 2.9.7: Update Smoke Tests
- [ ] Verify `test_import_tool_modules()` includes `playwright_util`
- [ ] Verify `assert playwright_util.pack == "playwright_util"`
- [ ] Run smoke tests

#### Task 2.9.8: Lint and Type Check
- [ ] Run `just lint` - fix issues
- [ ] Run `ruff check --fix src/otdev/tools/playwright_util.py`
- [ ] Run `just typecheck`
- [ ] Add type ignores if needed

#### Task 2.9.9: Test and Validate
- [ ] Run `just test -k playwright_util`
- [ ] Run `just test -k smoke`
- [ ] Manually test if possible (requires playwright MCP)
- [ ] Commit: "feat(tools): extract playwright_util pack from onetool-mcp"

---

## Phase 3: Configuration and Documentation - 8 tasks

### Task 3.1: Update README.md
- [ ] Add project overview and purpose
- [ ] Add installation instructions (`uvx onetool-dev`)
- [ ] Add configuration guide (`~/.onetool/dev.yaml`)
- [ ] Add tool pack reference (8 packs with descriptions)
- [ ] Add usage examples (standalone and proxied modes)
- [ ] Add development setup instructions
- [ ] Add testing and quality check instructions
- [ ] Add contributing guidelines
- [ ] Add license information

### Task 3.2: Update CLAUDE.md
- [ ] Add project context and purpose
- [ ] Add architecture overview (FastMCP server, 8 tool packs)
- [ ] Add development workflow
- [ ] Add testing strategy
- [ ] Add quality standards (ruff, mypy, pytest)
- [ ] Add tool pack reference (brief descriptions)
- [ ] Add common commands and patterns
- [ ] Add troubleshooting tips

### Task 3.3: Update CHANGELOG.md
- [ ] Add v1.0.0 release entry
- [ ] List all 8 tool packs as features
- [ ] List dependencies
- [ ] List configuration options
- [ ] Add "Initial release" note

### Task 3.4: Update dev/agents/hints.md
- [ ] Document project structure
- [ ] List common commands (`just check`, `just test`, `just lint`, etc.)
- [ ] Document tool pack locations
- [ ] Document import patterns (otcommon usage)
- [ ] Document testing strategy (smoke, unit, integration markers)
- [ ] Add quick reference for common tasks

### Task 3.5: Update dev/agents/project-map.md
- [ ] Create detailed directory tree
- [ ] Document each module's purpose
- [ ] Document dependency graph
- [ ] List key files and their purposes
- [ ] Add notes about tool pack structure

### Task 3.6: Update openspec/project.md
- [ ] Add project context and background
- [ ] Reference add-onetool-dev proposal
- [ ] Document relationship to onetool-mcp refactor
- [ ] List key architectural decisions
- [ ] Add links to consultation documents

### Task 3.7: Update server.json
- [ ] Set name: "onetool-dev"
- [ ] Set version: "1.0.0"
- [ ] Set description
- [ ] Set entrypoint: "onetool-dev"
- [ ] Add basic config schema
- [ ] List all tool packs
- [ ] Add required dependencies (rg CLI, etc.)

### Task 3.8: Verify Documentation
- [ ] Run markdown lint: `npx markdownlint-cli2 "**/*.md"`
- [ ] Fix any markdown issues
- [ ] Verify all links work
- [ ] Verify code examples are correct
- [ ] Commit: "docs: complete documentation for onetool-dev"

---

## Phase 4: Quality Assurance - 6 tasks

### Task 4.1: Final Linting
- [ ] Run `just lint`
- [ ] Fix all auto-fixable issues: `ruff check --fix .`
- [ ] Manually fix remaining issues
- [ ] Verify E402 is ignored for tool files
- [ ] Run `ruff format .` to format code
- [ ] Commit: "style: apply linting and formatting fixes"

### Task 4.2: Type Checking
- [ ] Run `just typecheck`
- [ ] Fix critical type errors in src/otdev/server.py
- [ ] Fix critical type errors in src/otdev/cli.py
- [ ] Add `# type: ignore` comments for known patterns
- [ ] Accept pre-existing tool type errors (can address later)
- [ ] Document any remaining type issues

### Task 4.3: Testing
- [ ] Run `just test` - all tests must pass
- [ ] Verify all 7 smoke tests pass
- [ ] Run `pytest -v --tb=short` for detailed output
- [ ] Fix any failing tests
- [ ] Verify test coverage: `pytest --cov=otdev --cov-report=term`
- [ ] Commit: "test: ensure all tests pass"

### Task 4.4: Integration Testing
- [ ] Install package in clean environment: `uvx onetool-dev`
- [ ] Test version command: `onetool-dev version`
- [ ] Test server starts: `onetool-dev serve` (Ctrl+C to stop)
- [ ] Test with Claude Code .mcp.json configuration
- [ ] Verify all tool packs are accessible
- [ ] Test a few tools manually

### Task 4.5: Security and Quality Checks
- [ ] Run gitleaks: `gitleaks detect --source . --verbose`
- [ ] Verify no secrets in codebase
- [ ] Run markdown lint: `npx markdownlint-cli2 "**/*.md"`
- [ ] Fix any issues found
- [ ] Commit: "chore: address security and quality checks"

### Task 4.6: Final Validation
- [ ] Run `just check` - must pass completely
- [ ] Verify all 7 smoke tests passing
- [ ] Verify linting passes with no errors
- [ ] Verify type checking passes (acceptable tool errors documented)
- [ ] Verify documentation is complete and accurate
- [ ] Create BLOCKERS.md if any issues remain

---

## Phase 5: Publication and Distribution - 4 tasks

### Task 5.1: Prepare for Publication
- [ ] Verify version is set to "1.0.0" in all files
- [ ] Verify pyproject.toml is complete and correct
- [ ] Verify all dependencies are correctly specified
- [ ] Verify onetool-common dependency is correct
- [ ] Update CHANGELOG.md with final v1.0.0 notes
- [ ] Tag release: `git tag v1.0.0`

### Task 5.2: Build Package
- [ ] Run `uv build`
- [ ] Verify dist/ directory created
- [ ] Verify wheel and source distribution created
- [ ] Check package metadata: `tar -tzf dist/onetool-dev-1.0.0.tar.gz | head -20`
- [ ] Verify package size is reasonable (~200-300 KB source)

### Task 5.3: Publish to PyPI
- [ ] Test publish to Test PyPI first (optional): `uv publish --repository testpypi`
- [ ] Verify package on Test PyPI (if used)
- [ ] Publish to PyPI: `uv publish`
- [ ] Verify package appears on PyPI: https://pypi.org/project/onetool-dev/
- [ ] Verify package metadata is correct on PyPI

### Task 5.4: Final Verification
- [ ] Install from PyPI in fresh environment: `uvx onetool-dev@latest`
- [ ] Verify version: `onetool-dev version` shows "1.0.0"
- [ ] Test basic functionality
- [ ] Push to GitHub: `git push && git push --tags`
- [ ] Verify GitHub repository shows v1.0.0 tag
- [ ] Verify repository is still private
- [ ] Create GitHub release from tag with CHANGELOG notes

---

## Summary

**Total tasks:** 103
- Phase 1: Project setup - 15 tasks
- Phase 2: Tool extraction - 72 tasks (8 tools × 9 tasks)
- Phase 3: Configuration and documentation - 8 tasks
- Phase 4: Quality assurance - 6 tasks
- Phase 5: Publication - 4 tasks

**Estimated completion time:** ~2.5 days with Claude Code assistance

**Key milestones:**
1. ✅ Phase 1 complete → Project structure ready
2. ✅ Phase 2 complete → All tools extracted and working
3. ✅ Phase 3 complete → Documentation complete
4. ✅ Phase 4 complete → All quality checks passing
5. ✅ Phase 5 complete → Package published and verified

**Success criteria:**
- All 7 smoke tests passing
- `just check` passes completely
- Package published to PyPI
- Repository on GitHub (private)
- Documentation complete
