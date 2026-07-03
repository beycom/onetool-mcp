# Core Concepts

## Packs

A **pack** is a namespace grouping related tool functions. Each tool file declares a `pack` variable and exports public functions:

```python
# src/otutil/tools/brave.py
pack = "brave"
__all__ = ["search", "news", "image", "video", "search_batch"]

def search(*, query: str, count: int = 10) -> dict: ...
def news(*, query: str, count: int = 10) -> dict: ...
```

Usage: `brave.search(query="test")`, `brave.news(query="AI")`

At runtime, packs become `PackProxy` objects in the execution namespace. Attribute access (`brave.search`) resolves to the actual function, wrapped with stats tracking.

## Aliases

Short names for frequently-used functions, defined in config:

```yaml
alias:
  ws: brave.search
  fr: file.read
```

Usage: `ws(query="test")` expands to `brave.search(query="test")`

Resolved via regex before execution. Sorted longest-first to avoid partial matches.

## Snippets

Jinja2 templates for multi-step operations, defined in config:

```yaml
snippets:
  compare:
    params:
      q1: { required: true }
      q2: { required: true }
    body: |
      r1 = brave.search(query="{{ q1 }}")
      r2 = brave.search(query="{{ q2 }}")
      {"q1": r1, "q2": r2}
```

Usage: `__onetool :compare q1=AI q2=ML`

Snippets support single-line (`:name k=v`) and multi-line (`:name\nk: v`) syntax. Snippet values are plain strings; Python syntax applies only after the template expands.

## Execution Namespace

The namespace passed to `exec()` contains only:

| Key | Type | Purpose |
|-----|------|---------|
| `brave`, `file`, ... | `PackProxy` | Tool pack dot-notation access |
| `github`, ... | `McpProxyPack` | External MCP server proxy |
| `db`, ... | `WorkerPackProxy` | Subprocess-isolated tools |
| `__format__` | magic var | Output format control |
| `__sanitize__` | magic var | Output sanitisation toggle |
| `str`, `int`, `len`, ... | builtins | Allowlisted safe builtins |

Nothing else is in scope - no `__import__`, no `exec`, no filesystem access except through tool packs.

## Output Formatting

| Mode | Output |
|------|--------|
| `json` (default) | Compact JSON |
| `json_h` | Pretty-printed JSON |
| `yml` | YAML flow style |
| `yml_h` | YAML block style |
| `raw` | Plain `str()` |

Set per-call: `__format__ = "yml_h"; brave.search(query="test")`
