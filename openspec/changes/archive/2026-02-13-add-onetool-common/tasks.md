## 1. Create onetool-common project

- [x] 1.1 Initialise `group-hobby/onetool-common` repo with `uv init --lib`, standard pyproject.toml (Python 3.11+, deps: pydantic, pyyaml, loguru, httpx, typer, rich)
- [x] 1.2 Set up project tooling: justfile (install, check, lint, typecheck, test), ruff config, mypy config, CLAUDE.md
- [x] 1.3 Create `src/onetool_common/__init__.py` with `__version__`

## 2. Extract config module

- [x] 2.1 Create `onetool_common/config/loader.py` - generic YAML loader with includes (max 5 deep), deep merge, array flatten, version validation. Accept any Pydantic schema class. Source: `ot/config/loader.py` + `ox/config/loader.py` (merge best of both)
- [x] 2.2 Create `onetool_common/config/secrets.py` - secrets loading from YAML, `${VAR}` and `${VAR:-default}` expansion, secrets-first then env var fallback. Source: `ot/config/secrets.py` + `ox/config/secrets.py`
- [x] 2.3 Create `onetool_common/config/__init__.py` - public API: `load_config`, `get_config`, `get_secret`, `expand_vars`, `ConfigNotFoundError`
- [x] 2.4 Write tests: config loading, includes processing, deep merge, secrets expansion, missing file handling

## 3. Extract logging module

- [x] 3.1 Create `onetool_common/logging/entry.py` - LogEntry with auto-timing, field tracking, success/failure, to_dict(). Source: `ot/logging/entry.py`
- [x] 3.2 Create `onetool_common/logging/span.py` - LogSpan context manager (sync + async), auto-log on exit. Source: `ot/logging/span.py`
- [x] 3.3 Create `onetool_common/logging/format.py` - format_log_entry, field truncation, URL sanitisation. Source: `ot/logging/format.py`
- [x] 3.4 Create `onetool_common/logging/config.py` - `configure_logging()` with dev formatter, JSON serialiser, stdlib interception, file rotation. Merge patterns from `ot/logging/config.py` + `ox/logging/config.py`
- [x] 3.5 Create `onetool_common/logging/__init__.py` - public API: `LogEntry`, `LogSpan`, `configure_logging`
- [x] 3.6 Write tests: LogEntry timing/fields, LogSpan context manager, configure_logging setup

## 4. Extract paths module

- [x] 4.1 Create `onetool_common/paths.py` - `get_global_dir()` (default `~/.onetool/`, env override `OT_GLOBAL_DIR`), `ensure_global_dir()`, `expand_path()`, subdirectory helpers (config, logs, cache). Source: `ot/paths.py` + `ox/paths.py`
- [x] 4.2 Write tests: path resolution, env override, directory creation

## 5. Extract HTTP utilities

- [x] 5.1 Create `onetool_common/http.py` - shared httpx client (singleton, connection pooling, atexit shutdown), `http_get()`, `api_headers()`. Source: `ot/http_client.py` + `ot/utils/http.py`
- [x] 5.2 Write tests: client creation, header building, mock HTTP calls

## 6. Extract tool wrapper

- [x] 6.1 Create `onetool_common/tools.py` - `@tool_wrapper(module_path, func_name)` decorator for sync-to-async wrapping with signature preservation. Source: `ox/server.py` (tool_wrapper function)
- [x] 6.2 Write tests: wrapper imports and calls sync impl, signature preserved

## 7. Extract CLI helpers

- [x] 7.1 Create `onetool_common/cli.py` - `create_cli(name, default_config)` Typer factory, `--config` flag, `--version` flag, first-run detection, signal handlers. Source: `ox/cli.py` + `ox/_cli.py` + `ot/cli.py` patterns
- [x] 7.2 Write tests: CLI creation, flag parsing

## 8. Create reference project template

- [x] 8.1 Create `template/pyproject.toml` with `{name}`, `{package}`, `{description}` placeholders, standard deps (fastmcp, onetool-common), ruff/mypy/pytest config
- [x] 8.2 Create `template/justfile` with install, check, lint, typecheck, test, dev commands
- [x] 8.3 Create `template/CLAUDE.md` with standard agent instructions (hints.md reference, just commands, openspec mention)
- [x] 8.4 Create `template/README.md` with `{name}`, `{description}` placeholders
- [x] 8.5 Create `template/.gitignore`, `template/.python-version`, `template/CHANGELOG.md`
- [x] 8.6 Create `template/.mcp.json` for dev testing with Claude Code
- [x] 8.7 Create `template/dev/agents/hints.md` - simplified quick reference for backend projects
- [x] 8.8 Create `template/dev/agents/project-map.md` - simplified structure map
- [x] 8.9 Create `template/openspec/project.md` - minimal stub (developer runs `openspec init` after scaffolding for full setup)
- [x] 8.10 Create `template/src/{package}/__init__.py`, `server.py`, `cli.py` - standard entry points using onetool-common
- [x] 8.11 Create `template/tests/conftest.py` and `test_sanity.py` with standard markers (smoke, unit, integration, tools)

## 9. Validate onetool-common

- [x] 9.1 Run `just check` (lint + typecheck + test) - all must pass
- [x] 9.2 Verify clean import from fresh venv: `from onetool_common.config import load_config`
- [x] 9.3 Publish to PyPI as `onetool-common` (or use editable install for next phase)

## 10. Refactor onetool-xero

- [x] 10.1 Add `onetool-common>=0.1.0` dependency to onetool-xero `pyproject.toml`
- [x] 10.2 Replace `ox.config.loader` with `onetool_common.config` - update all imports in config/__init__.py
- [x] 10.3 Replace `ox.config.secrets` with `onetool_common.config` - update secret access patterns
- [x] 10.4 Replace `ox.logging.config` with `onetool_common.logging` - update `configure_logging()` call in cli.py
- [x] 10.5 Replace `ox.paths` with `onetool_common.paths` - update all `get_global_dir()`, `get_config_dir()`, etc.
- [x] 10.6 Move `tool_wrapper` import from `ox.server` to `onetool_common.tools`
- [x] 10.7 Update config path convention: default config from `~/.one-xero/config/one-xero.yaml` to `~/.onetool/xero.yaml` (breaking change, with backwards compat fallback)
- [x] 10.8 Remove replaced modules: `ox/config/loader.py`, `ox/config/secrets.py`, `ox/_cli.py`, `ox/paths.py` (kept `ox/logging/config.py` - xero-specific, kept `ox/config/models.py` - xero-specific schema)
- [x] 10.9 Run full onetool-xero test suite - all tests must pass
- [x] 10.10 Smoke test: start `one-xero` server, verify tool calls work via Claude Code

## 11. Documentation

- [x] 11.1 Create onetool-common README.md with usage examples
- [x] 11.2 Update onetool-xero README.md noting the onetool-common dependency
- [x] 11.3 Update `wip/consult/v2-refactor.md` marking Proposal 1 as complete
