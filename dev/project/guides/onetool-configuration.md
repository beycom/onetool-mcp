# OneTool Configuration

## Config Resolution

Global-only (no project-level config in V2):

1. `ONETOOL_CONFIG` env var
2. `--config` CLI argument
3. `~/.onetool/config/onetool.yaml`

## Config Files

All under `.onetool/config/`:

| File | Purpose |
|------|---------|
| `onetool.yaml` | Main config (version, tools_dir, includes) |
| `security.yaml` | Validation allowlists (builtins, imports, calls) |
| `prompts.yaml` | System instructions for MCP |
| `snippets.yaml` | Snippet template definitions |
| `servers.yaml` | External MCP server definitions |
| `secrets.yaml` | API keys and credentials |

## Includes

Main config can include other files:

```yaml
version: 1
include:
  - prompts.yaml
  - security.yaml
  - snippets.yaml
```

Maximum include depth: 5 levels.

## Variable Expansion

`${VAR}` reads from `secrets.yaml` only (not environment variables). Use `${VAR:-default}` for defaults.

## Adding Tool Config

1. Define a `Config` class in your tool module:

```python
from pydantic import BaseModel, Field

class Config(BaseModel):
    timeout: float = Field(default=60.0, ge=1.0, le=300.0)
    max_results: int = Field(default=100, ge=1, le=1000)
```

2. Access at runtime:

```python
from ot.config import get_tool_config

config = get_tool_config("mytool", Config)
```

3. Users set values in `onetool.yaml`:

```yaml
mytool:
  timeout: 30.0
  max_results: 50
```

## Path Resolution

| Function | Use For |
|----------|---------|
| `resolve_ot_path()` | OneTool-owned files under the active `.onetool/` directory: databases, logs, stats, auth keys, runtime files |
| `resolve_cwd_path()` | Project files under the effective working directory: user-supplied inputs/outputs, project-local state, generated artifacts |
| `expand_path()` | Arbitrary external paths where neither OT_DIR nor project cwd semantics apply |

Never use `Path.expanduser()` directly. The resolvers honour `OT_GLOBAL_DIR` and project-level `.onetool/` directories.

Use relative defaults (e.g., `mem.db`) not absolute ones (e.g., `~/.onetool/mem.db`).

Use `resolve_ot_path()` when the file belongs to OneTool's active configuration/runtime directory:

```python
from ot.meta import resolve_ot_path

db_path = resolve_ot_path("mem.db")              # <OT_DIR>/mem.db
log_path = resolve_ot_path("logs/serve.log")     # <OT_DIR>/logs/serve.log
```

Use `resolve_cwd_path()` when the path is supplied by a caller or belongs to the user's project tree:

```python
from otpack import resolve_cwd_path

source = resolve_cwd_path(user_path)             # user-supplied file path
state = resolve_cwd_path(".onetool/state.yaml")  # project-local state
output = resolve_cwd_path("reports/out.md")      # project artifact
```

Use `expand_path()` only when the path is intentionally outside both OneTool's OT_DIR and the project tree:

```python
from otpack import expand_path

workbook = expand_path("~/Downloads/input.xlsx")
```

If a path is project-relative, do not use `expand_path()`. If a path is OneTool-owned, do not use `resolve_cwd_path()`.

## Project State

`otpack` provides `get_state(pack, key)` and `set_state(pack, key, value)` for small project-local runtime state.

State is not OneTool config and is not read from `onetool.yaml`. It lives under the effective project working directory:

```text
<effective project cwd>/.onetool/state.yaml
```

Because this is project-relative data, resolve the default path with:

```python
from otpack import resolve_cwd_path

state_path = resolve_cwd_path(".onetool/state.yaml")
```

## Secrets

Access secrets in tool code:

```python
from ot.config import get_secret

api_key = get_secret("BRAVE_API_KEY")
```

Secrets are stored in `secrets.yaml` and auto-merged into config.

## Output Format Modes

| Mode | Output |
|------|--------|
| `json` (default) | Compact JSON |
| `json_h` | Pretty-printed JSON |
| `yml` | YAML flow style |
| `yml_h` | YAML block style |
| `raw` | Plain `str()` |

Callers set per-call: `__format__ = "yml_h"; brave.search(query="test")`
