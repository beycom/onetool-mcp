## ADDED Requirements

### Requirement: Project-local state directory surface

The public `otpack` package SHALL expose `get_project_state_dir(pack)` for
resolving a pack-owned directory under the effective project working directory,
and SHALL NOT expose generic `get_state` or `set_state` helpers or an
`otpack.state` module.

#### Scenario: Resolve pack-owned project state directory

- **WHEN** a tool calls `get_project_state_dir("my_pack")`
- **THEN** the returned path SHALL be
  `{effective project cwd}/.onetool/state/my_pack`

#### Scenario: Removed generic state exports

- **WHEN** a caller imports the public `otpack` package
- **THEN** `get_state` and `set_state` SHALL NOT be public attributes or package
  exports

#### Scenario: Removed state module

- **WHEN** a caller attempts to import `otpack.state`
- **THEN** the import SHALL fail through Python's standard missing-module path
  without an alias, fallback, or compatibility implementation
