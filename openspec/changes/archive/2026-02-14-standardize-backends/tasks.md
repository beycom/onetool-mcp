# Tasks: Standardize Backend Servers

**Dependency:** None (can start immediately)

## Phase 1: Quick Metadata Fixes (1 hour)

### Task 1.1: Add .gitignore entries (10 min)
- [x] Add `.claude/` and `.mcp.json` to .gitignore in all 5 projects
- [x] Commit: `chore: add .claude and .mcp.json to gitignore`
- [x] Validation: Verify entries exist in each .gitignore

### Task 1.2: Standardize licenses (15 min)
- [x] Copy LICENSE from onetool-mcp to onetool-util
- [x] Copy LICENSE from onetool-mcp to onetool-dev
- [x] Update pyproject.toml license field to GPL-3.0 in util, dev
- [x] Update classifiers to GPL-3.0 in util, dev
- [x] Commit: `chore(license): change to GPL-3.0 to match onetool-mcp`
- [x] Validation: All projects have LICENSE file, pyproject.toml shows GPL-3.0

### Task 1.3: Standardize authors (10 min)
- [x] Update pyproject.toml authors in onetool-util: `Gavin Las <beycom99@gmail.com>`
- [x] Update pyproject.toml authors in onetool-dev: `Gavin Las <beycom99@gmail.com>`
- [x] Commit: `chore: update author to match onetool-mcp`
- [x] Validation: `grep "Gavin Las" */pyproject.toml` shows 5 matches

### Task 1.4: Standardize Python version (15 min)
- [x] Update requires-python to >=3.12 in util, dev, common
- [x] Update classifiers to Python 3.12/3.13 (remove 3.11)
- [x] Update ruff target-version to py312
- [x] Add .python-version="3.12" to mcp, xero, util, dev (common already has it)
- [x] Commit: `chore: require Python 3.12+ to match onetool-mcp`
- [x] Validation: All pyproject.toml have requires-python >=3.12, all have .python-version

### Task 1.5: Fix server.json placeholders (5 min)
- [x] Replace {package}, {name}, {description} in onetool-dev/server.json
- [x] Set proper values: onetool-dev, "OneTool Developer Tools", description
- [x] Commit: `fix: replace server.json template placeholders`
- [x] Validation: No { or } in server.json

### Task 1.6: Verify repository naming (10 min)
- [x] Check onetool-xero pyproject.toml URLs reference onetool-xero
- [x] Check onetool-xero server.json repository URL
- [x] Update if needed (PyPI name stays one-xero)
- [x] Commit: `chore: update repository URLs to onetool-xero for consistency`
- [x] Validation: All URLs point to onetool-xero GitHub repo

## Phase 2: DRY Infrastructure (3.5 hours)

### Task 2.1: Create shared/ directory structure (15 min)
- [x] Create onetool-common/shared/{dev/practices,openspec,quality,scripts}
- [x] Copy 11 practice guides from onetool-mcp/dev/practices/ to shared/dev/practices/
- [x] Copy AGENTS.md and README.md from onetool-mcp/openspec/ to shared/openspec/
- [x] Copy .gitleaks.toml, .markdownlint.json, cliff.toml to shared/quality/
- [x] Copy release.just to shared/scripts/
- [x] Validation: `ls shared/dev/practices/` shows 11 .md files

### Task 2.2: Create common.just (30 min)
- [x] Write shared/scripts/common.just with standard recipes
- [x] Include: default, install, check, test, test-unit, test-smoke, lint, lint-fix, fmt, fmt-check, typecheck, build, clean
- [x] Document usage in header comment
- [x] Validation: `just --list --justfile shared/scripts/common.just` shows all recipes

### Task 2.3: Create manifest.yaml (15 min)
- [x] Write shared/manifest.yaml with sync_rules
- [x] Define rules for: dev/practices, openspec/AGENTS.md, openspec/README.md, quality configs, release.just
- [x] Add descriptions for each rule
- [x] Validation: Valid YAML, all paths exist in shared/

