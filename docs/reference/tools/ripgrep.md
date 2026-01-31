# Ripgrep

**Blazing fast file search. Regex or literal. Any codebase.**

Fast text and regex search in files using ripgrep.

## Highlights

- Search, count, and list files with regex or literal patterns
- Filter by file type or glob pattern
- Context lines around matches
- Path resolution relative to effective cwd

## Functions

| Function | Description |
|----------|-------------|
| `ripgrep.search(pattern, path, ...)` | Search files for patterns |
| `ripgrep.count(pattern, path, ...)` | Count pattern occurrences |
| `ripgrep.files(path, ...)` | List files that would be searched |
| `ripgrep.types()` | List supported file types |

## Key Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `pattern` | str | Regex or literal pattern to search for |
| `path` | str | Directory or file to search (default: current directory) |
| `case_sensitive` | bool | Match case-sensitively (default: True) |
| `fixed_strings` | bool | Treat pattern as literal, not regex |
| `file_type` | str | Filter by type (e.g., "py", "js", "ts") |
| `glob` | str | Filter by glob pattern (e.g., "*.md") |
| `context` | int | Lines of context around matches |
| `max_results` | int | Limit number of matching lines |
| `word_match` | bool | Match whole words only (default: False) |
| `include_hidden` | bool | Search hidden files and directories (default: False) |

## Configuration

```yaml
tools:
  ripgrep:
    timeout: 60.0           # Command timeout in seconds
    relative_paths: true    # Output relative paths (default)
```

## Requires

- `rg` binary (install with: `brew install ripgrep`)

## Glob Patterns

The `glob` parameter supports full path patterns via ripgrep's `--glob` flag:

| Pattern | Description |
|---------|-------------|
| `*.py` | Python files in search path |
| `**/*.py` | Python files recursively |
| `src/**/*.py` | Python files under src/ |
| `**/test_*.py` | Test files recursively |
| `**/*.{ts,tsx}` | TypeScript files (brace expansion) |
| `!**/__pycache__/**` | Exclude pycache |

### Comparison with Claude Glob Tool

| Feature | Claude Glob | OneTool ripgrep.files |
|---------|-------------|----------------------|
| Pattern `src/**/*.py` | `Glob(pattern="src/**/*.py")` | `ripgrep.files(glob="src/**/*.py")` |
| Brace expansion | `**/*.{ts,tsx}` | `**/*.{ts,tsx}` |
| Type shortcut | N/A | `file_type="py"` |
| Hidden files | N/A | `include_hidden=True` |
| Returns | Absolute paths | Relative paths |

## Examples

```python
# Basic search
ripgrep.search(pattern="TODO", path="src/")

# Case insensitive in Python files
ripgrep.search(pattern="error", case_sensitive=False, file_type="py")

# Count occurrences
ripgrep.count(pattern="import", path=".", file_type="py")

# List files
ripgrep.files(path="src/", file_type="py")

# List supported file types
ripgrep.types()

# Full path glob patterns
ripgrep.files(glob="src/**/*.py")
ripgrep.files(glob="tests/**/test_*.py")
ripgrep.search(pattern="TODO", glob="**/*.{js,ts}")
ripgrep.count(pattern="import", glob="src/**/*.py")
```

## Source

[ripgrep](https://github.com/BurntSushi/ripgrep)

## Inspired by

[mcp-ripgrep](https://github.com/mcollina/mcp-ripgrep) by Matteo Collina (MIT)
