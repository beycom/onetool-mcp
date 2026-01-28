# OneTool Development Tasks
# Run `just` to see available commands

set dotenv-load := true

# Default: show available commands
default:
    @just --list --unsorted

# ============================================================================
# QUICK START
# ============================================================================

# Install all dependencies
install:
    uv sync --group dev

# Run all quality checks (lint, typecheck, test)
check: lint typecheck test

# Run the MCP server in development mode
dev *args:
    uv run ot-serve {{ args }}

# ============================================================================
# TESTING
# ============================================================================

# Run all tests (strict - errors on missing requirements)
test *args:
    uv run pytest {{ args }}

# Run tests with --allow-skips (lenient - skips on missing requirements)
test-lenient *args:
    uv run pytest --allow-skips {{ args }}

# Run unit tests only
test-unit:
    uv run pytest -m unit

# Run integration tests only
test-integration:
    uv run pytest -m integration

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
docs-serve:
    uv run mkdocs serve --dev-addr 127.0.0.1:8000

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
    uv build

# Clean build artifacts and caches
clean:
    rm -rf dist/ build/ *.egg-info tmp/
    find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# ============================================================================
# CODE SEARCH (ChunkHound)
# ============================================================================

# Index current project for semantic code search (requires OPENAI_API_KEY env var)
index path=".":
    @echo "=== Indexing {{ path }} for semantic code search ==="
    uvx chunkhound index {{ path }} --db {{ path }}/.chunkhound/db/chunks.db --model text-embedding-3-small --base-url https://openrouter.ai/api/v1
    @echo "=== Index complete. Use code.search() or code.status() ==="

# ============================================================================
# DEMO (submodule - use `just demo::task`)
# ============================================================================

mod demo

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
# GLOBAL TOOL MANAGEMENT
# ============================================================================

# Install onetool globally via uv
ot-install:
    uv tool install . -v

# Install onetool globally via uv
ot-install-dev:
    uv tool install . -e -v


# Uninstall global onetool
ot-uninstall:
    uv tool uninstall onetool-mcp || true

# List installed uv tools
ot-list:
    uv tool list

