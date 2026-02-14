# Tasks: Add Backend Management Features

**Dependencies:**
- `refactor-mcp-core` completed (proxy manager exists)
- Template exists in onetool-common

## Phase 1: Backend Management CLI (1 day)

### Task 1.1: Create backends module (30 min)
- [ ] Create src/onetool/backends.py
- [ ] Set up Typer app: `backends_app = typer.Typer(help="Manage backend servers")`
- [ ] Add to main CLI in src/onetool/cli.py: `app.add_typer(backends_app, name="backends")`
- [ ] Validation: `onetool backends --help` shows subcommands

### Task 1.2: Implement backends list (1.5 hours)
- [ ] Implement list_backends() command
- [ ] Query ProxyManager for running backends
- [ ] Read config for all backends
- [ ] Check if uvx package installed
- [ ] Show table: name, version, status, tool count
- [ ] Use rich for pretty formatting
- [ ] Write tests
- [ ] Validation: `onetool backends list` shows all backends

### Task 1.3: Implement backends install (2 hours)
- [ ] Implement install_backend(name: str) command
- [ ] Run `uvx install {name}` subprocess
- [ ] Create default config file in ~/.onetool/{name}.yaml
- [ ] Add to backend_servers in ~/.onetool/onetool.yaml
- [ ] Verify installation by starting backend
- [ ] Handle errors (package not found, install failed)
- [ ] Write tests
- [ ] Validation: `onetool backends install onetool-util` installs and registers

### Task 1.4: Implement backends update (1.5 hours)
- [ ] Implement update_backend(name: str | None) command
- [ ] If name provided: update specific backend
- [ ] If no name: check all backends for updates
- [ ] Run `uvx upgrade {name}` subprocess
- [ ] Show what changed (old version → new version)
- [ ] Restart updated backends
- [ ] Write tests
- [ ] Validation: `onetool backends update` checks and updates all

### Task 1.5: Implement backends health (1.5 hours)
- [ ] Implement health_check() command
- [ ] Start each backend (if not running)
- [ ] Query backend.list_tools()
- [ ] Measure response time
- [ ] Show status: ✓ healthy, ⚠ warning, ✗ error
- [ ] Report tool count
- [ ] Write tests
- [ ] Validation: `onetool backends health` checks all backends

### Task 1.6: Implement backends uninstall (1 hour)
- [ ] Implement uninstall_backend(name: str) command
- [ ] Confirm with user (unless --yes flag)
- [ ] Stop backend if running
- [ ] Remove from backend_servers config
- [ ] Delete config file (~/.onetool/{name}.yaml)
- [ ] Run `uvx uninstall {name}` subprocess
- [ ] Write tests
- [ ] Validation: `onetool backends uninstall onetool-util` removes completely

### Task 1.7: Add --json flag support (1 hour)
- [ ] Add --json flag to all backend commands
- [ ] Output structured JSON for scripting
- [ ] Write tests for JSON output
- [ ] Validation: `onetool backends list --json` returns valid JSON

## Phase 2: Server Template Generator (4 hours)

### Task 2.1: Create server_generator module (30 min)
- [ ] Create src/onetool/server_generator.py
- [ ] Add to CLI: `server_app = typer.Typer(help="Backend server tools")`
- [ ] Add to main CLI: `app.add_typer(server_app, name="server")`
- [ ] Validation: `onetool server --help` shows subcommands

### Task 2.2: Implement template copying (1.5 hours)
- [ ] Implement create_server(name, description, category) command
- [ ] Find onetool-common/template/ directory
- [ ] Copy template to new directory
- [ ] Replace {name}, {package}, {description} placeholders in all files
- [ ] Handle naming: onetool-finance → otfinance module
- [ ] Write tests
- [ ] Validation: Template files copied with replacements

### Task 2.3: Implement post-generation setup (1 hour)
- [ ] Run sync.py to get shared files
- [ ] Initialize git repository
- [ ] Create initial commit
- [ ] Run `just check` to verify
- [ ] Write tests
- [ ] Validation: Generated backend passes `just check`

### Task 2.4: Add --skip-git, --skip-sync flags (30 min)
- [ ] Add optional flags to skip git init
- [ ] Add optional flag to skip sync.py
- [ ] Update help text
- [ ] Write tests
- [ ] Validation: Flags work correctly

### Task 2.5: Print next steps (30 min)
- [ ] After generation, print clear next steps
- [ ] Show directory structure
- [ ] Show commands to run
- [ ] Suggest where to add tools
- [ ] Validation: Output is clear and helpful

## Phase 3: Interactive Installation (2 hours)

### Task 3.1: Create install module (30 min)
- [ ] Create src/onetool/install.py
- [ ] Add install() command to main CLI
- [ ] Import questionary for prompts
- [ ] Validation: `onetool install` starts wizard

### Task 3.2: Implement backend selection (1 hour)
- [ ] Show checkbox list of available backends
- [ ] Include descriptions for each
- [ ] Official backends: onetool-util, onetool-dev, onetool-xero
- [ ] Optional: external backends (github, devtools)
- [ ] Get user selections
- [ ] Write tests
- [ ] Validation: User can select multiple backends

### Task 3.3: Implement installation flow (1.5 hours)
- [ ] For each selected backend: call backends.install()
- [ ] Show progress for each installation
- [ ] Handle errors gracefully
- [ ] Create default configs
- [ ] Optionally update Claude Code mcp.json
- [ ] Show summary at end
- [ ] Write tests
- [ ] Validation: Wizard completes successfully, backends installed

