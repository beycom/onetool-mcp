## Context

OneTool v2.0 splits the monolithic MCP server into standalone backends. Both `onetool-mcp` and `onetool-xero` already implement overlapping infrastructure (config loading, logging, path resolution). Creating `onetool-common` as a shared library prevents this duplication from multiplying across 4+ backends.

**Stakeholders:** All backend server projects (onetool-util, onetool-dev, onetool-xero, onetool-mcp)

**Constraints:**
- Must work with Python 3.11+
- Must not break onetool-mcp (it stays unchanged in this proposal)
- Must support both standalone and proxied backend modes
- Backends are treated identically to external MCP servers (github, devtools)

## v2.0 Refactor Principles

These apply to ALL proposals in the v2.0 refactor (see `wip/consult/v2-refactor.md`):

1. **No backwards compatibility.** This is v2.0 - a clean break. No migration shims, no old-path detection, no deprecation warnings, no re-exports. Delete what's replaced. No current users means no impact.
2. **Simple, clean refactor.** Favour deleting code over wrapping it. Favour breaking changes over compatibility layers.
3. **Standalone backends.** Each backend is a completely standalone MCP server - identical to external backends.

## Goals / Non-Goals

**Goals:**
- Extract generic config/logging/paths/HTTP/CLI patterns into reusable library
- Refactor onetool-xero to prove the shared library works
- Publish `onetool-common` to PyPI
- Establish project template patterns for future backends

**Non-Goals:**
- Modifying onetool-mcp in any way
- Creating onetool-util or onetool-dev (separate proposals)
- Building the proxy manager or backend forwarding
- Migrating onetool-mcp to use onetool-common (separate proposal)

## Decisions

### Decision 1: Separate repository for onetool-common

**Choice:** New repo at `group-hobby/onetool-common` (Option A from consultation)

**Rationale:** Clean separation, independent versioning, any backend can depend on it without cloning onetool-mcp. During development, use editable installs (`uv pip install -e ../onetool-common`).

**Alternatives considered:**
- Option B (inside onetool-mcp mono-repo) - Rejected: muddier boundaries, xero devs must clone mcp
- Option C (no shared library) - Rejected: ~1,000 LOC duplication per backend

### Decision 2: Extract patterns from both ot.* and ox.*

**Choice:** Design the common API by merging the best of both implementations.

| Module | From ot (onetool-mcp) | From ox (onetool-xero) | Common API |
|--------|----------------------|----------------------|------------|
| Config | Includes, deep merge, array flatten, version validation | Same patterns, simpler schema | `load_config(path, schema_cls)` with generic loader |
| Secrets | `${VAR}` + `${VAR:-default}`, secrets-first lookup | Same pattern | `expand_vars(value, secrets)`, `get_secret(key)` |
| Logging | LogEntry + LogSpan + JSON format + dev format | Loguru setup + dev/JSON formatters + stdlib interception | LogEntry, LogSpan, `configure_logging()`, `InterceptHandler` |
| Paths | `~/.onetool/`, env override, project-level `.onetool/` | `~/.one-xero/`, env override | `get_global_dir(app_name)`, `ensure_global_dir()`, `expand_path()` |
| HTTP | Shared httpx client, connection pooling, LogSpan integration | Direct httpx via xero-python SDK | `http_get()`, `api_headers()`, `lazy_client()` |
| CLI | Typer with init/serve subcommands, first-run check | Same pattern | `create_cli(name)`, `serve_command()` pattern |
| Tools | AST registry, `pack` variable, `__all__` | `@tool_wrapper()` for sync→async | Both: `@tool_wrapper()` + optional AST registry |

### Decision 3: Config schema is NOT in common

**Choice:** onetool-common provides the loader machinery (YAML, includes, deep merge, secrets), but each backend defines its own Pydantic config model.

**Rationale:** `OneToolConfig` and `OneXeroConfig` have completely different fields. The loader logic is generic; the schema is not.

```python
# onetool-common provides:
from onetool_common.config import load_config, expand_vars, get_secret

# Each backend defines its own schema:
from my_backend.config.models import MyBackendConfig
config = load_config("~/.onetool/my-backend.yaml", schema=MyBackendConfig)
```

### Decision 4: Path resolution is parameterised by app name

