# Architecture schema grill

Status: Architecture schema and File Formats interviews complete. Report remains
deferred to a separate session. Started 2026-08-22.

This record separates confirmed decisions from ideas and unanswered questions.
It does not change the Architecture Pack contract.

## Split planning documents

The consolidated planning direction now lives in separate documents:

- [Architecture Pack v2 index](../index.md)
- [Architecture schema](../schema.md)
- [Report handoff](../report.md)
- [File formats](../file-formats.md)

This file remains the decision trail, including pressure tests and rejected
alternatives. When a later statement here conflicts with an earlier one, the
consolidated split documents contain the current direction.

## Goal

Break Architecture Pack v2 into clear parts and define a best-in-class pack for
modelling an organisation's architecture landscape and generating reports from
it.

## Confirmed decisions

### The pack has two main concepts

1. **Architecture** owns the organisation's architecture landscape.
2. **Report** selects and presents architecture data.

View definitions, the diagram catalogue, saved reports, and generated report
runtime data belong to the Report concept. They are not peer concepts beside
Architecture and Report.

Input and output formats are adapters around these concepts, not a third main
concept.

### The architecture landscape can model the entire organisation

An Architecture Landscape can contain the organisation's complete architecture
data. A report may select the entire landscape, a set of systems, or one system.

The packaged architecture data does not change while a generated report is
running. Reports and diagrams may still be derived from that data on demand.
The pack does not need to pre-create every possible report or diagram.

### View is not a public domain term

Do not use **View** as a public synonym for a report. Use these terms:

- **Architecture Landscape**: the complete organisation architecture dataset.
- **Report Definition**: a saved recipe that selects architecture data and
  configures report content.
- **Report**: the generated experience produced from a Report Definition.
- **Diagram**: one visual within a Report.
- **Projection**: an internal subset of nodes and edges prepared for a Diagram.

The current top-level `views` concept should be removed from the public model.
Its useful selection and configuration fields should move into Report
Definition.

### One report definition has one primary system scope

A Report Definition owns exactly one primary architecture scope. The scope
starts with a set of selected systems and may expand through a configured number
of interface hops. Most reports will start with one or two systems and include
the systems that affect them.

Every report table, count, and generated diagram derives from that scope. An
individual diagram may focus on a smaller projection, but it does not silently
widen the report scope. A materially different scope is a different Report
Definition. If reports later need grouping, use a separate Report Collection
concept rather than putting several scopes into one report.

### Report scope expands only through interfaces

Scope expansion is deliberately undirected. Starting from the selected system
set, each hop includes every system connected by an interface. Provider,
consumer, and data-flow direction do not restrict traversal.

Do not add a hop-direction setting. Generic relationships may be displayed when
relevant, but they never expand scope because their meaning does not reliably
imply architectural impact.

The resulting scope is the selected systems plus every system reachable within
`N` interface hops. Each included system should retain whether it was selected
or its shortest hop distance from the selected set.

"Blast radius" helped clarify the behavior during discussion but is rejected as
the public term. The final public term remains open.

Use **Selected systems** for the systems explicitly chosen for the report and
**Report scope** for the resulting set after scope expansion. **Scope
expansion** is the operation. **System hops** is the configured expansion
distance. The schema field is `system_hops`.

`system_hops: 0` means selected systems only. Each additional hop includes the
next systems connected through interfaces. The distance is the shortest number
of system-to-system connections from any selected system. Parallel interfaces
between the same systems count as one hop, and interfaces within one system do
not count. Replace `interface_depth` cleanly; do not retain it as an alias.

### Interfaces remain visible at the report-scope boundary

An interface whose endpoint systems are both in Report scope is an **Internal
interface**. An interface with exactly one endpoint system in Report scope is a
**Boundary interface**.

Boundary interfaces remain in the Interfaces table. A diagram represents the
excluded endpoint as a compact, labelled system stub. The stub does not add the
excluded system to Report scope, system counts, other tables, or detailed
diagrams.

### System is the top-level software boundary

- **System** is the highest-level software boundary in the Architecture
  Landscape. It represents a coherent body of software that provides value to
  people or other systems. A System may remain opaque or be decomposed into
  Subsystems.

The Architecture model defines its terms independently. External architecture
models may provide inspiration, but they do not define this contract.

### The middle architecture level is first-class

The level between System and Component is a first-class architecture entity,
not a visual grouping. It has stable identity, lifecycle, metadata, change
history, report representation, and may be an Interface endpoint independently
of its Components.

