# Tasks: add-onetool-util

**Status:** Ready
**Proposal:** `proposal.md`
**Design:** `design.md`

---

## Task List

### Phase 1: Repository Setup (Foundation)

- [ ] **1.1** Create GitHub repository `github.com/beycom/onetool-util` (private)
- [ ] **1.2** Initialize local git repository in `/Users/gavin/01-work-thor/projects/group-hobby/onetool-util`
- [ ] **1.3** Create branch structure: `main` branch
- [ ] **1.4** Set up repository settings (branch protection, required checks)

### Phase 2: Project Scaffolding (Structure)

- [ ] **2.1** Copy template from `onetool-common/template/` to `onetool-util/`
- [ ] **2.2** Create `pyproject.toml` with dependencies:
  - [ ] Core: fastmcp>=2.14.0, onetool-common>=0.1.0
  - [ ] Tools: openpyxl, pymupdf, python-docx, python-pptx, pillow, google-genai, httpx, trafilatura
  - [ ] Dev: pytest, ruff, mypy
- [ ] **2.3** Create `justfile` with standard commands (check, lint, typecheck, test, dev)
- [ ] **2.4** Create `.mcp.json` for local MCP testing
- [ ] **2.5** Create `server.json` with MCP server metadata
- [ ] **2.6** Create `CLAUDE.md` with agent instructions
- [ ] **2.7** Create `README.md` template (populate later)
- [ ] **2.8** Create `CHANGELOG.md` with v1.0.0 placeholder
- [ ] **2.9** Copy standard files: `.gitignore`, `.gitleaks.toml`, `.markdownlint.json`, `.python-version`

### Phase 3: Package Structure (Code Skeleton)

- [ ] **3.1** Create `src/otutil/__init__.py` with package metadata and version
- [ ] **3.2** Create `src/otutil/server.py` with FastMCP server entry point
- [ ] **3.3** Create `src/otutil/cli.py` with Typer CLI (`serve`, `version` commands)
- [ ] **3.4** Create `src/otutil/tools/__init__.py`
- [ ] **3.5** Create empty tool module stubs:
  - [ ] `src/otutil/tools/file.py`
  - [ ] `src/otutil/tools/excel.py`
  - [ ] `src/otutil/tools/convert.py`
  - [ ] `src/otutil/tools/brave.py`
  - [ ] `src/otutil/tools/ground.py`
  - [ ] `src/otutil/tools/_convert/__init__.py`

### Phase 4: Tool Extraction - File Pack (18 tools)

- [ ] **4.1** Copy `onetool-mcp/src/ot_tools/file.py` → `onetool-util/src/otutil/tools/file.py`
- [ ] **4.2** Update imports: `ot.config` → `otcommon.config`, `ot.logging` → `otcommon.logging`, `ot.paths` → `otcommon.paths`
- [ ] **4.3** Add `@tool_wrapper` decorators to all public functions
- [ ] **4.4** Update pack name: `pack = "file"` (unchanged)
- [ ] **4.5** Verify all 18 tools exported in `__all__`

### Phase 5: Tool Extraction - Excel Pack (30 tools)

- [ ] **5.1** Copy `onetool-mcp/src/ot_tools/excel.py` → `onetool-util/src/otutil/tools/excel.py`
- [ ] **5.2** Update imports: `ot.*` → `otcommon.*`
- [ ] **5.3** Add `@tool_wrapper` decorators to all public functions
- [ ] **5.4** Update pack name: `pack = "excel"` (unchanged)
- [ ] **5.5** Verify all 30 tools exported in `__all__`
- [ ] **5.6** Ensure `__ot_requires__` preserved for openpyxl dependency

### Phase 6: Tool Extraction - Convert Pack (5 tools + submodules)

- [ ] **6.1** Copy `onetool-mcp/src/ot_tools/convert.py` → `onetool-util/src/otutil/tools/convert.py`
- [ ] **6.2** Copy `onetool-mcp/src/ot_tools/_convert/` → `onetool-util/src/otutil/tools/_convert/` (entire directory)
- [ ] **6.3** Update imports in `convert.py`: `ot.*` → `otcommon.*`
- [ ] **6.4** Update imports in `_convert/*.py`: `ot.*` → `otcommon.*`
- [ ] **6.5** Add `@tool_wrapper` decorators to public functions
- [ ] **6.6** Update pack name: `pack = "convert"` (unchanged)
- [ ] **6.7** Verify submodules: `_convert/pdf.py`, `_convert/word.py`, `_convert/powerpoint.py`, `_convert/excel.py`, `_convert/utils.py`

