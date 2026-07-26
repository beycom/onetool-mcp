# File

Secure file operations with configurable security boundaries. Read, write, edit, and manage files with path validation against allowed directories.

Short alias: `f`

## Highlights

- Configurable security boundaries with allowed directories
- Pure-Python content search (no `rg` binary required) with `.gitignore` support
- Section-aware navigation: TOC, slice, and batch slice for markdown files
- Batch reads and recursive directory operations with pattern filtering

## Read Operations

| Function | Description |
|----------|-------------|
| `file.read(path, offset, limit, encoding, line_numbers)` | Read file content (raw by default) |
| `file.read_batch(paths, glob, encoding, max_files)` | Read multiple files in a single call |
| `file.info(path, follow_symlinks)` | Get file or directory metadata |

## Search Operations

| Function | Description |
|----------|-------------|
| `file.resolve(path, glob, match, kind, gitignore, include_hidden, path_type, multi, max_results)` | Resolve exact/glob or fuzzy quick-open file or directory references to path strings |
| `file.grep(pattern, path, glob, context, case_sensitive, max_matches, fixed_strings, gitignore)` | Search file contents with regex (pure Python) |

## Section Navigation

| Function | Description |
|----------|-------------|
| `file.toc(path, encoding)` | Display numbered section index (table of contents) |
| `file.slice(path, select, encoding)` | Extract content by section number, heading, or line range |
| `file.slice_batch(items)` | Extract sections from multiple files in a single call |

## List Operations

| Function | Description |
|----------|-------------|
| `file.list(path, pattern, recursive, include_hidden, sort_by, reverse, follow_symlinks)` | List directory contents |
| `file.tree(path, max_depth, include_hidden)` | Display directory tree structure |
| `file.search(path, pattern, glob, file_pattern, case_sensitive, include_hidden, max_results)` | Search for files by name or glob pattern |

## Write Operations

| Function | Description |
|----------|-------------|
| `file.write(path, content, append, create_dirs, encoding, dry_run)` | Write content to file |
| `file.edit(path, old_text, new_text, occurrence, encoding, dry_run)` | Edit file by replacing text |

## File Management

| Function | Description |
|----------|-------------|
| `file.copy(source, dest, follow_symlinks)` | Copy file or directory |
| `file.move(source, dest)` | Move or rename file or directory |
| `file.delete(path, backup, recursive, dry_run)` | Delete file or directory |

## Key Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `path` | str | File or directory path (relative to cwd or absolute) |
| `pattern` | str | Filename pattern for filtering (e.g., `*.py`, `*test*`) |
| `glob` | str\|list[str] | Glob pattern to filter paths; `file.resolve` also accepts a list of glob selectors |
| `match` | str\|list[str] | Fuzzy quick-open query or queries for `file.resolve` |
| `kind` | str | Candidate kind for `file.resolve`: `file` or `dir` (default: `file`) |
| `path_type` | str | Path output for `file.resolve`: `relative` or `absolute` (default: `relative`) |
| `multi` | str | Match handling for `file.resolve`: `error`, `first`, or `all` (default: `all`) |
| `max_results` | int | Maximum results per `file.resolve` selector (default: `10`) |
| `offset` | int | Line number to start from (1-indexed, default: 1) |
| `limit` | int | Maximum lines to return |
| `line_numbers` | bool | Include line-number prefixes in `file.read` output (default: `False`) |
| `occurrence` | int | Which match to replace (1=first, 0=all) |
| `encoding` | str | Character encoding (default: utf-8) |
| `dry_run` | bool | Show what would happen without making changes |
| `recursive` | bool | Delete non-empty directories |
| `follow_symlinks` | bool | Follow symlinks or treat as links |
| `include_hidden` | bool | Include hidden files and path segments in `file.resolve` (default: `true`) and hidden files in listing/search helpers when supported |
| `context` | int | Context lines before/after each match in grep (default: 2) |
| `max_matches` | int | Max total grep matches before stopping (default: 500) |
| `fixed_strings` | bool | Treat grep pattern as a literal string, not regex |
| `gitignore` | bool | Honour `.gitignore` when searching — pass `False` to include all files (default: True) |
| `max_files` | int | Maximum files to read in read_batch (default: 20) |
| `select` | int\|str\|list | Slice selector: section number, heading substring, line range, or list |
| `items` | list[dict] | List of `{path, select}` dicts for slice_batch (max 20) |

