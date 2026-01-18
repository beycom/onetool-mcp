# Demo Project

This directory contains demo configurations, sample data, and benchmarks for OneTool.

Use these demos to:

- Test OneTool's built-in namespaces (db, code, brave, excel, etc.)
- Run benchmarks comparing different LLM + tool combinations
- Explore the MCP server with real data

## Quick Start

From the project root:

```bash
# Download required assets (Northwind DB + OpenTelemetry project)
just demo-setup

# Start the MCP server with demo config
just demo-serve

# Run benchmark scenarios interactively
just demo-bench
```

## Commands

| Command | Description |
|---------|-------------|
| `just demo-setup` | Download DB, code project, and create search index |
| `just demo-serve` | Start MCP server with demo config |
| `just demo-bench` | Run benchmarks (interactive TUI picker) |
| `just demo-clean` | Remove all downloaded assets |
| `just demo-logs-clean` | Truncate log files |

## Benchmark Scenarios

The `bench/` directory contains YAML files testing different OneTool capabilities:

| File | Tests |
|------|-------|
| `tool_db.yaml` | SQL queries against Northwind |
| `tool_brave_search.yaml` | Web search |
| `tool_code_search.yaml` | Semantic code search |
| `tool_excel.yaml` | Excel file operations |
| `tool_ripgrep.yaml` | File content search |
| `tool_web_fetch.yaml` | URL fetching |
| `features.yaml` | Multi-namespace workflows |
| `compare.yaml` | LLM comparison tests |

## Directory Structure

```text
demo/
├── .onetool/      # OneTool configuration files
├── bench/         # Benchmark scenario YAML files
├── data/          # Sample data files
├── db/            # Database files (gitignored, download required)
├── src/           # Demo source code
└── tmp/           # Temporary files (gitignored)
```

## Cleanup

```bash
just demo-clean   # Remove all demo assets (db, zip, extracted project)
```