**Choice:** Common paths module works with any app name, defaulting to `~/.onetool/`.

```python
from onetool_common.paths import get_global_dir, ensure_global_dir

# For onetool-xero:
global_dir = get_global_dir()  # ~/.onetool/ (shared directory)
ensure_global_dir()            # Creates ~/.onetool/ with subdirs
```

**Migration:** onetool-xero moves from `~/.one-xero/` to `~/.onetool/`. Breaking change - no backwards compatibility detection. No current users to impact.

### Decision 5: tool_wrapper lives in common

**Choice:** The `@tool_wrapper()` decorator from onetool-xero is extracted into onetool-common since all backends need it.

```python
from onetool_common.tools import tool_wrapper

@mcp.tool()
@tool_wrapper("my_backend.tools.analytics")
async def calculate_metrics() -> dict:
    """Calculate key metrics."""
    raise NotImplementedError("Provided by @tool_wrapper")
```

### Decision 6: Reference directory template in onetool-common

**Choice:** A `template/` directory in onetool-common containing actual project files with `{name}`, `{package}`, `{description}` placeholders.

**Rationale:** Concrete files prevent drift between projects. Simple copy + search-replace - no Jinja2 or copier dependency needed. AI agents or the scaffold tool can use it directly.

**Template contents:**

```
onetool-common/template/
├── pyproject.toml              # {name}, {package}, {description} placeholders
├── justfile                    # install, check, lint, typecheck, test, dev
├── CLAUDE.md                   # Standard agent instructions
├── README.md                   # {name}, {description} placeholders
├── CHANGELOG.md                # Empty starter
├── .gitignore                  # Python + IDE + .onetool/
├── .python-version             # 3.11
├── .mcp.json                   # Dev testing config for Claude Code
├── dev/
│   └── agents/
│       ├── hints.md            # Simplified quick reference
│       └── project-map.md      # Simplified structure map
├── openspec/
│   └── project.md              # Minimal project context
├── src/{package}/
│   ├── __init__.py             # __version__, package metadata
│   ├── server.py               # FastMCP server + tool registration
│   └── cli.py                  # Typer CLI: serve, init, version
└── tests/
    ├── conftest.py             # Shared fixtures, markers
    └── test_sanity.py          # Import smoke test
```

**Placeholders:**
- `{name}` - PyPI package name (e.g., `onetool-xero`)
- `{package}` - Python package name (e.g., `onetool_xero`)
- `{description}` - One-line description

**Alternatives considered:**
- Copier template - Rejected: overkill for 4 projects, adds tooling dependency
- Documented standard only - Rejected: files drift without concrete reference

## Risks / Trade-offs

- **Risk:** Version coordination between common and backends
  - Mitigation: Semver pinning (`onetool-common>=1.0,<2.0`), minimal API surface
- **Risk:** Breaking onetool-xero during refactor
  - Mitigation: All existing tests must pass, change only import paths and config plumbing. No current users - clean break.

## Migration Plan

### Phase 1: Create onetool-common (~500-800 LOC)

1. Create repo with standard Python project structure
2. Extract config loader (YAML, includes, deep merge, secrets)
3. Extract logging (LogEntry, LogSpan, formatters, InterceptHandler)
4. Extract paths (global dir, ensure dirs, expand paths)
5. Extract HTTP helpers (shared client, api_headers)
6. Extract tool_wrapper decorator
7. Add CLI helper (Typer app factory)
8. Write tests
9. Publish to PyPI

### Phase 2: Refactor onetool-xero (~200-300 LOC changes)

1. Add `onetool-common` dependency
2. Replace `ox.config.loader` imports with `onetool_common.config`
3. Replace `ox.logging` imports with `onetool_common.logging`
4. Replace `ox.paths` imports with `onetool_common.paths`
5. Move `@tool_wrapper` import to `onetool_common.tools`
6. Update config path convention to `~/.onetool/xero.yaml`
7. Remove replaced ox modules (loader.py, logging/config.py, paths.py)
8. Run full test suite
9. Update pyproject.toml dependencies

### Rollback

- onetool-common is a new package - no rollback needed (just don't publish)
- onetool-xero changes are on a branch - revert if tests fail
- onetool-mcp is completely untouched

## Open Questions

None - all decisions resolved in consultation documents.
