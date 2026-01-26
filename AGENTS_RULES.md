# Rules

**IMPORTANT:** All code changes must update: code, tests, readme, docs and specs.

## Paths

- `/docs` - user docs
- `/openspec/specs` - feature specs
- `/openspec/changes` - pending proposals
- `/openspec/archive` - completed proposals

## Beta (Exclude)

- `ot-browse` CLI and `page` pack are beta - do not reference in docs or stats

## Spec Naming

| Pattern | Example | Description |
|---------|---------|-------------|
| `{cli}` | `bench`, `browse` | Main spec for a CLI (`ot-{cli}`) |
| `{cli}-{feature}` | `bench-config` | CLI feature spec |
| `serve-{feature}` | `serve-configuration` | MCP server feature spec |
| `tool-{name}` | `tool-brave-search` | Built-in tool spec |
| `_nf-{name}` | `_nf-observability` | Non-functional / cross-cutting spec |

## Models

- Bench default: `openai/gpt-5-mini`
- YAML bench: use `google/gemini-3-flash-preview` in `defaults.model`

## Style

- Australian English (colour, behaviour) except code identifiers (color, initialize)
- No em-dashes, use hyphens
- No backward compat - delete unused code completely

## CLI

- Use Rich with `highlight=False` for all CLIs (disables auto syntax highlighting)

## Python

- `__init__.py` required in `src/` packages
- `__init__.py` required in `tests/` subdirs (empty, avoids name collisions)

## Testing

Always use `uv run pytest` for proper dependency resolution (never bare `pytest` or `python -m pytest`).
Shortcut: `just test` runs the full suite.
Markers required: speed (`smoke`|`unit`|`integration`|`slow`) + component (`core`|`bench`|`serve`)
Principles: lean tests, DRY fixtures in `conftest.py`, test behaviour not implementation

## Logging

```python
with LogSpan(span="component.operation", key="value") as s:
    s.add("resultCount", len(result))
```

Span naming: `{component}.{operation}` (e.g., `brave.search.web`)
