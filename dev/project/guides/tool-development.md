# Tool Development

Guide for creating tools bundled with OneTool or optional extras.

When a pack needs distinct agent operating guidance, use the
[Skill Development](skill-development.md) ownership and authoring rules.

---

## File Location

```
src/ottools/<name>.py
src/otdev/tools/<name>.py
src/otutil/tools/<name>.py
```

One file per pack. The filename usually matches the pack name; when it does not, the module still declares the exported namespace with `pack = "<name>"`.

---

## File Structure

Each tool file follows this structure:

```python
"""Tool module docstring.

Brief description of what the tool does.
Requirements (e.g., "Requires MY_API_KEY in secrets.yaml").
"""

from __future__ import annotations

# Pack declaration MUST be before other imports
pack = "mytools"

# Export only these functions as tools
__all__ = ["search", "fetch", "batch"]

from typing import Any, Literal

from ot.config.secrets import get_secret
from ot.logging import LogSpan
```

---

## Minimal Tool Example

```python
"""Short description of what this pack does."""

from __future__ import annotations

pack = "mytool"
__all__ = ["search", "list_items"]


def search(*, query: str, count: int = 10) -> dict[str, list[dict[str, str]]]:
    """Search for items.

    Args:
        query: The search query.
        count: Number of results (1-100).

    Returns:
        Dict with results key containing list of result dicts.
    """
    return {"results": []}


def list_items(*, category: str = "all") -> list[str]:
    """List available items.

    Args:
        category: Filter by category.

    Returns:
        List of item names.
    """
    return []
```

Usage: `mytool.search(query="test")`, `mytool.list_items(category="web")`

---

## Required Elements

| Element | Purpose |
|---------|---------|
| `pack = "name"` | Dot-notation namespace (must be before imports) |
| `__all__ = [...]` | Public functions for registry |
| Type hints on all functions | mypy strict mode |
| Google-style docstrings | Registry extracts for introspection |
| Keyword-only args (`*,`) | All tool functions use keyword args |

---

## Pack Declaration

The `pack` variable enables dot notation:

```python
pack = "brave"  # Exposes brave.search(), brave.news()
pack = "webfetch"    # Exposes webfetch.fetch(), webfetch.fetch_batch()
```

**Important**: The pack declaration must appear before other imports (except `from __future__`).

---

## Export Control

Use `__all__` to declare which functions are exposed as tools:

```python
__all__ = ["search", "fetch", "batch"]  # Only these become tools
```

Without `__all__`, imported functions would be incorrectly exposed as tools.

---

## Function Signatures

All tool functions MUST use keyword-only arguments:

```python
# CORRECT
def search(
    *,
    query: str,
    count: int = 10,
) -> str:
    """Search for items."""
    ...

# WRONG - will cause runtime errors
def search(query: str, count: int = 10) -> str:
    ...
```

---

## Sync Public API, Async Internals

Tool functions exposed through `__all__` should be ordinary synchronous functions. OneTool invokes pack tools from an async MCP runner, and exposing `async def` tools or returning coroutine objects creates unclear serialization and lifecycle behavior.

It is fine for the implementation behind a sync tool to use concurrency:

- Use `ThreadPoolExecutor` for parallel blocking I/O or CPU-adjacent work.
- Use a bounded worker thread for libraries that require their own event loop.
- Keep background work observable with status, stats, or a flush/wait command when users need completion guarantees.
- Bound concurrency and queue sizes; surface dropped, failed, pending, and timed-out work in tool output or stats.
- Treat internal concurrency as an implementation detail unless it changes the user-facing contract.
- Keep batch docs aligned with behavior: blocking batch functions should not claim task polling, and task IDs should only be returned for work that continues after the function returns.

Avoid calling `asyncio.run(...)` directly inside a public sync tool. When the tool is called through MCP, the caller may already be inside OneTool's event loop, which can raise `asyncio.run() cannot be called from a running event loop`. If an async library is required, run the async coroutine in a dedicated worker thread or provide a small bridge helper that is safe both with and without an already-running event loop.

---

## Docstring Format