<!-- BEGIN GENERATED:PACK_REQUIREMENTS -->
## Runtime requirements

Pack distribution: OneTool `[util]`.

| Kind | Requirement | Purpose | Availability |
|---|---|---|---|
| `lib` | `pathspec` (import `pathspec`, OneTool `[util]`) | Apply gitignore-style path exclusion rules | Required |
| `lib` | `Send2Trash` (import `send2trash`, OneTool `[util]`) | Perform recoverable file deletion | Required |

Use `ot.help(query='<pack>', topic='setup')` for current readiness and non-mutating setup guidance.
<!-- END GENERATED:PACK_REQUIREMENTS -->

## Configuration

### Required

- No required `tools.file` settings.

### Optional

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `tools.file.allowed_dirs` | string[] | `[]` | Allowed directories for file operations. Empty means current working directory only. |
| `tools.file.exclude_patterns` | string[] | `[".git", "node_modules", "__pycache__", ".venv", "venv"]` | Path patterns excluded from operations. |
| `tools.file.max_file_size` | int | `10000000` | Max readable/writable file size in bytes. Range: `1000-100000000`. |
| `tools.file.max_list_entries` | int | `1000` | Max entries returned by `list()` and `tree()`. Range: `10-10000`. |
| `tools.file.backup_on_write` | bool | `true` | Create `.bak` backup files before overwriting. |
| `tools.file.use_trash` | bool | `true` | Move deleted files to trash when supported. |
| `tools.file.relative_paths` | bool | `true` | Return relative paths instead of absolute paths. |

```yaml
tools:
  file:
    allowed_dirs: ["."]
    exclude_patterns: [".git"]
    max_file_size: 10000000
    max_list_entries: 1000
    backup_on_write: true
    use_trash: true
    relative_paths: true
```

### Defaults

- If `tools.file` is omitted, the file pack uses the built-in safety limits and path behavior shown above.

## Examples

### Reading Files

```python
# Read entire file (raw content)
file.read(path="src/main.py")

# Read with pagination (lines 100-150)
file.read(path="large_file.log", offset=100, limit=50)

# Read with line numbers (opt-in)
file.read(path="src/main.py", line_numbers=True)

# Get file metadata
file.info(path="config.yaml")
```

### Listing Directories

```python
# List current directory
file.list()

# List with pattern filter
file.list(path="src", pattern="*.py")

# Recursive listing sorted by size
file.list(path=".", recursive=True, sort_by="size", reverse=True)

# Display tree structure
file.tree(path="src", max_depth=2)

# Search for files by filename pattern
file.search(pattern="*test*", file_pattern="*.py")

# Search with full path glob (recursive)
file.search(glob="src/**/*.py")
file.search(glob="tests/**/test_*.py")
file.search(glob="**/*.{yaml,yml}")
```

### Reading Multiple Files

```python
# Read specific files
file.read_batch(paths=["src/a.py", "src/b.py"])

# Read by glob pattern
file.read_batch(glob="src/**/*.py", max_files=10)  # "*.py" also works
file.read_batch(glob="docs/*.md")  # recurses into docs/ subdirs
```

### Resolving File References

```python
# Resolve file paths from an exact path or glob
file.resolve(glob="src/otutil/tools/file.py")

# Resolve directory paths
file.resolve(glob="src/otutil/**", kind="dir")

# Fuzzy quick-open matching
file.resolve(match="tlf")       # e.g. tests/unit/core/test_log_format.py
file.resolve(match="wip 2026")  # space-separated quick-open query

# Scope a file reference lookup to a known directory
file.resolve(path="dev/practices", match="cli-pattern", multi="first")
file.resolve(path="dev/project/guides", glob="tool-*.md")

# Return absolute paths or include gitignored files
file.resolve(glob="wip/**/*.log", path_type="absolute", gitignore=False)

# Ask for one path or an ambiguity error
file.resolve(glob="src/**/*.py", multi="first")
file.resolve(glob="src/**/*.py", multi="error")
```

