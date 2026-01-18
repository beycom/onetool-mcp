# Rules

## Paths

- `/docs` - user docs
- `/openspec/specs` - feature specs
- `/openspec/changes` - pending proposals
- `/openspec/archive` - completed proposals

## Models

- Bench default: `openai/gpt-5-mini`
- YAML bench: use `google/gemini-3-flash-preview` in `defaults.model`

## Style

- Australian English (colour, behaviour) except code identifiers (color, initialize)
- No em-dashes, use hyphens
- No backward compat - delete unused code completely

## Python

- `__init__.py` required in `src/` packages
- `__init__.py` required in `tests/` subdirs (empty, avoids name collisions)

## Testing

Markers required: speed (`smoke`|`unit`|`integration`|`slow`) + component (`core`|`bench`|`serve`)
Principles: lean tests, DRY fixtures in `conftest.py`, test behaviour not implementation

## Logging

```python
with LogSpan(span="component.operation", key="value") as s:
    s.add("resultCount", len(result))
```

Span naming: `{component}.{operation}` (e.g., `brave.search.web`)
