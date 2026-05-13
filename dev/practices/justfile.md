# Justfile & Dev Commands

Use `just` (not `make`) for all project commands. Run `just` with no args to see available commands.

## Quick Start

```bash
just install        # install all dependencies (uv sync --group dev)
just check          # run lint + typecheck + test (use before every commit)
just dev            # run MCP server in dev mode
```

## Testing

```bash
just test              # all tests, strict (errors on missing requirements)
just test-lenient      # skip tests with missing requirements
just test-unit         # unit tests only
just test-integration  # integration tests only
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
just docs-serve       # serve docs locally with hot reload (port 8000)
just docs-serve-stop  # stop docs server
just docs-build       # build docs (strict mode)
just docs-clean       # clean and rebuild
just docs-deploy      # deploy to GitHub Pages
```

## Build & Release

```bash
just build    # build the package (uv build)
just clean    # clean build artefacts and caches
```

## OneTool

```bash
just ot [args]              # run local dev onetool
just ot --v 1.0.0rc2 init   # run specific published version
just ot-direct "ot.packs()" # run via repo-local direct API
just ot-install             # install as global uv tool
just ot-uninstall           # uninstall global tool
just ot-list                # list global uv tools
just ot-inspector           # launch MCP Inspector (MCPJam)
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
just bench::demo::<task>   # run demo tasks
just release::<task>       # run release tasks
```

## Key Details

- All test commands use `uv run pytest` for proper dependency resolution
- Config caches stored in `tmp/` (.ruff_cache, .mypy_cache, .pytest_cache)
- Coverage HTML output goes to `tmp/htmlcov/`

