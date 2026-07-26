## ADDED Requirements

### Requirement: Portable version-correct operational guidance

Operational help needed to use a pack or configured proxy server SHALL be available through
runtime help in the installed OneTool version without requiring access to a repository checkout or
the public web.

#### Scenario: Remote agent requests a packaged topic
- **GIVEN** an agent can call a remote OneTool server but cannot read its filesystem
- **WHEN** it requests a registered workflow, setup, config, DSL, policy, provider, or template topic
- **THEN** the required content SHALL be returned in the `ot.help()` result
- **AND** a repository-relative path SHALL NOT be the only access mechanism

#### Scenario: Published documentation is supplementary
- **WHEN** pack or configured-server help includes a public documentation link
- **THEN** the link SHALL be derived from the same reviewed slug/source metadata as generated docs
- **AND** the link SHALL resolve to the matching published page
- **AND** failure to browse the link SHALL NOT prevent use of the packaged operational guidance

### Requirement: Generated pack guidance consistency

Pack summaries, ownership/profile coverage, router coverage, help-topic inventory, normalized
runtime-requirement sections, reference indexes, managed highlights, and documentation links SHALL
be generated or validated from the composed catalog and runtime inventory.

#### Scenario: Generated content is stale
- **GIVEN** an authored source, runtime pack, requirement, config model, help topic, owner, or docs slug changes
- **WHEN** read-only documentation/skill validation runs before synchronization
- **THEN** it SHALL identify each stale generated target
- **AND** synchronization SHALL update only named managed blocks or generated files

#### Scenario: Authored operating judgment is preserved
- **WHEN** generated pack and skill projections are synchronized
- **THEN** authored prose outside managed markers SHALL remain byte-for-byte unchanged
- **AND** complete skill bodies SHALL NOT be regenerated from catalog metadata

### Requirement: Audited pack guidance accuracy

Pack summaries, skills, examples, highlights, and reference pages SHALL describe only current
callable behavior and SHALL cover material lifecycle operations exposed by the runtime.

#### Scenario: Unsupported capability claims are removed
- **WHEN** generated and authored guidance is checked against the runtime inventory
- **THEN** Excel SHALL NOT claim pivot support without a callable pivot operation
- **AND** package version-staleness checks SHALL NOT be described as vulnerability or security audits
- **AND** Forge SHALL NOT direct users to inspect templates without a corresponding callable operation

#### Scenario: Lifecycle operations are complete
- **WHEN** a user reads timer, secrets, or local-history guidance
- **THEN** it SHALL include every material current lifecycle operation, including completion/removal/pruning operations where implemented
- **AND** names and parameters SHALL match the runtime inventory

#### Scenario: Mutation and return behavior is accurate
- **WHEN** a user reads DB guidance
- **THEN** it SHALL state the actual default mutation/read-only behavior and return shape of `db.query`
- **AND** the skill SHALL require an explicit read-only or mutation decision before consequential SQL

#### Scenario: Console and browser examples are callable
- **WHEN** a user copies a console, Playwright companion, or Chrome companion example
- **THEN** the named function and parameters SHALL exist in the runtime interface
- **AND** public examples SHALL use a supported realistic target or omit the URL
- **AND** examples SHALL NOT use `example.com`

#### Scenario: Platform contracts are current
- **WHEN** platform documentation and specifications are checked against current source
- **THEN** MCP resource URIs and run annotations SHALL match the registered runtime values
- **AND** explicit config-root and variable precedence documentation SHALL match current path/config behavior
- **AND** worker-isolation documentation SHALL distinguish in-process built-ins from isolated extension workers
- **AND** Python extra documentation SHALL state that `[all]` expands to `[util,dev]`, excludes the separately opt-in `[scrape]` dependencies, and does not mean every optional capability

### Requirement: Non-authoritative feature tracking isolation

`features/features.yaml` MAY remain as historical/changelog tracking, but it SHALL NOT be an
authoritative product, runtime, catalog, skill, documentation, test, build, or release input.

#### Scenario: Implementation inputs are inspected
- **WHEN** runtime, catalog, generator, validator, test-oracle, build, or release dependencies are reviewed
- **THEN** none SHALL import, parse, compose with, or require `features/features.yaml`
- **AND** its schema, coverage hash, examples, completeness, and continued existence SHALL not affect implementation behavior or validation success
- **AND** current code and validated public interfaces SHALL remain authoritative

### Requirement: Pack guidance development documentation

Developer documentation SHALL provide a single routed lifecycle for adding or changing an
in-process pack, proxy-backed capability, owning skill, runtime help,
and generated reference content.

#### Scenario: A contributor adds a pack
- **WHEN** a contributor follows the canonical pack-guidance lifecycle
- **THEN** it SHALL identify the authoritative source for every pack fact
- **AND** it SHALL explain how to choose an existing owner or justify a new skill
- **AND** it SHALL cover requirements, config hooks, help topics, generated projections, docs links, validation, and required checks
- **AND** it SHALL explain when and how to use the bundled `otpack` SDK rather than duplicating shared infrastructure

#### Scenario: A contributor integrates a proxy server
- **WHEN** a contributor follows the proxy-server integration guide
- **THEN** it SHALL cover current authoritative MCP documentation, transport/auth requirements, secret redaction, native/configured instruction layering, companion packs, floating-version examples, and validation
- **AND** indexes and related focused guides SHALL link to the canonical lifecycle rather than duplicate it

### Requirement: Skill installation documentation

User documentation SHALL describe current standard installation and maintenance of repository-root
OneTool skills through the upstream skills installer.

#### Scenario: Installation docs are synchronized
- **WHEN** catalog membership changes
- **THEN** Foundation, Core, Core + `[util]`, Core + `[dev]`, and skill `[all]` selection recipes SHALL regenerate from catalog roles/ownership
- **AND** examples SHALL use current verified upstream syntax without claiming native named-profile support
- **AND** fixed skill counts SHALL not be an acceptance oracle