### Phase 7: Tool Extraction - Brave Search Pack (6 tools)

- [ ] **7.1** Copy `onetool-mcp/src/ot_tools/brave_search.py` → `onetool-util/src/otutil/tools/brave.py` (rename file)
- [ ] **7.2** Update imports: `ot.*` → `otcommon.*`
- [ ] **7.3** Update pack name: `pack = "brave"` (changed from "brave_search")
- [ ] **7.4** Add `@tool_wrapper` decorators to public functions
- [ ] **7.5** Verify all 6 tools: `search`, `news`, `local`, `image`, `video`, `search_batch`
- [ ] **7.6** Update config key references: `brave_search` → `brave`

### Phase 8: Tool Extraction - Grounding Search Pack (5 tools)

- [ ] **8.1** Copy `onetool-mcp/src/ot_tools/grounding_search.py` → `onetool-util/src/otutil/tools/ground.py` (rename file)
- [ ] **8.2** Update imports: `ot.*` → `otcommon.*`
- [ ] **8.3** Update pack name: `pack = "ground"` (changed from "grounding_search")
- [ ] **8.4** Add `@tool_wrapper` decorators to public functions
- [ ] **8.5** Verify all 5 tools: `search`, `search_batch`, `dev`, `docs`, `reddit`
- [ ] **8.6** Update config key references: `grounding_search` → `ground`

### Phase 9: Server Implementation (FastMCP)

- [ ] **9.1** Implement `server.py`:
  - [ ] Import FastMCP and all tool modules
  - [ ] Create `mcp = FastMCP(name="onetool-util")`
  - [ ] Inject mcp into tool modules (`file.mcp = excel.mcp = ... = mcp`)
  - [ ] Add server instructions
  - [ ] Implement `main()` function with stdio transport
- [ ] **9.2** Implement `cli.py`:
  - [ ] Import Typer and server
  - [ ] Create `app = typer.Typer()`
  - [ ] Implement `serve` command with `--config` flag
  - [ ] Implement `version` command
  - [ ] Set up entry point
- [ ] **9.3** Wire up `pyproject.toml` scripts:
  - [ ] `onetool-util = "otutil.cli:main"`

### Phase 10: Configuration (Setup)

- [ ] **10.1** Create config template: `src/otutil/config_template.yaml`
- [ ] **10.2** Add config loading in `server.py` using `otcommon.config.load_config`
- [ ] **10.3** Add logging setup using `otcommon.logging.setup_logging`
- [ ] **10.4** Create `.mcp.json` with test config pointing to `global/.onetool/util.yaml`
- [ ] **10.5** Create example secrets file: `global/.onetool/secrets.yaml` (with placeholders)
- [ ] **10.6** Document environment variables: `OT_GLOBAL_DIR`, `BRAVE_API_KEY`, `GEMINI_API_KEY`

### Phase 11: Testing (Quality)

- [ ] **11.1** Create `tests/conftest.py` with fixtures
- [ ] **11.2** Create `tests/test_sanity.py`:
  - [ ] Test imports of all tool modules
  - [ ] Test server startup
  - [ ] Test CLI commands
- [ ] **11.3** Create `tests/test_tools/test_file.py`:
  - [ ] Test core file operations (read, write, delete)
  - [ ] Test file management (copy, move, list)
  - [ ] Test search and info
- [ ] **11.4** Create `tests/test_tools/test_excel.py`:
  - [ ] Test workbook creation and reading
  - [ ] Test cell operations
  - [ ] Test formulas and tables
- [ ] **11.5** Create `tests/test_tools/test_convert.py`:
  - [ ] Test PDF conversion (mocked files)
  - [ ] Test Word/PowerPoint conversion
  - [ ] Test auto-detection
- [ ] **11.6** Create `tests/test_tools/test_brave.py`:
  - [ ] Mock API responses
  - [ ] Test search, news, local, image, video
  - [ ] Test error handling
- [ ] **11.7** Create `tests/test_tools/test_ground.py`:
  - [ ] Mock API responses
  - [ ] Test search with sources
  - [ ] Test specialized searches (dev, docs, reddit)
- [ ] **11.8** Run `just test` - Ensure all tests pass
- [ ] **11.9** Run `just check` - Ensure lint, typecheck, test all pass

### Phase 12: Documentation Migration (User-Facing)

- [ ] **12.1** Copy and adapt tool documentation from onetool-mcp:
  - [ ] Copy relevant sections from onetool-mcp README for tool descriptions
  - [ ] Extract tool-specific docs from onetool-mcp docs/
  - [ ] Record in MIGRATION.md: source paths → destination paths
