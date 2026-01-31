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
```

## Source

[ripgrep](https://github.com/BurntSushi/ripgrep)

## Inspired by

[mcp-ripgrep](https://github.com/mcollina/mcp-ripgrep) by Matteo Collina (MIT)
