# OneTool Configuration

## Config Resolution

Explicit config-file model:

1. `ONETOOL_CONFIG` env var
2. `--config` CLI argument
3. User-selected default such as `~/.onetool/onetool.yaml`

## Config Files

All under the active OneTool config directory (`{OT_DIR}`):

| File | Purpose |
|------|---------|
| `onetool.yaml` | Main config (version, includes, root settings such as `llm`, `stats`, `env`) |
| `security.yaml` | Validation allowlists (builtins, imports, calls) |
| `prompts.yaml` | MCP prompt surfaces: `tools.run.description`, server `instructions`, templates, and pack descriptions |
| `snippets.yaml` | Snippet template definitions |
| `servers.yaml` | External MCP server definitions |
| `secrets.yaml` | API keys and credentials |

## Prompt Surface Ownership

`prompts.yaml` has multiple prompt surfaces with different priority and token budgets:

| Surface | Put Here |
|---------|----------|
| `tools.run.description` | Critical first-call invocation contract: code mode, snippet mode, natural-language-to-code mode, discovery fallback, and keyword-only repair rules |
| `instructions` | Concise server-level orientation: follow the run description, prefer MCP `run(command=...)`, discovery/safety pointers, output boundary warning |
| `skills/ot-ref.md` | Optional advanced reference for recovery loops, proxy handling, security checks, output controls, ctx handles, and param-prefix details |

Do not duplicate long guidance across all three. If a rule affects whether the first tool call is shaped correctly, it belongs in `tools.run.description`.

## Includes

Main config can include other files:

```yaml
version: 2
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
tools:
  mytool:
    timeout: 30.0
    max_results: 50
```

Pack config belongs under `tools.<pack>`. Unknown typed pack keys fail visibly when the pack reads its config, unless that config schema explicitly allows extra fields. Recognised keys with invalid values also fail visibly. Do not keep legacy config aliases or compatibility mappings.

The root template stays minimal. Shared generation belongs in the strict
discriminated `llm` backend, while embedding settings belong only in the
independent `embeddings` backend. Broad commented examples for every pack are
not.

## Path Resolution

| Function | Use For |
|----------|---------|
| `resolve_ot_path()` | Existing config-relative strings and explicit OT_DIR paths |
| `get_ot_runtime_dir(kind)` | Runtime directories under `runtime/`: logs, stats, sessions, reports |
| `get_ot_data_dir(kind)` | Config-scoped data stores under `data/` |
| `get_ot_template_dir(kind)` | Editable template override directories under `templates/` |
| `resolve_cwd_path()` | Project files under the effective working directory: user-supplied inputs/outputs, project-local state, generated artifacts |
| `get_project_state_dir(pack)` | Pack-owned project state under `.onetool/state/{pack}/` |
| `get_project_artifact_dir(kind)` | Generated project artifacts under `{CWD}` |
| `expand_path()` | Arbitrary external paths where neither OT_DIR nor project cwd semantics apply |

Never use `Path.expanduser()` directly. The resolvers honour the active OneTool config directory and effective project cwd.

Use relative defaults (e.g., `data/mem/default.db`) not absolute ones (e.g., `~/.onetool/mem.db`).

Use `resolve_ot_path()` when the file belongs to OneTool's active configuration/runtime directory:

```python
from ot.meta import resolve_ot_path

db_path = resolve_ot_path("data/mem/default.db")       # <OT_DIR>/data/mem/default.db
log_path = resolve_ot_path("runtime/logs/serve.log")   # <OT_DIR>/runtime/logs/serve.log
```

Use `resolve_cwd_path()` when the path is supplied by a caller or belongs to the user's project tree:

```python
from otpack import resolve_cwd_path

source = resolve_cwd_path(user_path)             # user-supplied file path
state = resolve_cwd_path(".onetool/state/my_pack/state.yaml")   # project-local state
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
<effective project cwd>/.onetool/state/<pack>/state.yaml
```

Because this is project-relative data, resolve pack-owned directories with:

```python
from otpack import get_project_state_dir

state_path = get_project_state_dir("my_pack") / "state.yaml"
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
