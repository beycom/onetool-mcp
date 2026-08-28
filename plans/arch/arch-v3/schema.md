# Architecture schema v3

Status: proposed. Entity semantics are inherited from
[arch-v2/schema.md](../arch-v2/schema.md) except where restated here. This
document owns the temporal model, which is new, and the v3 revisions agreed
at the phase-3 gate rework (2026-08-24): C4-aligned entity kinds, the id
scheme, inclusive `start_in`/`end_in` intervals over a **base** state, and
the Provider/Consumer interface model.

## Model

```text
Architecture
  Milestones          ordered catalog of named points of change
  Timelines           optional named milestone orderings (scenarios)
  Systems             ┐
  Containers          │
  Components          │  entity collections; every row carries an
  Code                │  optional inclusive [start_in, end_in] interval
  Users               │
  Interfaces          │
  Relationships       ┘
```

There is no `current_state` block, no `changes` block, and no replay. Every
entity row states its own temporal extent. The **base state** is the
architecture before any milestone lands — the filter "rows live at position
0"; any milestone's state is the same filter at that milestone's position.

## Entity kinds (C4-aligned)

| Kind | Meaning | Parent field | Contains |
| --- | --- | --- | --- |
| System | the overall product or platform | — | Subsystems, Containers |
| Subsystem | a cohesive business capability — a logical grouping of related containers | `parent` — a System | Containers |
| Container | an independently runnable/deployable application or data store | `parent` — a System **or** a Subsystem | Components |
| Component | a significant module inside a container | `container` — a Container | Code |
| Code | implementation details | `component` — a Component | — |

- **Subsystems are optional** (renamed level model, 2026-08-28 — replaces
  the earlier container-in-container nesting): a container may attach
  directly to its system. Subsystems never nest and are purely a logical
  grouping — deployability lives at the container.
- Containers no longer nest: `parent` must name a System or a Subsystem,
  never another Container.
- Code is a full modelled kind — same row shape, intervals, revisions, and
  interface eligibility as every other entity — expected to be unpopulated
  in most datasets.
- Users, Interfaces, and Relationships keep their v2 names and semantics.
  Interface endpoints and relationship `source`/`target` may reference any
  entity kind.
- Because `parent` may name a System or a Subsystem, an id present in both
  collections is a validation error (ambiguous parent). Containment is
  acyclic by construction (strict layering).

## Identifiers

ID grammar is inherited from v2: ASCII `[A-Za-z0-9._-]`, nonblank, unique
per collection (revision rows excepted). The milestone id `base` is
**reserved** — it names the base state in interval references and state
selectors.

Ids are stable machine keys (diff and revision grouping, URL fragments,
cross-references); human identity lives entirely in `name`. Generated ids
follow a per-kind prefixed sequential scheme:

| Kind | Scheme |
| --- | --- |
| System | `s-0001` |
| Subsystem | `ss-0001` |
| Container | `c-0001` |
| Component | `cp-0001` |
| Code | `cd-0001` |
| User | `u-0001` |
| Interface | `i-0001` |
| Relationship | `r-0001` |

Assignment rules: when a row arrives without an id (blank Excel cell on
import, `init` scaffolding), the pack assigns the next free id for its kind
— numerically `max + 1` over existing ids matching the kind's
`<prefix>-<digits>` pattern, zero-padded to four digits (wider once
exhausted). Gaps are permanent: deleting a row never renumbers others.
Hand-authored slug ids remain legal — the scheme is the default for
*generated* ids, not a validation constraint. Milestones and timelines are
always authored ids (no scheme).

## Canonical YAML

