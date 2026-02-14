# Tasks: Refactor onetool-mcp to Frontend/Proxy Role

**Dependencies:**
- onetool-util exists (DONE)
- onetool-dev exists (DONE)
- onetool-common exists (DONE)

## Phase 1: Remove Extracted Tools (2 hours)

### Task 1.1: Create MIGRATION.md (30 min)
- [ ] Create wip/MIGRATION.md documenting what moved where
- [ ] List all tools extracted to onetool-util
- [ ] List all tools extracted to onetool-dev
- [ ] Note what remains in onetool-mcp (mem, timer, scaffold, transform, meta)
- [ ] Validation: Document is clear and comprehensive

### Task 1.2: Remove onetool-util tools (30 min)
- [ ] Delete src/ot_tools/file.py
- [ ] Delete src/ot_tools/excel.py
- [ ] Delete src/ot_tools/convert.py
- [ ] Delete src/ot_tools/_convert/ directory
- [ ] Delete src/ot_tools/brave_search.py
- [ ] Delete src/ot_tools/grounding_search.py
- [ ] Validation: Files no longer exist

### Task 1.3: Remove onetool-dev tools (30 min)
- [ ] Delete src/ot_tools/db.py
- [ ] Delete src/ot_tools/ripgrep.py
- [ ] Delete src/ot_tools/web_fetch.py
- [ ] Delete src/ot_tools/package.py
- [ ] Delete src/ot_tools/context7.py
- [ ] Delete src/ot_tools/diagram.py
- [ ] Delete src/ot_tools/devtools_util.py
- [ ] Delete src/ot_tools/playwright_util.py
- [ ] Delete src/ot_tools/_inject_base.py
- [ ] Validation: Files no longer exist

### Task 1.4: Verify core tools remain (15 min)
- [ ] Verify src/ot_tools/mem.py exists
- [ ] Verify src/ot_tools/timer.py exists
- [ ] Verify src/ot_tools/scaffold.py exists
- [ ] Verify src/ot_tools/transform.py exists
- [ ] Verify src/ot_tools/meta.py exists
- [ ] Commit: `refactor: remove extracted tools (now in backends)`
- [ ] Validation: Only 5 tool files remain in ot_tools/

### Task 1.5: Remove tool tests (15 min)
- [ ] Delete tests for extracted tools (test_file, test_excel, test_db, etc.)
- [ ] Keep tests for core tools (test_mem, test_timer, etc.)
- [ ] Commit: `test: remove tests for extracted tools`
- [ ] Validation: Test suite still runs, passes with remaining tests

## Phase 2: Consolidate with onetool-common (6-8 hours)

### Task 2.1: Replace ot.http_client (30 min)
- [ ] Update src/ot_tools/web.py: `from otcommon.http import get_client`
- [ ] Update src/ot_tools/context7.py: `from otcommon.http import get_client`
- [ ] Verify no other usages of ot.http_client
- [ ] Delete src/ot/http_client.py
- [ ] Run tests to verify imports work
- [ ] Commit: `refactor: replace ot.http_client with otcommon.http`
- [ ] Validation: 146 LOC removed, tests pass

### Task 2.2: Consolidate ot.logging (2 hours)
- [ ] Identify MCP-specific code: InterceptHandler, JSONEncoder, json_serializer
- [ ] Create src/ot/logging/mcp_adapters.py with MCP-specific code (~184 LOC)
- [ ] Update imports across codebase: `from otcommon.logging import LogSpan, setup_logging`
- [ ] Keep ot.logging.mcp_adapters for MCP-specific extensions
- [ ] Delete duplicated base logging code
- [ ] Run all tests
- [ ] Commit: `refactor: consolidate ot.logging with otcommon.logging`
- [ ] Validation: ~921 LOC removed, tests pass

### Task 2.3: Consolidate ot.config (3 hours)
- [ ] Keep src/ot/config/models.py (ServerConfig, ProxyConfig, ExecutorConfig) ~739 LOC
- [ ] Keep src/ot/config/validation.py (~299 LOC)
- [ ] Update imports: `from otcommon.config import load_config, expand_vars, deep_merge`
- [ ] Replace base YAML loading logic with otcommon.config
- [ ] Update tests to use otcommon.config where applicable
- [ ] Commit: `refactor: consolidate ot.config base with otcommon.config`
- [ ] Validation: ~716 LOC removed, models/validation kept, tests pass

### Task 2.4: Consolidate ot.paths (1.5 hours)
- [ ] Identify MCP-specific paths: get_tools_dir, get_registry_dir, get_executor_cache_dir
- [ ] Create src/ot/paths_mcp.py with MCP-specific paths (~193 LOC)
- [ ] Update imports: `from otcommon.paths import resolve_path, get_project_dir`
- [ ] Delete duplicated base path code
- [ ] Update all path imports across codebase
- [ ] Run tests
- [ ] Commit: `refactor: consolidate ot.paths with otcommon.paths`
- [ ] Validation: ~244 LOC removed, tests pass

