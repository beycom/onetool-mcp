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
      - node_modules
      - __pycache__
      - .venv
      - venv
    max_file_size: 10000000       # Max file size (10MB)
    backup_on_write: true         # Create .bak before writes
    use_trash: false              # Use send2trash if available
    relative_paths: true          # Output relative paths (default: true)
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
- **THEN** it SHALL return raw file content lines (no line-number prefix)

#### Scenario: Line numbers opt-in
- **GIVEN** a valid file path
- **WHEN** `file.read(path=path, line_numbers=True)` is called
- **THEN** it SHALL prefix each line with its line number

#### Scenario: Line-based pagination
- **GIVEN** a file path with offset and limit
- **WHEN** `file.read(path=path, offset=100, limit=50)` is called
- **THEN** it SHALL return lines 100-149 (1-indexed offset, start at line N)
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
- **THEN** it SHALL return a dict with:
  - `path`: Relative path (or absolute if `relative_paths=False` or path is outside cwd)
  - `type`: "file" or "directory" when `follow_symlinks=True` (default); "symlink" when `follow_symlinks=False`
  - `size`: Size in bytes
  - `size_readable`: Human-readable size (e.g., "1.23 MB")
  - `permissions`: Unix permission string
  - `created`, `modified`, `accessed`: ISO timestamps

#### Scenario: Symlink target
- **GIVEN** a symlink
- **WHEN** `file.info(path=path)` is called
- **THEN** it SHALL include `target` with symlink destination

#### Scenario: Follow symlinks
- **GIVEN** a symlink with `follow_symlinks=True` (default)
- **WHEN** `file.info(path=path)` is called
- **THEN** it SHALL return target metadata
- **AND** `follow_symlinks=False` SHALL return symlink metadata

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

#### Scenario: Symlink type display
- **GIVEN** a directory with symlinks
- **WHEN** `file.list(path=path, follow_symlinks=False)` is called (default)
- **THEN** symlinks SHALL be shown as type 'l'
- **AND** `follow_symlinks=True` SHALL show them as their target type

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

#### Scenario: Hidden files
- **GIVEN** a directory with hidden files
- **WHEN** `file.search(pattern="*", include_hidden=False)` is called
- **THEN** it SHALL exclude hidden files (starting with `.`)
- **AND** `include_hidden=True` SHALL include them

### Requirement: File Reference Resolution

The `file.resolve()` function SHALL resolve exact/glob references and fuzzy quick-open references to file or directory path strings.

#### Scenario: Selector validation
- **GIVEN** neither `glob` nor `match` is provided
- **WHEN** `file.resolve()` is called
- **THEN** it SHALL return an error string
- **AND** providing both `glob` and `match` SHALL return an error string

#### Scenario: Glob reference
- **GIVEN** an exact path or glob pattern
- **WHEN** `file.resolve(glob="src/**/*.py")` is called
- **THEN** it SHALL return matching file paths sorted deterministically by case-insensitive path order
- **AND** exact file paths SHALL be accepted by the same code path as glob patterns
- **AND** by default it SHALL return at most 10 paths per selector

#### Scenario: Scoped glob reference
- **GIVEN** a directory path and a relative glob pattern
- **WHEN** `file.resolve(path="dev/guides", glob="tool-*.md")` is called
- **THEN** it SHALL resolve the relative glob from the supplied path root
- **AND** returned relative paths SHALL remain relative to the effective cwd when possible
- **AND** absolute glob patterns SHALL still resolve from the filesystem root

#### Scenario: Directory reference
- **GIVEN** matching directory and file candidates
- **WHEN** `file.resolve(glob="src/**", kind="dir")` is called
- **THEN** it SHALL return only matching directory paths
- **AND** `kind="file"` SHALL return only matching file paths
- **AND** invalid `kind` values SHALL return an error string

#### Scenario: Fuzzy quick-open reference
- **GIVEN** files under the effective cwd
- **WHEN** `file.resolve(match="tlf")` is called
- **THEN** it SHALL fuzzy-match against relative candidate paths using fzy-style path scoring
- **AND** match results SHALL be sorted by fuzzy score descending, then case-insensitive path order
- **AND** by default it SHALL return at most 10 paths per selector

#### Scenario: Scoped fuzzy quick-open reference
- **GIVEN** a directory path and files inside and outside that directory
- **WHEN** `file.resolve(path="dev/practices", match="cli-pattern")` is called
- **THEN** it SHALL build fuzzy candidates only from files under the supplied path root
- **AND** returned relative paths SHALL remain relative to the effective cwd when possible

