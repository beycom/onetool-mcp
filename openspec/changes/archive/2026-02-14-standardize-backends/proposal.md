# Proposal: Standardize Backend Servers

**Change ID:** `standardize-backends`
**Status:** Draft
**Effort:** ~5.5 hours
**Dependencies:** None

## Problem

Five OneTool repositories (onetool-mcp, onetool-xero, onetool-util, onetool-dev, onetool-common) have significant inconsistencies:

1. **Metadata inconsistency:** Mixed licenses (GPL-3.0 vs MIT), different authors (Gavin Las vs Beycom), Python version mismatch (3.11 vs 3.12)
2. **File duplication:** dev/practices/ (11 files), openspec/AGENTS.md (16KB), quality configs duplicated across repos
3. **Maintenance burden:** Fixing a bug requires manual copying to 4+ repos (90% wasted effort)
4. **Missing standardization:** No .python-version files, server.json has placeholders, inconsistent repository URLs

**Impact:** Maintenance nightmare, drift over time, poor developer experience, unclear which version is "correct"

## Solution

**Reference standard:** Use onetool-mcp as the gold standard (most mature, comprehensive)

**Three-part solution:**

1. **Standardize metadata** (1 hour): Unify licenses, authors, Python versions, fix placeholders
2. **Create DRY infrastructure** (3.5 hours): Shared files in onetool-common/shared/ with sync.py script
3. **Apply standardization** (1 hour): Sync to all backends, update justfiles

**Key insight:** DRY via sync.py reduces maintenance from 50 min/change to 5 min/change (90% reduction)

## Scope

**In scope:**
- Phases 1-11 from standardization plan
- Metadata standardization across 5 repos
- Creating onetool-common/shared/ directory structure
- Implementing sync.py script (~200 LOC)
- Syncing shared files to all backends
- Updating justfiles to import common.just

**Out of scope:**
- .claude/ and .mcp.json management (handled separately, added to .gitignore only)
- Code refactoring (that's separate proposals)
- New features

## Affected Projects

- onetool-mcp
- onetool-xero
- onetool-util
- onetool-dev
- onetool-common

## Success Criteria

- [ ] All projects use GPL-3.0 license
- [ ] All projects have author "Gavin Las <beycom99@gmail.com>"
- [ ] All projects require Python 3.12+
- [ ] All projects have .python-version file
- [ ] onetool-common/shared/ exists with 11 practice guides, AGENTS.md, quality configs
- [ ] sync.py script works (--dry-run and --status tested)
- [ ] All backends synced successfully
- [ ] All justfiles import common.just
- [ ] Fix one practice guide → sync to 4 backends in <5 minutes

## Risks

**Low risk:** No code changes, only metadata and file organization
- Metadata changes are mechanical (find-replace)
- Sync is copy operation (reversible)
- Justfile import is optional (import? won't fail)

**Mitigation:** Test sync.py with --dry-run first

## References

- Source: wip/consult/refactor/REMAINING-STEPS.md Part 1
- Analysis: backend-server-standards.md (1777 lines)
- Reference: onetool-mcp as gold standard