```yaml
schema_version: 3

milestones:
  - id: phase-1
    name: Consolidate payments
  - id: phase-2
    name: Retire legacy clearing

# timelines are optional; omitted means one timeline = catalog order
timelines:
  - id: preferred
    milestones: [phase-1, phase-2]

systems:
  - id: payments
    name: Payments
  - id: legacy-clearing
    name: Legacy Clearing
    end_in: phase-1        # last present at phase-1; gone at phase-2

# subsystems are optional groupings of containers within a system
subsystems:
  - id: clearing
    name: Clearing
    parent: payments

containers:
  - id: payments-api
    name: Payments API
    parent: payments        # directly under the system — no subsystem
  - id: clearing-api
    name: Clearing API
    parent: legacy-clearing
    end_in: phase-1
  - id: new-clearing
    name: Clearing API
    parent: clearing        # grouped under the payments/clearing subsystem
    start_in: phase-2

components: []
code: []

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
    end_in: phase-1
  - id: payments-to-new-clearing
    name: Submit clearing request
    provider: new-clearing
    consumer: payments-api
    start_in: phase-2

relationships:
  - id: payments-owned-by-team
    source: payments-team
    action: owns
    target: payments
```

The change story is *in* the data: each row names the span of states that
contain it. Grep `phase-2` and you see what arrives at phase-2 (`start_in`);
what phase-2 sweeps away carries `end_in: phase-1` — the last state it
survives. No patch grammar, no second vocabulary.

Root keys `schema_version`, `milestones`, and the eight entity collections
are required (collections may be empty). `timelines` is optional.

## Static architectures are the base case

An architecture with no change story is simply rows with no
`start_in`/`end_in`, `milestones: []`, and no `timelines` — a plain
inventory identical in shape to what v2's `current_state` held; the base
state is the whole dataset. The temporal model is strictly pay-as-you-go:
resolution over zero milestones is the identity filter, and nothing about
authoring, validation, or Excel gets harder because the capability exists.
Time enters the dataset one milestone at a time, only when there is a
change to describe.

## Milestones

A Milestone is a named point at which the architecture changes. It has
required `id` (any id except the reserved `base`), required `name`, optional
`description`, optional `tags`, optional flat `properties` (a delivery
date, owner, or status goes here — the schema assigns no meaning to them,
honoring v2's decision to keep Change metadata minimal until a concrete
behavior needs it).

Catalog order is the default ordering. A Milestone that appears in no
timeline (when timelines are declared) is valid: it is authored work not yet
scheduled — the same allowance v2 gave unreferenced Changes.

## Timelines (scenarios)

A Timeline is a named ordered subset of milestones, replacing v2's Roadmap:

```yaml
timelines:
  - id: preferred
    milestones: [phase-1, phase-2a]
  - id: fallback
    milestones: [phase-1, phase-2b]
```

Rules: at least one milestone, references must resolve, no repeats within a
timeline. When no timelines are declared there is exactly one implicit
timeline containing every milestone in catalog order.

Alternate futures are alternate timelines choosing different milestones,
from the same shared data. A row whose `start_in` milestone is not in the
selected timeline never appears on that timeline; a row whose `end_in`
milestone is not in the selected timeline is never removed on it.

## Intervals

`start_in` and `end_in` are optional references on every entity and
connection row. Both are **inclusive**: they name the first and the last
position whose state contains the row.

```text
positions:  base   m1   m2   m3
row A:              A    A          =>  A  start_in: m1, end_in: m2
```

Positions on a timeline: `0` = the base state, `i + 1` = the timeline's
`i`-th milestone. The reserved reference `base` names position 0 and
resolves through the same position lookup as any milestone.

- absent `start_in` — in the base state (exists from the beginning);
  `start_in: base` is legal and means the same;
- `start_in: m` — first present in the state at milestone `m`;
- absent `end_in` — never removed;
- `end_in: m` — last present at milestone `m`; absent from the following
  position onward;
- `end_in: base` — present only in the base state, removed by the first
  milestone of every timeline.

A row is live at position `p` on timeline `T` when
`pos(start_in) <= p <= pos(end_in)`, where an absent (or `base`)
`start_in` is 0, an absent `end_in` is +∞, and a milestone not in `T`
makes `start_in` = +∞ (never appears) or `end_in` = +∞ (never removed).

`start_in == end_in` is legal — the row exists at exactly that position.
When both reference milestones on one timeline, `start_in` must not come
after `end_in`.

