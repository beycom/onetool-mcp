# Scaffold

**Create extensions. Validate before reload. Manage your tools.**

Generate new extension tools from templates with a single command. Project or global scope.

## Highlights

- Single unified template with optional sections
- Validation before reload catches errors early
- Project or global scope for extensions
- Best practices checking and warnings
- PEP 723 metadata support for dependencies

## Functions

| Function | Description |
|----------|-------------|
| `scaffold.create(name, ...)` | Create a new extension tool from a template |
| `scaffold.validate(path)` | Validate an extension before reload |
| `scaffold.extensions()` | List loaded extension files |
| `scaffold.templates()` | List available extension templates |

## Key Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `name` | str | Extension name (used as directory and file name) |
| `template` | str | Template name (default: `extension`) |
| `pack_name` | str | Pack name for dot notation (default: same as name) |
| `function` | str | Main function name (default: `run`) |
| `description` | str | Module description |
| `scope` | str | Where to create: `project` (default) or `global` |
| `path` | str | Full path to extension file (for validate) |

## Requires

No API key required.

## Workflow

The recommended workflow for creating and activating extensions:

```text
scaffold.create(name) → (edit) → scaffold.validate(path) → ot.reload() → use
```

## Examples

```python
# List available templates
scaffold.templates()

# Create an extension in project scope
scaffold.create(name="my_tool", function="search")

# Validate before reload
scaffold.validate(path=".onetool/tools/my_tool/my_tool.py")

# Create in global scope (available to all projects)
scaffold.create(name="shared_tool", scope="global")

# List loaded extensions
scaffold.extensions()
```
