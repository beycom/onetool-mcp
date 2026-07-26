# OT Forge

Create and validate extension tools.

Short alias: `forge`

## Highlights

- Single in-process extension template with full `ot.*` access
- Validation before reload catches errors early
- Best practices checking and warnings

## Functions

| Function | Description |
|----------|-------------|
| `ot_forge.create_ext(name, ...)` | Create a new in-process extension tool |
| `ot_forge.validate_ext(path)` | Validate an extension before reload |

## Key Parameters

### create_ext

| Parameter | Type | Description |
|-----------|------|-------------|
| `name` | str | Extension name (used in scaffold file path) |
| `pack_name` | str | Pack name for dot notation (default: same as name) |
| `function` | str | Main function name (default: `run`) |
| `description` | str | Module description |
| `function_description` | str | Function docstring description |
| `api_key` | str | API key secret name for optional config (default: `MY_API_KEY`) |

### validate_ext

| Parameter | Type | Description |
|-----------|------|-------------|
| `path` | str | Full path to the extension file |

<!-- BEGIN GENERATED:PACK_REQUIREMENTS -->
## Runtime requirements

Pack distribution: OneTool `core`.

No additional runtime requirements are declared.
<!-- END GENERATED:PACK_REQUIREMENTS -->

## Workflow

The recommended workflow for creating and activating extensions:

```text
ot_forge.create_ext(name) → (edit) → ot_forge.validate_ext(path) → ot.reload() → use
```

## Configuration

### Required

- No required `tools.ot_forge` settings.

### Optional

- This pack does not define any pack-specific keys under `tools.ot_forge`.

### Defaults

- OneTool uses the built-in defaults for Forge.
- `create_ext` chooses a scaffold path compatible with active `tools_dir` globs (for example `tools/*.py` -> `.onetool/tools/<name>.py`).

## Examples

```python
# Create a new extension
ot_forge.create_ext(name="my_tool", function="search")

# Validate before reload
ot_forge.validate_ext(path=".onetool/tools/my_tool.py")
```
