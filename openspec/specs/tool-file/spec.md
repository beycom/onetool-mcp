# tool-file Specification

## Purpose

Provides secure file operations for OneTool including reading, writing, editing, and file management. All paths are validated against configurable allowed directories for security.

Configuration via `onetool.yaml`:

```yaml
tools:
  file:
    allowed_dirs: ["."]           # Allowed directories (empty = cwd only)
    exclude_patterns:             # Patterns to exclude (defaults shown)
      - .git
      - .svn
      - .hg
      - node_modules
      - .venv
      - venv
      - __pycache__
      - .pytest_cache
      - .mypy_cache
      - "*.pyc"
      - dist
      - build
      - ".env*"
      - .DS_Store
      - Thumbs.db
    max_file_size: 10000000       # Max file size (10MB)
    backup_on_write: true         # Create .bak before writes
    use_trash: false              # Use send2trash if available
```

## Requirements

### Requirement: Path Security

All file operations SHALL validate paths against security constraints.

#### Scenario: Allowed directories
- **GIVEN** a path within an allowed directory
- **WHEN** any file operation is called
- **THEN** the operation SHALL proceed normally

#### Scenario: Path outside allowed directories
- **GIVEN** a path outside configured `allowed_dirs`
- **WHEN** any file operation is called
- **THEN** it SHALL return "Error: Access denied: path outside allowed directories"

#### Scenario: Excluded patterns
- **GIVEN** a path matching an `exclude_patterns` pattern
- **WHEN** any file operation is called
- **THEN** it SHALL return "Error: Access denied: path matches exclude pattern"

#### Scenario: Default allowed directory
- **GIVEN** `allowed_dirs` is empty (default)
- **WHEN** any file operation is called
- **THEN** only paths under `get_effective_cwd()` SHALL be allowed

#### Scenario: Symlink resolution
- **GIVEN** a symlink pointing outside allowed directories
- **WHEN** the symlink is accessed
- **THEN** it SHALL return "Error: Access denied: path outside allowed directories"

### Requirement: File Reading

The `file.read()` function SHALL read file content with optional pagination.

#### Scenario: Basic read
- **GIVEN** a valid file path
- **WHEN** `file.read(path=path)` is called
- **THEN** it SHALL return file content with line numbers

#### Scenario: Line-based pagination
- **GIVEN** a file path with offset and limit
- **WHEN** `file.read(path=path, offset=100, limit=50)` is called
- **THEN** it SHALL return lines 101-150 (0-indexed offset)
- **AND** it SHALL show pagination info if more lines remain

#### Scenario: Binary file detection
- **GIVEN** a binary file
- **WHEN** `file.read(path=path)` is called
- **THEN** it SHALL return "Error: Binary file detected ({size} bytes). Use appropriate tools for binary files."

#### Scenario: File too large
- **GIVEN** a file exceeding `max_file_size`
- **WHEN** `file.read(path=path)` is called
- **THEN** it SHALL return "Error: File too large: {size}MB (max: {max}MB)"

#### Scenario: Encoding fallback
- **GIVEN** a file that cannot be decoded as UTF-8
- **WHEN** `file.read(path=path)` is called
- **THEN** it SHALL attempt charset detection via charset-normalizer
- **AND** it SHALL return encoding error if detection fails

### Requirement: File Metadata

The `file.info()` function SHALL return file metadata.

#### Scenario: File info
- **GIVEN** a valid file path
- **WHEN** `file.info(path=path)` is called
- **THEN** it SHALL return YAML with:
  - `path`: Resolved absolute path
  - `type`: "file", "directory", or "symlink"
  - `size`: Size in bytes
  - `size_readable`: Human-readable size (e.g., "1.23 MB")
  - `permissions`: Unix permission string
  - `created`, `modified`, `accessed`: ISO timestamps

#### Scenario: Symlink target
- **GIVEN** a symlink
- **WHEN** `file.info(path=path)` is called
- **THEN** it SHALL include `target` with symlink destination

### Requirement: Directory Listing

The `file.list()` function SHALL list directory contents.

