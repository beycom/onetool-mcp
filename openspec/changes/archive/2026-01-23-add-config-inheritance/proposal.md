# Change: Add Three-Tier Config Resolution with Inheritance

## Why

When installing OneTool via `uv tool install -e .`, the global `~/.onetool/` directory is never created because:
1. Default config files are not packaged in the wheel
2. Path resolution assumes development layout (`../../resources/config`)
3. No bootstrap runs on first CLI use

This causes config loading to fail when project configs reference includes like `prompts.yaml` or `snippets.yaml` that should fall back to global or bundled defaults.

## What Changes

- **ADDED**: `get_bundled_config_dir()` function using `importlib.resources` to access packaged defaults
- **ADDED**: Move default configs to `src/ot/config/defaults/` for proper packaging
- **MODIFIED**: `ensure_global_dir()` to copy from bundled package resources instead of filesystem path
- **ADDED**: Three-tier include resolution: project -> global -> bundled fallback
- **ADDED**: `inherit` directive for config files (`global` | `bundled` | `none`)
- **MODIFIED**: CLI entry points to bootstrap global dir on startup
- **ADDED**: Diagram templates packaging under bundled defaults

## Impact

- **Affected specs**: `_nf-paths`, `serve-configuration`
- **Affected code**:
  - [src/ot/paths.py](src/ot/paths.py) - add bundled config dir function
  - [src/ot/config/loader.py](src/ot/config/loader.py) - add inheritance and include fallback
  - [src/ot_serve/cli.py](src/ot_serve/cli.py) - bootstrap on startup
  - [src/ot_bench/cli.py](src/ot_bench/cli.py) - bootstrap on startup
  - [src/ot_browse/app.py](src/ot_browse/app.py) - bootstrap on startup
  - [pyproject.toml](pyproject.toml) - no changes needed (src layout auto-includes)
- **Migration**: None required - existing configs work unchanged; `inherit: global` is the implicit default

## User Experience After Fix

### Fresh Install
```bash
$ uv tool install onetool-mcp
$ ot-serve --help
Creating ~/.onetool/
  ok ot-serve.yaml
  ok prompts.yaml
  ok snippets.yaml
  ok servers.yaml
  ok diagram.yaml
  ok secrets.yaml
# Works immediately with bundled defaults
```

### Minimal Project Config
```yaml
# my-project/.onetool/ot-serve.yaml
version: 1
# inherit: global  (implicit default)

tools_dir:
  - ./tools/*.py
```
Loads project `tools_dir`, inherits prompts/snippets/servers from global.

### Standalone Config (No Inheritance)
```yaml
# isolated/.onetool/ot-serve.yaml
version: 1
inherit: none  # Explicit: don't merge anything

transform:
  model: local/llama3

prompts:
  instructions: |
    Custom standalone instructions.

tools_dir:
  - ./tools/*.py
```
