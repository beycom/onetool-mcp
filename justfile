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

# Run all tests
test *args:
    uv run pytest {{ args }}

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
# DEMO
# ============================================================================

# Download and setup all demo assets (database + code project + index)
demo-setup:
    @echo "=== Downloading Northwind database ==="
    @mkdir -p demo/db
    curl -L -o demo/db/northwind.db \
        https://github.com/jpwhite3/northwind-SQLite3/raw/main/dist/northwind.db
    @echo "=== Downloading OpenTelemetry demo ==="
    curl -L -o demo/opentelemetry-demo-main.zip \
        https://github.com/open-telemetry/opentelemetry-demo/archive/refs/heads/main.zip
    @echo "=== Extracting OpenTelemetry demo ==="
    cd demo && unzip -q -o opentelemetry-demo-main.zip
    @echo "=== Indexing OpenTelemetry demo ==="
    cd demo/opentelemetry-demo-main && OPENAI_API_KEY=$({{ _get_openai_key }}) uvx chunkhound index --model text-embedding-3-small --base-url https://openrouter.ai/api/v1
    @echo "=== Demo setup complete ==="
    @echo "Run 'just demo-bench' to run the benchmark scenarios."

# Remove all demo assets (database, zip, extracted project, logs)
demo-clean:
    rm -rf demo/db/northwind.db
    rm -rf demo/opentelemetry-demo-main.zip
    rm -rf demo/opentelemetry-demo-main
    rm -rf demo/tmp/*
    @for f in demo/logs/*.log; do [ -f "$f" ] && : > "$f"; done 2>/dev/null || true
    @echo "Demo assets cleaned"

# Run MCP server with demo project
demo-serve *args:
    OT_CWD=demo uv run ot-serve {{ args }}

# Run benchmark scenarios (TUI picker or specific file)
demo-bench *args:
    OT_CWD=demo uv run ot-bench run --tui --csv {{ args }}

# Truncate demo log files
demo-logs-clean:
    @for f in demo/logs/*.log; do [ -f "$f" ] && : > "$f" && echo "Truncated $f"; done || echo "No log files found"

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
tool-inspector:
    npx @mcpjam/inspector@latest

# ============================================================================
# GLOBAL TOOL MANAGEMENT
# ============================================================================

# Install onetool globally via uv
tool-install:
    uv tool install . -v

# Uninstall global onetool
tool-uninstall:
    uv tool uninstall onetool || true

# List installed uv tools
tool-list:
    uv tool list

# ============================================================================
# INTERNAL
# ============================================================================

# Secrets file path for API keys (used by demo-otel-index)
_secrets_file := justfile_directory() / "demo/.onetool/secrets.yaml"
_get_openai_key := "grep 'OPENAI_API_KEY' " + _secrets_file + " | cut -d'\"' -f2"