#### Scenario: Basic listing
- **GIVEN** a directory path
- **WHEN** `file.list(path=path)` is called
- **THEN** it SHALL return entries with type indicators (d=dir, f=file, l=symlink)
- **AND** files SHALL include human-readable size in parentheses
- **AND** directories SHALL be listed first, then files

#### Scenario: Pattern filtering
- **GIVEN** a directory path and glob pattern
- **WHEN** `file.list(path=path, pattern="*.py")` is called
- **THEN** it SHALL return only matching entries

#### Scenario: Recursive listing
- **GIVEN** a directory path with `recursive=True`
- **WHEN** `file.list(path=path, recursive=True)` is called
- **THEN** it SHALL list all entries recursively

#### Scenario: Hidden files
- **GIVEN** a directory with hidden files
- **WHEN** `file.list(path=path)` is called
- **THEN** it SHALL exclude hidden files by default
- **AND** `include_hidden=True` SHALL include them

#### Scenario: Sort options
- **GIVEN** a directory path with `sort_by` parameter
- **WHEN** `file.list(path=path, sort_by="size", reverse=True)` is called
- **THEN** it SHALL sort by the specified field (name, type, size, modified)
- **AND** `reverse=True` SHALL reverse the sort order

#### Scenario: Entry limit
- **GIVEN** a directory with many entries
- **WHEN** listing exceeds `max_list_entries`
- **THEN** it SHALL truncate and show "(truncated at N entries)"

### Requirement: Directory Tree

The `file.tree()` function SHALL display ASCII tree visualization.

#### Scenario: Basic tree
- **GIVEN** a directory path
- **WHEN** `file.tree(path=path)` is called
- **THEN** it SHALL return ASCII tree with Unicode box-drawing characters

#### Scenario: Depth limiting
- **GIVEN** a directory path with `max_depth=2`
- **WHEN** `file.tree(path=path, max_depth=2)` is called
- **THEN** it SHALL show at most 2 levels deep

### Requirement: File Search

The `file.search()` function SHALL search for files by name pattern.

#### Scenario: Basic search
- **GIVEN** a search pattern
- **WHEN** `file.search(pattern="*test*")` is called
- **THEN** it SHALL return matching files with path and size
- **AND** results SHALL be sorted by path

#### Scenario: File type filter
- **GIVEN** a search pattern with file_pattern
- **WHEN** `file.search(pattern="config", file_pattern="*.yaml")` is called
- **THEN** it SHALL return only files matching both patterns

#### Scenario: Case sensitivity
- **GIVEN** `case_sensitive=True`
- **WHEN** `file.search(pattern="README", case_sensitive=True)` is called
- **THEN** it SHALL match case-sensitively

#### Scenario: Result limit
- **GIVEN** many matching files
- **WHEN** results exceed `max_results` (default: 100)
- **THEN** it SHALL truncate and show "(limited to N results)"

### Requirement: File Writing

The `file.write()` function SHALL write content to files.

#### Scenario: Basic write
- **GIVEN** a file path and content
- **WHEN** `file.write(path=path, content=content)` is called
- **THEN** it SHALL write content to file
- **AND** it SHALL return "OK: wrote N bytes to path"

#### Scenario: Append mode
- **GIVEN** a file path with `append=True`
- **WHEN** `file.write(path=path, content=content, append=True)` is called
- **THEN** it SHALL append content to existing file

#### Scenario: Create directories
- **GIVEN** a path where parent directory doesn't exist
- **WHEN** `file.write(path=path, content=content, create_dirs=True)` is called
- **THEN** it SHALL create parent directories

#### Scenario: Atomic write
- **GIVEN** a file path (not append mode)
- **WHEN** `file.write(path=path, content=content)` is called
- **THEN** it SHALL write to temp file and rename for atomicity

#### Scenario: Backup on write
- **GIVEN** `backup_on_write=True` and existing file
- **WHEN** `file.write(path=path, content=content)` is called
- **THEN** it SHALL create `path.bak` before writing

### Requirement: File Editing