All public tool functions MUST include complete docstrings:

```python
def search(
    *,
    query: str,
    count: int = 10,
) -> str:
    """Search for items.

    Args:
        query: The search query string
        count: Number of results (1-20, default: 10)

    Returns:
        Formatted search results

    Example:
        mytools.search(query="python async", count=5)
    """
```

---

## Logging with LogSpan

All public tool functions must use LogSpan:

```python
from ot.logging import LogSpan

def search(*, query: str) -> list[dict]:
    """Search for items."""
    with LogSpan(span="mytools.search", query=query) as s:
        results = do_search(query)
        s.add("resultCount", len(results))
        return results  # Return native type directly
```

See [Logging](../../practices/logging.md) for detailed LogSpan patterns.

---

## Error Handling

Return error messages as strings, don't raise exceptions:

```python
def search(*, query: str) -> str:
    with LogSpan(span="mytools.search", query=query) as s:
        api_key = get_secret("MY_API_KEY")
        if not api_key:
            s.add("error", "no_api_key")
            return "Error: MY_API_KEY not configured"

        try:
            result = call_api(query)
            return result
        except APIError as e:
            s.add("error", str(e))
            return f"API error: {e}"
```

---

## Return Types

Tools return native Python types (`str`, `dict`, `list`). The framework handles
serialisation to JSON/YAML/raw based on the caller's `__format__` setting.

**Never call `json.dumps()` in a tool function.** The executor's
`serialize_result()` does this. Calling it yourself bypasses `--format` (the
output is already a string, so format modes like `yml_h` or `json_h` have no
effect), and produces misleading `-> str` annotations for what is actually
structured data.

```python
# WRONG — bypasses --format, lying return type
def tables(*, db_url: str) -> str:
    rows = _fetch(db_url)
    return json.dumps(rows)

# CORRECT — executor serializes; --format works
def tables(*, db_url: str) -> list[str]:
    return _fetch(db_url)
```

The same rule applies to error returns: always return a plain `str`, never
`json.dumps({"error": "..."})`.

```python
# WRONG
return json.dumps({"error": str(e)})

# CORRECT
return f"Error: {e}"
```

---

## Dependencies

### External Dependencies

Declare external dependencies with install hints:

```python
__ot_requires__ = {
    "cli": [("rg", "brew install ripgrep")],         # External binaries
    "lib": [("openpyxl", "pip install openpyxl")],    # Python packages
    "secrets": [("BRAVE_API_KEY", "Get from brave.com")],  # API keys
}
```

### Accessing Secrets

Access secrets at runtime:

```python
from ot.config import get_secret

api_key = get_secret("BRAVE_API_KEY")
if not api_key:
    raise ValueError("BRAVE_API_KEY not configured")
```

### Lazy Imports for Optional Dependencies

Tools with optional dependencies must use lazy imports inside functions:

**Wrong** - fails at module load:

```python
import sqlalchemy  # BREAKS tool loading if sqlalchemy not installed

def query(*, sql: str) -> str:
    engine = sqlalchemy.create_engine("sqlite:///:memory:")
    ...
```

**Correct** - lazy import inside function:

```python
def query(*, sql: str) -> str:
    """Query using SQLAlchemy."""
    try:
        import sqlalchemy
    except ImportError as e:
        raise ImportError(
            "sqlalchemy is required for query. Install with: pip install sqlalchemy"
        ) from e

    engine = sqlalchemy.create_engine("sqlite:///:memory:")
    ...
```

For type hints, use `TYPE_CHECKING`:

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from openai import OpenAI

def _get_client() -> "OpenAI":
    """Get OpenAI client with lazy import."""
    try:
        from openai import OpenAI
    except ImportError as e:
        raise ImportError(
            "openai is required. Install with: pip install openai"
        ) from e
    return OpenAI(api_key=get_secret("OPENAI_API_KEY"))
```

---

## Shared Utilities — Check Before You Implement

Before writing any of the following, check whether a shared utility already
exists in `ot.utils` or `ot.meta`. Reimplementing these is a common source of
bugs and drift.

### HTTP clients

Use the shared client — don't create your own `httpx.Client`:

```python
from ot.utils.factory import lazy_client
from ot.http_client import _format_http_error

