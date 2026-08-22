# Architecture schema v2: summary, pressure test, and ideas

Status: working design record for the experimental `arch-v2` branch, 2026-08-22.

This document describes the implemented schema-v2 contract, shows equivalent
YAML and Excel authoring, tests the design against likely report-v2 needs, and
records improvement ideas. It does not change the public schema or claim that
the ideas are implemented.

## Executive summary

Schema v2 has a sound core. It separates complete architecture state from
sparse delivery changes, applies changes through deterministic roadmaps, and
resolves saved views into one renderer-neutral graph. Stable IDs, explicit
removal, stale-value preconditions, removal cascades, source locations, and
YAML/Excel semantic parity make the state engine a credible base for report-v2.

The schema is strongest as an architecture facts and change model. It is less
settled at its boundaries:

- Excel is a compact, single-base representation rather than a complete
  representation of every valid YAML workspace.
- Presentation is deliberately configured outside portable YAML and Excel.
- Extension fields are preserved but have no shared vocabulary or validation.
- The layout result represents generated geometry, but there is no contract for
  durable user placement, locked shapes, locked connection points, or partially
  constrained auto-layout.
- The current report-v2 requirements explicitly exclude persisted layout
  coordinates and general manual placement. Adding saved placement is therefore
  a product and schema decision, not a small renderer feature.

The recommended sequence is to stabilise the existing state/change contract,
make the portability boundaries explicit, then design report-v2 around the
same resolved graph. If saved diagram placement is wanted, persist only user
layout intent as optional report-level constraints. Continue to derive the full
scene. This allows new nodes to be auto-laid out without moving locked content.

## 1. The schema's role

Schema v2 represents four related things:

1. Architecture facts in one or more complete states.
2. Sparse, independently addressable changes to those facts.
3. Ordered roadmaps that replay changes from a complete base.
4. Reusable selections and authored diagram catalogue entries.

It does not treat a rendered diagram as the architecture model. Layout,
viewport, generated routes, report grid state, and transient selection are
separate concerns.

The implemented top-level envelope is:

| Field | Meaning | Required |
| --- | --- | --- |
| `schema_version` | Exact portable schema version. Currently `2`. | Yes |
| `states` | Complete architecture states. | Yes, but the list may be empty for a derived-change artifact |
| `changes` | Sparse delivery changes. | No |
| `roadmaps` | Named linear applications of changes over a base state. | No |
| `views` | Named selections for state, comparison, focus, scope, and presentation choice. | No |
| `diagrams` | Catalogue of generated, static, dynamic, or external diagrams. | No |

The runtime model also contains `presentation`, but loaders supply that from
strict `tools.arch` configuration. Portable YAML and Excel reject authored
presentation configuration. See
`src/otdev/tools/_arch/v2/models.py:440` and
`src/otdev/tools/_arch/v2/load.py:151`.

## 2. Canonical architecture model

### 2.1 Identity and extensibility

Every state entity, change, roadmap, view, and diagram has a stable, non-blank
string ID. Entity IDs must be unique across entity kinds within one complete
state. Names are labels and can change without changing identity.

Authored facts are extensible. Unknown fields on states, entities, changes,
roadmaps, and diagram entries are preserved as metadata. Structural and
runtime contracts are strict and reject unknown fields. This supports local
metadata such as `portfolio_code` without allowing arbitrary fields into the
replay or layout machinery.

### 2.2 Entity kinds

| Kind | Required facts | Important optional facts | Containment or endpoints |
| --- | --- | --- | --- |
| `system` | `id`, `name` | description, tags, group, notes, icon, style, properties | Top-level container |
| `application` | `id`, `name`, `system` | technology and common facts | Contained by one system |
| `component` | `id`, `name`, `application` | technology and common facts | Contained by one application |
| `user` | `id`, `name` | open `kind` and common facts | May be an interface or relationship endpoint |
| `interface` | `id`, `name`, `provider`, `consumer` | direction, type, technology, tags, properties | Directed integration between canonical endpoints |
| `relationship` | `id`, `name`, `source_id`, `target_id` | direction, type, tags, properties | Generic non-interface connection |

Canonical endpoints may be systems, applications, components, or users.
Interfaces and relationships are first-class entities, not nested attributes.
The distinction matters: interface hops expand report scope; generic
relationships do not.

Common style fields are `icon`, `shape`, `color`, `size`, `position`,
`node_size`, `padding`, `text_size`, `opacity`, `border`, and `multiple`.
`position` is currently an unstructured string and is not consumed by the v2
layout path. It must not be mistaken for durable x/y placement. See
`src/otdev/tools/_arch/v2/models.py:77` and
`src/otdev/tools/_arch/v2/models.py:93`.

