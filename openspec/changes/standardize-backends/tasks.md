# Tasks: Standardize Backend Servers

**Dependency:** None (can start immediately)

## Phase 1: Quick Metadata Fixes (1 hour)

### Task 1.1: Add .gitignore entries (10 min)
- [ ] Add `.claude/` and `.mcp.json` to .gitignore in all 5 projects
- [ ] Commit: `chore: add .claude and .mcp.json to gitignore`
- [ ] Validation: Verify entries exist in each .gitignore

### Task 1.2: Standardize licenses (15 min)
- [ ] Copy LICENSE from onetool-mcp to onetool-util
- [ ] Copy LICENSE from onetool-mcp to onetool-dev
- [ ] Update pyproject.toml license field to GPL-3.0 in util, dev
- [ ] Update classifiers to GPL-3.0 in util, dev
- [ ] Commit: `chore(license): change to GPL-3.0 to match onetool-mcp`
- [ ] Validation: All projects have LICENSE file, pyproject.toml shows GPL-3.0

### Task 1.3: Standardize authors (10 min)
- [ ] Update pyproject.toml authors in onetool-util: `Gavin Las <beycom99@gmail.com>`
- [ ] Update pyproject.toml authors in onetool-dev: `Gavin Las <beycom99@gmail.com>`
- [ ] Commit: `chore: update author to match onetool-mcp`
- [ ] Validation: `grep "Gavin Las" */pyproject.toml` shows 5 matches

### Task 1.4: Standardize Python version (15 min)
- [ ] Update requires-python to >=3.12 in util, dev, common
- [ ] Update classifiers to Python 3.12/3.13 (remove 3.11)
- [ ] Update ruff target-version to py312
- [ ] Add .python-version="3.12" to mcp, xero, util, dev (common already has it)
- [ ] Commit: `chore: require Python 3.12+ to match onetool-mcp`
- [ ] Validation: All pyproject.toml have requires-python >=3.12, all have .python-version

### Task 1.5: Fix server.json placeholders (5 min)
- [ ] Replace {package}, {name}, {description} in onetool-dev/server.json
- [ ] Set proper values: onetool-dev, "OneTool Developer Tools", description
- [ ] Commit: `fix: replace server.json template placeholders`
- [ ] Validation: No { or } in server.json

### Task 1.6: Verify repository naming (10 min)
- [ ] Check onetool-xero pyproject.toml URLs reference onetool-xero
- [ ] Check onetool-xero server.json repository URL
- [ ] Update if needed (PyPI name stays one-xero)
- [ ] Commit: `chore: update repository URLs to onetool-xero for consistency`
- [ ] Validation: All URLs point to onetool-xero GitHub repo

## Phase 2: DRY Infrastructure (3.5 hours)

### Task 2.1: Create shared/ directory structure (15 min)
- [ ] Create onetool-common/shared/{dev/practices,openspec,quality,scripts}
- [ ] Copy 11 practice guides from onetool-mcp/dev/practices/ to shared/dev/practices/
- [ ] Copy AGENTS.md and README.md from onetool-mcp/openspec/ to shared/openspec/
- [ ] Copy .gitleaks.toml, .markdownlint.json, cliff.toml to shared/quality/
- [ ] Copy release.just to shared/scripts/
- [ ] Validation: `ls shared/dev/practices/` shows 11 .md files

### Task 2.2: Create common.just (30 min)
- [ ] Write shared/scripts/common.just with standard recipes
- [ ] Include: default, install, check, test, test-unit, test-smoke, lint, lint-fix, fmt, fmt-check, typecheck, build, clean
- [ ] Document usage in header comment
- [ ] Validation: `just --list --justfile shared/scripts/common.just` shows all recipes

### Task 2.3: Create manifest.yaml (15 min)
- [ ] Write shared/manifest.yaml with sync_rules
- [ ] Define rules for: dev/practices, openspec/AGENTS.md, openspec/README.md, quality configs, release.just
- [ ] Add descriptions for each rule
- [ ] Validation: Valid YAML, all paths exist in shared/

