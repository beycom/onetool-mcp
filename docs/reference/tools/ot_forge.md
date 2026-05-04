# OT Forge

Create, validate, and install extension tools and skill stubs.

Short alias: `forge`

## Highlights

- Single in-process extension template with full `ot.*` access
- Validation before reload catches errors early
- Best practices checking and warnings
- Skill stub installation for Claude, Codex, and OpenCode

## Functions

| Function | Description |
|----------|-------------|
| `ot_forge.create_ext(name, ...)` | Create a new in-process extension tool |
| `ot_forge.validate_ext(path)` | Validate an extension before reload |
| `ot_forge.install_skills(install, ...)` | Install a skill stub for an AI tool |

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

### install_skills

| Parameter | Type | Description |
|-----------|------|-------------|
| `install` | str | Skill name to install, or `"all"` for all skills (default: `"all"`) |
| `exclude` | list[str] | Skill names to skip when `install="all"` |
| `tool` | str | Target AI tool: `"claude"` (default), `"codex"`, `"opencode"`, `"pi"` |

## Requires

No API key required.

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

# List available skills (use ot.skills, not ot_forge)
ot.skills()

# Install a skill stub for Claude Code
ot_forge.install_skills(install="ot-ref")

# Install for a different AI tool
ot_forge.install_skills(install="ot-ref", tool="codex")

# Install all skills at once (default)
ot_forge.install_skills()

# Install all skills except specific ones
ot_forge.install_skills(exclude=["ot-ref"])
```