### 2.3 Complete states

A state is a complete snapshot, not a delta. It owns the six entity lists plus
optional name, description, properties, source trace, and extension metadata.

Containment is fixed to:

```text
system
└── application
    └── component
```

Users are external to that containment tree. Interfaces and relationships link
valid endpoint entities. A state with missing parents or endpoints is invalid.

### 2.4 Sparse changes

A change has stable metadata and six patch groups matching the entity kinds.
Useful change metadata includes:

- `name`, `description`, `deliver_date`, `delivery_lead`, `owner`, and `status`;
- `related_products`, `tags`, and list-valued `group`;
- `depends_on` for explicit change dependencies;
- preserved extension metadata.

Patch semantics are intentionally compact:

| Authored patch | Meaning |
| --- | --- |
| Entity or field omitted | No operation |
| Blank Excel cell | No operation |
| `unset: [field]` | Explicitly clear that optional field |
| New ID | Add, unless contradicted by `change_type` |
| Existing ID | Modify, unless contradicted by `change_type` |
| Changed parent | Move the application or component |
| `change_type: removed` | Explicit removal |
| `change_type: added` or `changed` | Assertion checked against the state at replay time |
| `expected: {field: value}` | Optimistic precondition that rejects a stale change |
| `change_note` | Explanation only; it does not mutate the entity |

Normalisation produces only `add`, `modify`, `move`, and `remove` operations.
Required fields cannot be unset. Additions require complete minimum facts,
parents and endpoints must exist at the application point, and an entity cannot
be patched twice by the same change. See
`src/otdev/tools/_arch/v2/normalize.py:334`.

Removing a system or application cascades to its descendants and to connected
interfaces and relationships. Generated removals retain their initiating
ancestor, cause, cascade path, and source. Removed values become tombstones so
comparison and transition views can explain what disappeared.

### 2.5 Roadmaps and replay

A roadmap identifies one complete base and a list of change/order pairs.
Order zero is always the base. Authored orders must be unique, positive, and
contiguous from one. They are never silently rewritten.

`depends_on` is enforced within each roadmap: every dependency must be present
at an earlier order. Replay stops at the first invalid change and retains every
valid earlier endpoint. Adjacent changes that are valid in either order but
produce different results generate an `arch.order_sensitive` warning. See
`src/otdev/tools/_arch/v2/replay.py:119`.

This is a linear scenario model. Alternatives are represented as separate
roadmaps sharing states and changes, not as branches inside one roadmap.

### 2.6 Views and selection

A saved view uses the same selection grammar as an ad hoc request:

| Axis | Fields |
| --- | --- |
| Snapshot | `state`, or `roadmap` with `through` or `order` |
| Comparison | `compare_from` |
| Change emphasis | `focus`, `include_future`, `visibility`, `display_statuses` |
| Scope | `system_set`, `browse_by`, `subject`, `interface_depth` |
| Representation | `projection`, `diagram`, `level`, `color_by`, `theme` |

`system_set` is a union of explicit systems, system groups, systems affected by
changes, systems affected by change groups, and tags. Only interfaces expand
the scope by `interface_depth`. State and roadmap are mutually exclusive, as
are `through` and `order`. Roadmap-only fields cannot be used with a directly
authored state. See `src/otdev/tools/_arch/v2/models.py:274`.

Default configuration, saved values, and ad hoc values merge in that order.
The normalised selection receives a deterministic content hash, which is
important for caching and for binding generated report artifacts.

### 2.7 Diagram catalogue and presentation

Diagram entries support four classes:

- `generated` for a generated architecture view;
- `static` and `dynamic` for local authored content;
- `external` for a validated local attachment or external representation.

An entry may identify source, LikeC4 view, variants, folder, and applicable
systems or changes. Diagram entries describe catalogue identity and
applicability. They do not define architecture facts.

Presentation defaults, palettes, themes, and table preferences are typed but
configured outside the portable workspace. This keeps architecture semantics
portable while allowing deployment-specific presentation.

### 2.8 Derived runtime contracts

The processing path is:

```text
YAML or Excel
    -> typed workspace plus field-level source locations
    -> validation and sparse-operation normalisation
    -> deterministic roadmap replay
    -> resolved state, comparison, history, and tombstones
    -> selection and solution projection
    -> renderer-neutral ViewGraph
    -> renderer-neutral generated layout
    -> report and export adapters
```