Its canonical name is **Subsystem**. A Subsystem is a first-class logical
division of exactly one System that owns a coherent set of Components. It is
non-recursive. Remove `Application` from the new contract rather than retaining
an alias. **Component group** is rejected because it understates these
semantics.

The hierarchy is:

```text
System
└── Subsystem
    └── Component
```

### Component ownership is singular

Every Component has exactly one owning Subsystem. A Component cannot be
contained by several Subsystems. Other Subsystems use a shared Component
through Interfaces. A runtime or data boundary with no natural owning
Subsystem belongs to an explicitly modelled shared Subsystem.

### Component is the leaf architecture level

A Component cannot contain another Component. It is a runtime or data boundary
within one Subsystem, such as a UI, back-end API, gateway, database, batch
process, or serverless function. Internal code structure is outside the
canonical Architecture Landscape.

### User represents human actors

A User is a human role, persona, or group that interacts with or is affected by
the architecture. Examples include Customer, Support Agent, Finance Team, and
System Administrator. Prefer stable roles, personas, and groups over named
individuals. Automated actors should be represented as Systems, Subsystems, or
Components. User should not become a catch-all for entities outside the
containment hierarchy.

### Definitions guide modelling; structure remains strict

System, Subsystem, Component, and User definitions are canonical modelling
guidance, not attempts to validate organisational meaning. The schema should
not infer whether a name describes a person, database, runtime, or logical
boundary.

Structural rules remain strict and machine-enforced: stable and unique IDs,
valid entity kinds, fixed containment levels, exactly one required parent,
non-recursive Components, and valid connection endpoints. Semantic flexibility
must not weaken these structural invariants.

This boundary applies to every Architecture entity. Validation reports
structural violations, not opinions about whether the modeller chose the ideal
entity kind.

### Interface is a bilateral realised connection

An Interface represents one realised connection between exactly one provider
endpoint and exactly one consumer endpoint. It is not a reusable contract with
many consumers.

When several consumers use the same API or protocol, model one Interface per
provider-consumer pair. Those Interfaces may share contract or technology
metadata, while retaining independent identity, lifecycle, and change history.

### Interface endpoints support mixed detail

An Interface provider and consumer may each be a System, Subsystem, Component,
or User. At least one endpoint must be a System, Subsystem, or Component;
User-to-User Interfaces are invalid. Interfaces and Relationships cannot be
connection endpoints.

Endpoints may use different detail levels so a detailed Component can connect
to an opaque external System. Scope expansion rolls Subsystem and Component
endpoints up to their owning Systems. User endpoints do not add systems.

### Provider and consumer define Interface orientation

`provider` owns or exposes the Interface. `consumer` uses or depends on it. The
ownership orientation is provider to consumer. Remove the generic `direction`
field cleanly because it conflates several independent meanings.

Interface orientation has three independent axes:

1. **Ownership** is derived from `provider` to `consumer`.
2. **Call direction** records which endpoint initiates the interaction.
3. **Data flow** records the direction of the business data.

Neither call direction nor data flow changes Interface identity,
provider/consumer roles, or scope expansion.

### Interface data flow is explicit

`data_flow` is a typed Interface field with three values:

- `provider_to_consumer`
- `consumer_to_provider`
- `bidirectional`

The field does not affect System hops or Interface identity.

The default is reopened. For a consumer calling a provider's REST API, the
request travels consumer to provider and the response travels provider to
consumer. The intended `data_flow` meaning appears to be the primary business
payload rather than raw request/response traffic; under that meaning the common
REST default is `provider_to_consumer`, not `bidirectional`.

Add a separate typed `call_direction` field using the same directional values
as `data_flow`. For a consumer calling a provider's API,
`call_direction=consumer_to_provider`; the returned business data may use
`data_flow=provider_to_consumer`.

Reports may switch connection arrows among Ownership, Call direction, and Data
flow without changing the underlying Report scope or Diagram projection.

Pattern pressure test:

| Pattern | Ownership | Call direction | Data flow |
| --- | --- | --- | --- |
| REST query | provider to consumer | consumer to provider | provider to consumer |
| REST command or upload | provider to consumer | consumer to provider | consumer to provider, or bidirectional |
| File download by pull | provider to consumer | consumer to provider | provider to consumer |
| File upload to owned endpoint | provider to consumer | consumer to provider | consumer to provider |
| Event or publication | provider to consumer | provider to consumer | provider to consumer |
| User interaction | system provider to user consumer | usually consumer to provider | usually bidirectional |