- [ ] **12.2** Write `README.md`:
  - [ ] Overview and features section
  - [ ] Installation instructions (standalone and via onetool)
  - [ ] Quick start guide
  - [ ] Configuration examples
  - [ ] Tool reference with descriptions copied from onetool-mcp
  - [ ] Link to full docs
- [ ] **12.3** Create/adapt `docs/tools.md`:
  - [ ] File operations (18 tools) - copy descriptions from onetool-mcp, add onetool-util context
  - [ ] Excel manipulation (30 tools) - copy descriptions from onetool-mcp, add onetool-util context
  - [ ] Document conversion (5 tools) - copy descriptions from onetool-mcp, add onetool-util context
  - [ ] Brave search (6 tools) - copy descriptions from onetool-mcp, add onetool-util context
  - [ ] Grounding search (5 tools) - copy descriptions from onetool-mcp, add onetool-util context
- [ ] **12.4** Create `docs/configuration.md`:
  - [ ] Config file structure
  - [ ] Secrets management
  - [ ] Tool-specific settings (copy from onetool-mcp where applicable)
  - [ ] Environment variables
- [ ] **12.5** Create `docs/examples.md`:
  - [ ] Standalone usage examples
  - [ ] Integration with onetool-mcp
  - [ ] Common workflows (adapt from onetool-mcp examples)

### Phase 13: Spec Migration (OpenSpec)

- [ ] **13.1** Copy tool specs from onetool-mcp to onetool-util:
  - [ ] Copy `openspec/specs/tool-file/` → `onetool-util/openspec/specs/tool-file/`
  - [ ] Copy `openspec/specs/tool-excel/` → `onetool-util/openspec/specs/tool-excel/`
  - [ ] Copy `openspec/specs/tool-convert/` → `onetool-util/openspec/specs/tool-convert/`
  - [ ] Copy `openspec/specs/tool-brave/` → `onetool-util/openspec/specs/tool-brave/`
  - [ ] Copy `openspec/specs/tool-ground/` → `onetool-util/openspec/specs/tool-ground/`
  - [ ] Record in MIGRATION.md: all copied spec directories
- [ ] **13.2** Update spec cross-references:
  - [ ] Update any references to onetool-mcp in copied specs
  - [ ] Add note to each spec indicating it's now in onetool-util
  - [ ] Keep specs compatible with current tool behavior
- [ ] **13.3** Create `openspec/specs/INDEX.md`:
  - [ ] List all tool specs in onetool-util
  - [ ] Link to backend-onetool-util spec

### Phase 14: Agent Documentation (AI Assistants)

- [ ] **14.1** Create `dev/agents/hints.md`:
  - [ ] Quick reference for project commands
  - [ ] Common patterns and conventions
  - [ ] Tool pack structure
  - [ ] Copy relevant patterns from onetool-mcp if applicable
- [ ] **14.2** Create `dev/agents/project-map.md`:
  - [ ] Detailed project structure
  - [ ] Module descriptions
  - [ ] Testing strategy
- [ ] **14.3** Create `openspec/project.md`:
  - [ ] Project purpose and context
  - [ ] Technology stack
  - [ ] Link to specifications

### Phase 15: Migration Tracking

- [ ] **15.1** Create `MIGRATION.md` in onetool-util root:
  - [ ] Document all files copied from onetool-mcp
  - [ ] Organize by category: code, tests, specs, docs
  - [ ] Include source and destination paths
  - [ ] Note: This file will be used in Proposal 4 to remove files from onetool-mcp
- [ ] **15.2** Verify migration completeness:
  - [ ] All 5 tool packs copied
  - [ ] All tests copied (file, excel, convert, brave, ground)
  - [ ] All specs copied (tool-file, tool-excel, tool-convert, tool-brave, tool-ground)
  - [ ] All relevant docs copied
- [ ] **15.3** Cross-reference check:
  - [ ] Compare onetool-mcp tool files with onetool-util copies
  - [ ] Ensure no tools missed
  - [ ] Verify test coverage equivalent

### Phase 16: Quality Assurance (Final Checks)

- [ ] **14.1** Run full quality suite: `just check`
  - [ ] Lint with ruff: `just lint`
  - [ ] Typecheck with mypy: `just typecheck`
  - [ ] Test with pytest: `just test`
- [ ] **14.2** Smoke test standalone mode:
  - [ ] Start server: `uv run onetool-util --config global/.onetool/util.yaml`
  - [ ] Test with Claude Code MCP client
  - [ ] Verify all 5 packs discoverable
  - [ ] Test sample tool calls from each pack
