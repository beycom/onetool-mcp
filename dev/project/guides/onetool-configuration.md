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
| `resolve_ot_path()` | Paths relative to `.onetool/` (databases, logs, stats) |
| `resolve_cwd_path()` | User-supplied file paths |
| `expand_path()` | Only for arbitrary user paths (spreadsheets, etc.) |

Never use `Path.expanduser()` directly. The resolvers honour `OT_GLOBAL_DIR` and project-level `.onetool/` directories.

Use relative defaults (e.g., `mem.db`) not absolute ones (e.g., `~/.onetool/mem.db`).

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
