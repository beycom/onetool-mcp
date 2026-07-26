# Tool Configuration

How to add settings, secrets, and path resolution to a tool pack. For the overall config architecture, see [Configuration](../arch/configuration-architecture.md).

## Defining a Config Class

Use a Pydantic model and expose it through the pack's explicit
`config_model` hook. The model may be local, imported, or subclassed:

```python
from pydantic import BaseModel, Field
from ot.config import get_tool_config


class Config(BaseModel):
    """Pack configuration."""
    timeout: float = Field(default=60.0, ge=1.0, le=300.0, description="Timeout in seconds")
    max_results: int = Field(default=100, ge=1, le=1000, description="Max results")
    relative_paths: bool = Field(default=True, description="Use relative paths in output")


def _get_config() -> Config:
    return get_tool_config("mytool", Config)


config_model = "Config"
```

Users set values in `onetool.yaml`:

```yaml
tools:
  mytool:
    timeout: 30.0
    max_results: 50
```

Keep pack defaults in the tool's Pydantic `Config` class. Shared LLM defaults live in the top-level `llm:` config model and package template. Do not add commented per-pack examples to the root `onetool.yaml` template.

Unknown fields in a typed `tools.<pack>` config raise configuration errors, unless that config schema explicitly allows extra fields. Recognised fields with invalid values also raise configuration errors instead of silently falling back to defaults. Remove or rename invalid fields instead of accepting legacy aliases.

The explicit hook powers redacted runtime introspection and setup help. Registry
validation fails when a configurable pack omits it.

## Declaring requirements

`__ot_requires__` is a list of normalized records. Every record has `kind`,
`name` and `purpose`. `optional` and `activation` apply when needed;
kind-specific identity/install fields are:

| Kind | Required identity | Meaning |
|---|---|---|
| `lib` | `import_name`, `install_extra` | Importable Python library and its supported OneTool install route |
| `cli` | `executable` | External executable on `PATH` |
| `secret` | `name` | OneTool secret name; value is never exposed |
| `server` | `name` | Configured MCP proxy server |
| `config` | `name` | Required pack config field |

Use `optional: true` when a pack remains useful without a workflow dependency.
Add an `activation` condition when current config determines whether that
workflow is active, such as embeddings or a selected renderer. An optional
on-demand workflow such as scraping or formula evaluation need not invent a
config condition. Do not represent conditional dependencies as always-missing
hard requirements.

Setup/config help is read-only. It may diagnose and propose exact existing
CLI/config/secrets operations, but it never installs packages, writes config,
sets credentials, starts services, or connects servers.

## Accessing Secrets

```python
from ot.config import get_secret

api_key = get_secret("BRAVE_API_KEY")
```

Secrets are loaded only from the explicit `--secrets <file>` path. CLI-generated
setups commonly place that file beside `onetool.yaml`, but runtime code does not
search a default location.

## Path Resolution

For paths relative to `.onetool/` (databases, logs, stats):

```python
from ot.meta import resolve_ot_path

db_path = resolve_ot_path("data/mem/default.db")
```

For user-supplied file paths:

```python
from ot.config import resolve_cwd_path

file_path = resolve_cwd_path(user_path)
```

Use relative defaults (e.g., `data/mem/default.db`) not absolute (e.g., `~/.onetool/mem.db`). These resolvers honour the active OneTool config directory and effective project cwd. Never use `Path.expanduser()` directly.
