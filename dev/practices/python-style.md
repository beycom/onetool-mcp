# Python Style

Reusable Python style defaults for this repository family. Treat package names, language preferences, and command links as the local project profile; the type-hinting, docstring, formatting, and deletion rules are intended to transfer across Python projects.

## Language & Version

- Python 3.12+ required
- Use `from __future__ import annotations` in all modules
- Australian English in comments/docs (colour, behaviour, initialise)
- American English in code identifiers (color, initialize)
- No em-dashes - use hyphens instead

## Type Hints

Strict mode is enabled (`mypy --strict`). All functions must have type annotations:

```python
def search(*, query: str, count: int = 10) -> dict[str, list[dict[str, str]]]:
    ...
```

## Docstrings

Google-style format:

```python
def search(*, query: str, count: int = 10) -> dict:
    """Search the web using Brave Search.

    Args:
        query: The search query string.
        count: Number of results to return (1-100).

    Returns:
        Dict with "web" key containing list of result dicts.

    Raises:
        ValueError: If BRAVE_API_KEY is not configured.
    """
```

## Formatting & Linting

- **Formatter**: Ruff (line length 88)
- **Linter**: Ruff (rules: E, W, F, I, B, C4, UP, ARG, SIM, TCH, PTH, RUF)
- **Type checker**: mypy (strict mode)

See the project command reference for how to run these in this repository: [OneTool Dev Commands](../project/guides/dev-commands.md).

## Package Structure

- `__init__.py` required in all `src/` packages
- `__init__.py` required in all `tests/` subdirs (empty, avoids name collisions)
- First-party packages: `ot`, `ottools`, `onetool`, `otdev`, `otutil`, `otpack`

## CLI Code

Use Rich with `highlight=False` for all CLI output.

## Deletion Policy

No backward compatibility hacks. Delete unused code completely - no `_deprecated_` prefixes, no re-exports, no `# removed` comments.
