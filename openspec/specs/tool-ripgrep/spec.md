# tool-ripgrep Specification

## Purpose

Provides fast text and regex search in files using ripgrep (`rg`). Requires the `rg` binary in PATH. Inspired by [mcp-ripgrep](https://github.com/mcollina/mcp-ripgrep) by Matteo Collina (MIT License).

Configuration via `onetool.yaml`:

```yaml
tools:
  ripgrep:
    timeout: 60.0           # Command timeout in seconds (default: 60)
    relative_paths: true    # Output relative paths (default: true)
```

## Requirements
### Requirement: Text Search

The `ripgrep.search()` function SHALL search files for patterns using ripgrep.

#### Scenario: Basic search
- **GIVEN** a search pattern and path
- **WHEN** `ripgrep.search(pattern="TODO", path="src/")` is called
- **THEN** it SHALL return matching lines with file paths and line numbers

#### Scenario: Case insensitive search
- **GIVEN** a pattern with case_sensitive=False
- **WHEN** `ripgrep.search(pattern="error", path=".", case_sensitive=False)` is called
- **THEN** it SHALL match case-insensitively

#### Scenario: Fixed string search
- **GIVEN** a pattern with fixed_strings=True
- **WHEN** `ripgrep.search(pattern="[test]", path=".", fixed_strings=True)` is called
- **THEN** it SHALL treat the pattern as a literal string, not a regex

#### Scenario: File type filter
- **GIVEN** a file_type parameter
- **WHEN** `ripgrep.search(pattern="import", path=".", file_type="py")` is called
- **THEN** it SHALL search only Python files

#### Scenario: Glob pattern filter
- **GIVEN** a glob parameter
- **WHEN** `ripgrep.search(pattern="TODO", path=".", glob="*.ts")` is called
- **THEN** it SHALL search only files matching the glob
- **NOTE**: Glob patterns are applied relative to path

#### Scenario: Context lines
- **GIVEN** a context parameter
- **WHEN** `ripgrep.search(pattern="error", path=".", context=2)` is called
- **THEN** it SHALL show 2 lines before and after each match

#### Scenario: Before/after context lines
- **GIVEN** before_context or after_context parameters
- **WHEN** `ripgrep.search(pattern="error", path=".", before_context=3, after_context=1)` is called
- **THEN** it SHALL show 3 lines before and 1 line after each match

#### Scenario: Max results per file
- **GIVEN** a max_per_file parameter
- **WHEN** `ripgrep.search(pattern="TODO", path=".", max_per_file=2)` is called
- **THEN** it SHALL return at most 2 matching lines per file

#### Scenario: Total results limit
- **GIVEN** a limit parameter
- **WHEN** `ripgrep.search(pattern="TODO", path=".", limit=10)` is called
- **THEN** it SHALL return at most 10 total matching lines with truncation message

#### Scenario: Word boundary match
- **GIVEN** word_match=True
- **WHEN** `ripgrep.search(pattern="test", path=".", word_match=True)` is called
- **THEN** it SHALL only match "test" as a whole word, not "testing"

#### Scenario: Include hidden files
- **GIVEN** include_hidden=True
- **WHEN** `ripgrep.search(pattern="secret", path=".", include_hidden=True)` is called
- **THEN** it SHALL search hidden files and directories

#### Scenario: Invert match
- **GIVEN** invert_match=True
- **WHEN** `ripgrep.search(pattern="import", path=".", invert_match=True)` is called
- **THEN** it SHALL return lines NOT matching the pattern

#### Scenario: Multiline patterns
- **GIVEN** multiline=True
- **WHEN** `ripgrep.search(pattern="def.*\\n.*return", path=".", multiline=True)` is called
- **THEN** it SHALL match patterns spanning multiple lines

#### Scenario: Only matching text
- **GIVEN** only_matching=True
- **WHEN** `ripgrep.search(pattern="TODO.*", path=".", only_matching=True)` is called
- **THEN** it SHALL return only the matched text, not the full line

#### Scenario: No ignore gitignore
- **GIVEN** no_ignore=True
- **WHEN** `ripgrep.search(pattern="test", path=".", no_ignore=True)` is called
- **THEN** it SHALL search files normally excluded by .gitignore

#### Scenario: Heading output
- **GIVEN** heading=True
- **WHEN** `ripgrep.search(pattern="TODO", path=".", heading=True)` is called
- **THEN** it SHALL group matches by file with headings

#### Scenario: No matches found
- **GIVEN** a pattern with no matches
- **WHEN** `ripgrep.search(pattern="nonexistent_xyz", path=".")` is called
- **THEN** it SHALL return "No matches found"

### Requirement: Match Counting

The `ripgrep.count()` function SHALL count pattern occurrences in files.

#### Scenario: Count matching lines
- **GIVEN** a pattern and path
- **WHEN** `ripgrep.count(pattern="TODO", path="src/")` is called
- **THEN** it SHALL return file paths with match counts per file

#### Scenario: Count total matches
- **GIVEN** count_all=True
- **WHEN** `ripgrep.count(pattern="import", path=".", count_all=True)` is called
- **THEN** it SHALL count all matches per line, not just matching lines

#### Scenario: Count with no_ignore
- **GIVEN** no_ignore=True
- **WHEN** `ripgrep.count(pattern="test", path=".", no_ignore=True)` is called
- **THEN** it SHALL count in files normally excluded by .gitignore

#### Scenario: No matches found
- **GIVEN** a pattern with no matches
- **WHEN** `ripgrep.count(pattern="nonexistent", path=".")` is called
- **THEN** it SHALL return "No matches found"

### Requirement: File Listing

The `ripgrep.files()` function SHALL list files that would be searched.

#### Scenario: List all files
- **GIVEN** a path
- **WHEN** `ripgrep.files(path="src/")` is called
- **THEN** it SHALL return a list of searchable file paths

#### Scenario: Filter by type
- **GIVEN** a file_type parameter
- **WHEN** `ripgrep.files(path=".", file_type="py")` is called
- **THEN** it SHALL return only Python files

#### Scenario: Filter by glob
- **GIVEN** a glob parameter
- **WHEN** `ripgrep.files(path=".", glob="*.md")` is called
- **THEN** it SHALL return only markdown files

#### Scenario: Include hidden
- **GIVEN** include_hidden=True
- **WHEN** `ripgrep.files(path=".", include_hidden=True)` is called
- **THEN** it SHALL include hidden files and directories

#### Scenario: No ignore gitignore
- **GIVEN** no_ignore=True
- **WHEN** `ripgrep.files(path=".", no_ignore=True)` is called
- **THEN** it SHALL include files normally excluded by .gitignore

#### Scenario: Sort files
- **GIVEN** a sort parameter
- **WHEN** `ripgrep.files(path=".", sort="modified")` is called
- **THEN** it SHALL return files sorted by modification time
- **NOTE**: Valid sort values: "path", "modified", "accessed", "created"

### Requirement: File Type Listing

The `ripgrep.types()` function SHALL list supported file types.

#### Scenario: List all types
- **WHEN** `ripgrep.types()` is called
- **THEN** it SHALL return all file types ripgrep supports with their extensions

### Requirement: Error Handling

The ripgrep tool SHALL handle errors gracefully.

#### Scenario: Missing rg binary
- **GIVEN** the `rg` command is not installed
- **WHEN** any ripgrep function is called
- **THEN** it SHALL return "Error: ripgrep (rg) is not installed. Install with: brew install ripgrep"

#### Scenario: Invalid path
- **GIVEN** a non-existent path
- **WHEN** `ripgrep.search(pattern="test", path="/nonexistent")` is called
- **THEN** it SHALL return an error indicating the path doesn't exist

#### Scenario: Invalid regex
- **GIVEN** an invalid regex pattern
- **WHEN** `ripgrep.search(pattern="[invalid", path=".")` is called
- **THEN** it SHALL return a user-friendly error message prefixed with "Error: Invalid regex pattern"

### Requirement: Ripgrep Tool Logging

The tool SHALL log all operations using LogSpan.

#### Scenario: Search logging
- **GIVEN** a search is requested
- **WHEN** the search completes
- **THEN** it SHALL log:
  - `span: "ripgrep.search"`
  - `pattern`: Search pattern
  - `path`: Search path
  - `matchCount`: Number of matches found

#### Scenario: Count logging
- **GIVEN** a count is requested
- **WHEN** the count completes
- **THEN** it SHALL log:
  - `span: "ripgrep.count"`
  - `pattern`: Search pattern
  - `path`: Search path

#### Scenario: Files logging
- **GIVEN** a file listing is requested
- **WHEN** the listing completes
- **THEN** it SHALL log:
  - `span: "ripgrep.files"`
  - `path`: Search path
  - `fileCount`: Number of files found
