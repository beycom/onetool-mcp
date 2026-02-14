# Proposal: add-onetool-util

**Status:** Draft
**Created:** 2026-02-14
**Depends on:** add-onetool-common (completed)

---

## Summary

Create `onetool-util` as a standalone MCP server containing general-purpose utility tools extracted from `onetool-mcp`. This is the second phase of the v2.0 modular architecture refactor.

**What:**
- Create new repository: `github.com/beycom/onetool-util`
- Extract 5 tool packs (~64 tools) from `onetool-mcp/src/ot_tools/`:
  - `file.py` - File operations (read, write, edit, delete, copy, move, list, tree, search, info)
  - `excel.py` - Excel workbook manipulation (create, read, write, format, formulas, tables)
  - `convert.py` + `_convert/` - Document conversion (PDF, Word, PowerPoint, Excel to markdown)
  - `brave_search.py` - Brave Search API integration (web, news, local, image, video search)
  - `grounding_search.py` - Google Grounding API integration (search with sources)
- Build on `onetool-common` shared library for config, logging, and utilities
- Publish to PyPI as `onetool-util`
- Support dual-mode operation: standalone MCP server OR proxied via onetool-mcp

**Why:**
- **Dependency isolation** - Heavy dependencies (pymupdf, openpyxl, google-genai) isolated to util backend
- **Fault isolation** - Util backend crashes don't affect other backends or core
- **Selective installation** - Users install only if they need utility tools
- **Token efficiency** - When proxied, ~95% reduction (30K→2K tokens)
- **Independent development** - Util backend evolves without coordinating with core

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
- Provides: config loading, logging, path resolution, HTTP helpers, CLI boilerplate
- Template available for new backends in `onetool-common/template/`
- Proven pattern with onetool-xero refactoring

### This Proposal

**Proposal 2: add-onetool-util (This)**
- First backend server to be extracted
- Establishes the backend server pattern for utility tools
- Paves the way for Proposal 3 (onetool-dev) and Proposal 4 (onetool-mcp refactor)

### Related Work

- **v2.0 refactor roadmap:** `wip/consult/v2-refactor.md`
- **Architecture decisions:** `wip/consult/one-servers.md`
- **Migration plan:** `wip/consult/one-server-migration.md`

---

## Objectives

### Primary Goals

1. **Create standalone backend server**
   - Repository structure following onetool-common template
   - FastMCP server with ~64 tools from 5 packs
   - Standard `--config` CLI interface
   - Dual-mode: standalone OR proxied operation

2. **Extract and adapt tools**
   - Move tools from onetool-mcp with minimal changes
   - Update imports: `ot.config` → `otcommon.config`, etc.
   - Preserve all existing functionality and behavior
   - Maintain test coverage

3. **Publish and distribute**
   - PyPI package: `onetool-util`
   - Invocation: `uvx onetool-util --config ~/.onetool/util.yaml`
   - GitHub repository with CI/CD
   - Documentation and examples

### Success Criteria

- ✅ `just check` passes (lint, typecheck, test)
- ✅ Standalone mode: Starts as MCP server, responds to tool calls
- ✅ Config: Loads from `~/.onetool/util.yaml`
- ✅ Tools: All 64 tools work identically to onetool-mcp v1.x
- ✅ Tests: All tool tests pass
- ✅ Docs: README, tool reference, configuration guide
- ✅ Quality: Matches onetool-common standards (ruff, mypy, pytest)

---

## Design

### Repository Structure