### Task 2.4: Implement sync.py script (2 hours)
- [ ] Create onetool-common/sync.py with ~200 LOC
- [ ] Implement: load_manifest(), sync_file(), sync_directory(), sync_shared()
- [ ] Implement: write_sync_metadata(), show_status()
- [ ] Add CLI args: --dry-run, --status
- [ ] Add error handling and progress reporting
- [ ] Validation: `uv run python sync.py --dry-run` from onetool-util shows what would sync

### Task 2.5: Test sync.py (30 min)
- [ ] Run sync.py --dry-run from each backend (util, dev, xero, mcp)
- [ ] Verify it shows correct files to sync
- [ ] Fix any issues
- [ ] Commit onetool-common changes: `feat: create shared/ directory for DRY across backends`
- [ ] Validation: Dry run successful from all 4 backends

## Phase 3: Apply Standardization (1 hour)

### Task 3.1: Sync to onetool-util (10 min)
- [ ] cd onetool-util && uv run python ../onetool-common/sync.py
- [ ] Verify dev/practices/, openspec/, quality configs synced
- [ ] Check .shared-sync.yaml created
- [ ] Commit: `feat: sync shared files from onetool-common`
- [ ] Validation: 11 practice files exist, AGENTS.md exists, configs updated

### Task 3.2: Sync to onetool-dev (10 min)
- [ ] cd onetool-dev && uv run python ../onetool-common/sync.py
- [ ] Verify files synced
- [ ] Commit: `feat: sync shared files from onetool-common`
- [ ] Validation: Same as util

### Task 3.3: Sync to onetool-xero (10 min)
- [ ] cd onetool-xero && uv run python ../onetool-common/sync.py
- [ ] Review git diff (updates existing files)
- [ ] Commit: `chore: sync with onetool-common shared files`
- [ ] Validation: Files updated to match shared/ versions

### Task 3.4: Sync to onetool-mcp (10 min)
- [ ] cd onetool-mcp && uv run python ../onetool-common/sync.py
- [ ] Review git diff (updates existing files)
- [ ] Commit: `chore: sync with onetool-common shared files`
- [ ] Validation: Files updated (mcp is source, but good to verify sync works)

### Task 3.5: Update justfiles (30 min)
- [ ] Add `import? '../onetool-common/shared/scripts/common.just'` to mcp/justfile
- [ ] Add same to xero/justfile
- [ ] Add same to util/justfile
- [ ] Add same to dev/justfile
- [ ] Add same to common/justfile
- [ ] Test `just --list` in each project shows common recipes
- [ ] Commit per project: `chore: import shared justfile recipes from onetool-common`
- [ ] Validation: All justfiles import common.just, `just check` works in all

### Task 3.6: Update template (1 hour) - OPTIONAL
- [ ] Update onetool-common/template/ to comprehensive structure
- [ ] Include references to shared/ files
- [ ] Add sync.py instructions to template README
- [ ] Commit: `feat: update template to comprehensive structure`
- [ ] Validation: Template has all standard files, instructions clear

## Verification

### Final Checklist
- [ ] All projects have .claude/ and .mcp.json in .gitignore
- [ ] All projects use GPL-3.0 license
- [ ] All projects have LICENSE file
- [ ] All projects have author "Gavin Las <beycom99@gmail.com>"
- [ ] All projects require Python 3.12+
- [ ] All projects have .python-version file
- [ ] onetool-dev server.json has no placeholders
- [ ] onetool-xero repository URLs reference onetool-xero
- [ ] onetool-common/shared/ exists with all files (11 practices, AGENTS.md, etc.)
- [ ] sync.py works with --dry-run and --status
- [ ] All 4 backends synced successfully (.shared-sync.yaml exists)
- [ ] All 5 justfiles import common.just
- [ ] `just check` passes in all projects

### Success Test
- [ ] Edit onetool-common/shared/dev/practices/git.md
- [ ] Run sync.py in all 4 backends
- [ ] Verify change propagated to all
- [ ] Time taken: <5 minutes

## Notes

- **Parallelization:** Tasks 1.1-1.6 can be done per-project in parallel
- **Dependencies:** Phase 2 must complete before Phase 3
- **Rollback:** All changes are reversible (metadata changes, file copies)
- **Testing:** Use --dry-run extensively before actual sync
