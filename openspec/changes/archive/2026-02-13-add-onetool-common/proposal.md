# Change: Create onetool-common shared library and refactor onetool-xero

## Why

The v2.0 architecture splits onetool-mcp into standalone backend servers. Every backend needs config loading, logging, path resolution, and CLI boilerplate. Both onetool-mcp (`ot.*`) and onetool-xero (`ox.*`) already implement these patterns independently - resulting in ~1,000 LOC of duplicated logic that will multiply with each new backend. A shared library eliminates this duplication and establishes the foundation for all future backends.

## What Changes

- **NEW**: Create `onetool-common` package in a separate repository (`group-hobby/onetool-common`)
  - Config loading: YAML with includes, deep merge, secrets expansion, Pydantic validation
  - Logging: Loguru setup with dev/JSON formatters, structured LogEntry/LogSpan
  - Path resolution: `~/.onetool/` global directory, expand paths, ensure directories
  - HTTP helpers: Shared httpx client with connection pooling, API header building
  - CLI boilerplate: Typer app factory with `--config` flag pattern
  - Tool registration: `@tool_wrapper()` decorator for sync-to-async FastMCP wrapping
  - Reference project template: `template/` directory with standard files for scaffolding new backends
- **REFACTOR**: Update `onetool-xero` to depend on `onetool-common` instead of inline `ox.config`, `ox.logging`, `ox.paths`
  - Replace `ox.config.loader` with `onetool_common.config`
  - Replace `ox.logging.config` with `onetool_common.logging`
  - Replace `ox.paths` with `onetool_common.paths`
  - Keep ox-specific code: `ox.auth`, `ox.xero`, `ox.tools`, `ox.utils`
- **NO CHANGE**: `onetool-mcp` remains stable and unchanged

## Impact

- Affected specs: `shared-library` (new), `backend-config` (new)
- Affected code:
  - New repo: `onetool-common/src/onetool_common/`
  - onetool-xero: `ox/config/`, `ox/logging/`, `ox/paths.py`, `ox/server.py`, `ox/cli.py`
- Affected projects: onetool-common (new), onetool-xero (refactor)
- No changes to onetool-mcp
