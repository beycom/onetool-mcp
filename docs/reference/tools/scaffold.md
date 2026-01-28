# Scaffold

**Create extensions. List templates. Manage your tools.**

Generate new extension tools from templates with a single command. Project or global scope.

## Highlights

- Multiple templates: simple, API-integrated, worker-based
- Project or global scope for extensions
- List existing extensions across scopes
- PEP 723 metadata support for dependencies

## Functions

| Function | Description |
|----------|-------------|
| `scaffold.create(name, ...)` | Create a new extension tool from a template |
| `scaffold.templates()` | List available extension templates |
| `scaffold.list_extensions()` | List installed extensions by scope |

## Key Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `name` | str | Extension name (used as directory and file name) |
| `template` | str | Template name (default: `extension_simple`) |
| `pack_name` | str | Pack name for dot notation (default: same as name) |
| `function` | str | Main function name (default: `run`) |
| `description` | str | Module description |
| `scope` | str | Where to create: `project` (default) or `global` |

## Requires

No API key required.

## Examples

```python
# List available templates
scaffold.templates()

# Create a simple extension in project scope
scaffold.create(name="my_tool", function="search")

# Create an API-integrated extension
scaffold.create(name="api_tool", template="extension", api_key="MY_API_KEY")

# Create in global scope (available to all projects)
scaffold.create(name="shared_tool", scope="global")

# List all installed extensions
scaffold.list_extensions()
```

## See Also

[Creating Tools Guide](../../extending/creating-tools.md) - Full guide on building custom extensions