No directional default is correct for every pattern. Do not infer either field
from Interface type unless a future explicitly configured vocabulary defines
that behavior.

Both `call_direction` and `data_flow` allow these values:

- `provider_to_consumer`
- `consumer_to_provider`
- `bidirectional`
- `unspecified`

Both default to `unspecified`. A report renders a neutral connection when the
active mode has no specified direction. Do not silently substitute ownership
direction.

The distinction among Ownership, Call direction, and Data flow is a core
product idea. The schema reference, report controls, Interface table, Diagram
arrows, legend, and details must explain which axis is active rather than using
an ambiguous generic direction.

The Report can switch among these three Interface aspects without changing
Report scope or Diagram membership:

- **Ownership** derives arrows from provider to consumer.
- **Call direction** uses `call_direction`.
- **Data flow** uses `data_flow`.

Switching the aspect changes arrows, labels, legend, and related table emphasis.
It does not resolve a different Architecture state or Projection.

### Relationship is a non-Interface semantic association

A Relationship is one typed semantic association between one source and one
target. It does not represent an Interface. Examples include `owns`, `supports`,
`replaces`, `governs`, or a high-level `uses` association where Interface
details are unknown.

Relationships do not have provider, consumer, call direction, or data flow.
They never contribute to System hops or expand Report scope.

### Relationship endpoints are flexible

Relationship source and target may each be a System, Subsystem, Component, or
User. Any pairing is allowed, including User-to-User and mixed detail levels.
Source and target must be different entities. Interfaces and Relationships
cannot themselves be endpoints.

Relationships appear when relevant to Report scope but never expand that scope.

### Relationship is an ordered statement

A Relationship has no direction or orientation field. It is read as:

```text
Source Action Target
```

For example, `Team A Owns Payments`. Source and target are semantically ordered;
reversing them changes the statement. Reports render the action as the
connection label and may use a neutral line rather than Interface-style flow
arrows.

`action` is required, non-blank, and open-ended. It replaces Relationship
`name` and `type`. The action should be a verb or verb phrase that reads
naturally between source and target. Relationship `description` remains
optional.

### State is a derived architecture snapshot

The normal authoring workflow defines one complete Baseline and then authors
sparse Changes. A Roadmap applies those Changes in order. Each Roadmap endpoint
is a derived, complete State representing the architecture at that phase.

Architects do not repeat unchanged architecture in each phase. They author only
the Change for that phase:

- a new stable ID introduces an entity or connection;
- an existing stable ID with supplied fields changes those fields;
- a changed parent moves the entity;
- removal is explicit;
- clearing a field is explicit;
- omitted entities and fields are unchanged.

The base is order 0. Applying the first Change derives the State at order 1;
applying the next derives the State at order 2, and so on. Reports select a
Roadmap endpoint and consume its resolved State.

### Change is authored and reusable

A Change is the compact, natural authoring unit for what differs. It owns the
delivery metadata and sparse entity patches but not its sequence. The same
Change may appear in more than one Roadmap.

Normalization derives internal add, modify, move, and remove operations from
the authored Change. State comparison may also derive a cumulative Change for
reporting, but that does not replace the authored delivery Changes.

### Current State to Target State

Architecture planning starts with the Current State as the authored Baseline. A
Roadmap applies one or more authored Changes to that Current State. Replay
derives a State after each Change, and the State at the final Roadmap endpoint is
the Target State.

```text
Current State
  -> Change 1 -> intermediate State
  -> Change 2 -> intermediate State
  -> Change 3 -> Target State
```

A simple Roadmap may contain one Change, so its first derived State is also its
Target State. Alternative targets use different Roadmaps from the same Current
State.

Target State is not a separately authored entity. It is always the final
derived endpoint of a Roadmap. This matches the way architecture is normally
documented and communicated: Current State, a path of Changes, and the resulting
Target State.

### Minimal Roadmap starter contract

Do not add named checkpoint States yet. Keep the author-facing story to three
parts:

```text
Current State + ordered Changes = Target State
```

The existing Roadmap remains useful because it owns the base and the order. It
also leaves room for alternative paths later without changing Change semantics.
For the confirmed starter contract:

- Roadmap needs only identity, base, and ordered Change references;
- Change needs identity, a readable name, and sparse entity patches;
- add and modify may be inferred from stable-ID existence;
- removal and property clearing remain explicit;
- delivery dates, ownership, groups, dependencies, checkpoint labels, and other
  metadata remain optional or can be deferred from the first documented path;
