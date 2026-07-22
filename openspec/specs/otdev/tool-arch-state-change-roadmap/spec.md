# tool-arch-state-change-roadmap Specification

## Purpose

Defines schema-v2 architecture states, sparse changes, normalized replay, roadmap resolution, comparison, materialization, and portable workspaces.

## Requirements

### Requirement: Complete state and sparse change schema
The tool SHALL accept schema-v2 workspaces containing complete states,
metadata-bearing changes with sparse patches, and named roadmaps that reference
a complete base state and apply changes in explicit order. A change SHALL have a
stable string ID, common typed attributes, preserved extension attributes, and
patch groups for every supported architecture entity type. It SHALL NOT define
a separate project or project-group entity.
System and change `group` attributes SHALL be optional ordered string lists.

#### Scenario: Author a base and two independent delivery changes
- **WHEN** a workspace defines complete base state `base`, changes `2027` and
  `2028`, and roadmap `preferred` with those changes at orders 1 and 2
- **THEN** both changes are independently addressable and the roadmap base is
  the implicit order 0

#### Scenario: Preserve change extension metadata
- **WHEN** a change contains additional YAML properties or Excel columns not
  assigned behavior by the typed schema
- **THEN** the tool preserves them as extension metadata without interpreting
  them as replay operations

#### Scenario: Select reusable groups
- **WHEN** systems share a system group or changes share a change group
- **THEN** the system group selects its member systems and the change group
  selects the union of systems impacted by its changes

### Requirement: Compact patch semantics
The tool SHALL treat omitted entities and omitted YAML properties or blank
Excel property cells as no operation. It SHALL treat `unset` as an explicit
property clear, `change_type=removed` as explicit removal, and `change_note` as
descriptive context only. It SHALL derive add versus modify from entity
existence unless an authored add/change assertion is supplied.

#### Scenario: Modify A without copying stable systems
- **WHEN** change `2027` supplies only a new description for A, additions B/C,
  and explicit removal of D while omitting E-H
- **THEN** A is modified, B/C are added, D is removed, and E-H are unchanged

#### Scenario: Blank differs from unset
- **WHEN** a patch leaves `technology` blank or omitted in one case and lists
  `technology` in `unset` in another
- **THEN** the blank/omitted case preserves the current value and the explicit
  unset case clears it

#### Scenario: Authored change assertion detects reorder error
- **WHEN** a patch asserts `changed` for an entity but the roadmap places it
  before the change that adds that entity
- **THEN** validation fails instead of converting the asserted modification to
  an add

### Requirement: Roadmap-wide impacted-system derivation
The tool SHALL derive change and change-group system indexes by replaying every
roadmap transition and comparing before/after ownership. Direct system patches,
descendant patches, containment moves, interface endpoints, relationship
endpoints, actor-connected endpoints, and generated cascades SHALL contribute
deterministic source-traced impact reasons. Selectors SHALL remain valid at
snapshots where a selected system is not yet or is no longer present.

#### Scenario: Move an application between systems
- **WHEN** a change moves an application from system A to system B
- **THEN** both A and B are impacted with distinct moved-from and moved-to reasons

#### Scenario: Select a future change at base
- **WHEN** a base snapshot selects a change that later adds system D
- **THEN** D remains a valid selected system and is reported as not yet present

#### Scenario: Include generated cascade impact
- **WHEN** removing a system generates descendant, interface, and relationship removals
- **THEN** every affected owning or endpoint system is indexed with the cascade source trace

### Requirement: Normalized operations and replay preconditions
The tool SHALL normalize YAML and Excel patches to `add`, `modify`, `move`, and
`remove` operations. Operations SHALL validate entity existence, required
parents, acyclic containment, interface endpoints, required addition fields,
and authored or generated field preconditions at their application point.

#### Scenario: Normalize a containment change
- **WHEN** an existing component patch changes its parent to a valid application
- **THEN** the tool records an internal `move` operation and exposes contextual
  status `change`

#### Scenario: Reject modify before add
- **WHEN** roadmap order applies a modification to `sys_x` before another change
  adds `sys_x`
- **THEN** replay fails at that roadmap order with the change, operation,
  entity, and source location

#### Scenario: Reject stale derived precondition
- **WHEN** a derived change expects a field value from its derivation base but
  replay finds a different current value
- **THEN** the tool rejects that operation as an incompatible stale assumption

### Requirement: Cascading containment removal
Removing a containment parent SHALL generate normalized removals for all
contained descendants and every interface connected to the removed subtree.
Generated removals SHALL record the initiating change, explicit ancestor,
cascade path or cause, and authored source location. Duplicate explicit and
generated removal of the same child SHALL normalize once.