```
onetool-util/
├── pyproject.toml              # Python package definition
├── justfile                    # Build and test commands
├── CLAUDE.md                   # Agent instructions
├── README.md                   # User documentation
├── CHANGELOG.md                # Version history
├── .mcp.json                   # Local MCP testing config
├── server.json                 # MCP server metadata
├── src/
│   └── otutil/                 # Python module (PEP 8: no underscores)
│       ├── __init__.py         # Package metadata, version
│       ├── server.py           # FastMCP server entry point
│       ├── cli.py              # Typer CLI (serve, version commands)
│       └── tools/
│           ├── file.py         # File operations pack
│           ├── excel.py        # Excel manipulation pack
│           ├── convert.py      # Document conversion pack
│           ├── brave.py        # Brave Search pack (renamed from brave_search)
│           ├── ground.py       # Grounding Search pack (renamed from grounding_search)
│           └── _convert/       # Conversion submodules
│               ├── __init__.py
│               ├── pdf.py
│               ├── word.py
│               ├── powerpoint.py
│               ├── excel.py
│               └── utils.py
├── tests/
│   ├── conftest.py             # Test fixtures
│   ├── test_sanity.py          # Import and startup smoke tests
│   └── test_tools/
│       ├── test_file.py
│       ├── test_excel.py
│       ├── test_convert.py
│       ├── test_brave.py
│       └── test_ground.py
├── openspec/                   # OpenSpec documentation
│   └── project.md              # Project context
└── dev/
    └── agents/
        ├── hints.md            # Quick reference for agents
        └── project-map.md      # Detailed project structure
```

### Key Design Decisions

#### 1. Python Module Naming

**Decision:** Use `otutil` (no underscores)

**Rationale:**
- PEP 8 compliant: Prefer `sklearn`, `bs4` pattern over `scikit_learn`, `beautiful_soup`
- Consistent with `otcommon` and `otxero` naming
- Package name (`onetool-util`) uses kebab-case as standard for PyPI

**Implementation:**
```python
# Package name (PyPI): onetool-util
# Python module: otutil
from otutil.tools import file, excel, convert, brave, ground
```

#### 2. Tool Pack Renaming

**Changes:**
- `brave_search.py` → `brave.py` (pack name: `brave`)
- `grounding_search.py` → `ground.py` (pack name: `ground`)
- Others keep names: `file`, `excel`, `convert`

**Rationale:**
- Shorter, cleaner names
- Consistent with pack naming convention
- No backwards compatibility needed (v2.0 is a clean break)

#### 3. Dependency on onetool-common

**Decision:** Use editable local install during development, version constraint in production

**Development:**
```toml
[tool.uv.sources]
onetool-common = { path = "../onetool-common", editable = true }
```

**Production:**
```toml
[project]
dependencies = ["onetool-common>=0.1.0,<1.0.0"]
```

**Rationale:**
- Fast iteration during v2.0 refactor
- Changes to onetool-common immediately visible
- Production uses semantic versioning for stability

#### 4. Configuration Structure

**Location:** `~/.onetool/util.yaml`

**Format:**
```yaml
version: 1.0.0

# Logging
log_level: INFO
log_file: ~/.onetool/logs/onetool-util.log

# Tool-specific config
file:
  allowed_dirs: ["."]
  exclude_patterns: [".git", "node_modules"]
  max_file_size: 10000000
  backup_on_write: true

excel:
  max_file_size: 100000000

convert:
  default_format: markdown
  max_workers: 4

brave:
  timeout: 30
  max_results: 10

ground:
  timeout: 30
  max_sources: 5
```

**Secrets:** `~/.onetool/secrets.yaml` (shared across backends)
```yaml
brave:
  api_key: "BSA..."

google:
  api_key: "AI..."
```

#### 5. Tool Registration Pattern

**Decision:** Use `otcommon.tools.@tool_wrapper()` decorator pattern (from onetool-xero)

**Implementation:**
```python
# src/otutil/tools/file.py
from otcommon.tools import tool_wrapper

mcp = None  # Injected by server.py

@tool_wrapper(mcp)
def read(*, path: str) -> str:
    """Read file contents."""
    # ... implementation
```

```python
# src/otutil/server.py
from fastmcp import FastMCP
from otutil.tools import file, excel, convert, brave, ground

mcp = FastMCP(name="onetool-util")

# Inject mcp instance into tool modules
file.mcp = excel.mcp = convert.mcp = brave.mcp = ground.mcp = mcp

# Tools auto-register via @tool_wrapper decorators
```

**Rationale:**
- Proven in onetool-xero
- Minimal boilerplate
- Consistent with onetool-common patterns
- Easy to maintain

---

## Migration Strategy

### Two-Phase Approach

**Phase 1: This Proposal (add-onetool-util)**
- ✅ COPY all code, tests, specs, and docs to onetool-util
- ✅ Track what was copied in MIGRATION.md
- ❌ DO NOT remove anything from onetool-mcp yet