Attribution note: `end_in` names the last position *containing* the row;
the removal event is the **following** position on the selected timeline,
and diffs report the removal there. A row with `end_in: m` appears in the
state at `m` and is reported removed in the diff `m -> next`.

## Revisions

Field values rarely change over time; when they do, author a second row with
the same `id` and a later `start_in`. Each row is the **complete**
definition of the entity while it is the newest live row:

```yaml
containers:
  - id: clearing-api
    name: Clearing API
    parent: legacy-clearing
  - id: clearing-api
    start_in: phase-2
    name: Clearing API
    parent: payments         # moved; all fields restated
```

Rules:

- Rows sharing an `id` are revisions of one entity. At most one row per id
  may start in the base (absent or `base` `start_in`); all `start_in`
  positions must be distinct.
- A revision row implicitly ends the previous revision immediately before
  its own `start_in`. Writing `end_in` on a non-final revision is only
  needed to create a gap (entity absent for a span, then reintroduced —
  same identity, as v2 flagged).
- Blank means blank. A revision that omits `description` has no description.
  There is no `unset`, no omitted-means-unchanged, no no-op detection — a
  revision identical to its predecessor is a validation *warning* (probable
  mistake), not an error.
- Repeating unchanged fields on the rare mutating row is the accepted cost;
  it buys per-row completeness, which is what makes Excel/SharePoint/SQLite
  editing safe (a row can be read, edited, and validated in isolation).

Prefer retire-and-add (new id) when the change is architecturally a
replacement; prefer a revision when identity genuinely continues (rename,
re-parent, property change).

## Provider / Consumer interface model

> A **Provider** owns or exposes a capability, resource, dataset, API,
> event stream, file, or service for consumption.
>
> A **Consumer** uses that capability, resource, dataset, API, event
> stream, file, or service.

Provider/Consumer describes **responsibility and usage, not direction**.
Source/Destination and Sender/Receiver ask a directional question that has
different answers for the call, the data, the event, and the ownership;
Provider/Consumer asks who provides and who consumes, which typically stays
stable across technology and integration-style changes (REST → GraphQL →
events → data product: same Provider, same Consumer). The definitions are
complementary: when the Provider is hard to identify, the Consumer usually
is not, and vice versa. Provider naturally aligns with System of Record,
capability/data/service ownership, and bounded contexts.

Directional concerns are modelled separately, as two enum fields on the
Interface:

| Field | Values (default first) |
| --- | --- |
| `call_direction` | `consumer_to_provider`, `provider_to_consumer` |
| `data_flow_direction` | `provider_to_consumer`, `consumer_to_provider`, `bidirectional` |

The defaults encode the canonical pattern — the Consumer invokes, the
Provider supplies data — so most interfaces state neither field. Overrides
cover push patterns (`call_direction: provider_to_consumer` for a webhook
or callback) and writes (`data_flow_direction: consumer_to_provider` for an
upload, `bidirectional` for CRUD against a database). Deterministic dumps
omit a field equal to its default.

Worked examples (roles first, directions follow):

| Pattern | Provider | Consumer | call | data |
| --- | --- | --- | --- | --- |
| REST API | Order Service | Cart Service | default | default |
| Event stream | Order Service | Fulfilment Service | default (subscribe) | default (events P→C) |
| Database | Order Database | Order Service | default (CRUD) | `bidirectional` |
| File transfer | ERP System | Warehouse System | default (request) | default (file P→C) |
| Webhook | Notification Hub | Client App | `provider_to_consumer` | default |

There is no relationship-type enum (decided 2026-08-24): interaction
technology and style (REST, event, file, batch, …) belong in `tags` or
`properties`, and ownership statements belong in the Relationships
collection. The report renders per-aspect arrows from these two fields —
the CALLS aspect from `call_direction`, the DATA aspect from
`data_flow_direction`.

## Resolution: clipping instead of cascades

v2 let an authored removal cascade to descendants and connections, recording
tombstones. v3 computes the same consequence from intervals:

