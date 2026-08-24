# Architecture Pack v3

Status: proposed way forward. Supersedes `plans/arch/arch-v2/` as the working
direction. v2's grilled decisions carry forward except where this document
explicitly replaces them.

## Why v3 exists

v1 and v2 each failed differently, and the failures point at one cause.

- **v1 (main)** was Excel-first with untyped rows, heavy alias tables, and no
  change-over-time model at all (~6,600 lines incl. tests).
- **v2 (this branch)** fixed the model but chose *authored patch replay* for
  change over time: `change_type` assertions, `unset` markers, no-op rejection,
  removal cascades, tombstones, preconditions, and a replay engine. That one
  choice drove roughly 40% of the 9,000-line implementation
  (`normalize.py`, `replay.py`, `compare.py`, and much of `viewgraph.py`),
  forced patch rows and patch columns into every Excel domain sheet, and
  produced three duplicate projection pipelines (`viewgraph.py`,
  `projection.py`, and `frontend/src/solution/projection.ts`).
- The **v2 grill** (`arch-v2/grill/schema-grill.md`) then simplified the patch
  grammar but kept the patch *model*. It compared patches only against
  "partial states" and never evaluated a third option.

v3 adopts that third option: **lifecycle intervals**. Entities and connections
carry inclusive `start_in` and `end_in` milestone references. A state is a filter, not a
replay. A diff is computed, not authored. See [schema](schema.md).

## What carries forward from v2 unchanged

These were settled by the grills and are not reopened:

- Entity model: System → Subsystem → Component containment, User, Interface
  (provider/consumer, `call_direction`, `data_flow_direction`), Relationship
  (Source Action Target).
- Common fields: `id`, `name` (`action` for Relationship), `description`,
  `tags`, flat `properties` (string or string-list only). No `group`, `notes`,
  `icon`, `style` on entities.
- ID and text rules: ASCII `[A-Za-z0-9._-]`, case-insensitive matching with
  declared spelling preserved, trimmed nonblank strings, no YAML null, no
  empty strings, no anchors/aliases/merge keys, unknown fields are errors.
- One canonical YAML file per Architecture; Excel is an adapter, never a
  second source of truth; import replaces atomically; export writes a new
  workbook.
- Excel conventions: `.xlsx` only, no formulas, `[a;b]` list cells,
  case/space/hyphen/underscore-insensitive headers, extra columns are
  properties, scalar coercion table.
- Report principles: Report selects and presents, never mutates; one primary
  System scope with undirected `system_hops`; boundary Interfaces render as
  stubs without widening scope; aspect switching (ownership / call direction /
  data flow) changes presentation only.
- Look and feel: the Archify profile and the react-flow-poc interaction model
  (canvas + passport panel + PATH/MAP/LENS + light/dark + copy-link).
- Tech: React Flow + elkjs + AG Grid Community; self-contained offline HTML;
  no per-report frontend build.
- No backward-compatible aliases; removed concepts fail validation.

## What v3 replaces

| v2 concept | v3 replacement |
| --- | --- |
| `current_state` block + `changes` patches + replay | Flat entity collections with `start_in`/`end_in` intervals; state = filter |
| `change_type: added/changed/removed` | Implied by `start_in`, `end_in`, and revision rows |
| `unset` marker, no-op patch validation | Revision rows are complete definitions; nothing is sparse |
| Authored removal cascades + tombstones | Computed clipping + computed consequences; retired rows stay in the file |
| Roadmap = ordered Change list | Ordered milestone catalog; optional named timelines for scenarios |
| `arch.diff` over replayed states | Diff computed directly from intervals and revision rows |
| Python ViewGraph + Python projection + TS projection | One projection implementation, in the report app |
| LikeC4 compile/layout node subprocess at generate time | elkjs layout in the report itself; generate = inject JSON into a prebuilt bundle |

## Documents

| Doc | Owns |
| --- | --- |
| [schema.md](schema.md) | Entities, milestones, intervals, revisions, resolution, validation, canonical YAML |
| [report.md](report.md) | Report app: views, time slider, diagrams, tables, pipeline |
| [adapters.md](adapters.md) | Excel mapping now; SharePoint, SQLite, CSV later |
| [delivery.md](delivery.md) | Phases, size budgets, and the guardrails that stop v3 circling |

## Principles (v3 additions)

1. **States are filters.** Any mechanism that requires replaying history to
   know what exists at a point in time is out.
2. **Rows are complete.** No row's meaning depends on another row's field
   values. Sparse-patch semantics (omitted-means-unchanged, unset markers) are
   out.
3. **The data is the audit trail.** Retired and future entities stay visible
   in the file with their intervals. History is never compacted implicitly;
   `advance` (see schema.md) compacts it explicitly.
4. **Tables all the way down.** The canonical model must map to plain tables
   with no row interleaving or cell mini-grammars beyond lists, so Excel,
   SharePoint lists, SQLite, and CSV are all the same adapter shape.
5. **One projection.** State filtering, scoping, and diffing are implemented
   once, in the report app; Python validates, adapts formats, and compiles the
   data payload.
6. **Budgets are contracts.** Each delivery phase in delivery.md carries a
   line budget. Blowing the budget is a design smell to fix, not a number to
   renegotiate.
