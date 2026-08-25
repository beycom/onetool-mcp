# Architecture schema

Status: agreed design direction. The current implementation differs in several
places listed below.

## Responsibility

The Architecture schema owns:

- the organisation's architecture entities and connections;
- one authored Current State;
- sparse authored Changes;
- Roadmaps that order Changes;
- validation and replay;
- complete derived States at Roadmap endpoints;
- tombstones and generated removal consequences.

It does not own report scope, report configuration, diagrams, layout, saved
reports, or output formats.

## Model

```text
Architecture
  Current State
    Systems
      Subsystems
        Components
    Users
    Interfaces
    Relationships
  Changes
  Roadmaps
  Resolver
    Intermediate States
    Target State
    Tombstones
```

## Terms

| Term | Meaning |
| --- | --- |
| Architecture | One internally consistent architecture dataset. A different baseline belongs to a different Architecture. |
| Current State | The one complete authored architecture snapshot from which every Roadmap starts. |
| Change | An authored, explicit, sparse description of additions, changes, and removals. |
| Roadmap | A named ordered list of Change references. |
| State | A complete architecture snapshot derived at a Roadmap endpoint. |
| Target State | The final derived State of a Roadmap. It is not separately authored. |
| System | The highest-level software boundary. It may remain opaque or contain Subsystems. |
| Subsystem | A first-class, non-recursive logical division of exactly one System. |
| Component | A leaf runtime or data boundary owned by exactly one Subsystem. |
| User | A human role, persona, or group that interacts with or is affected by the architecture. |
| Interface | One realised bilateral connection between one provider and one consumer. |
| Relationship | A non-Interface semantic statement read as Source Action Target. |

These definitions guide modelling. Validation enforces structure rather than
trying to decide whether an architect chose the ideal abstraction.

## Entity structure

### Containment

```text
System
└── Subsystem
    └── Component
```

- Subsystem replaces Application. The new contract has no Application alias.
- A Subsystem belongs to exactly one System and cannot contain another
  Subsystem.
- A Component belongs to exactly one Subsystem.
- Component is always a leaf and cannot contain another Component.
- Shared runtime or data boundaries belong to an explicitly modelled shared
  Subsystem. Other Subsystems connect to them through Interfaces.
- Users sit outside the software containment tree.

Every entity has a stable unique ID. ID matching ignores case while preserving
the declaration's spelling. Parent references and connection endpoints must
resolve at the selected State.

### Common fields

System, Subsystem, Component, User, Interface, and Relationship share:

- required `id`;
- optional `description`;
- optional ordered `tags`;
- optional flat `properties`.

System, Subsystem, Component, User, and Interface require `name`. Relationship
uses required `action` instead of `name`.

Property values are nonblank strings or ordered lists of nonblank strings.
Properties do not contain nested maps or nested lists. Common architecture facts
such as technology, Interface type, and User kind belong in `properties` until
a schema rule or resolver behaviour needs a dedicated field.

Generic `group`, `notes`, `icon`, and `style` fields are excluded. Report-owned
presentation does not belong on Architecture entities.

### System

A System is a coherent body of software that provides value to people or other
systems. It is the unit used for Report scope and System hops.

### Subsystem

A Subsystem is a first-class architecture entity, not a visual grouping. It has
stable identity, lifecycle, metadata, Change history, Report representation,
and may be an Interface endpoint independently of its Components.

### Component

A Component is a runtime or data boundary such as a UI, API, gateway, database,
batch process, or serverless function. Internal code structure is outside this
schema.

### User

A User represents a human role, persona, or group such as Customer, Support
Agent, Finance Team, or System Administrator. Named individuals are discouraged
but not rejected by validation. Automated actors use System, Subsystem, or
Component.

## Interface

An Interface represents one realised connection between exactly one provider
and one consumer. A shared API used by three consumers is modelled as three
Interfaces so that each connection has its own identity and lifecycle.