- the final Roadmap endpoint is the Target State.

Do not introduce both an implicit top-level Change order and an explicit
Roadmap mode. Two ways to express the same path would make loading, validation,
Excel parity, and documentation harder. Retaining the explicit Roadmap is the
smaller overall model because the implementation already uses it.

### Every authored Change is explicit

Every authored entity and connection patch requires `change_type`. This adds a
small amount of text but makes the architect's intent clear:

```yaml
- id: A
  change_type: changed
  description: Updated description
- id: B
  change_type: added
  name: New System
- id: D
  change_type: removed
```

The value is also an assertion checked during replay. `added` fails if the ID
already exists, and `changed` fails if it does not. This catches incorrect
Roadmap order and stale assumptions instead of silently changing the meaning of
the Change. A Change that needs different existence semantics in another
Roadmap is not actually the same reusable Change.

The costs are repetitive YAML or Excel cells and tighter coupling to the
expected prior State. These are acceptable for deliberate architecture work.
Generated cascade removals do not need separate authored rows or
`change_type` values.

Explicit removal of a System or Subsystem authorises the resolver to remove its
contained descendants and every Interface or Relationship connected to the
removed tree. The resolver records each consequence as a generated removal,
links it to the explicit ancestor removal, and retains a tombstone for reports.
Requiring separate authored removal patches for those consequences would add
duplication and allow the authored Change to contradict containment validity.

The author also states the changed values explicitly. A `changed` patch may omit
unchanged fields, but it must supply a real mutation through a new value, a new
parent, changed endpoints, or `unset`. The resolver:

- checks that `added` IDs are absent;
- checks that `changed` and `removed` IDs exist;
- checks parents, endpoints, and required fields;
- rejects or diagnoses ineffective and conflicting patches;
- expands removal cascades;
- materialises the derived State and its tombstones.

`change_type` describes authored intent at entity level. A distinct `moved`
type is unnecessary because a move may occur together with property changes;
`change_type: changed` plus an explicitly changed parent expresses both.

An explicitly authored `changed` patch that produces no effective difference is
a validation error. It usually means the Change is stale, duplicated, or placed
after another Change that already produced the same result. Description-only
notes belong on the Change itself rather than in a no-op entity patch.

### No authored previous-value assertions

The `expected` map has low value in the starter contract. It duplicates values
from the Current or preceding derived State and makes ordinary Changes harder to
author. It is removed from the public Change schema rather than retained as a
rarely used optional feature.

The resolver still validates required `change_type` intent, entity existence,
real differences, parents, endpoints, references, and Roadmap order. Internal
normalised operations may retain structural preconditions such as present,
absent, and parent exists. Those are resolver details, not authored fields.

An `arch.diff`-generated Change will no longer carry exact previous-field
assertions. It remains explicit and replayable, with the same existence and
structural checks as an authored Change. This is an acceptable loss for the
simpler contract.

### Explicit field clearing uses unset

The later File Formats grill changed the physical spelling while retaining this
schema decision. `unset` now appears as the value being cleared:

```yaml
description: unset
tags: unset
properties:
  owner: unset
```

Omitting a YAML field or leaving an Excel patch cell blank means unchanged. The
resolver rejects attempts to clear IDs or other required fields. YAML null is
not a clearing instruction.

### Minimal Change metadata

The starter Change schema has required `id`, `name`, and `patches`, plus optional
`description`. Delivery dates, delivery leads, ownership, status, related
products, dependencies, groups, tags, and per-patch notes are not part of the
starter contract. They can be reconsidered with concrete reporting needs rather
than carried forward speculatively.

### Roadmap is a direct ordered Change list

The domain meaning of a Roadmap is an ordered list of Change references over a
base. YAML represents it directly:

```yaml
roadmaps:
  - id: preferred
    changes: [phase-1, phase-2]
```

This removes the `RoadmapItem` object, repeated `order` values, and validation
for gaps or duplicate orders. List position is the order. Report selection can
still use a Change ID or zero-based base endpoint.

Excel uses one row per Roadmap Change. Row order defines Change order, matching
YAML list order. Each Roadmap occupies one contiguous block of rows.

The public `RoadmapItem {change, order}` structure is removed. Numeric order is
derived from list position when needed for resolution or reporting.

### Roadmaps share the Current State