`ViewGraph` carries canonical nodes, hierarchy, edges, statuses, related
changes, source traces, properties, and selection identity. The current
`SolutionLayoutResult` carries absolute node bounds, edge point routes, overall
bounds, and string diagnostics. It is output geometry only. It has no authored
constraint, port, lock, label-bound, or persistence model. See
`src/otdev/tools/_arch/v2/models.py:548` and
`src/otdev/tools/_arch/v2/models.py:721`.

## 3. YAML example

This example is based on the canonical production fixture. It omits unchanged
systems E-H and adds a generic relationship, an explicit dependency, and a
broader saved view so that the main authoring forms are visible together. The
production-controlled example is
`tests/otdev/fixtures/arch_v2/arch-v2-canonical.yaml:1`.

```yaml
schema_version: 2

states:
  - id: arch-v2-base
    name: Payments baseline
    systems:
      - id: A
        name: System A
        description: Existing payment entry point
        tags: [core]
        group: [payments, core-platform]
        properties:
          owner: payments
          tier: one
      - id: D
        name: System D
        description: Retiring dependency
    applications:
      - id: app-a
        name: Application A
        system: A
      - id: app-d
        name: Application D
        system: D
    components:
      - id: cmp-d
        name: Component D
        application: app-d
    interfaces:
      - id: arch-v2-interface-a-to-d
        name: A to D
        provider: app-a
        consumer: app-d
        direction: provider_to_consumer
        type: api
    users:
      - id: customer
        name: Customer
        kind: actor
    relationships:
      - id: customer-uses-a
        name: Customer uses System A
        source_id: customer
        target_id: A
        direction: forward
        type: uses

changes:
  - id: arch-v2-change-2027
    name: 2027 delivery
    deliver_date: 2027-06-30
    owner: Team Payments
    group: [wave-one]
    related_products: [wallet, payments]
    portfolio_code: P-2027
    patches:
      systems:
        - id: A
          change_type: changed
          description: Modernized payment entry point
          change_note: Improve customer payment flow
        - id: B
          change_type: added
          name: System B
          description: New orchestration service
        - id: D
          change_type: removed
          change_note: Retire legacy dependency

  - id: arch-v2-change-2028
    name: 2028 delivery
    deliver_date: 2028-06-30
    owner: Team Ledger
    depends_on: [arch-v2-change-2027]
    patches:
      systems:
        - id: B
          change_type: changed
          description: Expanded orchestration service
          expected:
            description: New orchestration service
        - id: I
          change_type: added
          name: System I
          description: Reporting service

roadmaps:
  - id: preferred
    name: Preferred delivery
    base: arch-v2-base
    items:
      - change: arch-v2-change-2027
        order: 1
      - change: arch-v2-change-2028
        order: 2

views:
  - id: state-2027
    name: State at 2027
    roadmap: preferred
    through: arch-v2-change-2027

  - id: compare-base-2027
    name: Base to 2027
    roadmap: preferred
    through: arch-v2-change-2027
    compare_from: base
    visibility: changes_with_context

  - id: payments-target
    name: Payments target
    roadmap: preferred
    through: arch-v2-change-2028
    system_set:
      system_groups: [payments]
    interface_depth: 1
    level: application
    color_by: change_status

diagrams:
  - id: platform-delivery
    name: Platform delivery flow
    kind: dynamic
    source: views/platform-delivery.c4
    variants:
      - id: diagram
        kind: diagram
      - id: sequence
        kind: sequence
    systems: [A, B, I]
```

Important behaviour in this example:

- Systems or fields absent from a change remain unchanged.
- Removing D also removes `app-d`, `cmp-d`, and the A-to-D interface.
- `portfolio_code` is preserved extension metadata.
- The 2028 modification of B fails if the replayed description is not the
  expected 2027 value.
- The relationship does not expand the `payments-target` interface-hop scope.

## 4. Equivalent Excel example

Excel contains domain sheets, not a serialized YAML document and not a `model`
sheet. The implemented sheet set is:

| Sheet | Content |
| --- | --- |
| `change` | One row per change and its metadata |
| `roadmap` | One row per roadmap/change/order association |
| `view` | One row per saved view |
| `diagram` | One row per diagram catalogue entry |
| `sys` | Base systems and system patches |
| `app` | Base applications and application patches |
| `cmp` | Base components and component patches |
| `interface` | Base/interface patches and generic relationships distinguished by `entity_kind` |
| `usr` | Base users and user patches |

The tables below show the material columns for the YAML example. A generated
workbook may also include empty/default columns such as `tags`, `depends_on`,
or `display_statuses` because headers expand from the typed rows.

### `change`