Provider and consumer may each be a System, Subsystem, Component, or User. At
least one endpoint must be software. User-to-User Interfaces are invalid.
Interfaces and Relationships cannot themselves be endpoints.

Interface orientation has three independent axes:

1. Ownership is derived from provider to consumer.
2. `call_direction` records which endpoint initiates the interaction.
3. `data_flow` records the direction of the primary business data.

`call_direction` and `data_flow` each allow:

- `provider_to_consumer`
- `consumer_to_provider`
- `bidirectional`
- `unspecified`

Both default to `unspecified`. The schema does not infer them from Interface
type. The generic `direction` field is removed because it conflates ownership,
call direction, and data flow.

## Relationship

A Relationship is not an Interface. It represents a semantic association such
as owns, supports, replaces, governs, or a high-level uses statement when no
realised Interface is known.

Relationship has:

- a source endpoint;
- a required open-ended `action`;
- a target endpoint;
- an optional description.

It is read as:

```text
Source Action Target
```

Source and target are ordered, so reversing them changes the statement. Either
endpoint may be a System, Subsystem, Component, or User, including User-to-User
and mixed-level pairings. They must be different entities. Relationship has no
provider, consumer, direction, call direction, or data flow.

## Current State, Change, and Roadmap

Architecture work normally starts at Current State and moves to Target State
through one or more Changes:

```text
Current State
  -> Change 1 -> intermediate State
  -> Change 2 -> intermediate State
  -> Change 3 -> Target State
```

Only Current State is authored completely. Each intermediate State and Target
State is derived. Architects never repeat unchanged architecture for each
phase.

### Change metadata

The starter Change contract has:

- required `id`;
- required `name`;
- optional `description`;
- required `patches` grouped by entity and connection kind.

Delivery dates, delivery leads, owner, status, related products, dependencies,
groups, tags, and per-patch notes are excluded from the starter contract. They
can return only when a concrete Architecture or Report requirement needs them.

### Explicit Change intent

Every authored patch requires `change_type`:

- `added`
- `changed`
- `removed`

The resolver checks the declaration. `added` fails when the ID already exists.
`changed` and `removed` fail when the ID does not exist.

A `changed` patch lists only the new values. Omitted fields remain unchanged. A
changed parent is an explicit move, represented as `change_type: changed` plus
the new parent. A separate `moved` type is unnecessary because one patch may
move an entity and change other fields together.

A `changed` patch that produces no effective difference is a validation error.
It normally indicates stale assumptions, duplicate work, or an incorrect
Roadmap position.

### Field clearing

The scalar marker `unset` explicitly clears a supported field in a `changed`
patch. Omission means unchanged:

```yaml
description: unset
tags: unset
properties:
  owner: unset
```

It removes an optional description, empties tags, or removes one property.
Supplied property values replace those values while omitted property keys remain
unchanged. The `properties` map itself cannot be unset.

The resolver rejects `unset` in Current State, additions, removals, IDs,
required names, parents, endpoints, Relationship actions, and Interface
direction fields. Authors set a direction to `unspecified` explicitly. YAML
null and empty strings are invalid.

The `expected` previous-value map is removed. It duplicated Current State data
for little value. Internal normalised operations may still carry structural
checks such as present, absent, and parent exists.

### Removal cascades

Explicitly removing a System or Subsystem authorises the resolver to remove:

- every contained descendant;
- every Interface connected to the removed tree;
- every Relationship connected to the removed tree.

The author does not repeat these consequences as `removed` patches. The
resolver records each generated removal, links it to the explicit ancestor, and
retains its previous value as a tombstone for reporting.

### Atomicity

A Change applies atomically. If any authored or generated operation is invalid,
the resolver does not produce the State for that Roadmap endpoint. Earlier
valid Roadmap endpoints remain available.

## Roadmap

A Roadmap is deliberately small:

```yaml
roadmaps:
  - id: preferred
    changes: [phase-1, phase-2]
```