**Phase 2: Future Proposal (refactor-onetool-mcp)**
- REMOVE copied files from onetool-mcp
- Use MIGRATION.md as deletion checklist
- Update onetool-mcp to proxy to onetool-util

**Rationale:**
- Allows onetool-util to be complete and standalone immediately
- Defers breaking changes to onetool-mcp until v2.0 refactor complete
- Prevents rework - copy once, delete once
- Clear tracking makes deletion safe and complete

### What Gets Copied

**Code (5 tool packs):**
- `onetool-mcp/src/ot_tools/file.py` → `onetool-util/src/otutil/tools/file.py`
- `onetool-mcp/src/ot_tools/excel.py` → `onetool-util/src/otutil/tools/excel.py`
- `onetool-mcp/src/ot_tools/convert.py` → `onetool-util/src/otutil/tools/convert.py`
- `onetool-mcp/src/ot_tools/brave_search.py` → `onetool-util/src/otutil/tools/brave.py` (renamed)
- `onetool-mcp/src/ot_tools/grounding_search.py` → `onetool-util/src/otutil/tools/ground.py` (renamed)
- `onetool-mcp/src/ot_tools/_convert/` → `onetool-util/src/otutil/tools/_convert/` (entire directory)

**Tests:**
- `onetool-mcp/tests/test_tools/test_file.py` → `onetool-util/tests/test_tools/test_file.py`
- `onetool-mcp/tests/test_tools/test_excel.py` → `onetool-util/tests/test_tools/test_excel.py`
- `onetool-mcp/tests/test_tools/test_convert.py` → `onetool-util/tests/test_tools/test_convert.py`
- `onetool-mcp/tests/test_tools/test_brave*.py` → `onetool-util/tests/test_tools/test_brave.py`
- `onetool-mcp/tests/test_tools/test_ground*.py` → `onetool-util/tests/test_tools/test_ground.py`
- Related test fixtures and conftest.py sections

**Specs (OpenSpec):**
- `onetool-mcp/openspec/specs/tool-file/` → `onetool-util/openspec/specs/tool-file/`
- `onetool-mcp/openspec/specs/tool-excel/` → `onetool-util/openspec/specs/tool-excel/`
- `onetool-mcp/openspec/specs/tool-convert/` → `onetool-util/openspec/specs/tool-convert/`
- `onetool-mcp/openspec/specs/tool-brave/` → `onetool-util/openspec/specs/tool-brave/`
- `onetool-mcp/openspec/specs/tool-ground/` → `onetool-util/openspec/specs/tool-ground/`

**Documentation:**
- Relevant tool descriptions from onetool-mcp README
- Tool-specific docs from onetool-mcp docs/
- Examples and use cases for extracted tools
- Configuration documentation for tool-specific settings

### Migration Tracking

**MIGRATION.md format:**
```markdown
# Migration Tracking: onetool-mcp → onetool-util

Files copied from onetool-mcp to onetool-util.
Use this for deletion in Proposal 4 (refactor-onetool-mcp).

## Code
- src/ot_tools/file.py → src/otutil/tools/file.py
- src/ot_tools/excel.py → src/otutil/tools/excel.py
- src/ot_tools/convert.py → src/otutil/tools/convert.py
- src/ot_tools/brave_search.py → src/otutil/tools/brave.py
- src/ot_tools/grounding_search.py → src/otutil/tools/ground.py
- src/ot_tools/_convert/ → src/otutil/tools/_convert/ (entire directory)

## Tests
- tests/test_tools/test_file.py
- tests/test_tools/test_excel.py
[...]

## Specs
- openspec/specs/tool-file/
- openspec/specs/tool-excel/
[...]

## Docs
- README.md sections: [list specific sections]
- docs/tools/file.md
[...]
```

### Import Path Changes

**Pattern:** `ot.*` → `otcommon.*`

**Files affected:**
- All copied tool files (file.py, excel.py, convert.py, brave.py, ground.py)
- All _convert/ submodules