Each Architecture has exactly one authored Current State, so every Roadmap
starts there. Roadmap does not repeat a `base` reference. A genuinely different
baseline belongs to a different Architecture dataset.

The minimal Roadmap is therefore:

```yaml
roadmaps:
  - id: preferred
    changes: [phase-1, phase-2]
```

### Reports select Roadmap endpoints

The public Architecture-to-Report State selector has three forms:

```yaml
state: current
```

```yaml
roadmap: preferred
through: phase-1
```

```yaml
roadmap: preferred
```

These select Current State, the intermediate State after `phase-1`, and Target
State respectively. Numeric positions and generated resolved-State IDs are
internal details and do not appear in authored Report Definitions.

## Working shape

```text
Architecture
  Landscape
  Entities
  Authored Baseline
  Authored sparse Changes
  States derived at Roadmap endpoints
  Roadmaps
  Load, validate, replay, resolve

Report
  Report definitions
  Diagram catalogue
  Saved reports
  Tables and diagrams
  Runtime projections, layout, scenes, and interactions
  Generated outputs
```

This shape is provisional below the two confirmed top-level concepts. Each part
still needs to be grilled.

## Ideas to test

- Replace the internal name `ViewGraph` with `DiagramProjection` if the latter
  remains accurate after the report and diagram contracts are settled.
- Package an immutable, indexed architecture dataset with an offline report,
  then derive report and diagram projections from it at runtime.
- Treat saved report definitions as useful recipes, not as an exhaustive list
  of every report the architecture data can support.
- Keep architecture authoring formats separate from report output formats:
  architecture may accept YAML and Excel, while reports may emit HTML, SVG,
  PNG, and other explicitly supported artifacts.

## Open questions

1. Should a Report select one State and optionally select a comparison origin
   using the same Current/Roadmap/through grammar?
2. What exact data contract crosses from Architecture into Report?
3. What are the precise semantics of User, Interface, and Relationship?
4. How should State, Change, and Roadmap divide responsibility?
5. What belongs in the Diagram catalogue versus a Report Definition?
6. Which report choices are durable, and which runtime interactions are
   transient?
7. Is saved diagram placement part of Report v2, and if so, what intent is
   persisted?
8. What are the supported input, saved-definition, runtime, and output formats?

## Next decision

Decide whether snapshot and comparison Reports share one State-selection model.

## External tool comparison for partial States

The useful distinction is not complete files versus partial files. It is among
three different operations:

1. **Model composition** combines several source files into one current model.
2. **Report or diagram selection** shows part of that model without changing it.
3. **Temporal modelling** represents the architecture at another time or in a
   proposed scenario.

Partial source files and partial diagrams do not establish temporal
omission-as-unchanged semantics.

### Structurizr