| id | name | deliver_date | owner | group | related_products | depends_on | portfolio_code |
| --- | --- | --- | --- | --- | --- | --- | --- |
| arch-v2-change-2027 | 2027 delivery | 2027-06-30 | Team Payments | `[wave-one]` | `[wallet;payments]` | `[]` | P-2027 |
| arch-v2-change-2028 | 2028 delivery | 2028-06-30 | Team Ledger | `[]` | `[]` | `[arch-v2-change-2027]` | |

### `roadmap`

| roadmap | roadmap_name | base | change | order |
| --- | --- | --- | --- | ---: |
| preferred | Preferred delivery | arch-v2-base | arch-v2-change-2027 | 1 |
| preferred | Preferred delivery | arch-v2-base | arch-v2-change-2028 | 2 |

### `sys`

Blank `change` means a complete base row. A named `change` means a sparse patch.
State metadata can be repeated on any base rows and must agree.

| state | state_name | change | id | name | description | tags | group | properties | change_type | change_note | expected |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| arch-v2-base | Payments baseline | | A | System A | Existing payment entry point | `[core]` | `[payments;core-platform]` | `{"owner":"payments","tier":"one"}` | | | |
| arch-v2-base | Payments baseline | | D | System D | Retiring dependency | `[]` | `[]` | `{}` | | | |
| | | arch-v2-change-2027 | A | | Modernized payment entry point | | | | changed | Improve customer payment flow | |
| | | arch-v2-change-2027 | B | System B | New orchestration service | | | | added | | |
| | | arch-v2-change-2027 | D | | | | | | removed | Retire legacy dependency | |
| | | arch-v2-change-2028 | B | | Expanded orchestration service | | | | changed | | `{"description":"New orchestration service"}` |
| | | arch-v2-change-2028 | I | System I | Reporting service | | | | added | | |

### `app`, `cmp`, and `usr`

`app`:

| state | change | id | name | system |
| --- | --- | --- | --- | --- |
| arch-v2-base | | app-a | Application A | A |
| arch-v2-base | | app-d | Application D | D |

`cmp`:

| state | change | id | name | application |
| --- | --- | --- | --- | --- |
| arch-v2-base | | cmp-d | Component D | app-d |

`usr`:

| state | change | id | name | kind |
| --- | --- | --- | --- | --- |
| arch-v2-base | | customer | Customer | actor |

### `interface`

Interfaces leave `entity_kind` blank. Generic relationships use
`entity_kind=relationship` and share the same sheet.

| state | change | entity_kind | id | name | provider | consumer | source_id | target_id | direction | type |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| arch-v2-base | | | arch-v2-interface-a-to-d | A to D | app-a | app-d | | | provider_to_consumer | api |
| arch-v2-base | | relationship | customer-uses-a | Customer uses System A | | | customer | A | forward | uses |

### `view`

Structured fields such as `system_set` are compact JSON. Simple lists use the
bracketed semicolon form.

| id | name | roadmap | through | compare_from | visibility | system_set | interface_depth | level | color_by |
| --- | --- | --- | --- | --- | --- | --- | ---: | --- | --- |
| state-2027 | State at 2027 | preferred | arch-v2-change-2027 | | | | 0 | system | change_status |
| compare-base-2027 | Base to 2027 | preferred | arch-v2-change-2027 | base | changes_with_context | | 0 | system | change_status |
| payments-target | Payments target | preferred | arch-v2-change-2028 | | | `{"system_groups":["payments"]}` | 1 | application | change_status |

### `diagram`

| id | name | kind | source | variants | systems |
| --- | --- | --- | --- | --- | --- |
| platform-delivery | Platform delivery flow | dynamic | views/platform-delivery.c4 | `[{"id":"diagram","kind":"diagram"},{"id":"sequence","kind":"sequence"}]` | `[A;B;I]` |

### Excel authoring rules

- IDs in year-like numeric cells are canonicalised to strings.
- Simple lists are written as `[a;b]`.
- Dictionaries and nested lists are compact JSON.
- `properties` also accepts `owner:payments;tier:one` or one `name:value`
  entry per line. Duplicate, blank, or malformed names fail with sheet, row,
  and column context.
- Blank cells are omitted. Use the `unset` column, such as
  `[technology;notes]`, to clear fields deliberately.
- Additional columns on extensible rows are preserved as extension metadata.
- Source locations retain workbook, sheet, row, and column.
- The Excel writer requires exactly one complete base state. An empty base with
  state metadata cannot be represented because metadata is carried on base
  domain rows. See `src/otdev/tools/_arch/v2/write.py:152`.
- Repeated output is byte-stable: sheet order, archive entry order, and ZIP
  timestamps are normalised. See `src/otdev/tools/_arch/v2/write.py:276`.

## 5. What is already strong

### Stable semantics across authoring formats

