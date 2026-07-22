# tool-arch-validation Specification

## Purpose

Defines unified production validation, stable diagnostics, source tracing, export prerequisites, executable acceptance, and cleanup checks.

## Requirements

### Requirement: Unified production validation operation
`arch.validate(input_path, roadmaps=None, views=None)` SHALL use the same
loaders, schemas, normalizer, replay engine, selector resolver, LikeC4 compiler,
asset/theme/icon resolver, and exporter prerequisite checks as generation and
export. Roadmap/view filters SHALL restrict requested validation without
changing shared semantics.

#### Scenario: Validate the canonical workspace end to end
- **WHEN** equivalent canonical YAML and Excel workspaces are validated
- **THEN** both are valid and report identical normalized operation, roadmap,
  resolved-state, view, diagram, and asset summary counts

#### Scenario: Prevent validation bypass
- **WHEN** generation/export receives a workspace that production validation
  rejects
- **THEN** it cannot report success or publish a replacement output

### Requirement: Schema and identity diagnostics
Validation SHALL detect duplicate or invalid state, change, roadmap, view,
diagram, entity, interface, table, column, theme, and artifact identities plus
unknown fields where typed schemas disallow extensions.

#### Scenario: Report duplicate IDs with all locations
- **WHEN** two entities or views share an ID
- **THEN** one stable diagnostic identifies the duplicate kind, ID, and every
  conflicting YAML or Excel source location

### Requirement: Replay and order diagnostics
Validation SHALL detect unknown roadmap changes, duplicate/non-positive/gapped
orders, incomplete additions, modify/remove before add, operations after
remove, duplicate add/remove, incompatible field changes, stale expected
values, missing parents/endpoints, invalid containment, cascade effects,
missing/cyclic dependencies, incompatible derived changes, and order-sensitive
valid outcomes.

#### Scenario: Report reorder dependency precisely
- **WHEN** `proj2` modifies `sys_x` before `proj1-stage2` adds it
- **THEN** the issue identifies roadmap, order, both relevant changes,
  operation, entity, source location, and suggested dependency/order

#### Scenario: Report cascade expansion
- **WHEN** an explicit system removal expands to descendants and interfaces
- **THEN** validation reports the initiating ancestor and generated removal
  paths without counting duplicate child operations

### Requirement: Selection and reference diagnostics
Validation SHALL detect mutually exclusive or inapplicable selectors, unknown
or later comparison points, subjects, focus changes, diagrams, statuses,
projections, levels, theme references, source references, and applicability.

#### Scenario: Reject incompatible state and future request
- **WHEN** an authored-state selection supplies `include_future=true`
- **THEN** validation identifies the incompatible fields and view/request source

#### Scenario: Reject unknown interface endpoint and diagram
- **WHEN** a workspace contains an interface with an unknown endpoint and a view
  with an unknown diagram ID
- **THEN** separate stable diagnostics retain both canonical identities and
  complete source locations

### Requirement: LikeC4 and asset safety diagnostics
Validation SHALL check the pinned LikeC4 subset, view-only source statements,
identifier mappings, dynamic/sequence participants, theme/style values, every
supported pinned icon name, local SVG safety, and external attachment paths and
types. Remote, unsafe, missing, path-escaping, individually oversized, or
aggregate-oversized assets SHALL be errors. Attachment limits SHALL be 10 MiB
per file and 25 MiB for distinct embedded content.

The pinned compiler and exporter boundaries SHALL consume complete stdin
reliably when invoked from MCP, CLI, test, or other supported parent runtimes,
including runtimes whose inherited descriptors use non-blocking I/O.

#### Scenario: Compile through a non-blocking parent runtime
- **WHEN** `arch.validate`, `arch.generate`, or `arch.export` sends generated
  LikeC4 source to the pinned Node boundary
- **THEN** the boundary consumes the complete request without surfacing a
  transient fd-0 `EAGAIN` error

#### Scenario: Locate a disallowed LikeC4 declaration
- **WHEN** view-only source contains a deployment declaration
- **THEN** the issue identifies file, line/location, diagram/view, statement,
  and stable code

#### Scenario: Reject path traversal in a local icon
- **WHEN** `@icons` resolves outside `assets/icons/`
- **THEN** validation rejects it before any renderer or exporter reads the file

### Requirement: Export prerequisite and fidelity diagnostics
Validation SHALL check format support, required layout/compiler/exporter
versions, output selection compatibility, and known icon/style/diagram fidelity
mapping. Unsupported silent loss SHALL be an error; explicitly supported
presentation differences SHALL be warnings included in the artifact manifest.

#### Scenario: Warn on supported Draw.io fidelity difference
- **WHEN** a selected React-only presentation field lacks a Draw.io mapping but
  semantic export remains supported
- **THEN** validation emits a warning that identifies format, field, elements,
  and expected manifest entry

#### Scenario: Fail unsupported semantic loss
- **WHEN** an exporter would omit canonical interface identity or direction
- **THEN** validation fails the artifact before output publication

### Requirement: Stable issue envelope and full source trace
All operations SHALL return one envelope with `ok`, `valid` when applicable,
structured `issues.errors` and `issues.warnings`, reconciled summary counts,
selection identities, artifact outcomes, and source locations. Every issue
SHALL retain applicable file/workbook, YAML path or sheet/row/column, roadmap,
order, change, operation, state, view, entity, interface, diagram, and
artifact identities.

#### Scenario: Reconcile result counts
- **WHEN** validation returns errors and warnings across multiple sources
- **THEN** summary counts exactly match issue arrays and no issue is hidden by
  an `ok` or `valid` value

#### Scenario: Preserve trace through generated operation
- **WHEN** a generated cascade removal causes a downstream report/export issue
- **THEN** the issue traces through generated operation, initiating change and
  ancestor, canonical entity/interface, and authored source location

### Requirement: Validation and acceptance use executable fixtures
Every normative scenario SHALL map to an automated test or explicit executable
verification fixture using the production path. Required acceptance tests SHALL
not count as complete while skipped, expected-failing, mock-only, or replaced by
manual assertion.

#### Scenario: Refuse skipped acceptance proof
- **WHEN** a required YAML/Excel, explorer, interface, diagram, SVG/Draw.io,
  offline, accessibility, or cleanup acceptance test is skipped or xfailed
- **THEN** its implementation task remains incomplete

### Requirement: Renderer-boundary and runtime acceptance
Repository verification SHALL inventory every LikeC4 import and low-level field
and reject use outside the explicit adapter/build/compatibility allowlist.
Executable acceptance SHALL cover normalized cache keys, bounded eviction,
stale-result rejection, empty and oversized projections, actual browser node
and edge topology, URL restoration, offline operation, and deterministic
renderer-neutral geometry.

#### Scenario: Prevent renderer dependency spread
- **WHEN** a product state, projection, inspector, table, or export module imports a low-level renderer contract
- **THEN** verification fails before the generated explorer is accepted

#### Scenario: Enforce deterministic performance budgets
- **WHEN** the benchmark fixture exercises realistic systems, interfaces, groups, tags, and snapshots
- **THEN** selector projection, cache retrieval, layout dispatch, control response, and payload size remain within documented budgets

### Requirement: Cleanup is validated by absence
Validation and repository checks SHALL prove removal of public/runtime/config/
template/generated paths for snapshots, revisions, project grouping,
deployment, D2, embedded Draw.io SVG, old APIs, aliases, fixtures, tests, and
documentation.

#### Scenario: Detect a remaining compatibility path
- **WHEN** a removed v1 parameter, config key, registered operation, alias, or
  renderer remains executable
- **THEN** cleanup verification fails with its repository location
