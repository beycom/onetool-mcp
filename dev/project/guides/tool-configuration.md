# Tool Configuration

How to add settings, secrets, and path resolution to a tool pack. For the overall config architecture, see [Configuration](../arch/configuration-architecture.md).

## Defining a Config Class

Use a Pydantic `Config` class in your tool module. The registry auto-discovers it:

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
```

Users set values in `onetool.yaml`:

```yaml
mytool:
  timeout: 30.0
  max_results: 50
```

## Accessing Secrets

```python
from ot.config import get_secret

api_key = get_secret("BRAVE_API_KEY")
```

Secrets live in `.onetool/config/secrets.yaml`.

## Path Resolution

For paths relative to `.onetool/` (databases, logs, stats):

```python
from ot.meta import resolve_ot_path

db_path = resolve_ot_path("mem.db")
```

For user-supplied file paths:

```python
from ot.config import resolve_cwd_path

file_path = resolve_cwd_path(user_path)
```

Use relative defaults (e.g., `mem.db`) not absolute (e.g., `~/.onetool/mem.db`). These resolvers honour `OT_GLOBAL_DIR` and project-level `.onetool/` directories. Never use `Path.expanduser()` directly.
