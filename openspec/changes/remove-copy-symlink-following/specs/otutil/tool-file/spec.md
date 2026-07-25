## MODIFIED Requirements

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

- **GIVEN** a destination directory already exists
- **WHEN** `file.copy(source=src, dest=dst)` is called for a directory
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