_client = lazy_client(lambda: httpx.Client(timeout=30.0))

def _make_request(url: str, **kwargs) -> tuple[bool, dict | str]:
    try:
        r = _client().get(url, **kwargs)
        r.raise_for_status()
        return True, r.json()
    except Exception as e:
        return False, _format_http_error(e)
```

- `lazy_client()` — thread-safe lazy init with `.reset()` support (`ot.utils.factory`)
- `_format_http_error()` — standard HTTP error message formatting (`ot.http_client`)
- `_get_shared_client()` — project-wide singleton for generic HTTP (`ot.http_client`)

**Do not use** `@functools.lru_cache` or bare module globals for HTTP clients.

### Caching

For **function memoization**, use `@cache.memoize()` on the shared singleton:

```python
from ot.utils.cache import cache

@cache.memoize(ttl=3600)
def _resolve_something(key: str) -> str:
    ...
```

For **manual key/value stores** (e.g. raw HTTP responses, session data), use a
per-module `Cache()` instance:

```python
from ot.utils.cache import Cache

_cache = Cache()
_cache.set("key", value)
val = _cache.get("key")  # None if missing or expired
```

### Result truncation

```python
from ot.utils.truncate import truncate

description = truncate(raw_description, max_length=200)
```

Don't write `text[:N-3] + "..."` — use `truncate()`.

### Storage paths

For any path under `.onetool/`, use:

```python
from ot.meta import resolve_ot_path  # resolve .onetool/<subdir>
```

Call `.mkdir(parents=True, exist_ok=True)` yourself if you need a directory.

### Batch operations

```python
from ot.utils.batch import batch_execute, normalize_items, format_batch_results
```

Used by brave, tavily, ground, file — use the same pattern for consistency.

### What NOT to reimplement

| Pattern | Use instead |
|---|---|
| `[:N] + "..."` truncation | `ot.utils.truncate.truncate()` |
| Manual HTTP client init | `ot.utils.factory.lazy_client()` |
| `hasattr(e, "response")` error check | `ot.http_client._format_http_error()` |
| `@lru_cache` on a client factory | `lazy_client()` (supports `.reset()`) |
| `resolve_ot_path(x); x.mkdir(...)` | Same — just always pair them |
| Duration strings (`"30m"`, `"2h"`) | `ot.utils.duration.parse_duration()` (if available) |
| `len(text.split())` as token count | `tiktoken` — see Token counting above |
| New `OpenAI()` per call | `_client_cache` dict — see OpenAI-compatible client cache above |
| `except Exception: pass` in `_get_config` | `except Exception as e: logger.warning(...)` |

---

## Path Handling

| Function | Import From | Resolves Relative To |
|----------|-------------|----------------------|
| `resolve_cwd_path()` | `otpack` | Project directory (`OT_CWD`) |
| `resolve_ot_path()` | `ot.meta` | Config directory (`.onetool/`) |
| `get_effective_cwd()` | `otpack` | Returns project directory |
| `expand_path()` | `otpack` | Only expands `~` |

For tools in `src/ottools/`, import path helpers from `otpack` (not `ot.paths` directly):

```python
from otpack import LogSpan, get_secret, get_tool_config, resolve_cwd_path

def read_file(*, path: str) -> str:
    resolved = resolve_cwd_path(path)
    return resolved.read_text()
```

**Never use** `Path.expanduser()` or bare `expand_path()` for project-relative paths. Use `resolve_cwd_path()` for user-supplied paths, `resolve_ot_path()` or `get_ot_data_dir()` for `.onetool/` data, `get_ot_runtime_dir()` for runtime files, and `get_project_state_dir()` for pack state. Use relative defaults (e.g., `data/mem/default.db` not `~/.onetool/mem.db`).

---

## Configuration Access

Tools can define a `Config` class that is automatically discovered:

```python
from pydantic import BaseModel, Field
from ot.config import get_tool_config

