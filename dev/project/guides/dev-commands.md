# OneTool Dev Commands

OneTool uses `just` (not `make`) for project commands. Run `just` with no args to see available commands.

## Quick Start

```bash
just install        # install all dependencies for day-to-day development
just install-locked # install from the lockfile for release/repro checks
just check          # run lint + typecheck + test (use before every commit)
just dev            # run MCP server in dev mode
```

## Testing

```bash
just test              # all tests, strict (errors on missing requirements)
just test [args]       # pass extra pytest args
just test-lenient      # skip tests with missing requirements
just test-unit         # unit tests only
just test-int          # integration tests only
just test-all          # all tests including integration, strict
just test-setup        # download test data into tests/data/
just test-coverage     # non-integration tests, all shipped packages (tmp/htmlcov/)
```

## Code Quality

```bash
just lint          # check shipped sources (src/ and packages/onetool-pack/src/)
just lint-fix      # auto-fix lint issues
just fmt           # format shipped sources
just fmt-check     # check shipped-source formatting without changes
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
