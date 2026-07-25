# OneTool Dev Commands

OneTool uses `just` (not `make`) for project commands. Run `just` with no args to see available commands.

## Quick Start

```bash
just install        # install all dependencies for day-to-day development
just install-locked # install from the lockfile for release/repro checks
just check          # run lint + typecheck + test (use before every commit)
just dev            # run MCP server in dev mode
```

## Worktrees

Install [WTP](https://github.com/satococoa/wtp), then create a new branch and
bootstrapped worktree:

```bash
brew install satococoa/tap/wtp
just worktree-new feature/my-change       # branch from main
just worktree-new hotfix/urgent v2.0.0    # branch from another ref
```

The recipe prints the new worktree's absolute path and a shell-safe `cd`
command. It cannot change the calling shell's directory, so run the printed
command before starting development.

Worktrees use the final component of the branch name, so
`feature/my-change` is created at `../onetool-mcp-worktrees/my-change` while
the Git branch remains `feature/my-change`. Final components must therefore be
unique across active worktrees.

WTP applies the repository's `.wtp.yml` hooks before the recipe moves the
worktree to its flat path and installs its locked `.venv`. Each worktree gets
its own Codex/Claude configuration and OneTool configuration while sharing
maintained agent skills, work-in-progress artifacts, and OneTool secrets.

Start a fresh Codex or Claude session from the new worktree when testing MCP
changes. This ensures the client launches that worktree's
`.venv/bin/onetool`, rather than retaining an MCP process from another
checkout.

## Testing

```bash
just test              # all tests, strict (errors on missing requirements)
just test [args]       # pass extra pytest args
just test-lenient      # skip tests with missing requirements
just test-unit         # unit tests only
just test-int          # integration tests only
just test-all          # all tests including integration, strict
just test-setup        # download test data into tests/data/
just test-coverage     # with HTML coverage report (tmp/htmlcov/)
```

## Code Quality

```bash
just lint          # check lint issues (ruff check src/)
just lint-fix      # auto-fix lint issues
just fmt           # format code (ruff format src/)
just fmt-check     # check formatting without changes
just typecheck     # run mypy
just deps-check    # check for unused dependencies (deptry)
just secrets-check # scan for leaked secrets (gitleaks)
```

## Documentation

```bash
just docs-sync        # sync generated docs blocks and validate runtime counts
just docs-serve       # serve docs locally with hot reload (port 8000)
just docs-serve-stop  # stop docs server
just docs-build       # build docs (strict mode)
just docs-clean       # clean and rebuild
just docs-deploy      # deploy to GitHub Pages
```

## Build & Release

```bash
just build        # build the package (uv build)
just build-inject # bundle inject.js annotation script
just clean        # clean build artefacts and caches
just reset-env    # recreate .venv from scratch
```

## OneTool

```bash
just ot [args]                    # run local dev onetool
just ot --v 1.0.0rc2 init         # run specific published version
just ot-direct "ot.packs()"       # run via repo-local direct API
just dev [args]                   # run MCP server in development mode
just ot-install                   # install as global uv tool
just ot-uninstall                 # uninstall global tool
just ot-list                      # list global uv tools
just ot-inspector                 # launch MCP Inspector (MCPJam)
```

## Diagram Server (Kroki)

```bash
just tool-diagram-start    # start Kroki via Docker
just tool-diagram-stop     # stop Kroki
just tool-diagram-status   # check Kroki health
just tool-diagram-logs     # view Kroki logs
```

## Module Commands

```bash
just release::<task>       # run release tasks
```

## Key Details

- All test commands use `uv run pytest` for proper dependency resolution
- Config caches stored in `tmp/` (.ruff_cache, .mypy_cache, .pytest_cache)
- Coverage HTML output goes to `tmp/htmlcov/`