- An entity is *effectively live* only while its parent chain is live
  (code → component → container → … → system, through any container
  nesting).
- An Interface or Relationship is effectively live only while both endpoints
  are effectively live.
- The resolver clips accordingly and reports every clip as a **derived
  consequence** (`clipped_by: <ancestor or endpoint>`) — the computed
  equivalent of v2's tombstone-with-cause, available to reports and diffs.

Setting `end_in` on a System removes its whole tree and every connection
into it from the following position onward, with nothing repeated by the
author. Validation flags a child or connection whose *authored* interval
extends beyond what clipping allows as a warning, not an error — the file
stays editable in any row order.

## Diff

`diff(at_a, at_b)` is computed set arithmetic over the two filtered states:

- **added** — live at `b`, not at `a`;
- **removed** — live at `a`, not at `b` (with derived consequences attached);
- **changed** — live at both via different revision rows, reported
  field-by-field.

Nothing about a diff is authored, so it can never disagree with the data.
This restores what v2 lost when it removed `expected`: exact previous values
in every diff, for free.

## Advancing the baseline

Architectures live for years; delivered milestones must not accumulate
forever. `arch.advance(through=<milestone>)` mechanically rewrites the file
so the state at `through` becomes the new base:

- rows whose `end_in` is `base` or comes before `through` in timeline order
  are deleted (they are absent from the new base);
- rows with `end_in: through` are rewritten to `end_in: base` (the new base
  is the last state containing them);
- `start_in` markers at or before `through` are removed (rows become base
  rows);
- superseded revision rows are dropped, keeping the one governing at
  `through`;
- the milestone(s) are removed from the catalog and timelines.

This is an explicit, reviewable git commit — the file stays small and the
history lives in version control, honoring "the data is the audit trail"
without unbounded file growth.

## Validation

Structural (errors): unique ids per collection (revision rows excepted per
the rules above), resolvable parents, endpoints, and milestone references,
ambiguous `parent` (id present in both `systems` and `subsystems`),
container `parent` naming another container (containers no longer nest),
the reserved milestone id `base`, required fields,
interval ordering (`start_in` after `end_in` when both are milestones on
one timeline; equality is legal), timeline rules, ID/text/property rules
inherited from v2.

Advisory (warnings): identical adjacent revisions, authored intervals that
exceed clipping, milestones referenced by no row, entities live on no
timeline.

Endpoint and parent references must resolve to an entity whose *identity*
exists (any revision) — liveness overlap is checked by clipping, not by
reference resolution, so rows can be authored in any order.

## State selection boundary (Architecture → Report)

```yaml
at: base
```

```yaml
timeline: preferred
at: phase-1
```

```yaml
timeline: preferred
at: end
```

`base`, a milestone id, or `end` (the last milestone of the timeline —
v2's Target State; with zero milestones, `end` equals `base`). `timeline`
may be omitted when only the implicit timeline exists or when exactly one
timeline is declared (that one is then selected); with several declared
timelines it is required. An optional `compare` key takes the same grammar
and selects the diff origin — resolving v2's open comparison-origin
question with the same selector rather than a new concept.

## Why this is not v2's rejected "partial states"

The grill rejected partial states because omission was ambiguous: a partial
snapshot needs base identity, removal, clearing, and ordering rules — i.e. it
secretly *is* patch semantics. Intervals have no omission ambiguity: every
row is complete, and `start_in`/`end_in` are explicit single-purpose
markers. The grill's verdict "authors never repeat unchanged architecture"
holds — an unchanged entity is one row, forever, on every timeline.

## Migration

One-shot converter from v2 YAML: `current_state` rows become interval-less
base rows; each Change's `added` patches become `start_in` markers naming a
milestone derived from the Change id; `removed` patches become `end_in`
markers naming that milestone's predecessor on the primary timeline (`base`
when it is the first); `changed` patches become revision rows materialized
from the replayed state. Roadmaps become timelines. The converter is
throwaway tooling, not a compatibility layer.
