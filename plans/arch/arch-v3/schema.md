# Architecture schema v3

Status: proposed. Entity semantics are inherited from
[arch-v2/schema.md](../arch-v2/schema.md) except where restated here. This
document owns the temporal model, which is new.

## Model

```text
Architecture
  Milestones          ordered catalog of named points of change
  Timelines           optional named milestone orderings (scenarios)
  Systems             each row carries an optional [from, until) interval
  Subsystems
  Components
  Users
  Interfaces
  Relationships
```

There is no `current_state` block, no `changes` block, and no replay. Every
entity row states its own temporal extent. The current state is the filter
"rows whose interval covers now"; any milestone's state is the same filter at
that milestone.

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
    until: phase-2

subsystems:
  - id: payments-api
    name: Payments API
    system: payments
  - id: clearing-api
    name: Clearing API
    system: legacy-clearing
    until: phase-2
  - id: new-clearing
    name: Clearing
    system: payments
    from: phase-2

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
    until: phase-2
  - id: payments-to-new-clearing
    name: Submit clearing request
    provider: new-clearing
    consumer: payments-api
    call_direction: consumer_to_provider
    from: phase-2

relationships:
  - id: payments-owned-by-team
    source: payments-team
    action: owns
    target: payments
```

The change story is *in* the data: grep `phase-2` and you see everything that
phase adds and retires. No patch grammar, no second vocabulary.

Root keys `schema_version`, `milestones`, and the six entity collections are
required (collections may be empty). `timelines` is optional.

## Static architectures are the base case

An architecture with no change story is simply rows with no `from`/`until`,
`milestones: []`, and no `timelines` — a plain inventory identical in shape
to what v2's `current_state` held. The temporal model is strictly
pay-as-you-go: resolution over zero milestones is the identity filter, and
nothing about authoring, validation, or Excel gets harder because the
capability exists. Time enters the dataset one milestone at a time, only
when there is a change to describe.

## Milestones

A Milestone is a named point at which the architecture changes. It has
required `id`, required `name`, optional `description`, optional `tags`,
optional flat `properties` (a delivery date, owner, or status goes here — the
schema assigns no meaning to them, honoring v2's decision to keep Change
metadata minimal until a concrete behavior needs it).

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

Alternate futures are alternate timelines choosing different milestones, from
the same shared data. A row whose `from` milestone is not in the selected
timeline never appears on that timeline; a row whose `until` milestone is not
in the selected timeline is never retired on it.

## Intervals

`from` and `until` are optional single milestone references on every entity
and connection row:

- absent `from` — exists in the current state (from the beginning);
- `from: m` — comes into existence *at* milestone `m`;
- absent `until` — exists to the end of every timeline;
- `until: m` — ceases to exist *at* milestone `m` (half-open: present before
  `m`, absent at `m`).

State at position `p` on timeline `T` (position −1 = current): a row is live
when `pos(from) <= p` and `pos(until) > p`, where an absent `from` is −∞, an
absent `until` is +∞, and a milestone not in `T` makes `from` = +∞ (never
appears) or `until` = +∞ (never retired).

`from` and `until` on the same row must not be equal, and when both are on
one timeline `from` must precede `until`.

## Revisions

Field values rarely change over time; when they do, author a second row with
the same `id` and a later `from`. Each row is the **complete** definition of
the entity while it is the newest live row:

```yaml
subsystems:
  - id: clearing-api
    name: Clearing API
    system: legacy-clearing
  - id: clearing-api
    from: phase-2
    name: Clearing API
    system: payments        # moved; all fields restated
```

Rules:

- Rows sharing an `id` are revisions of one entity. At most one row may omit
  `from`; all `from` values must be distinct.
- A revision row implicitly ends the previous revision at its `from`. Writing
  `until` on a non-final revision is only needed to create a gap (entity
  absent for a span, then reintroduced — same identity, as v2 flagged).
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

## Resolution: clipping instead of cascades

v2 let an authored removal cascade to descendants and connections, recording
tombstones. v3 computes the same consequence from intervals:

- An entity is *effectively live* only while its parent chain is live.
- An Interface or Relationship is effectively live only while both endpoints
  are effectively live.
- The resolver clips accordingly and reports every clip as a **derived
  consequence** (`clipped_by: <ancestor or endpoint>`) — the computed
  equivalent of v2's tombstone-with-cause, available to reports and diffs.

Setting `until` on a System retires its whole tree and every connection into
it, with nothing repeated by the author. Validation flags a child or
connection whose *authored* interval extends beyond what clipping allows as a
warning, not an error — the file stays editable in any row order.

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
forever. `arch.advance(through=<milestone>)` mechanically rewrites the file:

- rows with `until` at or before the milestone are deleted;
- `from` markers at or before it are removed (rows become current);
- superseded revision rows are dropped, keeping the newest;
- the milestone(s) are removed from the catalog and timelines.

This is an explicit, reviewable git commit — the file stays small and the
history lives in version control, honoring "the data is the audit trail"
without unbounded file growth.

## Validation

Structural (errors): unique ids per collection (revision rows excepted per
the rules above), resolvable parents, endpoints, and milestone references,
required fields, interval ordering, timeline rules, ID/text/property rules
inherited from v2.

Advisory (warnings): identical adjacent revisions, authored intervals that
exceed clipping, milestones referenced by no row, entities live on no
timeline.

Endpoint and parent references must resolve to an entity whose *identity*
exists (any revision) — liveness overlap is checked by clipping, not by
reference resolution, so rows can be authored in any order.

## State selection boundary (Architecture → Report)

```yaml
at: current
```

```yaml
timeline: preferred
at: phase-1
```

```yaml
timeline: preferred
at: end
```

`current`, a milestone id, or `end` (the last milestone of the timeline —
v2's Target State). `timeline` may be omitted when only the implicit timeline
exists. An optional `compare` key takes the same grammar and selects the diff
origin — resolving v2's open comparison-origin question with the same
selector rather than a new concept.

## Why this is not v2's rejected "partial states"

The grill rejected partial states because omission was ambiguous: a partial
snapshot needs base identity, removal, clearing, and ordering rules — i.e. it
secretly *is* patch semantics. Intervals have no omission ambiguity: every
row is complete, and `from`/`until` are explicit single-purpose markers. The
grill's verdict "authors never repeat unchanged architecture" holds — an
unchanged entity is one row, forever, on every timeline.

## Migration

One-shot converter from v2 YAML: `current_state` rows become interval-less
rows; each Change's `added`/`removed` patches become `from`/`until` markers
naming a milestone derived from the Change id; `changed` patches become
revision rows materialized from the replayed state. Roadmaps become
timelines. The converter is throwaway tooling, not a compatibility layer.