class Config(BaseModel):
    timeout: float = Field(default=30.0, ge=1.0, le=120.0)

def search(*, query: str, timeout: float | None = None) -> str:
    if timeout is None:
        config = get_tool_config("mytool", Config)
        timeout = config.timeout
    # ...
```

See [Tool Configuration](tool-configuration.md) for detailed configuration patterns.

### LLM config fallback pattern

For tools that call an LLM, support pack-level override with fallback to the top-level
`llm.*` config. Follow the `ot_image` pattern exactly:

```python
from loguru import logger
from otpack import get_secret, get_tool_config
from pydantic import BaseModel, Field

class Config(BaseModel):
    model: str = Field(default="", description="Model (empty = inherit from llm.model)")
    base_url: str = Field(default="", description="API base URL (empty = inherit from llm.base_url)")
    timeout: int = Field(default=30)

def _get_config() -> Config:
    from ot.config import get_llm_config
    config = get_tool_config("mytool", Config)
    try:
        llm = get_llm_config()
        updates: dict[str, str] = {}
        if not config.base_url and llm.base_url:
            updates["base_url"] = llm.base_url
        if not config.model and llm.model:
            updates["model"] = llm.model
        if updates:
            config = config.model_copy(update=updates)
    except Exception as e:
        logger.warning("Failed to load top-level llm config for mytool fallbacks: {}", e)
    return config
```

Do not use silent `except Exception: pass` — always log a warning so misconfiguration is visible.

### OpenAI-compatible client cache

Cache clients by `(api_key, base_url, timeout)` to avoid a new connection pool per call:

```python
from openai import OpenAI

_client_cache: dict[tuple[str, str, int], OpenAI] = {}

def _get_client(config: Config) -> tuple[OpenAI, str] | tuple[None, str]:
    """Return (client, model) or (None, error_string)."""
    api_key = get_secret("OPENAI_API_KEY") or get_secret("OT_LLM_API_KEY")
    if not api_key:
        return None, "Error: mytool not configured. Set OPENAI_API_KEY in secrets.yaml."
    if not config.base_url:
        return None, "Error: mytool not configured. Set llm.base_url in onetool.yaml."
    if not config.model:
        return None, "Error: mytool not configured. Set llm.model in onetool.yaml."
    cache_key = (api_key, config.base_url, config.timeout)
    if cache_key not in _client_cache:
        _client_cache[cache_key] = OpenAI(
            api_key=api_key, base_url=config.base_url, timeout=config.timeout
        )
    return _client_cache[cache_key], config.model
```

Return three separate error strings — one for each missing field — with an actionable fix in each.
Do **not** use `@functools.lru_cache` or `lazy_client()` for OpenAI clients.

### Token counting

Use tiktoken. Declare it as a hard dependency in `__ot_requires__` (no word-count fallback):

```python
__ot_requires__ = {"lib": [("tiktoken", "pip install tiktoken")]}

def _count_tokens(text: str) -> int:
    import tiktoken
    try:
        enc = tiktoken.encoding_for_model("gpt-4")
    except KeyError:
        enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(text))
```

Do **not** use `len(text.split())` as a token count — it undercounts by 20–30% and misleads users.

---

## Testing Your Tool

Test file paths depend on which source package the tool lives in:

| Tool location | Unit tests | Integration tests |
|---|---|---|
| `src/ottools/<name>.py` | `tests/ottools/unit/tools/test_<name>.py` | `tests/integration/tools/test_<name>.py` |
| `src/otutil/tools/<name>.py` | `tests/otutil/unit/tools/test_<name>.py` | `tests/integration/tools/test_<name>.py` |
| `src/otdev/tools/<name>.py` | `tests/otdev/unit/tools/test_<name>.py` | `tests/otdev/integration/tools/test_<name>.py` |

```python
# tests/ottools/unit/tools/test_mytool.py
import pytest

@pytest.mark.unit
@pytest.mark.tools
class TestMyTool:
    def test_empty_query_returns_empty(self):
        from ottools.mytool import search
        result = search(query="")
        assert result == {"results": []}