**Changes per file (~5-10 imports):**
```python
# OLD (onetool-mcp)
from ot.config import get_tool_config, get_secret
from ot.logging import LogSpan
from ot.paths import resolve_cwd_path
from ot.http_client import http_get

# NEW (onetool-util)
from otcommon.config import get_tool_config, get_secret
from otcommon.logging import LogSpan
from otcommon.paths import resolve_cwd_path
from otcommon.http import http_get
```

**Estimate:** ~30-50 import lines to update across all files

### Temporary Duplication

**During transition (v2.0 development):**
- onetool-mcp contains: file, excel, convert, brave, ground tools
- onetool-util contains: same tools (copied)
- Both are functional
- Tests pass in both repos

**After Proposal 4 (refactor-onetool-mcp):**
- onetool-mcp: Tools removed, proxies to onetool-util
- onetool-util: Standalone backend server
- No duplication

**Benefits:**
- Zero downtime migration
- Clear rollback path (keep using onetool-mcp v1.x)
- Each repo independently testable
- Clean cutover when ready

### Breaking Changes

**None for users of onetool-mcp v1.x** - This is a new package

**For v2.0 users (after Proposal 4):**
- Tools move from `onetool-mcp` to `onetool-util`
- Import paths change (only affects direct Python usage, not MCP)
- Config location: `~/.onetool/util.yaml` (new)

**Migration path for v1.x users:**
- Install onetool-util: `uvx onetool-util`
- Update MCP config to point to onetool-util
- Or: Use onetool-mcp v2.0 which proxies to backends

---

## Dependencies

### Python Dependencies

```toml
[project]
dependencies = [
    # Core
    "fastmcp>=2.14.0,<3.0.0",
    "onetool-common>=0.1.0,<1.0.0",

    # Tool-specific
    "openpyxl>=3.1.0",           # Excel
    "pymupdf>=1.24.0",           # PDF conversion
    "python-docx>=1.1.0",        # Word conversion
    "python-pptx>=1.0.0",        # PowerPoint conversion
    "pillow>=10.0.0",            # Image conversion
    "google-genai>=0.8.0",       # Grounding search
    "httpx>=0.28.0",             # Brave search, HTTP client
    "trafilatura>=2.0.0",        # Web content extraction
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.24.0",
    "ruff>=0.9.0",
    "mypy>=1.13.0",
]
```

**Heavy dependencies extracted:**
- `pymupdf` - 20MB+ (PDF processing)
- `google-genai` - Large AI SDK
- `openpyxl` - Excel manipulation
- `python-docx`, `python-pptx` - Office document processing

**Total package size:** ~100-120 MB (isolated from core)

### External Services

**Required for full functionality:**
- **Brave Search API** - Requires `BRAVE_API_KEY` environment variable or config
- **Google Gemini API** - Requires `GEMINI_API_KEY` for grounding search

**Graceful degradation:**
- Tools fail with clear error messages if API keys missing
- Other tools continue working

---

## Testing Strategy

### Test Coverage

**Smoke tests (fast):**
- `test_sanity.py` - Import all modules, start server
- Basic tool calls for each pack

**Unit tests:**
- `test_tools/test_file.py` - All file operations
- `test_tools/test_excel.py` - Excel manipulation
- `test_tools/test_convert.py` - Document conversion
- `test_tools/test_brave.py` - Brave API (mocked)
- `test_tools/test_ground.py` - Grounding API (mocked)

**Integration tests:**
- End-to-end MCP server communication
- Config loading with secrets
- Logging output format

### Test Markers

```python
@pytest.mark.smoke     # Fast sanity checks (<1s)
@pytest.mark.unit      # Unit tests (<1s, no I/O)
@pytest.mark.tools     # Tool-specific tests
@pytest.mark.integration  # End-to-end tests
```

### CI/CD

**GitHub Actions:**
- Lint (ruff)
- Typecheck (mypy)
- Test (pytest)
- Build (uv build)
- Release (cliff + git tag)

---

## Documentation

### Required Documentation

1. **README.md**
   - Overview and features
   - Installation instructions
   - Quick start guide
   - Tool reference (brief)
   - Configuration examples

2. **Tool Reference** (in README or separate)
   - File operations (18 tools)
   - Excel manipulation (30 tools)
   - Document conversion (5 tools)
   - Brave search (6 tools)
   - Grounding search (5 tools)