Structurizr's workspace wraps one architecture model and its views. DSL
`!include` does not create a partial state. The parser inlines each fragment
into the parent document in discovery order. Workspace extension similarly
starts with a base workspace and adds elements, relationships, views, or
details to the resulting workspace. See the official
[Includes](https://docs.structurizr.com/dsl/includes) and
[Workspace extension](https://docs.structurizr.com/dsl/cookbook/workspace-extension/)
documentation.

Views are selections over the workspace model. Their `include` and `exclude`
rules determine what a diagram contains, so omission from a view does not mean
removal from the model. See the
[DSL language reference](https://docs.structurizr.com/dsl/language).

Structurizr can retain previous workspace versions when a new workspace is
pushed. The push workflow sends a local DSL or JSON workspace, merges remote
diagram layout information by default, and can archive the previous workspace.
It does not merge omitted model elements from the remote version into the new
model. Structurizr branches also have no built-in merge, rebase, or diff. The
official guidance delegates those operations to version control. See
[Push](https://docs.structurizr.com/push),
[Workspace versioning](https://docs.structurizr.com/server/workspace-versions),
and [Workspace branches](https://docs.structurizr.com/cloud/workspace-branches).

Structurizr therefore supports partial files as build-time composition and
partial diagrams as projections. Its published DSL does not define a temporal
partial state in which an omitted model item means "inherit it from the prior
state".

### LikeC4

LikeC4 makes the composition rule explicit: it recursively reads the project's
source files and merges them into one architecture model. Separate files can
extend existing elements and relationships, but they are fragments of the same
current model. See
[Introduction](https://likec4.dev/dsl/intro/) and
[Extending model](https://likec4.dev/dsl/extend/).

LikeC4 views are generated projections of that model. Predicates select which
elements and relationships appear, and model edits update the views. A dynamic
view describes the ordered interactions in a use case; it is not a historical
or future architecture snapshot. See
[Views](https://likec4.dev/dsl/views/),
[View predicates](https://likec4.dev/dsl/views/predicates/), and
[Dynamic views](https://likec4.dev/dsl/views/dynamic/).

The reviewed LikeC4 DSL documentation does not define temporal States,
roadmaps, or architecture diffs. Splitting a model into files cannot supply
those semantics because every file contributes to the same current model.

### IcePanel

IcePanel also separates a shared model from diagrams. A landscape owns the
shared model and a set of diagrams. Diagrams may show only selected objects.
Removing an object from a diagram does not remove it from the model; permanent
removal is a separate model operation. See
[Landscapes](https://docs.icepanel.io/core-features/landscape) and
[Diagramming](https://docs.icepanel.io/core-features/diagramming).

IcePanel versions are static snapshots of a design at a specific point in
time. They can be taken at landscape, domain, system, or app scope, then viewed
on a timeline or reverted. See
[Versioning](https://docs.icepanel.io/future-state-design/versioning).

Future design uses Drafts rather than partial snapshots. A Draft starts from
the current model, isolates edits, and records additions, updates, and removals.
Review and merge lists those changes, rejects conflicts, and creates a new
model version after merge. See
[Drafts](https://docs.icepanel.io/future-state-design/drafts).

IcePanel is the closest match to the intended workflow, but its concepts remain
separate: a Draft is a change set over a base, while a Version is the resulting
static snapshot.

### Pressure-test result

Calling the proposed object a partial `State` blurs snapshot and patch
semantics. If omission means unchanged, the object must identify a base and
define explicit rules for:

- removal of an entity or connection;
- clearing an optional field versus leaving it unchanged;
- adding versus updating an ID;
- moving an entity between parents;
- ordering and conflict detection when several partial States build on one
  another.

Those are Change semantics. A desired-state overlay can still be easier to
author than a list of explicit operations. Stable IDs let the resolver infer
add versus update, and a changed parent lets it infer a move. The author must
still mark removals and field clears explicitly. Each overlay is also
order-dependent unless it declares its base.

A different, coherent meaning of partial is **scope-complete**: for example, a
State declares System A as its scope, is complete within System A, and says
nothing about the rest of the Landscape. Inside the declared scope, omission
can mean removal; outside it, omission means out of scope. This would need firm
rules for cross-boundary Interfaces, entities moving into or out of scope, and
validation of referenced external endpoints. It is a new capability, not a
simpler spelling of the current State contract.

The current implementation already uses a useful hybrid. `CompleteState`
contains complete entity lists. An authored `Change` contains sparse
desired-state patches. The normalizer infers add or update from ID existence and
infers a move from a changed parent; removal and field clearing remain explicit.
Roadmap replay then produces complete resolved States and tombstones.
`compare_states` can also derive a net Change by comparing two complete States.

Under the current code, omitted lists in an authored State default to empty and
comparison treats IDs missing from the target as removals. A partial State with
omission-as-unchanged is therefore not the implemented behavior. Most of its
proposed convenience already exists in the sparse Change authoring contract.
See
`src/otdev/tools/_arch/v2/models.py:145`,
`src/otdev/tools/_arch/v2/models.py:238`,
`src/otdev/tools/_arch/v2/compare.py:30`, and
`src/otdev/tools/_arch/v2/normalize.py:334`.

### Confirmed direction after concrete walkthrough

The existing mechanism is correct:

- one complete Baseline is authored once;
- Changes are authored sparsely;
- omission in a Change means unchanged;
- removal and property clearing are explicit;
- Roadmaps order Changes over the Baseline;
- every Roadmap endpoint derives a complete State for reporting;
- `arch.diff` may derive a cumulative comparison Change between two States, but
  this is separate from the authored delivery Changes.

The canonical fixture demonstrates the model. Its 2027 Change modifies System
A, introduces B and C, and explicitly removes D. Systems E through H do not
appear in the Change and remain untouched. Removing D cascades to its
Application, Component, and connected Interface. Replay produces the derived
State `arch-v2-base@preferred:1` containing Systems A, B, C, E, F, G, and H.

The temporary idea of authoring sparse Phase States and deriving all Changes
was rejected. Architects describe each phase through its Change; the State of
the architecture at that phase is the replay result.