YAML and Excel load into the same typed workspace. Golden tests cover
YAML-to-Excel-to-YAML, Excel-to-YAML-to-Excel, normalisation, validation,
selection, replay, resolved-state output, impact indexes, and export. The
acceptance registry is
`tests/otdev/fixtures/arch_v2/acceptance-matrix.json:1`.

### Sparse intent is explicit

The blank-versus-unset distinction avoids accidental data loss in both formats.
Optional `change_type` assertions catch invalid ordering rather than changing a
modification into an addition. `expected` protects derived or reviewed changes
from silently applying to a stale base.

### Change effects are explainable

Normalised operations, contributing history, impact reasons, generated cascade
metadata, and tombstones provide enough evidence for report explanations and
auditing. This is more reliable than deriving status from colour or renderer
state.

### Selection is reusable and renderer-neutral

One selection grammar drives saved views, ad hoc generation, solution scope,
comparison, focus, report preparation, and export. Stable selection identities
support cache reuse without leaking renderer-specific IDs.

### Errors retain authoring context

Validation reports canonical identity plus YAML data path or Excel
workbook/sheet/row/column. Publication can be gated on the same production
normalisation, replay, projection, presentation, diagram, and render paths.

## 6. Pressure test

The following findings separate release-blocking clarity from optional model
growth. “Gap” means the current contract is unclear or cannot meet an already
stated direction. “Opportunity” means the present choice is coherent but may
become restrictive.

| Priority | Finding | Type | Consequence | Recommendation |
| --- | --- | --- | --- | --- |
| P0 | YAML permits multiple complete states; compact Excel requires exactly one | Gap | “YAML/Excel parity” can be read more broadly than the writer supports | Publish a format capability matrix and define parity as the single-base portable subset, or redesign Excel before declaring unrestricted parity |
| P0 | Empty states with metadata cannot be written to Excel | Gap | Valid YAML cannot always round-trip | Either reject this shape from the portable subset or add a dedicated state metadata sheet |
| P0 | Derived changes can be written only to YAML | Gap | The general format story differs by operation | Document the asymmetry explicitly or add a deliberate Excel change-artifact representation |
| P0 | Full workspaces and standalone derived-change artifacts share one envelope | Gap | `states: []` is valid for one operation but unusable for ordinary resolve/report flows | Introduce an explicit artifact kind or validate operation-specific document modes clearly |
| P0 | Saved layout is requested, but current report requirements forbid persisted coordinates and general manual placement | Decision conflict | Implementing it now would violate `OUT-08` and `DATA-12` | Decide whether constrained placement is in report-v2 scope, then revise requirements and create an OpenSpec change before implementation |
| P0 | Generated layout output lacks ports, edge sections, label bounds, shared lanes, and structured diagnostics required by report-v2 | Gap | Browser and export cannot share the complete target scene contract | Stabilise the neutral layout/scene contract before selecting or embedding a layout engine |
| P0 | Clean-checkout production validation cannot currently load the LikeC4 compiler dependency, while `just arch-frontend-check` uses `npm ci` and repository rules ignore every package-manager lockfile | Operational gap | Canonical YAML and Excel validation both fail with `arch.likec4_compile`, so the full publication gate is not reproducible from this worktree | Commit one chosen lockfile and make the frontend check and validation bootstrap use that reproducible dependency set |
| P1 | `ElementStyle.position` is an unused free string | Gap | It invites incompatible placement conventions with no runtime effect | Remove it or replace it through a typed layout-intent contract; do not overload it with x/y JSON |
| P1 | Parallel visual edges may aggregate several canonical interfaces | Gap for editing | An aggregate edge ID can change as scope or state changes, making saved route locks stale | Bind route intent to canonical edge IDs or an explicit stable bundle ID, never to a transient renderer aggregate |
| P1 | Extension metadata is preserved but untyped | Opportunity | Teams can create spelling drift, conflicting meanings, and hard-to-query properties | Add optional property dictionaries/profiles with names, types, allowed values, sensitivity, and display hints |
| P1 | Interface `type` and `technology`, relationship `type`, and user `kind` are open strings | Opportunity | Cross-workspace filtering and report columns become inconsistent | Keep the core extensible, but support optional named vocabularies rather than hard-coding one enterprise taxonomy |
| P1 | There is no source-of-truth or drift contract between equivalent YAML and Excel files | Gap in workflow | Both copies can be edited and diverge despite semantic conversion support | Make one source authoritative and generate the other, with a content hash or manifest to detect drift |
| P1 | Schema evolution rules are implicit | Gap | A strict no-alias policy needs a clear rule for version increments and conversion | Define which changes require schema version 3, how unsupported versions fail, and which generated artifacts carry their own sub-schema version |
| P2 | Roadmaps are strictly linear | Opportunity | Parallel work, optional changes, and scenario branches require multiple roadmaps | Keep linear replay until a real use case justifies a DAG; improve shared-change/scenario authoring first |
| P2 | Containment stops at component and has no typed infrastructure/data-store kinds | Opportunity | Detailed technology views rely on tags, style, or properties | Prefer profiles or tags first; add canonical kinds only when they change replay, scope, or reporting semantics |
| P2 | Ordered list fields accept duplicates | Minor gap | Duplicate tags/groups add noise even though selectors later behave as sets | Reject duplicates while preserving authored order, or state explicitly that duplicates are harmless but retained |
| P2 | Excel is semantically strong but an austere authoring surface | Opportunity | JSON cells and repeated state metadata are error-prone for non-technical editors | Add validation lists, frozen headers, notes, and generated help without changing the domain-sheet semantics |