### Task 2.5: Update pyproject.toml dependencies (30 min)
- [ ] Add onetool-common as dependency
- [ ] Verify onetool-common brings: pydantic, pyyaml, loguru, httpx, typer
- [ ] No changes yet to other dependencies (wait for Task 6)
- [ ] Commit: `chore: add onetool-common dependency`
- [ ] Validation: `just check` passes with new dependency

## Phase 3: Implement Backend Proxy (1 day)

### Task 3.1: Create proxy module structure (15 min)
- [ ] Create src/ot/proxy/__init__.py
- [ ] Create src/ot/proxy/manager.py (skeleton)
- [ ] Create src/ot/proxy/client.py (skeleton)
- [ ] Create src/ot/proxy/discovery.py (skeleton)
- [ ] Validation: Module imports successfully

### Task 3.2: Implement BackendConfig model (30 min)
- [ ] Add to src/ot/config/models.py:
  - BackendServerConfig (command, args, env, enabled, lazy)
  - Update OneToolConfig to include backend_servers field
- [ ] Write tests for config models
- [ ] Validation: Config model tests pass

### Task 3.3: Implement MCP client (2 hours)
- [ ] Implement src/ot/proxy/client.py:
  - MCPClient class
  - connect() - start subprocess with stdio
  - list_tools() - MCP protocol
  - list_prompts() - MCP protocol
  - list_resources() - MCP protocol
  - call_tool() - MCP protocol
  - disconnect() - cleanup
- [ ] Write unit tests for MCPClient
- [ ] Validation: Can connect to onetool-util, list tools, call tool

### Task 3.4: Implement proxy manager (3 hours)
- [ ] Implement src/ot/proxy/manager.py:
  - ProxyManager class
  - __init__(backends: dict[str, BackendServerConfig])
  - start() - start non-lazy backends
  - _start_backend(name) - start backend subprocess
  - call_tool(tool_name, **kwargs) - route to correct backend
  - list_all_tools() - aggregate from all backends
  - health_check() - verify all backends respond
  - shutdown() - cleanup all backends
- [ ] Implement lazy loading (start backend on first use)
- [ ] Write tests for ProxyManager
- [ ] Validation: Can manage multiple backends, route calls correctly

### Task 3.5: Implement backend discovery (1 hour)
- [ ] Implement src/ot/proxy/discovery.py:
  - discover_backends(config) - load from config
  - validate_backend(config) - check command exists
  - Auto-discovery from installed packages (optional)
- [ ] Write tests
- [ ] Validation: Discovers backends from config correctly

### Task 3.6: Integrate with executor (2 hours)
- [ ] Update executor namespace building to include backend tools
- [ ] Create PackProxy class for pack.tool() syntax
- [ ] Map backend tools to namespace (e.g., file.read() routes to onetool-util)
- [ ] Write integration tests
- [ ] Validation: `__ot file.read(path="test.txt")` works via proxy

## Phase 4: Update Configuration (2 hours)

### Task 4.1: Create default backend_servers config (30 min)
- [ ] Add to default ~/.onetool/onetool.yaml template:
  ```yaml
  backend_servers:
    onetool-util:
      command: uvx
      args: ["onetool-util", "--config", "~/.onetool/util.yaml"]
      enabled: true
      lazy: true
    onetool-dev:
      command: uvx
      args: ["onetool-dev", "--config", "~/.onetool/dev.yaml"]
      enabled: true
      lazy: true
  ```
- [ ] Validation: Config loads successfully

### Task 4.2: Update config loading to start backends (30 min)
- [ ] Update main startup to initialize ProxyManager
- [ ] Start backends based on config
- [ ] Handle backend startup failures gracefully
- [ ] Validation: Backends start on onetool startup

### Task 4.3: Add backend_servers schema validation (30 min)
- [ ] Add validation for backend_servers section
- [ ] Check required fields (command, args)
- [ ] Validate paths exist for command
- [ ] Write validation tests
- [ ] Validation: Invalid configs rejected with clear errors

### Task 4.4: Update config documentation (30 min)
- [ ] Document backend_servers section in config docs
- [ ] Add examples for official backends
- [ ] Add examples for external backends (github, devtools)
- [ ] Validation: Documentation clear and accurate

## Phase 5: Update Meta Tools (1 hour)

### Task 5.1: Update ot.tools() (30 min)
- [ ] Modify to include backend tools
- [ ] Query ProxyManager for all backend tools
- [ ] Merge with core tools
- [ ] Filter by pattern if provided
- [ ] Validation: `ot.tools()` shows 100+ tools from backends

