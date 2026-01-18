# Ripgrep

**Blazing fast file search. Regex or literal. Any codebase.**

Fast text and regex search in files using ripgrep. Requires the `rg` binary (install with: `brew install ripgrep`).

| Function | Description |
|----------|-------------|
| `ripgrep.search(pattern, path, ...)` | Search files for patterns |
| `ripgrep.count(pattern, path, ...)` | Count pattern occurrences |
| `ripgrep.files(path, ...)` | List files that would be searched |
| `ripgrep.types()` | List supported file types |

**Key Parameters:**
- `pattern`: Regex or literal pattern to search for
- `path`: Directory or file to search (default: current directory)
- `case_sensitive`: Match case-sensitively (default: True)
- `fixed_strings`: Treat pattern as literal, not regex
- `file_type`: Filter by type (e.g., "py", "js", "ts")
- `glob`: Filter by glob pattern (e.g., "*.md")
- `context`: Lines of context around matches
- `max_results`: Limit number of matching lines

**Example:**

```python
# Basic search
ripgrep.search(pattern="TODO", path="src/")

# Case insensitive in Python files
ripgrep.search(pattern="error", case_sensitive=False, file_type="py")

# Count occurrences
ripgrep.count(pattern="import", path=".", file_type="py")

# List files
ripgrep.files(path="src/", file_type="py")
```

**Inspired by:** [mcp-ripgrep](https://github.com/mcollina/mcp-ripgrep) by Matteo Collina

**Comparison:** Original implementation inspired by mcp-ripgrep. Provides search, count, files, and types functions with path resolution relative to effective cwd.

**License:** MIT