#### Scenario: Invalid path root
- **GIVEN** a missing path or file path
- **WHEN** `file.resolve(path=path, match="query")` is called
- **THEN** it SHALL return an error string

#### Scenario: Result shape
- **GIVEN** a single-string selector
- **WHEN** `multi` is omitted or set to `"all"`
- **THEN** `file.resolve()` SHALL return a list of path strings
- **AND** no matches SHALL return an empty list
- **AND** `multi="first"` SHALL return a single path string when resolution succeeds
- **AND** `multi="error"` SHALL return a single path string only when exactly one path resolves
- **AND** list selector input SHALL always return a flat list in input order

#### Scenario: Multiple matches
- **GIVEN** a selector with multiple matches
- **WHEN** `file.resolve(..., multi="error")` is called
- **THEN** it SHALL return an error string with numbered candidate paths
- **AND** the error SHALL suggest `multi="first"` or `multi="all"`

#### Scenario: Filtering
- **GIVEN** hidden files, gitignored files, and files matching `exclude_patterns`
- **WHEN** `file.resolve()` resolves candidates
- **THEN** it SHALL include hidden path segments by default
- **AND** it SHALL skip hidden path segments when `include_hidden=False`
- **AND** it SHALL honor `.gitignore` when `gitignore=True`
- **AND** it SHALL include gitignored files when `gitignore=False`
- **AND** it SHALL always apply `exclude_patterns`

#### Scenario: Result limit
- **GIVEN** more matches than `max_results`
- **WHEN** `file.resolve(max_results=10)` is called
- **THEN** it SHALL return at most 10 matches per selector
- **AND** invalid non-positive `max_results` values SHALL return an error string

#### Scenario: Path type
- **GIVEN** a matching file under the effective cwd
- **WHEN** `file.resolve(path_type="relative")` is called
- **THEN** it SHALL return cwd-relative paths when possible
- **AND** `path_type="absolute"` SHALL return absolute paths
- **AND** invalid `path_type` values SHALL return an error string

### Requirement: Content Grep

The `file.grep()` function SHALL search file contents using pure-Python regex (no external binaries required).

#### Scenario: Basic match
- **GIVEN** a pattern and directory path
- **WHEN** `file.grep(pattern="foo", path=".")` is called
- **THEN** it SHALL return matches in ripgrep format: `filename:lineno: line`
- **AND** context lines SHALL appear as `filename-lineno- line`

#### Scenario: Glob filter
- **GIVEN** a glob parameter
- **WHEN** `file.grep(pattern="foo", path=".", glob="*.py")` is called
- **THEN** it SHALL search only files matching the glob, recursively into subdirectories
- **AND** `glob="*.py"` and `glob="**/*.py"` SHALL produce identical results

#### Scenario: Case insensitive
- **GIVEN** `case_sensitive=False`
- **WHEN** `file.grep(pattern="FOO", case_sensitive=False)` is called
- **THEN** it SHALL match regardless of case

#### Scenario: Fixed strings
- **GIVEN** `fixed_strings=True`
- **WHEN** `file.grep(pattern="foo()", fixed_strings=True)` is called
- **THEN** it SHALL treat the pattern as a literal string, not a regex

#### Scenario: No match
- **GIVEN** a pattern with no matches
- **WHEN** `file.grep(pattern="xyzzy")` is called
- **THEN** it SHALL return "No matches found for: <pattern>"

#### Scenario: Binary files skipped
- **GIVEN** a directory containing binary files
- **WHEN** `file.grep(pattern="foo")` is called
- **THEN** it SHALL silently skip binary files

#### Scenario: Oversized files skipped
- **GIVEN** a file exceeding `max_file_size`
- **WHEN** `file.grep(pattern="foo")` is called
- **THEN** it SHALL silently skip the oversized file

#### Scenario: Max matches cap
- **GIVEN** many matches across files
- **WHEN** matches exceed `max_matches` (default: 500)
- **THEN** it SHALL stop and append a truncation notice
- **AND** it SHALL NOT apply any additional hidden per-file or per-group cap

#### Scenario: Zero context output format
- **GIVEN** a file with multiple non-adjacent matching lines
- **WHEN** `file.grep(pattern="foo", context=0)` is called
- **THEN** each match SHALL be returned as one line in `filename:lineno: line`
  format