3. **Configuration Guide**
   - Config file structure
   - Secrets management
   - Tool-specific settings
   - Environment variables

4. **Examples**
   - Common use cases
   - Integration with onetool-mcp
   - Standalone usage

### Agent Documentation

**dev/agents/hints.md** - Quick reference
**dev/agents/project-map.md** - Detailed structure
**openspec/project.md** - Project context

---

## Risks and Mitigations

### Risk 1: Import Path Breakage

**Risk:** Mechanical import changes introduce bugs

**Mitigation:**
- Careful find-and-replace
- Run `just check` after each file
- Test each tool manually
- Compare behavior with onetool-mcp v1.x

**Likelihood:** Low (mechanical change)
**Impact:** Medium (tool breakage)

### Risk 2: Tool Behavior Regression

**Risk:** Tools behave differently in new environment

**Mitigation:**
- Copy tools verbatim first
- Change only imports initially
- Run existing tests against new package
- Smoke test each tool with Claude Code

**Likelihood:** Low
**Impact:** High (user-facing)

### Risk 3: Dependency Conflicts

**Risk:** Heavy deps conflict during development

**Mitigation:**
- Use `uv` for isolated environments
- Test installation in fresh venv
- Document known conflicts

**Likelihood:** Low (isolated backend)
**Impact:** Medium (installation issues)

### Risk 4: API Key Configuration

**Risk:** Users confused about API key setup

**Mitigation:**
- Clear error messages
- Documentation with examples
- Graceful degradation (other tools work)
- Template config with placeholders

**Likelihood:** Medium
**Impact:** Low (user education)

---

## Alternatives Considered

### Alternative 1: Keep Tools in onetool-mcp

**Rejected because:**
- Defeats purpose of v2.0 modular architecture
- Dependency bloat remains
- No fault isolation
- Proposal 1 (onetool-common) wasted effort

### Alternative 2: Create Micro-Backends Per Tool Pack

**Rejected because:**
- Too granular (5 separate repos/packages)
- Overhead outweighs benefits
- Util tools are cohesive group
- More complex for users to install

### Alternative 3: Bundle All Non-Core Tools in One Backend

**Rejected because:**
- Mixes util and dev tools (different concerns)
- Single point of failure
- Harder to maintain
- v2-refactor plan already splits util vs dev

---

## Open Questions

### Q1: PyPI Publishing Timeline

**Question:** Publish to PyPI immediately or wait for full v2.0 release?

**Options:**
- **Option A:** Publish immediately as `onetool-util==1.0.0-beta.1`
- **Option B:** Wait for Proposals 3+4 completion, release all together

**Recommendation:** Option A - Early feedback, independent versioning

**Status:** To be decided during implementation

### Q2: Backwards Compatibility for onetool-mcp

**Question:** Should onetool-mcp v1.x keep util tools while v2.0 extracts them?

**Options:**
- **Option A:** Branch v1.x, keep tools, only security fixes
- **Option B:** Remove from v1.x immediately (breaking)

**Recommendation:** Option A - Safety for existing users

**Status:** Deferred to Proposal 4 (onetool-mcp refactor)

---

## Next Steps

1. **Approve this proposal** - Review and approve design decisions
2. **Create repository** - Initialize `github.com/beycom/onetool-util`
3. **Scaffold project** - Use onetool-common template
4. **Extract tools** - Copy and adapt tool packs
5. **Implement server** - FastMCP server and CLI
6. **Write tests** - Ensure all tools work
7. **Document** - README, examples, configuration
8. **Publish** - PyPI package and GitHub release

---

## References

- **v2.0 Refactor Roadmap:** `wip/consult/v2-refactor.md`
- **Architecture Decisions:** `wip/consult/one-servers.md`
- **Migration Plan:** `wip/consult/one-server-migration.md`
- **onetool-common Template:** `../onetool-common/template/`
- **onetool-xero Reference:** See for tool registration pattern

---

**Proposal Status:** Ready for review
**Estimated Effort:** 0.5 days with AI assistance
**Blocking:** None (onetool-common complete)
**Blocks:** Proposal 3 (onetool-dev), Proposal 4 (onetool-mcp refactor)