### Additional edge cases to keep explicit

- A rename is a `name` modification. IDs must remain stable; do not introduce
  display-name matching or rename aliases.
- A containment move changes ownership and must affect both old and new systems
  in impact reporting.
- A parent removal cascades through descendants and both connection types.
- Generic relationships remain visible connections but do not expand interface
  scope. This is intentional and should be obvious in user documentation.
- Selection constraints must be resolved against the active roadmap snapshot.
  A selected future or removed system may remain a valid selection while being
  reported as absent at that snapshot.
- Re-adding a previously removed ID should be treated as the same stable
  identity only if that is the intended domain meaning. Saved layout and report
  state will otherwise reattach to it.

## 7. Idea: saved placement with constrained auto-layout

### 7.1 Product decision required

The current report-v2 requirements say:

- the report is not an architecture editor;
- general manual diagram placement is out of initial scope; and
- layout coordinates must not be persisted in saved report YAML.

See `plans/arch/requirements.md:37` and
`plans/arch/requirements.md:135`.

The requested feature is still compatible with the broader architecture if it
is framed as constrained report layout rather than architecture editing. It
does require those requirements to change. The report would save presentation
intent while continuing to leave source YAML/Excel architecture facts alone.

### 7.2 Separate facts, intent, and output

Use three layers:

| Layer | Owns | Does not own |
| --- | --- | --- |
| Architecture workspace | Entities, connections, changes, roadmaps, views, stable IDs | x/y coordinates, ports, routes, viewport |
| Saved report layout intent | User-moved positions, locks, preferred ports, optional waypoints | Complete derived geometry or renderer state |
| Generated scene/layout result | Bounds, ports, routes, labels, lanes, diagnostics for the active projection | Durable source facts |

Do not store coordinates in entity `properties`, `style.position`, React Flow
state, or Draw.io output. Those locations either mix concerns or bind the
contract to one renderer.

### 7.3 Save constraints, not the whole auto-layout

If every generated coordinate is saved, the next added node turns the previous
auto-layout into a fully fixed drawing. Save only deliberate user intent:

- a moved node's preferred or fixed x/y;
- an explicitly fixed width/height;
- a chosen connection slot and whether it is locked;
- user-authored waypoints and their strength;
- explicit container membership expected when the intent was saved.

The engine continues to calculate all unspecified geometry.

Recommended node policies:

| Policy | Save x/y | Auto-layout may move it | User may drag it |
| --- | --- | --- | --- |
| `auto` | No | Yes | Yes; dragging changes policy to `prefer` |
| `prefer` | Yes | Yes, if needed to avoid conflicts | Yes |
| `pin` | Yes | No | Yes; the new position remains pinned |
| `lock` | Yes | No | No until explicitly unlocked |

Width and height should have a separate `size_policy` of `auto` or `lock`.
This avoids making a position lock accidentally freeze text-driven sizing.

### 7.4 Stable connection slots

Raw port coordinates are brittle when a shape is resized. Store a logical slot
on the shape perimeter.

Use a fixed 12-slot clockwise convention:

```text
             1       2       3
          +---------------------+
       12 |                     | 4
       11 |        shape        | 5
       10 |                     | 6
          +---------------------+
             9       8       7
```

Slot 1 is the top-side position nearest the top-left, then numbering proceeds
clockwise. Slots are deliberately offset from exact corners because a corner
has two possible outward directions. A circle, diamond, or custom shape maps
the same logical slots to its own perimeter intersections.

Each endpoint needs its own policy:

- `auto`: the router chooses a slot;
- `prefer`: retain the saved slot when it remains sensible;
- `lock`: use that slot or report a conflict.