- **AND** blank separator lines SHALL NOT be inserted between match lines

#### Scenario: Gitignore respected by default
- **GIVEN** a `.gitignore` at the search root listing `ignored.py`
- **WHEN** `file.grep(pattern="foo", path=".")` is called (default `gitignore=True`)
- **THEN** it SHALL skip files matched by `.gitignore`
- **AND** non-ignored files SHALL still be searched

#### Scenario: Gitignore opt-out
- **GIVEN** a `.gitignore` at the search root
- **WHEN** `file.grep(pattern="foo", path=".", gitignore=False)` is called
- **THEN** it SHALL search all files regardless of `.gitignore`

#### Scenario: No gitignore file
- **GIVEN** no `.gitignore` exists at the search root
- **WHEN** `file.grep(pattern="foo", path=".", gitignore=True)` is called
- **THEN** it SHALL search all files normally (no-op)

### Requirement: Batch File Reading

The `file.read_batch()` function SHALL read multiple files in a single call.

#### Scenario: Read by path list
- **GIVEN** a list of file paths
- **WHEN** `file.read_batch(paths=["a.py", "b.py"])` is called
- **THEN** it SHALL return concatenated file contents separated by `---` dividers
- **AND** each section SHALL begin with `# filename` header

#### Scenario: Read by glob
- **GIVEN** a glob pattern
- **WHEN** `file.read_batch(glob="src/**/*.py")` is called
- **THEN** it SHALL read all matching text files up to `max_files` limit, recursively
- **AND** `glob="*.py"` and `glob="**/*.py"` SHALL produce identical results

#### Scenario: Missing input
- **GIVEN** neither paths nor glob provided
- **WHEN** `file.read_batch()` is called
- **THEN** it SHALL return an error

#### Scenario: Binary files skipped
- **GIVEN** a path list containing binary files
- **WHEN** `file.read_batch(paths=[...])` is called
- **THEN** binary files SHALL be silently skipped

#### Scenario: Security-rejected paths dropped
- **GIVEN** a paths list containing a path outside allowed directories
- **WHEN** `file.read_batch(paths=[...])` is called
- **THEN** the rejected path SHALL be silently dropped (not read, not reported)
- **AND** allowed paths SHALL be read normally

#### Scenario: Oversized file gets error entry
- **GIVEN** a path list where one file exceeds `max_file_size`
- **WHEN** `file.read_batch(paths=[...])` is called
- **THEN** the oversized file SHALL produce an error entry in the output
- **AND** remaining files SHALL still be read

### Requirement: File TOC

The `file.toc()` function SHALL display a numbered section index for a file.

#### Scenario: Markdown headings
- **GIVEN** a markdown file with ATX headings
- **WHEN** `file.toc(path="README.md")` is called
- **THEN** it SHALL return a numbered list of sections with line ranges

#### Scenario: No headings
- **GIVEN** a file with no markdown headings
- **WHEN** `file.toc(path="plain.txt")` is called
- **THEN** it SHALL return "No sections found"

### Requirement: File Slice

The `file.slice()` function SHALL extract content from a file by section, heading, or line range.

#### Scenario: Line range
- **GIVEN** a line range selector like ":50" or "100:200"
- **WHEN** `file.slice(path="file.md", select=":50")` is called
- **THEN** it SHALL return lines 1 through 50

#### Scenario: Heading match
- **GIVEN** a heading substring selector
- **WHEN** `file.slice(path="file.md", select="Installation")` is called
- **THEN** it SHALL return the section under the matched heading

#### Scenario: Section number
- **GIVEN** an integer selector
- **WHEN** `file.slice(path="file.md", select=2)` is called
- **THEN** it SHALL return the content of the 2nd heading section

#### Scenario: List of selectors
- **GIVEN** a list of selectors
- **WHEN** `file.slice(path="file.md", select=[1, "Usage"])` is called
- **THEN** it SHALL return concatenated content for each matched selector

#### Scenario: No match
- **GIVEN** a selector that matches nothing
- **WHEN** `file.slice()` is called
- **THEN** it SHALL return "No matching content found for the given selector(s)"

### Requirement: Slice Batch

The `file.slice_batch()` function SHALL extract sections from multiple files in a single call.

#### Scenario: Multiple files
- **GIVEN** a list of items with path and select
- **WHEN** `file.slice_batch(items=[{"path": "a.md", "select": "Intro"}, ...])` is called
- **THEN** it SHALL return sliced content from each file with path headers and dividers