### Searching File Contents

```python
# Search for a regex pattern (glob always recurses — "*.py" == "**/*.py")
file.grep(pattern="LogSpan", path="src/", glob="*.py")

# One rg-style match per line with no context separators
file.grep(pattern="def ", path="src/", glob="*.py", context=0, max_matches=5000)

# Case-insensitive with context lines
file.grep(pattern="TODO", path=".", context=3, case_sensitive=False)

# Literal string (no regex)
file.grep(pattern="print(", path="src/", fixed_strings=True)

# Recursive with glob filter
file.grep(pattern="def \\w+\\(", path="src/", glob="**/*.py", context=1)

# Include gitignored files (e.g. search logs or build output)
file.grep(pattern="error", path=".", gitignore=False)

# Explicitly opt in (same as default)
file.grep(pattern="secret", path=".", gitignore=True)
```

`file.grep` is a pure-Python search, not a native `rg` wrapper. It follows
OneTool file safety policy, skips binary and oversized files, respects
`.gitignore` by default, and uses `max_matches` as the public total match cap.

### Navigating Sections

```python
# Show table of contents for a markdown file
file.toc(path="README.md")
file.toc(path="docs/spec.md")

# Extract by section number (from toc output)
file.slice(path="README.md", select=2)

# Extract by heading substring (case-insensitive)
file.slice(path="README.md", select="Installation")

# Extract by line range
file.slice(path="README.md", select=":50")       # first 50 lines
file.slice(path="README.md", select="100:200")   # lines 100–200
file.slice(path="README.md", select="-30:")      # last 30 lines

# Mixed selectors
file.slice(path="README.md", select=[1, "Usage", "300:400"])

# Batch slice from multiple files
file.slice_batch(items=[
    {"path": "docs/creating-tools.md", "select": "Checklist"},
    {"path": "docs/testing.md", "select": "Required Markers"},
    {"path": "src/file.py", "select": ":50"},
])
```

### Writing Files

```python
# Write new file
file.write(path="output.txt", content="Hello, World!")

# Append to file
file.write(path="log.txt", content="New entry\n", append=True)

# Create with parent directories
file.write(path="new/dir/file.txt", content="data", create_dirs=True)
```

### Editing Files

```python
# Replace text (errors if multiple occurrences)
file.edit(path="config.py", old_text="DEBUG = False", new_text="DEBUG = True")

# Replace all occurrences
file.edit(path="main.py", old_text="TODO", new_text="DONE", occurrence=0)

# Replace specific occurrence (2nd match)
file.edit(path="data.txt", old_text="foo", new_text="bar", occurrence=2)
```

### File Management

```python
# Copy file
file.copy(source="config.yaml", dest="config.backup.yaml")

# Copy directory
file.copy(source="src/", dest="src_backup/")

# Copy preserving symlinks
file.copy(source="src/", dest="backup/", follow_symlinks=False)

# Move/rename file
file.move(source="old_name.py", dest="new_name.py")

# Delete file (creates backup by default)
file.delete(path="temp.txt")

# Delete without backup
file.delete(path="temp.txt", backup=False)

# Delete non-empty directory
file.delete(path="old_dir/", recursive=True)
```

### Dry Run Mode

```python
# Preview write operation
file.write(path="output.txt", content="data", dry_run=True)

# Preview edit operation
file.edit(path="config.py", old_text="DEBUG = False", new_text="DEBUG = True", dry_run=True)

# Preview delete operation
file.delete(path="temp.txt", dry_run=True)
```

### Symlink Handling

```python
# Get symlink metadata (not target)
file.info(path="link.txt", follow_symlinks=False)

# List showing symlinks as type 'l'
file.list(path=".", follow_symlinks=False)

# Search including hidden files
file.search(pattern="*.conf", include_hidden=True)
```

## Security

All paths are validated against:
- **Allowed directories**: Paths must be under configured `allowed_dirs`
- **Exclude patterns**: Paths matching patterns like `.git` are blocked
- **File size limits**: Large files are rejected to prevent memory issues

## Inspired by

This tool was inspired by [fast-filesystem-mcp](https://github.com/efforthye/fast-filesystem-mcp)
by efforthye, licensed under Apache 2.0.
