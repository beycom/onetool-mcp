## ADDED Requirements

### Requirement: Argv-based release publish subprocess execution

The release publish script (`scripts/release_publish.py`) SHALL invoke every
subprocess command via an argv list (`subprocess.run(list[str], ...)` with no
`shell=True`), not via a shell string. No file under `scripts/` SHALL contain
`shell=True`.

#### Scenario: No shell=True in scripts

- **WHEN** `rg "shell=True" scripts/` is run
- **THEN** the command SHALL produce zero matches (empty output, exit code 1)

### Requirement: Version metadata consistency for the 3.0.0 release

The three release version files — `pyproject.toml`, `server.json`, and `packages/onetool-pack/pyproject.toml` — SHALL declare identical version strings after `just release::prep 3.0.0` runs.

#### Scenario: Versions match across the three files

- **WHEN** the version fields are read from `pyproject.toml`, `server.json`,
  and `packages/onetool-pack/pyproject.toml`
- **THEN** all three SHALL equal `3.0.0`

### Requirement: 3.0.0 changelog entry content

`CHANGELOG.md` SHALL contain a `## [3.0.0]` entry as its top entry, with a
breaking-changes-and-migration-notes section listed before any other
subsection. That section SHALL cover: the `__run`→`__onetool` trigger rename,
`mem.export`→`mem.dump` and `mem.snap`→`mem.snapshot`, `direct.*`→
`direct.host.*` config nesting, `file.read` raw-lines-by-default, and the
removed surfaces (`onetool-bench`, the AWS pack, the entire handoff pack,
public proxy reference pages, `output.compact`/`__compact__`, plus this
release cycle's removals: `ot.skills`/`install_skills`, the `[whiteboard]`
extra, and the pack API param renames). Tool improvements SHALL be grouped
under a "New tools and improvements" section without raw commit lists. The
entry SHALL NOT describe net-zero added-and-removed churn (caveman
compaction, IDE bridge, handoff Codex delegation) as shipped.

#### Scenario: Breaking changes lead the entry

- **WHEN** `CHANGELOG.md` is read from the top
- **THEN** the first entry SHALL be `## [3.0.0]`
- **AND** its first subsection SHALL list breaking changes and migration
  notes before any other subsection

#### Scenario: Removed-surface names are absent from non-changelog docs

- **WHEN** `rg` is run for each removed-surface name (`onetool-bench`, the AWS
  pack, `src/ot/handoff`, `output.compact`, `__compact__`, `install_skills`)
  across `openspec/`, `docs/`, and `src/`
- **THEN** no stale references SHALL remain outside `CHANGELOG.md`'s
  historical breaking-changes note

### Requirement: Recorded direct-run release gate

`dev/practices/release.md` SHALL document the direct-run sanity recipe
(`tests/explore/test-cli.md` lines 122-128, the seven `onetool direct run`
probe commands run against a live root process) as an explicit release gate
step that SHALL pass before `just release::publish` is invoked.

#### Scenario: Gate documented before the publish step

- **WHEN** `dev/practices/release.md` is read
- **THEN** it SHALL contain a step instructing the releaser to run the
  direct-run sanity commands from `tests/explore/test-cli.md:122-128` against
  a running root process
- **AND** SHALL state that this gate must pass before proceeding to
  `just release::publish`