```

See [Testing](../../practices/testing.md) for markers, fixtures, and patterns.

---

## Large Packs: Multi-File Layout

When a pack grows beyond ~500 lines, split it into a private package using the
`convert.py` / `_convert/` convention. The tool loader discovers only `*.py`
files in the tools directory; private packages (underscore prefix) are
implementation detail.

### Layout

```
src/otutil/tools/
├── mem.py          ← discovered by tool loader (pack = "mem", __all__, __ot_requires__)
└── _mem/           ← private implementation package (not discovered directly)
    ├── __init__.py ← re-exports everything; also used for direct imports in tests
    ├── config.py
    ├── db.py
    ├── write.py
    └── ...
```

### Facade file (`mem.py`)

```python
"""Tool description."""
from __future__ import annotations

pack = "mem"

# Only public functions go here – these become MCP tools.
__all__ = ["write", "read", "search", ...]

__ot_requires__ = {"lib": [("openai", "pip install openai")]}

# Import public API (and any private symbols needed by tests / type checkers)
from otutil.tools._mem import (
    write, read, search, ...,  # public
    _close_connection, Config, ...,  # private – available but not in __all__
)
```

### Private package (`_mem/__init__.py`)

Keeps `pack`, `__all__` (full list including privates), and imports from
submodules. This is what tests import when they need internal symbols:

```python
from otutil.tools._mem import Config, _close_connection
```

### Key rules

- Facade `__all__` lists **only public tool functions** — private symbols are
  importable but not exposed as MCP tools.
- Internal submodules use relative imports (`from .config import Config`).
- Tests that patch submodule internals use the `_mem` path:
  `@patch("otutil.tools._mem.write._get_connection")`.
- The underscore prefix (`_mem/`) is what prevents the loader from treating
  the package as a second pack registration.

---

## Checklist

- [ ] Checked `ot.utils` for existing shared utilities before implementing HTTP clients, caching, truncation, batch ops, or path helpers
- [ ] File at `src/ottools/<name>.py`
- [ ] Module docstring with description
- [ ] `pack = "..."` before imports
- [ ] `__all__ = [...]` listing exports
- [ ] `__ot_requires__` declared if external dependencies needed
- [ ] All functions use keyword-only args (`*,`)
- [ ] Type hints on all functions
- [ ] Complete Google-style docstrings (Args, Returns, Example)
- [ ] `LogSpan` for operations with external calls
- [ ] Error handling returning strings (not raising exceptions)
- [ ] No `json.dumps()` calls in tool functions — return native types (`dict`, `list`, `str`)
- [ ] Lazy imports for optional dependencies
- [ ] Secrets accessed via `get_secret()` from `otpack`
- [ ] Path resolution using `resolve_cwd_path()` (from `otpack`) or `resolve_ot_path()` (from `ot.meta`)
- [ ] `Config` class if tool has settings
- [ ] If calling an LLM: `_get_config()` with `llm.*` fallback + `logger.warning` on exception (not `pass`)
- [ ] If calling an LLM: `_client_cache` dict for OpenAI client — not `@lru_cache` or new client per call
- [ ] If counting tokens: use `tiktoken`, declare as hard dep in `__ot_requires__`
- [ ] Unit tests with `@pytest.mark.unit` + `@pytest.mark.tools`
- [ ] Integration tests if external APIs involved
- [ ] Spec at `openspec/specs/tool-<name>/spec.md` (for non-trivial tools)
- [ ] Reference doc at `docs/reference/tools/<pack>.md` (see [Tool Reference Docs](tool-reference-docs.md))
- [ ] Attribution level determined (see [Attribution](attribution.md))
- [ ] Update `src/ot/config/global_templates/agent-hints.md` if adding user-facing tools
- [ ] `just check` passes

---

**Related:**
- [Tool Configuration](tool-configuration.md) - Adding config to tools
- [Logging](../../practices/logging.md) - LogSpan patterns
- [Testing](../../practices/testing.md) - Test markers and fixtures
- [Attribution](attribution.md) - License handling for derived tools