- [ ] **14.3** Verify dependency isolation:
  - [ ] Install in fresh venv
  - [ ] Check package size
  - [ ] Verify all heavy deps present (pymupdf, openpyxl, google-genai)
- [ ] **14.4** Test config loading:
  - [ ] Load from `~/.onetool/util.yaml`
  - [ ] Load secrets from `~/.onetool/secrets.yaml`
  - [ ] Verify environment variable expansion
- [ ] **14.5** Test logging:
  - [ ] Verify logs written to `~/.onetool/logs/onetool-util.log`
  - [ ] Check log format (JSON in production, dev in dev)
  - [ ] Verify log levels (INFO, DEBUG, ERROR)

### Phase 17: Release Preparation (Publishing)

- [ ] **15.1** Update `CHANGELOG.md`:
  - [ ] Add v1.0.0 section with feature list
  - [ ] List all 64 tools
  - [ ] Note dependencies and requirements
- [ ] **15.2** Configure release automation:
  - [ ] Set up cliff.toml for changelog generation
  - [ ] Create release.just with release targets
  - [ ] Test `just release-dry-run`
- [ ] **15.3** Set up GitHub Actions CI:
  - [ ] Lint workflow
  - [ ] Typecheck workflow
  - [ ] Test workflow
  - [ ] Build workflow
  - [ ] Release workflow (on tag)
- [ ] **15.4** Test local build:
  - [ ] `uv build`
  - [ ] Verify dist/ contents
  - [ ] Check wheel and sdist
- [ ] **15.5** Tag release: `v1.0.0`
- [ ] **15.6** Publish to PyPI (when approved):
  - [ ] Test publish to TestPyPI first
  - [ ] Publish to PyPI: `uv publish`
  - [ ] Verify package available: `pip install onetool-util`

### Phase 18: Integration (Connect to Ecosystem)

- [ ] **16.1** Document integration with onetool-mcp:
  - [ ] Update onetool-mcp to reference onetool-util in docs
  - [ ] Example backend_servers config in onetool.yaml
  - [ ] Migration notes for v1.x users
- [ ] **16.2** Update onetool-common to reference onetool-util as example backend
- [ ] **16.3** Create migration guide from onetool-mcp v1.x to v2.0+onetool-util
- [ ] **16.4** Announce release (when ready):
  - [ ] GitHub release with notes
  - [ ] Update v2-refactor.md status

---

## Task Dependencies

**Sequential dependencies:**
- Phase 1 → Phase 2 → Phase 3 → Phases 4-8 (parallel) → Phase 9 → Phase 10 → Phase 11 → Phases 12-14 (parallel) → Phase 15 → Phase 16 → Phase 17 → Phase 18

**Parallelizable work:**
- Phases 4-8: Tool extraction can be done in parallel (independent packs)
- Phases 12-14: Documentation, specs, and agent docs can be copied/written in parallel
- Phase 11 and 12-14 can overlap (tests and docs are independent)

---

## Validation Checklist

**Before marking proposal complete:**

- [ ] All tasks completed (updated count: 16 phases)
- [ ] `just check` passes (lint, typecheck, test)
- [ ] Standalone mode tested with Claude Code
- [ ] Documentation complete (README, tools, config, examples)
- [ ] Published to PyPI as `onetool-util>=1.0.0`
- [ ] GitHub repository public and accessible
- [ ] CI/CD workflows passing
- [ ] Integration with onetool-mcp documented

---

## Notes

**Estimated Time:** 0.75 days with AI assistance (increased due to migration tracking)

**Key Milestones:**
- Phase 3 complete: Project structure ready
- Phase 8 complete: All tools extracted
- Phase 11 complete: All tests copied and passing
- Phase 13 complete: All specs copied
- Phase 15 complete: Migration tracking complete
- Phase 17 complete: Published and released

**Blockers:**
- onetool-common must be published (✅ Complete)
- GitHub repository must be created (✅ Complete)
- API keys needed for testing brave/ground tools (use mocks for now)

**Important - Removal from onetool-mcp:**
- This proposal COPIES everything to onetool-util
- REMOVAL from onetool-mcp will happen in Proposal 4: refactor-onetool-mcp
- MIGRATION.md tracks what to remove (see Phase 15)
- Both repos will temporarily contain the same tools/tests/specs/docs

**Post-Completion:**
- Archive this change: `openspec archive add-onetool-util --skip-specs --yes`
- Start Proposal 3: add-onetool-dev (can run in parallel with Proposal 4)
- Proposal 4 will use MIGRATION.md to remove copied files from onetool-mcp
