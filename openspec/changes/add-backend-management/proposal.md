# Proposal: Add Backend Management Features

**Change ID:** `add-backend-management`
**Status:** Draft
**Effort:** ~1-2 days
**Dependencies:**
- `refactor-mcp-core` (backends must be proxied)

## Problem

After v2.0 refactor, users need ways to manage backend servers:

1. **Installation:** No easy way to install/register backends
2. **Discovery:** Users don't know what backends exist or what tools they provide
3. **Health monitoring:** No way to check if backends are working
4. **Updates:** No mechanism to update backends
5. **Development:** No easy way to create new backend servers
6. **Documentation gap:** No migration guide, no backend dev guide

**Current state:**
- Backend servers work (onetool-util, onetool-dev, onetool-xero)
- Proxy manager connects to them
- But users must manually:
  - Install via uvx
  - Edit config files
  - Debug backend issues themselves
  - Create new backends from scratch

## Solution

Add comprehensive backend management features:

1. **CLI commands** (1 day):
   - `onetool backends list` - Show installed backends
   - `onetool backends install <name>` - Install and register
   - `onetool backends update` - Update backends
   - `onetool backends health` - Health check
   - `onetool backends uninstall <name>` - Remove backend
   - `onetool server create <name>` - Create new backend from template

2. **Interactive installation** (2 hours):
   - `onetool install` - Wizard for selecting/installing backends
   - Auto-configure Claude Code mcp.json
   - Create default configs

3. **Documentation** (4 hours):
   - Migration guide (v1.x → v2.0)
   - Backend development guide
   - Architecture overview
   - User installation guide

4. **Release automation** (2 hours):
   - Coordinated release script for all packages
   - Version management

## Scope

**In scope:**
- Backend management CLI commands
- Interactive installation wizard
- Server template generator
- Comprehensive documentation (4 guides)
- Release automation script

**Out of scope:**
- Centralized backend registry (use PyPI)
- Backend permissions system (future)
- Automated testing of community backends (future)
- Backend discovery beyond PyPI search (future)

## Affected Files

**New files:**
- src/onetool/backends.py (~400 LOC) - Backend management commands
- src/onetool/server_generator.py (~200 LOC) - Template generator
- src/onetool/install.py (~150 LOC) - Interactive installation
- scripts/release-all.sh (~50 LOC) - Coordinated release
- docs/migration-v2.md (~500 lines) - Migration guide
- docs/backend-development.md (~800 lines) - Backend dev guide
- docs/architecture-v2.md (~600 lines) - Architecture overview
- docs/installation.md (~400 lines) - User install guide

**Modified:**
- src/onetool/cli.py (add backends subcommand)
- README.md (link to new docs)

## Success Criteria

- [ ] `onetool backends list` shows installed backends with status
- [ ] `onetool backends install onetool-util` installs and registers
- [ ] `onetool backends update` checks for and applies updates
- [ ] `onetool backends health` verifies all backends respond
- [ ] `onetool backends uninstall <name>` removes backend
- [ ] `onetool server create <name>` generates working template
- [ ] `onetool install` interactive wizard works
- [ ] Migration guide complete and tested
- [ ] Backend development guide complete with examples
- [ ] Architecture overview clear and accurate
- [ ] Installation guide covers all scenarios
- [ ] Release automation tested with all packages

## Risks

**Low risk:** Mostly CLI commands and documentation
- Backend management is non-destructive (can uninstall)
- Template generation is file operations
- Documentation has no code risk

**Mitigation:**
- Test each CLI command thoroughly
- Verify template generates working backends
- Have users review documentation

## User Experience

**Installing backends:**
```bash
$ onetool install

? Which backends would you like to install?
  [x] onetool-util   - Utilities (web, file, excel, convert)
  [x] onetool-dev    - Developer tools (db, search, packages)
  [ ] onetool-xero   - Xero financial analysis

Installing onetool-util... ✓
Installing onetool-dev... ✓

✓ Installed 2 backends
✓ Updated ~/.claude/mcp.json
✓ Created ~/.onetool/util.yaml
✓ Created ~/.onetool/dev.yaml

Ready! Try: __ot file.read(path="README.md")
```

**Managing backends:**
```bash
$ onetool backends list
onetool-util  v1.0.0  [running]   5 packs, 64 tools
onetool-dev   v1.0.0  [running]   8 packs, 34 tools
onetool-xero  v0.1.0  [stopped]   1 pack, 60 tools

$ onetool backends health
✓ onetool-util  [healthy]  64 tools responding
✓ onetool-dev   [healthy]  34 tools responding
⚠ onetool-xero  [warning]  API rate limit
```

**Creating backend:**
```bash
$ onetool server create onetool-finance

Created onetool-finance/
  ✓ Project structure
  ✓ Template files
  ✓ Synced shared files
  ✓ Git repository

Next steps:
  1. cd onetool-finance
  2. Add tools to src/otfinance/tools/
  3. just check
  4. Publish to PyPI
```

## Architecture

**CLI structure:**
```
onetool
├── serve                    # Start MCP server
├── version                  # Show version
├── install                  # Interactive installation
├── backends
│   ├── list                 # List backends
│   ├── install <name>       # Install backend
│   ├── update [name]        # Update backend(s)
│   ├── health               # Health check
│   └── uninstall <name>     # Uninstall backend
└── server
    └── create <name>        # Create new backend
```

## References

- Source: wip/consult/refactor/REMAINING-STEPS.md Part 3
- CLI patterns: onetool-common/cli.py (Typer patterns)
- Template: onetool-common/template/ (to be used by generator)