The stored value should be `port_slot: 1`, not a renderer handle ID such as
`react-flow-source-1`.

### 7.5 Illustrative saved-report YAML

This is a design sketch, not current valid schema-v2 YAML:

```yaml
report_schema_version: 1
reports:
  - id: payments-target-report
    name: Payments target report
    selection:
      roadmap: preferred
      through: arch-v2-change-2028
      system_set:
        system_groups: [payments]
      interface_depth: 1
      level: application

    layouts:
      - id: payments-application-layout
        schema_version: 1
        level: application
        coordinate_space: parent_relative

        nodes:
          - id: app-a
            parent: A
            x: 120
            y: 80
            position_policy: lock

          - id: app-b
            parent: B
            x: 520
            y: 80
            position_policy: prefer
            width: 220
            height: 110
            size_policy: lock

        edges:
          - id: arch-v2-interface-a-to-b
            source:
              port_slot: 5
              policy: lock
            target:
              port_slot: 11
              policy: prefer
            route_policy: waypoints
            waypoints:
              - x: 390
                y: 135
                policy: lock
```

The saved-report and nested layout contracts should each own their versions
rather than reusing the architecture workspace `schema_version`.

### 7.6 Incremental layout behaviour

For an active graph, the layout pipeline should:

1. Resolve the architecture and projection before reading layout intent.
2. Match constraints only by canonical ID and expected parent/detail level.
3. Place locked containers and nodes as hard obstacles.
4. Place pinned nodes without moving them, but allow surrounding geometry to
   change.
5. Use preferred positions as stability hints, moving them only to resolve
   overlap, containment, or route-quality problems.
6. Auto-place new and unconstrained nodes near their parent and strongest
   neighbours.
7. Apply locked endpoint slots before routing unlocked edges.
8. Preserve locked waypoints, then route remaining segments and edges.
9. Return full neutral geometry plus structured conflicts and stale-constraint
   diagnostics.

Hard constraints must never be silently broken. If two locked nodes overlap,
a locked child falls outside a locked container, or locked ports make a route
impossible, show the conflict and offer an explicit unlock or reset action.

### 7.7 Containment and coordinate space

Store child positions relative to their canonical parent. Moving a system then
moves its applications and components as a unit. The generated scene may use
absolute coordinates, but saved intent should state
`coordinate_space: parent_relative`.

A constraint should record the parent observed when it was saved. If an
application later moves to another system, downgrade the old position to a
soft preference or ignore it with a structured `layout.parent_changed`
diagnostic. Do not reinterpret the same numeric x/y inside a different parent
without telling the user.

Keep separate layout intent by architectural `level`. A system-level node and
an application-level container can share a canonical ID but do not represent
the same geometry.

### 7.8 Roadmap changes and stale intent

Stable IDs allow unchanged nodes to retain placement across roadmap states.
Added nodes have no constraint and are auto-placed. Removed nodes leave dormant
constraints rather than errors, so moving backward through the roadmap restores
their placement.

Every application should produce deterministic diagnostics for:

- constrained ID absent from the active projection;
- expected parent changed;
- edge endpoint changed;
- saved port slot unsupported by a shape;
- hard-constraint collision;
- waypoint outside the valid coordinate space;
- constraint created for a different detail level or graph family.

Missing IDs must not be matched by name. An explicit “remove stale layout
rules” action can clean dormant constraints after review.

### 7.9 Edge aggregation

The report may visually combine parallel interfaces. A transient aggregate is
not a safe persistence key because its members change with state, scope, and
status.

Prefer one of these rules:

1. Store endpoint and route intent on canonical interfaces, and derive an
   aggregate route only when all members agree.
2. Add an explicitly authored stable bundle ID and bind shared route intent to
   that bundle.

Do not persist a hash of the current aggregate members as if it were durable.

### 7.10 Excel representation, if later required

The recommended first implementation keeps layout intent in saved-report YAML.
It should not extend the architecture workbook.

If Excel authoring of layout becomes a real requirement, add dedicated sheets
rather than x/y columns to `sys`, `app`, or `cmp`:

`layout_node`:

| layout | level | node_id | parent_id | x | y | position_policy | width | height | size_policy |
| --- | --- | --- | --- | ---: | ---: | --- | ---: | ---: | --- |
| payments-application-layout | application | app-a | A | 120 | 80 | lock | | | auto |
| payments-application-layout | application | app-b | B | 520 | 80 | prefer | 220 | 110 | lock |

`layout_edge`:

| layout | level | edge_id | source_port_slot | source_policy | target_port_slot | target_policy | route_policy | waypoints |
| --- | --- | --- | ---: | --- | ---: | --- | --- | --- |
| payments-application-layout | application | arch-v2-interface-a-to-b | 5 | lock | 11 | prefer | waypoints | `[{"x":390,"y":135,"policy":"lock"}]` |

This would change the current YAML/Excel parity contract and sheet set. It
therefore needs an explicit schema design and OpenSpec change, not an informal
extra worksheet.

### 7.11 Required UX controls

A constrained-layout feature needs clear, reversible controls:

- move and save as preferred position;
- pin, lock, unlock, and return to auto;
- choose or release a connection slot;
- add, move, or remove a waypoint;
- auto-layout unlocked items;
- auto-layout the selection, container, or whole diagram;
- reset layout intent by scope and detail level;
- show conflicts and stale rules;
- keyboard equivalents for move and lock actions.

“Auto-layout” must say what it will preserve before it runs. A safe default is
“re-layout unlocked items.”

## 8. Recommended stabilisation gates

Complete these before treating schema v2 as stable enough to underpin
report-v2:

1. Publish one schema reference generated or checked against the Pydantic
   models, covering every field, default, extension point, and invalid
   combination.
2. Define a format capability matrix for full workspace, complete state,
   derived change, YAML, and Excel. Resolve or explicitly accept the single-base
   and empty-state Excel limits.
3. Keep one canonical YAML fixture and production-generated Excel counterpart.
   Add example-drift checks for any documentation example derived from them.
4. Define artifact modes. A full workspace, standalone complete state, and
   standalone derived change should fail early when passed to an incompatible
   operation.
5. Decide the fate of `ElementStyle.position` before users depend on it.
6. Decide whether constrained saved placement is in report-v2. If yes, revise
   `OUT-08` and `DATA-12`, then specify saved layout intent and neutral scene
   output together.
7. Extend the neutral layout result to meet report-v2 requirements before
   renderer selection: ports, edge sections, label bounds, lanes, metrics, and
   structured diagnostics.
8. Add pressure fixtures for multiple states, empty states with metadata,
   cross-kind ID collisions, change dependency cycles, containment moves,
   remove/re-add identity, aggregate-edge changes, and stale layout constraints.
9. Define optional metadata vocabularies only after collecting real report
   filtering and governance needs. Avoid expanding the canonical entity kinds
   speculatively.
10. Document the authoritative-source workflow so paired YAML and Excel files
    cannot drift unnoticed.
11. Restore a clean-checkout frontend dependency path. The
    `just arch-frontend-check` command and production validation must pass from
    the committed dependency manifest and lockfile without relying on an
    existing `node_modules` directory.

## 9. Proposed decision order

The decisions have dependencies and should be made in this order:

```text
portable schema-v2 subset
    -> artifact modes and validation boundary
    -> stable ViewGraph and projection identity
    -> saved report contract
    -> optional layout-intent contract
    -> complete neutral scene/layout contract
    -> layout engine and renderer selection
    -> report-v2 implementation
```

The most valuable immediate outcome is not adding more entity fields. It is
making the existing contract precise at the YAML/Excel, workspace/artifact,
and saved-intent/generated-geometry boundaries. Once those boundaries are
stable, report-v2 can evolve without reopening the state/change engine.

## 10. Source map

The main implementation and specification evidence used for this assessment is:

- `src/otdev/tools/_arch/v2/models.py:17` for IDs, entity kinds, style, states,
  changes, roadmaps, views, graphs, and layout results.
- `src/otdev/tools/_arch/v2/normalize.py:29` for entity mappings, parent rules,
  sparse operation normalisation, and cascades.
- `src/otdev/tools/_arch/v2/replay.py:119` for roadmap and dependency
  validation.
- `src/otdev/tools/_arch/v2/load.py:151` for YAML loading and source traces,
  and `src/otdev/tools/_arch/v2/load.py:382` for Excel loading.
- `src/otdev/tools/_arch/v2/write.py:152` for Excel limits and row mapping, and
  `src/otdev/tools/_arch/v2/write.py:302` for the fixed sheet set.
- `openspec/specs/otdev/tool-arch-state-change-roadmap/spec.md:1` for state,
  change, replay, comparison, and materialisation requirements.
- `openspec/specs/otdev/tool-arch-yaml-excel-parity/spec.md:1` for format parity
  and source-location requirements.
- `openspec/specs/otdev/tool-arch-view-resolution/spec.md:1` for shared
  selection and view semantics.
- `plans/arch/requirements.md:64` for report-v2 ownership boundaries and
  `plans/arch/requirements.md:135` for the current saved-report contract.
- `justfile:84` and `.gitignore:76` for the current reproducible frontend
  install conflict.
