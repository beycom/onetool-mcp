# Proposal: Refactor onetool-mcp to Frontend/Proxy Role

**Change ID:** `refactor-mcp-core`
**Status:** Draft
**Effort:** ~2-3 days
**Dependencies:**
- `standardize-backends` (optional, but recommended)
- Backends exist: onetool-util, onetool-dev (already created)

## Problem

onetool-mcp is currently monolithic with 100+ tools bundled in one codebase:

1. **Large surface area:** 15+ tool packs (file, excel, db, ripgrep, etc.) all in ot_tools/
2. **Heavy dependencies:** ~100 dependencies (pymupdf, openpyxl, sqlalchemy, etc.) all required
3. **Duplication:** ot.http_client, ot.logging, ot.config overlap heavily with onetool-common
4. **Wrong role:** Should be frontend/proxy, not monolithic tool server
5. **Token bloat potential:** Without backends, would expose 100+ tools = 50K+ tokens

**Current state:**
- onetool-util and onetool-dev backends created with tools extracted
- But onetool-mcp still has the original tool code (duplication)
- onetool-mcp not yet proxying to backends
- Heavy dependencies not yet removed

## Solution

Transform onetool-mcp from monolithic server to slim frontend/proxy:

1. **Remove extracted tools** (2 hours): Delete ot_tools/ files now in backends
2. **Consolidate with onetool-common** (6-8 hours): Replace ot.http_client, consolidate logging/config/paths (~1,468 LOC reduction)
3. **Add backend proxy** (1 day): Implement proxy manager for backend MCP servers
4. **Update configuration** (2 hours): Add backend_servers section to config schema
5. **Update meta tools** (1 hour): Include backend tools in ot.tools(), ot.help()
6. **Remove dependencies** (1 hour): Eliminate backend-specific dependencies
7. **Update tests** (4 hours): Remove tool tests, add proxy tests
8. **Update docs** (2 hours): Document v2.0 architecture

**Result:**
- Core onetool-mcp: <10 LOC tools (mem, timer, scaffold, transform, meta)
- Dependencies: 85-90% reduction (~10-15 vs ~100)
- LOC reduction: ~1,468 LOC from consolidation + removed tools
- Connects to 3 official backends + external backends (github, devtools, etc.)

## Scope

**In scope:**
- Remove extracted tool packs from src/ot_tools/
- Consolidate ot.http_client, ot.logging, ot.config, ot.paths with onetool-common
- Implement backend server proxy manager (src/ot/proxy/)
- Update configuration schema for backend_servers
- Update meta tools to show backend tools
- Remove heavy dependencies
- Update tests and documentation

**Out of scope:**
- Backend server creation (already done)
- Backend management CLI (separate proposal)
- Breaking v1.x compatibility (this is v2.0, clean break)

## Affected Files

**Deletions:**
- src/ot_tools/file.py, excel.py, convert.py, brave_search.py, grounding_search.py (to onetool-util)
- src/ot_tools/db.py, ripgrep.py, web_fetch.py, package.py, context7.py, diagram.py (to onetool-dev)
- src/ot_tools/_convert/, _inject_base.py, devtools_util.py, playwright_util.py
- src/ot/http_client.py (replaced by otcommon.http)
- Large parts of ot/logging/, ot/config/, ot/paths/ (consolidated)

**New files:**
- src/ot/proxy/manager.py (~300 LOC)
- src/ot/proxy/client.py (~150 LOC)
- src/ot/proxy/discovery.py (~150 LOC)

**Modified:**
- pyproject.toml (dependency cleanup)
- src/ot/config/models.py (add BackendServerConfig)
- src/ot_tools/meta.py (include backend tools)
- tests/ (remove tool tests, add proxy tests)
- README.md, CLAUDE.md, CHANGELOG.md

## Success Criteria

- [ ] Extracted tools removed from ot_tools/ (14 files)
- [ ] Core tools remain: mem.py, timer.py, scaffold.py, transform.py, meta.py
- [ ] ot.http_client replaced with otcommon.http
- [ ] ot.logging consolidated (MCP-specific adapters kept)
- [ ] ot.config consolidated (models kept, base loading from otcommon)
- [ ] ot.paths consolidated (MCP-specific kept)
- [ ] Proxy manager implemented and connects to backends
- [ ] backend_servers config section working
- [ ] Meta tools (ot.tools, ot.help) show backend tools
- [ ] Dependencies reduced from ~100 to ~10-15
- [ ] All tests passing (smoke, unit, integration)
- [ ] `just check` passes
- [ ] Documentation updated for v2.0

## Risks

**Medium risk:**
- Config/logging consolidation requires thorough testing
- Proxy manager is new code (potential bugs)
- Breaking change for any v1.x users (but no current users)

**Mitigation:**
- Keep v1.x branch for reference
- Comprehensive test suite for proxy
- Clear migration documentation
- Test with real backends (util, dev, xero)

## Architecture Overview

**Before (v1.x):**
```
onetool-mcp (monolithic)
├── ot_tools/ (100+ tools)
├── executor/
├── config/ (full implementation)
└── logging/ (full implementation)
```

**After (v2.0):**
```
onetool-mcp (frontend/proxy)
├── ot_tools/ (5 meta tools)
├── executor/ (unchanged)
├── proxy/ (NEW - backend manager)
├── config/ (models only, base from otcommon)
└── logging/ (MCP adapters only, base from otcommon)

Backend servers (standalone):
- onetool-util (64 tools)
- onetool-dev (34 tools)
- onetool-xero (60 tools)
- github MCP (external)
- devtools MCP (external)
```

## References

- Source: wip/consult/refactor/REMAINING-STEPS.md Part 2
- Analysis: onetool-common-opportunities.md (~1,468 LOC reduction)
- Architecture: one-servers.md (standalone servers principle)