### Task 3.4: Add quick start message (30 min)
- [ ] After installation, show example commands
- [ ] Show how to verify installation
- [ ] Show first tool call to try
- [ ] Validation: New users know what to do next

## Phase 4: Documentation (4 hours)

### Task 4.1: Create migration guide (1 hour)
- [ ] Create docs/migration-v2.md
- [ ] Document v1.x → v2.0 changes
- [ ] Config file format changes
- [ ] Tool location changes (what moved where)
- [ ] Step-by-step upgrade instructions
- [ ] Troubleshooting section
- [ ] Validation: Guide is clear and comprehensive

### Task 4.2: Create backend development guide (1.5 hours)
- [ ] Create docs/backend-development.md
- [ ] Using onetool-common library
- [ ] Project structure
- [ ] Tool registration patterns
- [ ] Testing backend servers
- [ ] Publishing to PyPI
- [ ] Examples: onetool-util, onetool-dev, onetool-xero
- [ ] Common patterns and best practices
- [ ] Validation: Developers can create backends from guide

### Task 4.3: Create architecture overview (1 hour)
- [ ] Create docs/architecture-v2.md
- [ ] Frontend vs backend servers
- [ ] Proxy architecture diagram
- [ ] Token efficiency (2K vs 30-60K)
- [ ] Fault isolation
- [ ] Dependency isolation
- [ ] Code execution paradigm
- [ ] Validation: Architecture clear to new users

### Task 4.4: Create installation guide (1 hour)
- [ ] Create docs/installation.md
- [ ] Installing onetool core
- [ ] Installing backends (interactive and manual)
- [ ] Configuration
- [ ] Claude Code setup
- [ ] Examples and quick start
- [ ] Troubleshooting
- [ ] Validation: New users can install from guide

### Task 4.5: Update main docs (30 min)
- [ ] Update README.md to link new docs
- [ ] Update CLAUDE.md to reference new architecture
- [ ] Create docs/index.md with navigation
- [ ] Validation: Documentation is discoverable

## Phase 5: Release Automation (2 hours)

### Task 5.1: Create release-all script (1 hour)
- [ ] Create scripts/release-all.sh
- [ ] Release order: common → backends → frontend
- [ ] Parallel backend releases (util, dev, xero)
- [ ] Wait for all to complete
- [ ] Handle errors
- [ ] Validation: Script can release all packages in order

### Task 5.2: Add version coordination (30 min)
- [ ] Check version compatibility
- [ ] Warn if onetool-mcp depends on unreleased common version
- [ ] Document version scheme (common: 0.1.x, backends: 1.0.x, frontend: 2.0.x)
- [ ] Validation: Version checks work correctly

### Task 5.3: Add dry-run mode (30 min)
- [ ] Add --dry-run flag to release-all.sh
- [ ] Show what would be released without doing it
- [ ] Validation: Dry run shows correct actions

### Task 5.4: Test coordinated release (2 hours) - MANUAL
- [ ] Test release-all.sh in development
- [ ] Verify order is correct
- [ ] Verify all packages build
- [ ] Verify dependency resolution works
- [ ] Document the release process
- [ ] Validation: Can perform coordinated release

## Phase 6: Polish and Testing (3 hours)

### Task 6.1: Write comprehensive tests (2 hours)
- [ ] Test all backends CLI commands
- [ ] Test server generator
- [ ] Test interactive install
- [ ] Mock subprocess calls
- [ ] Test error handling
- [ ] Validation: All CLI tests pass

### Task 6.2: Add help text and examples (30 min)
- [ ] Improve help text for all commands
- [ ] Add usage examples to --help
- [ ] Add examples to documentation
- [ ] Validation: Help is comprehensive

### Task 6.3: Error handling polish (30 min)
- [ ] Improve error messages
- [ ] Add suggestions for common errors
- [ ] Add recovery instructions
- [ ] Validation: Errors are clear and actionable

### Task 6.4: Integration testing (1 hour)
- [ ] Test full workflow: install → list → health → update → uninstall
- [ ] Test server create → development → publish workflow
- [ ] Test with real backends
- [ ] Validation: All workflows work end-to-end

## Verification

### Final Checklist
- [ ] `onetool backends list` works, shows all backends
- [ ] `onetool backends install <name>` installs and registers
- [ ] `onetool backends update` checks for updates
- [ ] `onetool backends health` verifies backends
- [ ] `onetool backends uninstall <name>` removes backend
- [ ] `onetool server create <name>` generates working template
- [ ] `onetool install` wizard works end-to-end
- [ ] Migration guide complete (docs/migration-v2.md)
- [ ] Backend dev guide complete (docs/backend-development.md)
- [ ] Architecture overview complete (docs/architecture-v2.md)
- [ ] Installation guide complete (docs/installation.md)
- [ ] Release script works (scripts/release-all.sh)
- [ ] All tests passing
- [ ] `just check` passes
- [ ] Help text comprehensive

### Success Test
- [ ] New user runs `onetool install`
- [ ] Selects onetool-util and onetool-dev
- [ ] Installation completes successfully
- [ ] User runs `__ot file.read(path="README.md")`
- [ ] Tool works via backend proxy
- [ ] User runs `onetool backends health`
- [ ] All backends show healthy
- [ ] User creates new backend with `onetool server create onetool-finance`
- [ ] Generated backend passes `just check`

## Notes

- **Dependencies:** Cannot start until refactor-mcp-core complete (proxy manager needed)
- **Parallelization:** Documentation tasks (4.1-4.5) can be done in parallel
- **Testing:** Focus on real-world workflows, not just unit tests
- **UX:** Make error messages and help text very clear for new users
