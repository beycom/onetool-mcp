# File

**Read. Write. Edit. Move. All with security boundaries.**

Secure file operations with configurable security boundaries. Read, write, edit, and manage files with path validation against allowed directories.

## Highlights

- Configurable security boundaries with allowed directories
- Automatic backup creation before writes
- Recursive directory operations with pattern filtering
- Line-numbered file reading with pagination
- Text replacement with occurrence control

## Read Operations

| Function | Description |
|----------|-------------|
| `file.read(path, offset, limit, encoding)` | Read file content with line numbers |
| `file.info(path)` | Get file or directory metadata |

## List Operations

| Function | Description |
|----------|-------------|
| `file.list(path, pattern, recursive, include_hidden, sort_by, reverse)` | List directory contents |
| `file.tree(path, max_depth, include_hidden)` | Display directory tree structure |
| `file.search(path, pattern, glob, file_pattern, case_sensitive, max_results)` | Search for files by name or glob pattern |

## Write Operations

| Function | Description |
|----------|-------------|
| `file.write(path, content, append, create_dirs)` | Write content to file |
| `file.edit(path, old_text, new_text, occurrence)` | Edit file by replacing text |

## File Management

| Function | Description |
|----------|-------------|
| `file.copy(source, dest)` | Copy file or directory |
| `file.move(source, dest)` | Move or rename file or directory |
| `file.delete(path, backup)` | Delete file or empty directory |

## Key Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `path` | str | File or directory path (relative to cwd or absolute) |
| `pattern` | str | Filename pattern for filtering (e.g., `*.py`, `*test*`) |
| `glob` | str | Full path glob pattern (e.g., `src/**/*.py`, `**/*.md`) |
| `offset` | int | Line number to start from (1-indexed, default: 1) |
| `limit` | int | Maximum lines to return |
| `occurrence` | int | Which match to replace (1=first, 0=all) |

## Configuration

Configure via `onetool.yaml`:

```yaml
tools:
  file:
    allowed_dirs: ["."]          # Allowed directories (empty = cwd only)
    exclude_patterns: [".git"]   # Patterns to exclude
    max_file_size: 10000000      # Max file size (10MB)
    max_list_entries: 1000       # Max entries in list/tree
    backup_on_write: true        # Create .bak before writes
    use_trash: false             # Use send2trash if available
    relative_paths: true         # Output relative paths (default)
```

## Examples

### Reading Files

```python
# Read entire file with line numbers
file.read(path="src/main.py")

# Read with pagination (lines 100-150)
file.read(path="large_file.log", offset=100, limit=50)

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

# Move/rename file
file.move(source="old_name.py", dest="new_name.py")

# Delete file (creates backup by default)
file.delete(path="temp.txt")

# Delete without backup
file.delete(path="temp.txt", backup=False)
```

## Security

All paths are validated against:
- **Allowed directories**: Paths must be under configured `allowed_dirs`
- **Exclude patterns**: Paths matching patterns like `.git` are blocked
- **File size limits**: Large files are rejected to prevent memory issues

## Source

[Python pathlib](https://docs.python.org/3/library/pathlib.html) | [shutil](https://docs.python.org/3/library/shutil.html)

## Inspired by

[fast-filesystem-mcp](https://github.com/efforthye/fast-filesystem-mcp) by efforthye (Apache 2.0)