- Every Roadmap starts from the Architecture's one Current State.
- Roadmap does not repeat a `base` reference.
- List position defines Change order.
- The public `RoadmapItem {change, order}` structure is removed.
- Numeric positions may exist internally but are not public identity.
- The final Change endpoint is Target State.
- Different possible targets use separate Roadmaps from the same Current State.
- Change order exists only in Roadmap. Do not add a second implicit top-level
  order.
- A Roadmap contains at least one Change.
- One Change cannot appear twice in the same Roadmap.
- A Change may remain unreferenced while an architect prepares it for a later
  scenario.

Named checkpoint States and Roadmap-item labels are deferred.

## Resolution and validation

The resolver:

1. starts from Current State;
2. validates and applies each Change in Roadmap list order;
3. creates a complete State after each Change;
4. records authored operations, generated cascades, and tombstones;
5. stops at the first invalid Change;
6. returns the final valid endpoint or a requested earlier endpoint.

Validation includes:

- globally unique stable IDs;
- fixed containment and required parents;
- valid Interface and Relationship endpoints;
- required fields on additions;
- `change_type` existence assertions;
- changed patches that produce a real difference;
- valid moves and connection changes;
- atomic Change application;
- valid Roadmap references and order.

## State selection boundary

Architecture exposes three selectors to Report:

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

They select Current State, the State after `phase-1`, and Target State. Numeric
Roadmap positions and generated resolved-State IDs remain internal.

The question of selecting a comparison origin belongs to Report and is not part
of the settled Architecture schema.

## Canonical YAML shape

The exact authoring rules and Excel mapping live in
[Architecture file formats](file-formats.md).

```yaml
schema_version: 2

current_state:
  systems:
    - id: payments
      name: Payments
    - id: legacy-clearing
      name: Legacy Clearing
  subsystems:
    - id: payments-api
      name: Payments API
      system: payments
    - id: clearing-api
      name: Clearing API
      system: legacy-clearing
  components:
    - id: payments-db
      name: Payments Database
      subsystem: payments-api
  users:
    - id: customer
      name: Customer
    - id: payments-team
      name: Payments Team
  interfaces:
    - id: payments-to-clearing
      name: Submit clearing request
      provider: clearing-api
      consumer: payments-api
      call_direction: consumer_to_provider
      data_flow: consumer_to_provider
  relationships:
    - id: payments-owned-by-team
      source: payments-team
      action: owns
      target: payments

changes:
  - id: replace-clearing
    name: Replace legacy clearing
    description: Move clearing into the Payments System
    patches:
      systems:
        - id: legacy-clearing
          change_type: removed
      subsystems:
        - id: new-clearing
          change_type: added
          name: Clearing
          system: payments

roadmaps:
  - id: preferred
    changes: [replace-clearing]
```

## Differences from the current implementation

The current schema-v2 implementation is the starting point, not the final
contract. The agreed design requires these clean changes:

- rename Application to Subsystem and remove Application without an alias;
- replace the `states` list with one ID-less `current_state` mapping;
- make `change_type` required rather than inferred;
- reject no-op `changed` patches;
- remove authored `expected` values;
- reduce Change metadata to the starter fields;
- replace the `unset` field list with per-field `unset` values;
- restrict properties to flat string and string-list values with sparse
  per-property patches;
- replace `RoadmapItem {change, order}` with an ordered `changes` list;
- remove Roadmap `base` because one Current State is shared;
- replace Interface `direction` with `call_direction` and `data_flow`;
- change Relationship to Source Action Target with no generic direction;
- remove numeric order and generated State IDs from public selection;
- move public View definitions out of Architecture and into Report.

No backward-compatible aliases or transition fields should remain when this
contract is implemented.

## Implementation readiness

The schema decisions needed for implementation are settled. The canonical YAML
and Excel mappings, string and ID rules, clearing syntax, and round-trip
guarantees are defined in [Architecture file formats](file-formats.md).

Report Definition, comparison-origin selection, and generated-output contracts
remain deferred to the Report grill. They do not block Architecture schema
implementation.
