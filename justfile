# OneTool Development Tasks
# Run `just` to see available commands

set dotenv-load := true
set positional-arguments := true

# Project-local OneTool config base
ot_config := justfile_directory() + "/.onetool/onetool.yaml"
ot_dir := justfile_directory() + "/.onetool"
direct_port := "8765"

# Default: show available commands
default:
    @just --list --unsorted

# ============================================================================
# QUICK START
# ============================================================================

# Install all dependencies (including optional extras: util, dev)
install:
    uv sync --group dev --all-extras

# Run all quality checks (lint, typecheck, test, Admin UI checks)
check: lint typecheck test
    just admin-ui::check

# Run the MCP server in development mode (uses dev config)
dev *args:
    uv run onetool --config {{ ot_config }} {{ args }}

# Serve the Admin App and open it in the default browser
admin-open port="8760" direct_start_port="8765" scan_max="10":
    #!/usr/bin/env bash
    set -euo pipefail
    url="http://127.0.0.1:{{ port }}"
    if curl -fsS "$url/api/admin/health" >/dev/null 2>&1; then
        uv run python -m webbrowser "$url" >/dev/null 2>&1
        exit 0
    fi
    (
        for _ in {1..40}; do
            if curl -fsS "$url/api/admin/health" >/dev/null 2>&1; then
                uv run python -m webbrowser "$url" >/dev/null 2>&1
                exit 0
            fi
            sleep 0.25
        done
    ) &
    uv run onetool admin serve \
        --ot-dir {{ quote(ot_dir) }} \
        --port {{ port }} \
        --direct-start-port {{ direct_start_port }} \
        --scan-max {{ scan_max }}

# ============================================================================
# TESTING
# ============================================================================

# Run unit tests (strict - errors on missing requirements)
test *args:
    uv run --all-extras pytest -m "not integration" {{ args }}

# Run tests with --allow-skips (lenient - skips on missing requirements)
test-lenient *args:
    uv run --all-extras pytest -m "not integration" --allow-skips {{ args }}

# Run unit tests only
test-unit:
    uv run --all-extras pytest -m unit

# Run integration tests only
test-int *args:
    uv run --all-extras pytest -m integration {{ args }}

# Run caveman skill eval (baseline vs ot-cm vs jb_caveman). Use --reset-baseline to regenerate cached baseline.
eval-caveman *args:
    uv run python scripts/eval_caveman_skill.py {{ args }}

# Run all tests including integration (strict)
test-all *args:
    uv run --all-extras pytest {{ args }}

# Download test data from beycom/onetool-mcp-test into tests/data/
test-setup:
    @echo "=== Downloading test data ==="
    @mkdir -p tests/data
    curl -sL https://github.com/beycom/onetool-mcp-test/archive/refs/heads/main.zip -o /tmp/ot-test-data.zip
    unzip -jo /tmp/ot-test-data.zip -d tests/data/
    @rm -f /tmp/ot-test-data.zip tests/data/README.md
    @echo "=== Test data ready at tests/data/ ==="

# Run tests with coverage report
test-coverage:
    uv run pytest --cov=onetool --cov-report=html

# ============================================================================
# CODE QUALITY
# ============================================================================

# Lint code with ruff
lint:
    uv run ruff check src/

# Lint and auto-fix issues
lint-fix:
    uv run ruff check --fix src/

# Format code with ruff
fmt:
    uv run ruff format src/

# Check formatting without changes
fmt-check:
    uv run ruff format --check src/

# Type check with mypy
typecheck:
    uv run mypy

# Check for unused dependencies
deps-check:
    uvx deptry . 2>&1 | grep -v "^Assuming"

# Scan for secrets with gitleaks
secrets-check:
    gitleaks detect --source . --verbose

# ============================================================================
# DOCUMENTATION
# ============================================================================

# Serve documentation locally with hot reload
docs-serve *args:
    uv run mkdocs serve --dev-addr 127.0.0.1:8000 {{ args }}

