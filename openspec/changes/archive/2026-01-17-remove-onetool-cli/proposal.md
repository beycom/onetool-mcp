# Change: Remove onetool CLI and Simplify Installation

## Why

The `onetool` CLI provides auxiliary commands (check, config, upgrade, diagram) that are rarely used. The core product is `ot-serve`. Removing `onetool` simplifies the package and enables a cleaner installation via `uv tool install`.

Current installation requires git clone + path configuration. With this change, users can install with a single command and the MCP config becomes trivial.

## What Changes

- **REMOVED**: `src/onetool/` package (CLI, paths, migrations)
- **REMOVED**: `onetool` entry point from pyproject.toml
- **REMOVED**: `onetool-cli` spec (entire capability removed)
- **MODIFIED**: Installation docs - use `uv tool install onetool-mcp`
- **MODIFIED**: Quickstart - simpler install flow
- **MODIFIED**: README - updated installation section
- **MODIFIED**: CLI reference - remove onetool section
- **MODIFIED**: project.md - remove onetool from CLIs list

## Impact

- Affected specs: `onetool-cli` (removed), `docs` (modified)
- Affected code:
  - `src/onetool/` - deleted
  - `pyproject.toml` - entry point removed
  - `docs/getting-started/` - updated
  - `docs/reference/cli/` - updated
  - `README.md` - updated
  - `openspec/project.md` - updated

## Migration

Users currently relying on `onetool` commands can:
- `onetool check` - Run manually or check secrets.yaml directly
- `onetool config` - Use `cat ~/.onetool/ot-serve.yaml`
- `onetool upgrade` - Follow CHANGELOG migration notes
- `onetool diagram *` - Follow docs for Kroki setup

## Rationale

| Before | After |
|--------|-------|
| `git clone ... && cd onetool && uv sync` | `uv tool install onetool-mcp` |
| `{"command": "uv", "args": ["--directory", "/path/to/onetool", "run", "ot-serve"]}` | `{"command": "ot-serve"}` |

Installation friction is the #1 barrier to adoption. This change removes it.