#### Scenario: Empty items
- **GIVEN** an empty items list
- **WHEN** `file.slice_batch(items=[])` is called
- **THEN** it SHALL return an error

#### Scenario: Too many items
- **GIVEN** more than 20 items
- **WHEN** `file.slice_batch(items=[...])` is called (21+ items)
- **THEN** it SHALL return an error referencing the 20-item limit

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

#### Scenario: Custom encoding
- **GIVEN** a file path, content, and encoding
- **WHEN** `file.write(path=path, content=content, encoding="latin-1")` is called
- **THEN** it SHALL write content using the specified encoding

#### Scenario: Dry run mode
- **GIVEN** a file path with `dry_run=True`
- **WHEN** `file.write(path=path, content=content, dry_run=True)` is called
- **THEN** it SHALL return what would happen without writing
- **AND** no file changes SHALL be made

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

#### Scenario: Custom encoding
- **GIVEN** a file with non-UTF-8 encoding
- **WHEN** `file.edit(path=path, old_text=old, new_text=new, encoding="latin-1")` is called
- **THEN** it SHALL read and write using the specified encoding

#### Scenario: Dry run mode
- **GIVEN** a file path with `dry_run=True`
- **WHEN** `file.edit(path=path, old_text=old, new_text=new, dry_run=True)` is called
- **THEN** it SHALL return what would happen without editing
- **AND** no file changes SHALL be made

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
- **THEN** it SHALL return "Error: Directory not empty: path. Use recursive=True to delete contents."

#### Scenario: Recursive delete
- **GIVEN** a non-empty directory with `recursive=True`
- **WHEN** `file.delete(path=path, recursive=True)` is called
- **THEN** it SHALL delete the directory and all contents

#### Scenario: Dry run mode
- **GIVEN** a file or directory with `dry_run=True`
- **WHEN** `file.delete(path=path, dry_run=True)` is called
- **THEN** it SHALL return what would happen without deleting
- **AND** no file changes SHALL be made

### Requirement: File Copy

The `file.copy()` function SHALL copy regular files and link-free directory
trees without exposing a `follow_symlinks` parameter, SHALL never dereference or
publish a symlink, and SHALL atomically publish a complete destination only
after the source copy succeeds.

#### Scenario: Copy file

- **GIVEN** regular source and destination paths
- **WHEN** `file.copy(source=src, dest=dst)` is called
- **THEN** it SHALL copy the file with metadata through a unique
  same-directory staging path
- **AND** it SHALL atomically publish the completed destination

#### Scenario: Copy directory

- **GIVEN** a link-free source directory and absent destination path
- **WHEN** `file.copy(source=src, dest=dst)` is called
- **THEN** it SHALL copy the entire directory tree through a unique
  same-directory staging path
- **AND** it SHALL atomically publish the completed destination

#### Scenario: Destination exists

- **GIVEN** destination directory already exists
- **WHEN** `file.copy(source=src, dest=dst)` is called for directory
- **THEN** it SHALL return "Error: Destination already exists: dst"
- **AND** the existing destination SHALL remain byte-identical

#### Scenario: Top-level symlink rejected

- **GIVEN** the source path itself is a file or directory symlink
- **WHEN** `file.copy(source=link, dest=dst)` is called
- **THEN** it SHALL reject the operation without reading the target
- **AND** the destination SHALL remain absent or byte-identical

#### Scenario: Nested symlink rejected

- **GIVEN** a source directory contains any file or directory symlink
- **WHEN** `file.copy(source=src, dest=dst)` is called
- **THEN** it SHALL reject the entire operation without reading the link target
- **AND** it SHALL publish no partial destination

#### Scenario: Entry replaced by symlink during traversal

- **GIVEN** a regular source entry is replaced by a symlink after discovery
- **WHEN** `file.copy(source=src, dest=dst)` opens that entry
- **THEN** it SHALL reject the entire operation without reading target bytes
- **AND** it SHALL remove every staging artifact

#### Scenario: Removed symlink mode

- **WHEN** the current `file.copy()` interface is inspected
- **THEN** it SHALL expose only `source`, `dest`, and `overwrite`
- **AND** it SHALL provide no alias, hidden preserve mode, or compatibility
  fallback for `follow_symlinks`

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

All file operations SHALL emit structured runtime logs.

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
