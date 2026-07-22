# OneTool Development Tasks
# Run `just` to see available commands

set dotenv-load := true
set positional-arguments := true

# Project-local OneTool config base
ot_config := justfile_directory() + "/.onetool/onetool.yaml"
ot_dir := justfile_directory() + "/.onetool"
direct_port := "8765"
oneskill_project := "/Users/gavin/01-work-thor/projects/group-hobby/oneskill"
apm_manifest := justfile_directory() + "/apm.yaml"
agents_ot_ref := justfile_directory() + "/.agents/skills/ot-ref"
codex_skills := justfile_directory() + "/.codex/skills"

# Default: show available commands
default:
    @just --list --unsorted

# ============================================================================
# QUICK START
# ============================================================================

# Install all dependencies (including optional extras: util, dev)
install:
    uv sync --group dev --all-extras

# Reproducible install from the locked resolution (fails if uv.lock is stale)
install-locked:
    uv sync --locked --group dev --all-extras

# Install project skills for Claude and Codex
skills-install *args:
    #!/usr/bin/env bash
    set -euo pipefail
    for arg in "$@"; do
        if [[ "$arg" == "--dry-run" ]]; then
            exec uv run --project {{ quote(oneskill_project) }} oneskill install \
                --manifest {{ quote(apm_manifest) }} "$@"
        fi
    done
    mkdir -p {{ quote(justfile_directory() + "/.agents/skills") }}
    if [[ -d {{ quote(codex_skills + "/ot-ref") }} ]]; then
        rm -rf {{ quote(agents_ot_ref) }}
        cp -R {{ quote(codex_skills + "/ot-ref") }} {{ quote(agents_ot_ref) }}
    fi
    uv run --project {{ quote(oneskill_project) }} oneskill install \
        --manifest {{ quote(apm_manifest) }} "$@"
    mkdir -p {{ quote(codex_skills) }}
    rm -rf {{ quote(codex_skills + "/ot-ref") }}
    mv {{ quote(agents_ot_ref) }} {{ quote(codex_skills + "/ot-ref") }}

# Run all quality checks (lint, typecheck, test, architecture frontend)
check: lint typecheck test arch-frontend-check

# Run the MCP server in development mode (uses dev config)
dev *args:
    uv run onetool --config {{ ot_config }} {{ args }}

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

# Run all tests including integration (strict)
test-all *args:
    uv run --all-extras pytest {{ args }}

# Reproducibly install and verify the pinned offline architecture frontend
arch-frontend-check:
    cd src/otdev/tools/_arch/frontend && npm ci --ignore-scripts
    cd src/otdev/tools/_arch/frontend && npm_config_offline=true npm run check

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

# Audit installed dependencies for known vulnerabilities (requires: pip-audit)
# PYSEC-2026-597: nltk (via crawl4ai) has no fixed release yet — drop the
# ignore once one ships.
audit:
    uv run --with pip-audit pip-audit --skip-editable --ignore-vuln PYSEC-2026-597

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
    uv run python scripts/sync_skill_pack_map.py
    uv run python scripts/check_docs_registry.py

# Stop the documentation server
docs-serve-stop:
    @lsof -ti :8000 | xargs kill 2>/dev/null && echo "Docs server stopped" || echo "No server running on port 8000"

# Mirror bootstrap installer scripts into docs/ with sha256 checksums so the
# docs-domain copies never drift from the versioned source in scripts/.
docs-install-scripts:
    cp scripts/install.sh docs/install.sh
    cp scripts/install.ps1 docs/install.ps1
    cd docs && shasum -a 256 install.sh > install.sh.sha256
    cd docs && shasum -a 256 install.ps1 > install.ps1.sha256

# Build documentation site (strict mode)
docs-build: docs-install-scripts
    uv run mkdocs build --strict

# Clean and rebuild docs (strict mode)
docs-clean:
    rm -rf dist/site && uv run mkdocs build --strict

# Deploy documentation to GitHub Pages
docs-deploy: docs-install-scripts
    uv run mkdocs gh-deploy --force

# ============================================================================
# BUILD & RELEASE
# ============================================================================

# Build the package
build:
    uv build

# Bundle inject.js annotation script (requires npm install in src/ot/assets/)
build-inject:
    cd src/ot/assets && npm run build

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