The `file.edit()` function SHALL perform exact string replacement.

#### Scenario: Basic edit
- **GIVEN** a file path and old/new text
- **WHEN** `file.edit(path=path, old_text=old, new_text=new)` is called
- **THEN** it SHALL replace first occurrence of old_text with new_text

#### Scenario: Replace all
- **GIVEN** `occurrence=0`
- **WHEN** `file.edit(path=path, old_text=old, new_text=new, occurrence=0)` is called
- **THEN** it SHALL replace all occurrences

#### Scenario: Ambiguous match
- **GIVEN** old_text appears multiple times and occurrence not specified
- **WHEN** `file.edit(path=path, old_text=old, new_text=new)` is called
- **THEN** it SHALL return "Error: Found N occurrences. Use occurrence=0 to replace all..."

#### Scenario: Text not found
- **GIVEN** old_text not in file
- **WHEN** `file.edit(path=path, old_text=old, new_text=new)` is called
- **THEN** it SHALL return "Error: Text not found in file"

### Requirement: File Deletion

The `file.delete()` function SHALL delete files safely.

#### Scenario: Delete file
- **GIVEN** a valid file path
- **WHEN** `file.delete(path=path)` is called
- **THEN** it SHALL delete the file
- **AND** create backup if `backup=True` (default)

#### Scenario: Trash support
- **GIVEN** `use_trash=True` and send2trash installed
- **WHEN** `file.delete(path=path)` is called
- **THEN** it SHALL move file to system trash
- **AND** return "OK: Moved to trash: path"

#### Scenario: Non-empty directory
- **GIVEN** a non-empty directory
- **WHEN** `file.delete(path=path)` is called
- **THEN** it SHALL return "Error: Directory not empty: path"

### Requirement: File Copy

The `file.copy()` function SHALL copy files and directories.

#### Scenario: Copy file
- **GIVEN** source and destination paths
- **WHEN** `file.copy(source=src, dest=dst)` is called
- **THEN** it SHALL copy file with metadata

#### Scenario: Copy directory
- **GIVEN** source directory and destination path
- **WHEN** `file.copy(source=src, dest=dst)` is called
- **THEN** it SHALL copy entire directory tree

#### Scenario: Destination exists
- **GIVEN** destination directory already exists
- **WHEN** `file.copy(source=src, dest=dst)` is called for directory
- **THEN** it SHALL return "Error: Destination already exists: dst"

### Requirement: File Move

The `file.move()` function SHALL move or rename files.

#### Scenario: Move file
- **GIVEN** source and destination paths
- **WHEN** `file.move(source=src, dest=dst)` is called
- **THEN** it SHALL move file to destination

#### Scenario: Rename file
- **GIVEN** source and destination in same directory
- **WHEN** `file.move(source=old_name, dest=new_name)` is called
- **THEN** it SHALL rename the file

#### Scenario: Destination parent missing
- **GIVEN** destination directory doesn't exist
- **WHEN** `file.move(source=src, dest=dst)` is called
- **THEN** it SHALL return "Error: Destination directory does not exist: parent"

### Requirement: Logging

All file operations SHALL log using LogSpan.

#### Scenario: Read logging
- **GIVEN** a file read operation
- **WHEN** the operation completes
- **THEN** it SHALL log:
  - `span: "file.read"`
  - `path`: File path
  - `resultLen`: Output length
  - `totalLines`: Total lines in file

#### Scenario: Write logging
- **GIVEN** a file write operation
- **WHEN** the operation completes
- **THEN** it SHALL log:
  - `span: "file.write"`
  - `path`: File path
  - `bytesWritten`: Bytes written

#### Scenario: Search logging
- **GIVEN** a file search operation
- **WHEN** the operation completes
- **THEN** it SHALL log:
  - `span: "file.search"`
  - `path`: Search root path
  - `pattern`: Search pattern
  - `resultCount`: Number of results

#### Scenario: Error logging
- **GIVEN** any file operation that fails
- **WHEN** the operation completes
- **THEN** it SHALL log `error` attribute with error description