### Task 5.2: Update ot.help() (30 min)
- [ ] Update search to include backend tools
- [ ] Show which backend each tool comes from
- [ ] Update examples
- [ ] Validation: `ot.help(query="file")` shows file pack from onetool-util

## Phase 6: Remove Heavy Dependencies (1 hour)

### Task 6.1: Identify removable dependencies (15 min)
- [ ] List dependencies now only in backends:
  - pymupdf, python-docx, python-pptx, openpyxl (in onetool-util)
  - sqlalchemy, trafilatura (in onetool-dev)
  - google-generativeai (in onetool-util)
- [ ] Validation: Confirmed these are not used in core

### Task 6.2: Update pyproject.toml (15 min)
- [ ] Remove backend-specific dependencies
- [ ] Keep core dependencies: fastmcp, openai, tiktoken, jinja2, onetool-common
- [ ] Commit: `chore: remove backend-specific dependencies`
- [ ] Validation: Dependency count reduced from ~100 to ~10-15

### Task 6.3: Test without heavy dependencies (30 min)
- [ ] Run `uv sync`
- [ ] Run all tests
- [ ] Verify core functionality works
- [ ] Validation: Tests pass, significantly smaller venv

## Phase 7: Update Tests (4 hours)

### Task 7.1: Write proxy unit tests (2 hours)
- [ ] tests/test_proxy/test_client.py - MCPClient tests
- [ ] tests/test_proxy/test_manager.py - ProxyManager tests
- [ ] tests/test_proxy/test_discovery.py - Discovery tests
- [ ] Mock backend responses
- [ ] Test error handling
- [ ] Validation: All proxy tests pass

### Task 7.2: Write proxy integration tests (1.5 hours)
- [ ] tests/integration/test_backend_proxy.py
- [ ] Test connection to real onetool-util backend
- [ ] Test tool call routing
- [ ] Test multiple backends
- [ ] Test lazy loading
- [ ] Test fault isolation (backend crash doesn't affect core)
- [ ] Validation: Integration tests pass with real backends

### Task 7.3: Update existing tests (30 min)
- [ ] Update tests that depend on removed tools
- [ ] Update config tests for new backend_servers section
- [ ] Update meta tool tests
- [ ] Validation: All existing tests pass

## Phase 8: Update Documentation (2 hours)

### Task 8.1: Update README.md (30 min)
- [ ] Add v2.0 architecture section
- [ ] Explain backend servers concept
- [ ] Update installation instructions
- [ ] Update tool count (~5 core + 100+ via backends)
- [ ] Validation: README accurately reflects v2.0

### Task 8.2: Update CLAUDE.md (30 min)
- [ ] Update project structure
- [ ] Document backend_servers config
- [ ] Update tool count and examples
- [ ] Add backend proxy section
- [ ] Validation: CLAUDE.md accurate for v2.0

### Task 8.3: Update CHANGELOG.md (30 min)
- [ ] Document v2.0.0 breaking changes
- [ ] List tool migrations (where tools moved)
- [ ] Note 85-90% dependency reduction
- [ ] Backend server features
- [ ] Validation: CHANGELOG comprehensive

### Task 8.4: Create migration guide (30 min)
- [ ] Create docs/migration-v2.md
- [ ] Explain v1.x → v2.0 changes
- [ ] Config migration steps
- [ ] Backend installation
- [ ] Troubleshooting
- [ ] Validation: Migration guide clear and helpful

## Verification

### Final Checklist
- [ ] 14 tool files removed from ot_tools/
- [ ] 5 core tools remain (mem, timer, scaffold, transform, meta)
- [ ] ot.http_client deleted, using otcommon.http
- [ ] ot.logging consolidated (~921 LOC removed)
- [ ] ot.config consolidated (~716 LOC removed)
- [ ] ot.paths consolidated (~244 LOC removed)
- [ ] Total LOC reduction: ~2,027 LOC + removed tools
- [ ] Proxy manager working, connects to backends
- [ ] backend_servers config section implemented
- [ ] Meta tools show backend tools
- [ ] Dependencies: ~10-15 (from ~100), 85-90% reduction
- [ ] All tests passing (smoke, unit, integration, proxy)
- [ ] `just check` passes
- [ ] Documentation updated for v2.0

### Success Test
- [ ] Start onetool: backends auto-start
- [ ] Call backend tool: `__ot file.read(path="test.txt")` works
- [ ] List all tools: `__ot ot.tools()` shows 100+ tools
- [ ] Backend crash: core still works (fault isolation)
- [ ] Check dependencies: <15 packages in venv

## Notes

- **Parallelization:** Tasks in Phase 2 (consolidation) can partially overlap
- **Risk:** Config/logging changes require careful testing - use `just check` after each
- **Testing:** Run integration tests with real backends throughout
- **Rollback:** Keep v1.x branch before starting
