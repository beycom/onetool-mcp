# Configuration Architecture

## Resolution Order

Explicit config-file model:

1. `ONETOOL_CONFIG` env var
2. `--config` CLI argument
3. User-selected default such as `~/.onetool/onetool.yaml`

## Config Files

All under the active OneTool config directory (`{OT_DIR}`):

| File | Purpose |
|------|---------|
| `onetool.yaml` | Main config (version, tools_dir, includes, aliases) |
| `security.yaml` | Validation allowlists (builtins, imports, calls) |
| `prompts.yaml` | MCP prompt surfaces: run tool contract, server instructions, templates, pack descriptions |
| `snippets.yaml` | Snippet template definitions |
| `servers.yaml` | External MCP server definitions |
| `secrets.yaml` | API keys and credentials |

## Prompt Surfaces

Prompt guidance is split by priority:

| Surface | Responsibility |
|---------|----------------|
| `tools.run.description` | Authoritative invocation contract for first-call behavior: run code, execute snippet, natural language to code, discovery fallback, keyword-only repair |
| `instructions` | Short MCP handshake orientation that points agents to the run description and core safety/discovery guidance |
| `global_templates/skills/ot-ref.md` | Optional advanced reference loaded on demand via `ot.skills(name="ot-ref")` |

Keep critical first-call behavior in `tools.run.description`; keep advanced recovery/detail in `ot-ref`; keep server instructions concise.

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

`${VAR}` reads from `secrets.yaml` only (not env vars). Use `${VAR:-default}` for defaults.

## Output Format Modes

| Mode | Output |
|------|--------|
| `json` (default) | Compact JSON |
| `json_h` | Pretty-printed JSON |
| `yml` | YAML flow style |
| `yml_h` | YAML block style |
| `raw` | Plain `str()` |

## Tool Authors

For tool-specific config (Pydantic Config classes, secrets, path resolution), see [Tool Configuration](../guides/tool-configuration.md).

## Project-Local State

OneTool config is global-only in V2, but `otpack` also exposes a separate project-local state API for small runtime values:

```python
from otpack import get_state, set_state
```

This state is not config and is not loaded from `onetool.yaml`. It is stored at:

```text
<effective project cwd>/.onetool/state/<pack>/state.yaml
```

Default state directory resolution should use `get_project_state_dir(pack)` because the directory follows the effective project cwd.

## Key Files

| File | Role |
|------|------|
| `src/ot/config/loader.py` | YAML loading, includes, variable expansion |
| `src/ot/config/models.py` | OneToolConfig Pydantic model |
| `src/ot/meta/_constants.py` | `resolve_ot_path()` |
| `packages/onetool-pack/src/otpack/state.py` | Project-local pack state helpers |
| `src/ot/utils/format.py` | Result serialisation |