#### Scenario: Remove a system subtree
- **WHEN** change `2027` explicitly removes system D containing applications and
  components connected through interface `A-to-D`
- **THEN** the resolved state excludes D, all descendants, and `A-to-D`, while
  the change report retains tombstones and distinguishes the explicit removal
  from generated cascade effects

#### Scenario: Deduplicate an explicit child removal
- **WHEN** one change explicitly removes a system and one of its children
- **THEN** the generated cascade contains one normalized removal for the child
  and retains the explicit source context

### Requirement: Deterministic roadmap resolution
The tool SHALL replay roadmap changes by unique contiguous positive `order`
values starting at 1, with base at order 0, and SHALL resolve every valid
order to a complete state. A selected roadmap without an endpoint SHALL
resolve its final change. The tool SHALL NOT rewrite authored roadmap order.

#### Scenario: Resolve through ID or numeric order
- **WHEN** change `2027` occupies order 1 and the user resolves once through
  `2027` and once through order 1
- **THEN** both requests return semantically identical complete states

#### Scenario: Resolve the base
- **WHEN** the user selects `through=base` or `order=0`
- **THEN** the tool returns the complete roadmap base without requiring a base
  change or roadmap row

#### Scenario: Diagnose invalid reordering
- **WHEN** a user-authored roadmap places a dependent change before the change
  satisfying its preconditions
- **THEN** the tool reports the supplied order as invalid and may suggest a
  dependency or alternate order without modifying the roadmap

#### Scenario: Warn on result-sensitive valid ordering
- **WHEN** two orders both satisfy operation preconditions but resolve to
  different complete states
- **THEN** validation emits a stable `order_sensitive` warning describing the
  affected changes and fields

### Requirement: State comparison and derived changes
The tool SHALL compare complete states by stable entity and interface IDs,
derive additions, removals, property modifications, moves, and relationship
changes, and distinguish cumulative net differences from contributing replay
history. A materialized derived change SHALL require an explicit stable
`change_id` and SHALL contain base/target identities plus generated
preconditions.

#### Scenario: Derive the authored 2027 change
- **WHEN** complete authored base and target states encode the same outcome as
  the canonical 2027 sparse change
- **THEN** `arch.diff` derives semantically identical normalized operations

#### Scenario: Preserve canceled contributing history
- **WHEN** an entity is added and removed between the comparison origin and
  selected endpoint
- **THEN** it is absent from the cumulative net difference but both operations
  remain in contributing history

#### Scenario: Require identity for materialized change
- **WHEN** `arch.diff` is asked to write a derived change without `change_id`
- **THEN** it fails rather than inventing an identity from a file name

### Requirement: State materialization
The tool SHALL implement `arch.resolve(input_path, output_path, state=None,
roadmap=None, through=None, order=None, output_state_id=None)` to materialize exactly one complete
state, infer YAML or Excel from the output extension, and use either the
explicit output ID or a documented deterministic selection-derived ID.

#### Scenario: Materialize the 2027 state in both formats
- **WHEN** the user resolves roadmap `preferred` through `2027` to YAML and to
  Excel
- **THEN** both files contain semantically equivalent complete architecture and
  no sparse change rows

### Requirement: Workspace initialization and portable bundle
`arch.init(output_path, template="solution")` SHALL create a schema-v2
workspace containing matching YAML and Excel examples, the bundled clean theme,
and view, style, and local-asset folders. `arch.bundle(input_path, output_path,
include_generated=False)` SHALL produce a deterministic archive containing all
sources and local assets required to reproduce the workspace and SHALL include
only manifest-owned generated outputs when requested.

#### Scenario: Initialize a canonical solution workspace
- **WHEN** the user runs `arch.init` with the default template
- **THEN** the output contains paired examples whose base, changes, roadmap,
  views, and diagrams normalize identically

#### Scenario: Reproduce from an offline bundle
- **WHEN** a generated bundle is copied to a path containing spaces and opened
  or regenerated with network access blocked
- **THEN** every included source, view, style, icon, and attachment resolves
  locally and generated content is reproducible

### Requirement: Removed v1 contracts fail normally
The tool SHALL remove revision-set, project/project-scope, deployment,
D2, embedded Draw.io SVG, and removed v1 operation names or parameters from the
registered API, schemas, configuration, templates, and runtime. The tool SHALL
NOT accept aliases, shims, or compatibility branches.

#### Scenario: Call a removed revision parameter
- **WHEN** a caller supplies a removed revision or project-scope parameter to a
  v2 operation
- **THEN** the current signature or schema validation path rejects it