# Sync generated docs blocks and validate index counts against runtime registry
docs-sync:
    uv run python scripts/sync_docs_generated.py
    uv run python scripts/list_tool_inventory.py --tool-descriptions
    uv run python scripts/check_docs_registry.py

# Stop the documentation server
docs-serve-stop:
    @lsof -ti :8000 | xargs kill 2>/dev/null && echo "Docs server stopped" || echo "No server running on port 8000"

# Build documentation site (strict mode)
docs-build:
    uv run mkdocs build --strict

# Clean and rebuild docs (strict mode)
docs-clean:
    rm -rf dist/site && uv run mkdocs build --strict

# Deploy documentation to GitHub Pages
docs-deploy:
    uv run mkdocs gh-deploy --force

# ============================================================================
# BUILD & RELEASE
# ============================================================================

# Build the package
build:
    just admin-ui::build
    uv build

# Bundle inject.js annotation script (requires npm install in src/ot/assets/)
build-inject:
    cd src/ot/assets && npm run build

# Bundle Admin UI TypeScript app (requires npm install in packages/admin-ui/)
build-display:
    just admin-ui::build

# Clean build artifacts and caches
clean:
    rm -rf dist/ build/ *.egg-info tmp/
    find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
    uv cache clean

# Recreate the local Python environment from scratch
reset-env: clean
    rm -rf .venv
    uv cache clean
    just install

# ============================================================================
# MODULES (use `just <module>::<task>`)
# ============================================================================

mod bench 'packages/onetool-bench/justfile'
mod admin-ui "packages/admin-ui/justfile"
mod release "release.just"

# ============================================================================
# TOOL: DIAGRAM (Kroki Server)
# ============================================================================

# Start Kroki diagram server
tool-diagram-start:
    docker compose -f resources/docker/kroki/docker-compose.yaml up -d
    @echo "Kroki running at http://localhost:8000"
    @echo "Health check: curl http://localhost:8000/health"

# Stop Kroki diagram server
tool-diagram-stop:
    docker compose -f resources/docker/kroki/docker-compose.yaml down

# Show Kroki server status
tool-diagram-status:
    @docker compose -f resources/docker/kroki/docker-compose.yaml ps 2>/dev/null || echo "Kroki not running"
    @curl -s http://localhost:8000/health 2>/dev/null && echo " - Kroki healthy" || echo "Kroki not responding"

# View Kroki server logs
tool-diagram-logs:
    docker compose -f resources/docker/kroki/docker-compose.yaml logs -f

# ============================================================================
# TOOL: MCP INSPECTOR (MCPJam)
# ============================================================================

# Launch MCP Inspector for testing MCP servers
# https://github.com/MCPJam/inspector
ot-inspector:
    npx @mcpjam/inspector@latest

# ============================================================================
# ONETOOL
# ============================================================================

# Run onetool (local dev by default)
#   --v VERSION      use published version (e.g., 1.0.0rc2)
#   --config PATH    use custom config file path
# Example: just ot --v 1.0.0rc2 init validate
[arg("v", long)]
[arg("config", long)]
ot v="" config="" *args:
    #!/usr/bin/env bash
    set -euo pipefail
    shift 2
    config_path={{ quote(if config == "" { ot_config } else { config }) }}
    if [[ -z {{ quote(v) }} ]]; then
        exec uv run onetool --config "$config_path" "$@"
    fi
    exec uvx --from {{ quote("onetool-mcp==" + v) }} onetool --config "$config_path" "$@"

# Run a command through this repo's MCP-owned direct API
ot-direct *args:
    #!/usr/bin/env bash
    set -euo pipefail
    exec uv run onetool --config {{ quote(ot_config) }} direct run \
        --port {{ quote(direct_port) }} \
        --ot-dir {{ quote(ot_dir) }} \
        "$@"

# Install as global uv tool
ot-install:
    uv tool install . -v

# Uninstall global uv tool
ot-uninstall:
    uv tool uninstall onetool-mcp || true

# List global uv tools
ot-list:
    uv tool list