### Task 2.4: Implement sync.py script (2 hours)
- [x] Create onetool-common/sync.py with ~200 LOC
- [x] Implement: load_manifest(), sync_file(), sync_directory(), sync_shared()
- [x] Implement: write_sync_metadata(), show_status()
- [x] Add CLI args: --dry-run, --status
- [x] Add error handling and progress reporting
- [x] Validation: `uv run python sync.py --dry-run` from onetool-util shows what would sync

### Task 2.5: Test sync.py (30 min)
- [x] Run sync.py --dry-run from each backend (util, dev, xero, mcp)
- [x] Verify it shows correct files to sync
- [x] Fix any issues
- [x] Commit onetool-common changes: `feat: create shared/ directory for DRY across backends`
- [x] Validation: Dry run successful from all 4 backends

## Phase 3: Apply Standardization (1 hour)

### Task 3.1: Sync to onetool-util (10 min)
- [x] cd onetool-util && uv run python ../onetool-common/sync.py
- [x] Verify dev/practices/, openspec/, quality configs synced
- [x] Check .shared-sync.yaml created
- [x] Commit: `feat: sync shared files from onetool-common`
- [x] Validation: 11 practice files exist, AGENTS.md exists, configs updated

### Task 3.2: Sync to onetool-dev (10 min)
- [x] cd onetool-dev && uv run python ../onetool-common/sync.py
- [x] Verify files synced
- [x] Commit: `feat: sync shared files from onetool-common`
- [x] Validation: Same as util

### Task 3.3: Sync to onetool-xero (10 min)
- [x] cd onetool-xero && uv run python ../onetool-common/sync.py
- [x] Review git diff (updates existing files)
- [x] Commit: `chore: sync with onetool-common shared files`
- [x] Validation: Files updated to match shared/ versions

### Task 3.4: Sync to onetool-mcp (10 min)
- [x] cd onetool-mcp && uv run python ../onetool-common/sync.py
- [x] Review git diff (updates existing files)
- [x] Commit: `chore: sync with onetool-common shared files`
- [x] Validation: Files updated (mcp is source, but good to verify sync works)

### Task 3.5: Update justfiles (30 min)
- [x] Add `import? '../onetool-common/shared/scripts/common.just'` to mcp/justfile
- [x] Add same to xero/justfile
- [x] Add same to util/justfile
- [x] Add same to dev/justfile
- [x] Add same to common/justfile
- [x] Test `just --list` in each project shows common recipes
- [x] Commit per project: `chore: import shared justfile recipes from onetool-common`
- [x] Validation: All justfiles import common.just, `just check` works in all

### Task 3.6: Update template (1 hour) - OPTIONAL
- [x] Update onetool-common/template/ to comprehensive structure
- [x] Include references to shared/ files
- [x] Add sync.py instructions to template README
- [x] Commit: `feat: update template to comprehensive structure`
- [x] Validation: Template has all standard files, instructions clear

## Verification

### Final Checklist
- [x] All projects have .claude/ and .mcp.json in .gitignore
- [x] All projects use GPL-3.0 license
- [x] All projects have LICENSE file
- [x] All projects have author "Gavin Las <beycom99@gmail.com>"
- [x] All projects require Python 3.12+
- [x] All projects have .python-version file
- [x] onetool-dev server.json has no placeholders
- [x] onetool-xero repository URLs reference onetool-xero
- [x] onetool-common/shared/ exists with all files (11 practices, AGENTS.md, etc.)
- [x] sync.py works with --dry-run and --status
- [x] All 4 backends synced successfully (.shared-sync.yaml exists)
- [x] All 5 justfiles import common.just
- [x] `just check` passes in all projects

### Success Test
- [x] Edit onetool-common/shared/dev/practices/git.md
- [x] Run sync.py in all 4 backends
- [x] Verify change propagated to all
- [x] Time taken: <5 minutes

## Notes

- **Parallelization:** Tasks 1.1-1.6 can be done per-project in parallel
- **Dependencies:** Phase 2 must complete before Phase 3
- **Rollback:** All changes are reversible (metadata changes, file copies)
- **Testing:** Use --dry-run extensively before actual sync
