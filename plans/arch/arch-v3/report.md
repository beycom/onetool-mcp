# Report v3

Status: proposed. Inherits the v2 report principles (select-and-present,
system_hops scoping, boundary stubs, aspect switching) and the react-flow-poc
interaction model. This document owns what changes: the pipeline and the time
dimension.

## Shape

One self-contained offline HTML file: a **prebuilt** React app shipped inside
the wheel, into which `arch.generate` injects a JSON data payload. No Node,
npm, vite, or LikeC4 at generate time — generation is template substitution
plus payload validation, fixing the v2 requirement (REQ:398) that the v2
implementation violated (`frontend.py` ran vite per generate).

```text
canonical YAML
  -> validate + compile payload (Python)
  -> inject into prebuilt single-file bundle
  -> report.html  (works from file://, zero network)
```

The payload is the flat interval model itself — milestones, timelines, and
entity rows with interval positions pre-resolved to integers — plus derived
consequences from clipping. It is small, human-inspectable, and contains
every state implicitly. The normative shape is "Payload contract (v1)"
below.

Bundle location (decided 2026-08-23, closes plan.md open question 1): app
source lives in `frontend/arch-report/` (vite + React + TS); `just
build-arch-report` builds the single-file template to
`src/otdev/tools/_arch/v3/_bundle/report-template.html`, which is
**committed** — wheel builds and dev installs never need Node. Rebuild is a
manual step when the frontend changes.

## One projection, in the app

Because a state is a filter, the report app derives everything client-side:

- **state at stage position** — one array filter;
- **diff between positions** — set arithmetic;
- **scope** (selected systems + hops) — BFS over live interfaces;
- **level** (four C4 levels since wave 2 — see "Wave-2 UI contract") —
  roll-up of nodes and edges.

This deletes v2's three parallel pipelines (`viewgraph.py` 863 lines,
`projection.py` 450, `projection.ts` 385) and the Python/TS parity tests
between them. Python never builds a graph.

## Payload contract (v1)

Normative. Compiled by `build_payload(arch, source_name) -> dict`
(`_arch/v3/payload.py`); injected by `arch.generate`.

### Position space

Positions are integers **per timeline**: `0` = the base state, `i + 1` =
the timeline's `i`-th milestone. The domain of a timeline with `M`
milestones is `0..M`; the slider stop index IS the position. (`base`/`end`
selectors stay a resolver-side convention; they do not appear in the
payload.)

### Top-level shape (fixed key order)

```json
{
  "payload": "arch-report/v1",
  "schema_version": 3,
  "source": "acme.yaml",
  "milestones": [ {"id": "acme-2027-edge-foundation", "name": "Edge foundation", "…": "…"} ],
  "timelines": [ {"id": "program", "milestones": ["acme-2027-edge-foundation", "…"]} ],
  "rows": {
    "systems":       [ {"id": "commerce-platform", "name": "Commerce Platform",
                        "start_in": "acme-2027-edge-foundation",
                        "intervals": [ {"live": [[1, null]], "clips": []} ]} ],
    "containers":    [], "components": [], "code": [], "users": [],
    "interfaces":    [], "relationships": []
  }
}
```

- `source` — basename of the input YAML, display only.
- `milestones` — the full catalog in authored order, every milestone (on a
  timeline or not), serialized like rows (below).
- `timelines` — **materialized**: no declared timelines → one entry
  `{"id": null, "milestones": [<catalog order>]}`; otherwise the declared
  timelines in declared order. The picker renders when there are several;
  the first is the default. Time UI renders only when the selected
  timeline has at least one milestone (progressive disclosure).
- `rows` — the seven collections in schema order (systems, containers,
  components, code, users, interfaces, relationships), each in **authored
  order**. Row identity is `(collection, array index)`; revision rows share
  an `id` across indices.
- `files` (added 2026-08-30, lands with P21) — present only when any
  interface or sequence message carries attachments (schema.md
  "Attachments"): an object keyed by relative path (sorted), each value
  `{"lang": "json" | "xml" | "csv" | "yaml" | "text", "text": "<file
  content>"}` — each referenced file embedded exactly once at generate
  time, `lang` derived from the extension. Follows `sequences` in key
  order; omitted entirely when no attachments exist, so payloads without
  them stay byte-identical.

### Row serialization

Model fields dumped as authored (`start_in`/`end_in` carry the authored
milestone id or `base` — kept for the passport panel), omitting `null`s,
empty `tags`/`properties`, and `call_direction`/`data_flow_direction` when
equal to their schema defaults (the client applies the defaults).
Interface rows carry `attachments` as authored (path list, omitted when
empty — the client joins to the top-level `files` map). Plus one
derived field:

- `intervals` — array **parallel to `timelines`**. Entry `k` describes the
  row on `timelines[k]`:
  - `live` — inclusive segments `[start, end]` (`end` = the **last** live
    position; `null` = unbounded) where this row is the **governing
    revision and effectively live** (revision succession, off-timeline
    milestone rules, and clipping all folded in).
  - `clips` — segments `{"start": s, "end": e, "by": id}` (same inclusive
    convention) where this row governs but is clipped; `by` is the authored
    root cause per the resolver's `Clip.clipped_by` semantics. Runs with
    the same cause are coalesced.

Segment lists are sorted, disjoint, and coalesced; all bounds lie in the
timeline's domain. Within one revision group the union of all rows'
`live` + `clips` segments is disjoint — at most one row of a group governs
any position. A row that never governs on a timeline has both lists empty.

State-at-position is therefore literally
`rows[kind].filter(r => within(r.intervals[t].live, p))`; ghost/consequence
rendering reads `clips` the same way. The payload carries **no** per-position
materialized states and no diffs — diff, scope BFS, and level roll-up are
client projections (D7) over these arrays. Size stays linear in
rows × timelines.

### Compilation (normative algorithm)

For each timeline `t` and each position `p` in `0..M`, run the authoritative
resolver (`resolve` with the selector for `p`; governing-row identity via
`group_revisions` + `governing_row`): the governing effective row is live at
`p`; a `(kind, id)` in `ResolvedState.clips` marks the governing row clipped
at `p` with its `clipped_by`. Merge consecutive positions into segments.
Interval/clipping semantics must NOT be reimplemented — the resolver is the
single source of truth (this is what killed v2's parity tests).

### Determinism and injection

- No timestamps anywhere; fixed key order as above. Same input file ⇒
  byte-identical payload and report.
- The built template contains
  `<script id="arch-payload" type="application/json">__ARCH_PAYLOAD_JSON__</script>`.
  `arch.generate` validates (refusing on errors, like `arch.export`),
  replaces the token with the compact JSON dump (`ensure_ascii=False`),
  escapes every `</` as `<\/` (script-block safety; still valid JSON), and
  writes atomically (temp file + replace). The app boots with
  `JSON.parse(getElementById('arch-payload').textContent)`.
- Pretty-printed payload for inspection comes from the `payload` CLI
  subcommand, not from the report.

## Client projection contract (v1)

Normative for D7. Pure functions over the payload; no React in the
projection layer. The authoritative test vectors live in
`tests/unit/tools/fixtures/arch/projection/` (`vectors.json` + its README):
`state_at` and `diff` expectations were computed by the Python resolver;
`scope` and `rollup` encode this section. Vectors are read-only for
executors; the frontend vitest suite drives the functions below against
them.

Shared conventions: a **node key** is `"<kind>:<id>"` (ids are unique per
collection, not globally). `t` is a timeline index into `payload.timelines`,
`p` a position in that timeline's domain. All output lists are
deterministically ordered: entity lists in authored group order, node/edge
lists sorted by key, diff lists by KINDS order (systems, containers,
components, code, users, interfaces, relationships) then authored group
order.

- **`liveAt(row, t, p)`** — true iff some segment `[s, e]` of
  `row.intervals[t].live` has `s <= p` and (`e === null` or `p <= e`)
  (segments are end-inclusive). `clipAt(row, t, p)` looks up
  `intervals[t].clips` the same way and yields the segment's `by`.
- **`stateAt(payload, t, p)`** — per kind: the rows passing `liveAt` (at
  most one row per id by construction), plus the clipped map
  `id -> {row, by}` from the clip segments. This is the single source for
  canvas AND tables.
- **`diffStates(payload, t, a, b)`** — mirrors the Python resolver's diff
  exactly: **added** `{kind, id, name}` (name = `action` for relationships)
  for ids live at `b` only; **removed** `{kind, id, name, clipped_by}` for
  ids live at `a` only, `clipped_by` taken from the id's clip at `b` when
  present, else null; **changed** for ids live at both via different row
  indices whose content differs — compare every serialized field except
  `id`, `start_in`, `end_in`, `intervals`; `properties` per key as
  `properties.<key>` (old/new null when added/removed); `tags` as a whole
  list; absent optional fields compare as absent. Equal-content
  different-index pairs are not reported.
- **`scopeAt(state, systems, hops)`** — top-level representative of a live
  entity: systems and users are themselves; anything else walks its parent
  chain to the owning system (code → component → container → … → system,
  through any container nesting). Build the system-level graph over
  live **interfaces only** (edge between the two endpoints' distinct
  representatives). Kept = the selected systems (ignoring ones not live)
  plus every node within `hops` BFS steps. A connection (interface or
  relationship) is **retained** iff at least one endpoint representative is
  kept; a non-kept representative touched by a retained connection is a
  **boundary stub** (rendered collapsed). Kept entities = live entities
  whose representative is kept, plus retained connections. `scope = null`
  disables filtering.
- **`rollUp(state, level)`** — representative at a level (system /
  container / component): entities below the level map UP to their ancestor
  at the level (code to its component, and onward up the parent chain);
  entities at or above it (and users) stay themselves. Nodes = live entities of the level's kind,
  plus users, plus every retained edge-endpoint representative. Edges are
  keyed by the **unordered** representative pair, self-pairs dropped, and
  carry their member `interfaces` / `relationships` id lists in authored
  order — arrowheads per aspect are derived from members at render time.
  Containment containers come from the parent references client-side and
  are presentation, not part of this contract.
- **`unionGraph(payload, t, level)`** — the same roll-up over the
  **ever-live** rows (any non-empty `intervals[t].live`; a group's first
  ever-live row supplies display fields). Layout runs once on the union
  graph (elkjs, deterministic); per-position rendering filters nodes/edges
  without moving anything.

Composition order: `stateAt` → `scopeAt` → `rollUp` (diff overlays compute
`diffStates` and mark the rolled-up nodes/edges containing affected
entities). Every canvas view and every table reads from this one pipeline.

## Confirmed UI direction (2026-08-27) — normative

[ui-polish-direction.md](ui-polish-direction.md) is the authoritative UI
and interaction contract for the Phase 3 report. Where it conflicts with
"Stages instead of a time slider", "Views", "Canvas and look", or the
"Wave-2 UI contract" below, the direction wins; the Wave-2 contract
remains the record of what D10 built. Headline deltas from the built
wave-2 UI:

- **App shell** — Option E supplies the shell only: a compact header
  (model identity + `Cmd/Ctrl+K` global search), the **View** dock left
  (diagram selection + view controls), the adaptive **Info** dock right
  (inspector, opens on selection), and the full-width **Data** dock at the
  bottom (tables + payload viewer). Docks reserve layout space, resize,
  and collapse into rails; the only canvas overlay is the fixed lower-left
  `Map | Fit | − | % · level | +` cluster with its optional minimap. No
  floating selection toolbar, no status bar.
- **Controls move into View** — Diagram (grouped list: Architecture,
  Sequences), Detail (dropdown), Stage (dropdown — replaces the time
  slider and the Compare control), Relationship (dropdown — the "aspect"
  control), Tags (the only lens), Guided stories, Copy view link. Empty
  controls hide. Scope/hop controls are removed from the viewer.
- **Cards** — larger, text-led, one rounded shape for every kind; pills
  for kind and high-value facts; no vendor logos or generic entity icons.
  Semantic zoom is Far / Read / Full.
- **Edges** — **splines** are the only architecture edge style (orthogonal
  routing is superseded). Same-endpoint same-direction connections
  aggregate with a count chip; opposite directions stay two separated
  splines.
- **Selection** — one-hop IcePanel-style emphasis: strongest accent on the
  selected card, animated outgoing / static incoming splines in one accent
  color, brightened direct neighbors, dimmed-but-readable everything else.
- **Stability** — layout never moves across Stage, Relationship, or tag
  changes; tags brighten/dim, never hide; stage changes use pills and
  narrow border markers, never opacity.
- **Payloads and dependencies** — linked request/response/JSON/XML/CSV
  files list under Info's Attachments and open read-only in Data's Payload
  tab. Dependencies opens contextually from Info's "View dependencies",
  never from a global list.
- **Scope floor** — light theme only; viewports down to **1024 × 720**
  (the wave-2 500 px responsive target is superseded).
- **Removed or deferred** (full list in the direction): dark theme,
  application fullscreen, Share, a Changes diagram view or Info tab, saved
  report creation, manual card positioning, viewer scope/hop controls,
  Technology/Status lenses, floating panels.

## Stages instead of a time slider

The single interaction v1 and v2 never delivered — moving through the
architecture's states — ships as the **Stage dropdown** in the View dock
(the 2026-08-26 design review retired the slider; see the direction's
"Stage" section):

- One entry per named stage ("0 · Base", "4 · Transaction Core", …).
  Selecting a stage updates the canvas, Data tables, counts, and Info
  together, in place.
- Additions, removals, and changes are relative to the **previous stage**
  — diff styling is a property of the selected stage, not a separate
  Compare mode (the Compare control is removed). Stage changes render as
  pills and narrow border markers — colors always paired with a non-color
  cue per the v2 accessibility rule — and appear as a concise section in
  entity Info.
- A timeline picker appears when the architecture declares multiple
  timelines, making scenario comparison a two-click act.
- Progressive disclosure: with zero milestones (the common static case)
  the Stage control does not render at all — the report is a pure
  base-state explorer.
- Layout stability across positions: layout the **union graph** (all rows,
  all positions) once with elkjs, then keep node positions fixed while
  filtering — absent nodes drop/ghost rather than trigger re-layout.
  Ghosting composes with expansion (exit-gate fix 2026-08-30): an entity
  removed at the current position while EXPANDED renders as a ghost
  boundary (dashed, dimmed, no collapse control), so its removed children
  keep their layout parent instead of orphaning at the boundary-relative
  origin; ghost boundaries merge from the previous position's projection
  exactly like ghost nodes.
  This sidesteps v2's roadmap-displacement quality gates by construction; a
  per-position re-layout is an explicit user action ("re-fit this state").

## Views (dynamic, all URL-fragment encoded)

A view is a client-side configuration, shareable via View's **Copy view
link** (the direction's "Interaction and shared links" section governs
what a link preserves and excludes):

| Control | Fragment key | Values |
| --- | --- | --- |
| Detail | `level` | `systems` / `subsystems` / `containers` / `components` |
| Drill | `drill` | `<kind>:<id>` (child projection; pushes history) |
| Dependency focus | `deps` | `<kind>:<id>` (entered from Info's "View dependencies") |
| Stage | `timeline`, `time` | timeline + stage position |
| Relationship | `aspect` | calls / data flow / ownership |
| Tags | `lens` | emphasized tags (dim, never hide) |
| Selection | `select` | `<kind>:<id>` (current selection) |
| *(reserved)* | `view` | guided stories — D11 |
| Sequence view | `seq`, `scenario`, `step`, `focus`, `hide` | owned by sequence.md; canvas-only keys ignored in that section |

Removed keys (2026-08-27, per the confirmed direction): `scope`/`hops`
(scope is a report-*generation* concern, not viewer state — the scopeAt
projection stays in the contract for that pipeline), `compare`/
`compare-at` (each stage inherently diffs against the previous stage),
and `theme` (light only in the first pass). The `mode` key (MAP/PATH/
LENS) was already retired in wave 2. Dock sizes, collapsed state, table
layouts, searches, pan, and zoom are session-local (localStorage /
transient), never fragment state.

Saved Report Definitions (YAML files holding these fields) come later; the
URL fragment *is* the saved view in phase one. No coordinates, pan, or zoom
are ever persisted — reaffirming the v2 decision and closing the saved-
placement conflict the wip docs left open: v3.0 is auto-layout only, and any
future layout-hint feature is a new schema discussion, not a report feature.

## Canvas and look

- React Flow v12, custom nodes/edges. The visual language is the
  direction's "Canvas visual language": light, near-white, **plain**
  background (no grid or hatch); larger text-led cards in one rounded
  shape with kind/fact pills and no entity icons or logos; containment
  boundaries as subtle tints with clear headers; interfaces as small
  labeled ports attached where a spline connects; **splines** as the only
  edge style, with distributed anchors, aggregation count chips, wide hit
  rails, and one-hop IcePanel-style selection emphasis; graduated dimming
  for every emphasis state.
- elkjs layout in a web worker inside the report (deterministic: fixed
  seed, sorted inputs; hierarchical `INCLUDE_CHILDREN` from wave 2 for
  boundary boxes). Running layout in the viewer removes v2's unresolved
  "ELK needs a JS runtime in the CLI" gate entirely.
- The Option E docked shell (direction "App shell"): View dock left,
  adaptive Info dock right, full-width Data dock bottom, fixed lower-left
  Map/Fit/Zoom cluster; light theme; keyboard operability.
- AG Grid Community tables (entities, interfaces, milestones, diff) in the
  Data dock at v2 feature parity, always consistent with the canvas
  because both read the same filtered arrays; Data also hosts the
  read-only **Payload** viewer for linked request/response files
  (direction "Data dock").

## Wave-2 UI contract (v1)

Normative for D10 (D10a chrome/panels/tables, D10b canvas semantics and
visuals). Applies after the wave-1 (D9) gate. It **extends** "Client
projection contract (v1)": where this section names a change, this section
wins; everything it does not name is unchanged. Sources reconciled here
(2026-08-24): the twelve `p2-*` issues, the binding lists and measured
values in `research/ui/ui-research-findings.md`, and the mined subset of
`plans/arch/archive/v2-wip/interactions.md` (now superseded — see "Interaction
baseline"). Quoted pixel/opacity/duration values are the Archify-measured
styling reference — tune only by eye at the gate, never invent different
mechanisms.

> **Superseded where it conflicts (2026-08-27).** This contract is the
> record of what D10 built and gated. The confirmed direction
> ([ui-polish-direction.md](ui-polish-direction.md)) now governs the UI;
> the deltas are summarized in "Confirmed UI direction" above. In
> particular: the header's theme / copy-link / fullscreen actions, the
> bottom-right zoom rail, the floating legend panel, the "Fullscreen"
> section, dark theme, and the 500 px responsive target are superseded;
> the docked side panel becomes the Info dock, the bottom tables panel
> becomes the full-width Data dock, orthogonal edge styling gives way to
> splines, and MAP/READ/FULL reading depth becomes Far/Read/Full semantic
> zoom. Non-UI semantics — C4 zoom and drill, roll-up rules, graduated
> dimming as a reference, fragment restoration, reduced-motion and
> non-color-cue rules — carry forward.

### Chrome and layout (D10a)

- **One compact header line**: brand mark, model name, current-view
  summary, global actions (theme, copy link, fullscreen) *(superseded —
  the direction's header keeps only identity + global search; Copy view
  link moves to the bottom of View)*. No second
  full-width control bar; the canvas starts directly below the header.
- Controls sit in **grouped clusters** on/around the canvas: the time
  strip (timeline picker + slider + compare toggle) as one visual unit at
  the top of the canvas; the projection cluster (C4 zoom, scope, aspect)
  adjacent to the canvas; the **zoom rail** bottom-right (fit, zoom out,
  current percentage + reading depth, zoom in, fullscreen toggle)
  *(superseded — the direction moves controls into the View dock and puts
  one fixed `Map | Fit | Zoom` row at the lower left, with no fullscreen)*.
- Related controls share one card/pill container; unrelated controls never
  share a row. Every control has a visible label or tooltip.
- Narrow viewports: clusters collapse into menus, never wrap into stacked
  full-width rows *(the 500 px floor of this clause is superseded — the
  direction's first-pass minimum is 1024 × 720, with View auto-collapsing
  to its rail when Info opens at 1024 px)*.
- The MAP/PATH/LENS mode buttons are **removed** (resolves the D7 gate
  note): LENS is subsumed by the legend lens, PATH/guided views are D11
  (`view` fragment key stays reserved), MAP is simply the default state.

### Plain background (D10a)

Near-flat canvas in both themes: light = paper white / very subtle tint;
dark = flat dark surface (IcePanel-style, ~`rgb(31,33,33)` class). No
hatch or strong grid (do-not-copy: Archify's 32 px page grid); at most an
extremely faint dot grid that fades out below ~75% zoom. Nodes, edges, and
boundaries separate from the ground by contrast, not texture.

### Docked side panel (D10a)

Replaces the floating passport popup. Docked at the right edge; opens on
node / edge / boundary selection; the **canvas resizes** — the panel never
overlays it (do-not-copy: IcePanel's occluding overlay). Close deselects;
selecting another target swaps the content in place. Resizable and
collapsible per "Resizable panels".

- Header: kind icon + name. Tabs: **Details** and **Connections**.
- Details: description, kind, parent ("Belongs to", clickable), live /
  retired status at the current position incl. `clipped_by`, contains
  count, tags, properties as a key/value list, `start_in` / `end_in`.
- Connections: incoming and outgoing interfaces of the selection at the
  current position (live only), grouped by direction under the current
  aspect; each row clickable (selects that interface / other endpoint).
  Plus an **Open dependency view** action.
- Edge selection shows the same panel for the aggregated edge: direction
  summary and the full member interface/relationship list — every
  canonical member reachable, activating one selects it (INT-SELECT-16).

### Resizable panels (D10a)

Bottom tables panel, right side panel, and the legend panel each get: a
drag handle (bottom panel: height; side panel: width), a collapse toggle
that reduces to a slim bar and restores the previous size, and
double-click-on-handle to reset the default. The canvas absorbs freed
space and refits without losing the current zoom/pan intent. Sizes and
collapsed state persist per session (localStorage, validated on load);
pixel sizes never enter URL fragments.

### Fullscreen (D10a) — removed 2026-08-27 (direction: no application fullscreen)

Toggle on the zoom rail + keyboard `f`; Escape exits after higher layers
(menus, then side panel) have dismissed. Browser Fullscreen API where
available, full-window layout fallback under `file://`. Header and bottom
tables panel hide; floating clusters and the side panel remain usable.
Entry preserves selection and view state and refits the camera; exit
restores the inline layout and the invoking control's focus. Transient —
never in the URL.

### Tables at v2 parity (D10a)

AG Grid Community + a custom toolbar (harvest the v2 donor's
`grid/ArchitectureGrid.tsx` patterns):

- multi-sort; quick-search box over all columns; per-column filters with
  kind/status as set filters;
- searchable Columns menu: hide/show, pin, drag to reorder, drag to
  resize; density toggle;
- per-table layout persistence to localStorage validated against known
  columns on load (v2 `tableLayouts` pattern), plus a "Reset table"
  action;
- copy-selected-as-TSV and CSV export (filtered / all);
- row selection synced with canvas selection in both directions;
- columns = core fields plus auto-discovered property columns.

### C4 zoom and drill (D10b)

The flat level selector becomes a four-level **C4 zoom** control.
(Level model renamed 2026-08-28 — Subsystem replaces the former
`top-containers` / "Child Containers" split; see schema.md "Entity
kinds".) Internal level ids (fragment tokens and the `rollUp` level
argument) with their UI labels:

| Level id | UI label | Node set |
| --- | --- | --- |
| `systems` | System | systems roll-up; flat, no boundaries |
| `subsystems` | Subsystem | subsystems as nodes; a container with no subsystem stays itself; components/code roll up through their container |
| `containers` | Container | every live container stays itself; subsystems and systems become boundaries |
| `components` | Component | components level (a container without live components represents itself) |

The Subsystem option is **hidden** when the model defines no subsystems
(the level is dataset-optional); its fragment token remains valid and
then renders identically to an all-ungrouped subsystem view. Users stay
plain nodes at every level. `rollUp`'s edge rules (unordered pair key,
self-pairs dropped, member id lists, direction from members) are
unchanged; the representative function follows the strict
System ⊃ Subsystem ⊃ Container ⊃ Component ⊃ Code layering. Projection
vectors are renamed/re-cut to these levels (subsystem roll-up gets its
own vector cases).

**Boundary boxes** (presentation, IcePanel profile): ancestors above the
active level render as containment group boxes — thin rounded outline
(~8–10 px radius), restrained fill, small icon + name label at the top
left (no solid title bar), generous inset around children. At
`subsystems`: systems with displayed children are boundary boxes,
childless systems are plain nodes. At `containers`: system boundaries plus
subsystem boundaries, nested. At `components`: the full
system/subsystem/container ancestor chain. Boundary boxes are selectable (open the
side panel) but are **never edge endpoints** — edges attach to displayed
leaf nodes and cross boundary outlines (research A2). A roll-up node that
hides children carries a child-count badge.

Layout: union graph per level through ELK **hierarchical** layout
(`INCLUDE_CHILDREN`), deterministic; positions stay fixed while scrubbing;
boundary boxes size to their laid-out children.

**Drill** — distinct from selection (INT-C4NAV-02; research #2): a node
or boundary with live children exposes an explicit drill affordance
(magnifier button + keyboard action; primary click remains selection).
The drill projection renders the drilled entity as one boundary box
containing its live **direct children** (whatever their kinds); a
connection with an endpoint inside the drilled subtree keeps that
endpoint's representative among the displayed children, while the outside
endpoint rolls to its system representative rendered as a collapsed
boundary stub (existing stub styling). Drill state is the `drill`
fragment key and **pushes history** — browser Back returns
(INT-C4NAV-06/08); a breadcrumb chip in the header shows the drill path
with an Up action. Drill respects the time position; the scope control is
disabled while drilled *(moot since 2026-08-27 — the viewer no longer has
a scope control)*.

### Entity boxes (D10b)

Uniform size per level (layout stability); text never overflows the box.
Anatomy, top to bottom:

- **context line** — parent name, small and muted;
- **identity line** — icon + name; the icon derives from a recognized
  `technology`/`type` property value, else the kind default; users get a
  person glyph, store-like nodes may use a cylinder;
- **description** — one–two lines, truncated;
- **facts line** — up to two `key: value` property pairs; the keys are
  the two most frequent property keys across the current scene
  (deterministic; alphabetical tie-break);
- **badges** — child count, tag count, the existing revision/diff badges,
  clip state.

**Reading depth** gates the content (research #5/#6; INT-VIEW-10/11/15):
**MAP** (<100%) icon + name only; **READ** (100–174%) adds context line,
description, badges; **FULL** (≥175%) adds the facts line and edge label
chips. Thresholds are centralized constants, not scattered per component.
The zoom rail displays the current depth + percentage and updates on every
camera change, whatever caused it (INT-VIEW-14). Facts hidden at the
current depth remain available through selection and the side panel.

### Edges and emphasis (D10b)

Styling reference (measured; tune by eye at the gate):

- default stroke 1.5 px, clearly visible in both themes (`#7b97aa`-class
  in light — not near-invisible grey); emphasis 1.8 px teal (`#0d9488`
  light / `#2dd4bf` dark); filled triangle arrowheads; labels in pill
  chips on the path.
- every edge has a transparent **~24 px hit rail** and a visible ~6 px
  focus rail (research #4; INT-SELECT-14); line, label, and rail all
  select the same canonical edge.
- anchors distribute on the node side facing the counterpart; parallel
  connections between one pair are already one aggregated edge (unordered
  key) — it shows a member-count chip; routing avoids crossing node and
  boundary interiors where ELK permits.

**Selection emphasis** (p2-ui-flows-animation): the selection's
**outgoing** edges (direction under the current aspect, derived per
member) animate a directional dash flow (~1.75–2.15 s period); its
**incoming** edges get the static emphasis stroke — in vs out readable at
a glance. An aggregated edge with members both ways highlights without
animation and labels both directions. Unrelated content dims per the
tiers below; the selection's edge labels stay legible. Deselect restores
neutral. `prefers-reduced-motion` replaces all animation with the static
highlight (INT-A11Y-07).

**Graduated dimming tiers** — emphasis always dims, never hides
(research #3):

| State | Emphasized | Neighbors | Unrelated |
| --- | --- | --- | --- |
| selection | 1.0 (+ shadow) | 1.0 | 0.13 |
| hover (fine pointers only) | 1.0 | 1.0 | 0.2 |
| lens | 1.0 | 0.62 | 0.11 |

Dimming combines opacity with the existing non-color cues; color or
motion alone never carries meaning (research #10; INT-A11Y-03).

### Legend and tag lens (D10b) — floating panel superseded (Tags moves into the View dock)

A floating, collapsible legend panel on the canvas (reusing the D10a
panel behaviors; the one floating panel in wave 2). Entries = the **tags**
present in the current projection — swatch + label + count, counts
computed from the projected arrays, never the DOM (INT-LEGEND-07);
zero-count entries omitted. Clicking an entry toggles that tag in the
**lens** (multi-select, OR semantics); matched / neighbor / unrelated
render per the lens dim tiers. Nothing is ever hidden and there is no
solo/isolate mode (decision 2026-08-24). Selecting every tag or clearing
the last one returns to neutral (INT-LEGEND-05); an explicit Clear exists.
Keyboard operable with visible pressed state. Lens state lives in the
`lens` fragment key, never in saved data; the lens never changes scope,
selection, layout, or the grids (INT-LEGEND-08/09). A configurable driver
(property/kind switch) is deferred.

### Dependency focus view (D10b)

A dedicated view for one focused entity (IcePanel dependencies pattern;
research #7 — supersedes INT-FOCUS-10..14's in-place emphasis):

- the focused entity centered; **incoming** dependencies as a left
  column, **outgoing** as a right column, at the current C4 level's
  representatives; direction per the current aspect;
- one bundled edge per neighbor with a connection-count chip; header
  totals: incoming dependencies, outgoing dependencies, total
  connections; live interfaces only, at the current time position;
- rows are entity boxes (anatomy above); clicking one refocuses the view
  on it; the side panel follows the selection; a picker at the top swaps
  the focus entity;
- entered from the side panel's "Open dependency view" (and a canvas
  control when an entity is selected); encoded as the `deps` fragment key
  (pushes history); Back or an explicit close returns to the map.

### Interaction baseline (mined from wip/interactions.md, 2026-08-24)

`plans/arch/archive/v2-wip/interactions.md` is **superseded**. These are the clauses
carried into v3, adapted to v3 naming; everything not listed is dropped
or deferred (notably PATH/route probe, radar, guided stories → D11; scope
builder, saved reports, attachments, tabs → out of scope or later
phases).

- One action → one coherent state change; selection is shared between
  canvas and tables; a stale async layout/projection result never applies
  (INT-STATE-01/02/06).
- Fit changes only the camera. Reset view also clears lens and drill/deps
  emphasis but keeps a valid selection (INT-VIEW-01/02). Camera moves
  from selection or table-row activation reveal the target without
  needless zoom change; an already fully visible target does not move the
  camera (INT-VIEW-08/09).
- Keyboard: the canvas is one page-level tab stop; Enter/Space selects;
  `Ctrl`/`Cmd` `+`/`-`/`0` zoom in/out/reset while the frame has focus
  (INT-VIEW-05); Escape dismisses one layer at a time in the order menu →
  side panel → lens/drill/deps emphasis → fullscreen (INT-DISMISS-01);
  letter shortcuts never fire from text inputs (INT-SHORT-02).
- Fragment restoration validates every id against the payload, applies
  the remaining valid state with a console-visible diagnostic, and never
  substitutes by display name (INT-LINK-03/04). Meaningful view changes
  (drill, deps, guided view) push browser history; selection, lens, and
  slider changes replace URL state (INT-LINK-07; INT-C4NAV-08).
- Reduced motion removes edge animation and animated camera transitions
  (INT-A11Y-07); touch targets ≥ 44 px where space permits
  (INT-A11Y-08); hover previews are omitted on coarse pointers without
  hiding any fact (INT-RESP-06).
- An empty projection explains why and offers a recovery action; a layout
  or render failure keeps the app navigable with a concise diagnostic
  (INT-FAIL-02/05).

**Overrides** — where the 2026-08-24 decisions or issue text beat the
INT-* contract, recorded per open question 6:

| Superseded INT clause(s) | Winner |
| --- | --- |
| INT-LEGEND-01 legend over kinds/statuses/scopes/types | tags-only first pass; driver switch deferred |
| INT-FOCUS-10..14 in-place inbound/outbound emphasis controls | dedicated dependency focus view (`p2-ui-dependency-focus`) |
| INT-SELECT-07 separate floating Relationship Passport | docked side panel showing the aggregated edge's member list |
| INT-PANEL-02..11 floating drag-grip panel machinery | docked resizable panels; only the legend floats (collapse, no drag contract) |
| INT-FRAME-04/05 MAP/PATH/LENS as primary modes | mode buttons removed; lens = legend, PATH → D11 guided views, MAP = default |

(The `p2-ui-legend` hide-vs-dim and `p2-ui-nested-groupings`
expand-vs-drill conflicts were resolved the other way — the INT/research
position won by user decision; both issue files carry the decision note.)

### Wave-2 verification (gate inputs)

- The existing vitest vector suite stays green — contract-v1 semantics
  are unchanged for the existing levels.
- The structural tests listed in the D10 prompts (top-containers
  invariants, drill node set, legend counts).
- A rule-9 Playwright pass per `wip/notes/test-ui.md`: clean console and
  **zero external requests from `file://`** remain gate checks
  (do-not-copy: remote assets, Google Fonts included).

## Polish contract — pass 1: app shell (D13a)

Normative for D13a (re-authored 2026-08-27; the 2026-08-25
presentation-only pass-1 contract is superseded — full text in git
history). This pass implements the app-shell portion of
[ui-polish-direction.md](ui-polish-direction.md); the direction is
authoritative for behavior, this section scopes exactly what pass 1
changes and what waits for later passes. Unlike its predecessor this
pass changes structure and behavior: chrome layout, control types, and
fragment keys.

### Shell regions

Per the direction's "App shell" table and defaults:

- **Header** (compact): brand mark, model name (payload `source`), and
  the global search trigger with `Cmd/Ctrl+K`. Nothing else — the theme
  toggle, fullscreen, and copy-link controls leave the header.
- **View dock** (left, open by default): the grouped diagram list
  (Architecture → Canvas, the default; a Sequences group only when the
  payload has sequences — none yet; Dependencies is not a list item)
  followed by the view controls in the direction's order: Detail, Stage,
  Relationship, Tags, Guided views (absent until D11), Copy view link.
- **Info dock** (right, collapsed until selection): rehouses the
  existing side panel as-is — Details/Connections tabs, aggregated-edge
  member rows, the dependency action. Content redesign is pass 4; pass 1
  changes the housing only: opens on selection, swaps content in place,
  close deselects.
- **Data dock** (bottom): rehouses the tables panel; spans the full
  application width beneath View, Canvas, and Info; collapses (the
  default) into a full-width bottom bar; tabs unchanged (Entities,
  Interfaces, Milestones, Diff).
- **Dock behavior**: each dock is resizable and collapsible (side docks
  into attached rails, Data into the bar); double-clicking a resize
  handle restores the default size; sizes and collapsed state persist in
  localStorage (extend the existing `layoutPreferences` pattern), never
  in fragments. At 1024 px width, opening Info collapses View to its
  rail; closing Info restores it.
- **Camera on dock changes**: keep the existing refit behavior for now —
  the direction's preserve-zoom / minimal-shift contract is pass 2
  (D13b). Do not add new camera logic in this pass.

### Controls conversion

- **Detail dropdown** (System / Subsystem / Container / Component —
  level model renamed 2026-08-28; the Subsystem option is hidden when
  the model defines no subsystems) replacing the level control; the
  `level` fragment tokens are the level ids in the C4 zoom table.
- **Stage dropdown** ("0 · Base", "1 · <name>", …) replacing both the
  time slider and the Compare control. Selecting a stage updates canvas,
  Data tables, counts, and Info together. Diff styling is driven by
  (position, position − 1) — the separate compare mode and its fragment
  keys are removed. The timeline picker stays, rendered only with
  multiple timelines.
- **Relationship dropdown** (Calls default / Data flow / Ownership)
  replacing the aspect control; `aspect` fragment tokens unchanged.
- **Tags**: the floating legend panel is removed; the tag lens moves
  into View with the same multi-select OR, dim-never-hide semantics,
  projected-array counts, Clear action, and `lens` fragment key.
- **Scope**: the control is removed from the viewer (the `scopeAt`
  projection function and its vectors stay — it is a generation-time
  concern).
- **Progressive disclosure**: Stage hides with zero milestones, Tags
  with zero tags, the timeline picker with one timeline.

### Global search

`Cmd/Ctrl+K` opens a floating search box (temporary UI — it may float
while active). It matches entities and interfaces by name and id among
rows live at the current stage position, plus diagram names. Choosing a
model item switches to Canvas when needed, centers and selects it, and
opens Info; arrows + Enter navigate; Escape closes. Flat ranked list —
no fuzzy-match dependency.

### Map, Fit, and Zoom

One fixed row at the canvas lower left:
`Map | Fit | − | percentage + semantic label | +`, replacing the
bottom-right zoom rail. Map toggles the minimap, which attaches directly
above the row and is closed by default. The semantic label is renamed
Far / Read / Full (labels only — the thresholds are re-derived in
pass 2). Controls never move as values change. The status bar is
removed: a transient "Laying out" indicator appears beside the row while
layout runs; the node/connection counts and `rendered-node-ids` span
stay in the DOM visually hidden (clip-rect) with their data-testids.

### Removals

Dark theme and its toggle (delete the dark variable set), application
fullscreen (control, `f` key, Escape layer), the floating legend, the
time slider, the Compare control, the scope control, and the header
copy-link (it moves to View). Escape order becomes: topmost temporary
UI (menu / search) first, then clear selection and close Info. Escape
never collapses docks.

### Fragments

Removed keys: `scope`, `hops`, `compare`, `compare-at`, `theme`
(removed/unknown keys are ignored with the existing console
diagnostic). New key: `select` = `<kind>:<id>` — the current selection,
written on selection change (replaceState, not push), restored on load
after validation against the payload (invalid → ignored). All other
keys keep their wave-2 semantics.

### Visual foundation (carried from the superseded contract, light only)

- Tokens on `:root`: fonts, type scale (no chrome text below 11 px),
  spacing 4/8/12/16/24 px, radius 6/10 px, two elevations, 30 px
  control height. Light theme only — no dark redefinitions.
- Sans-for-UI / mono-for-data split; the uppercase mono micro-labels
  become sentence-case sans labels.
- One shared surface recipe (background, border, radius, elevation) for
  docks, rails, the lower-left cluster, minimap, and menus.
- Inline-SVG chrome icons (16×16 viewBox, 1.5 px stroke,
  `currentColor`, local components — no icon font, no external assets).
  Node kind icons and the drill magnifier are untouched (pass 3 owns
  cards).
- Contrast audit: labels ~4.5:1 against their surface, interactive
  outlines ≥3:1.

### Verification (gate inputs)

- Tests: update ONLY tests that reference removed or moved chrome
  (theme, fullscreen, slider, compare, scope, legend); the
  projection/vector suites pass untouched. New tests, exactly four:
  (1) `select` fragment round-trip + invalid-id ignore; (2) removed
  fragment keys ignored with a diagnostic; (3) the Stage dropdown
  renders one entry per position and drives the same projected state as
  the old slider; (4) dock size/collapse localStorage round-trip.
- Rule-9 browser pass at 1440 × 900 AND 1024 × 720, light theme, from
  `file://`: clean console, zero external requests; docks resize,
  collapse, and restore; opening Info at 1024 collapses View; the
  selected item stays visible when Info opens. Screenshots for the
  gate: default view before/after at 1440 × 900, plus 1024 × 720 with
  Info open.

## Polish contract — pass 2: canvas composition (D13b)

Normative for D13b (authored 2026-08-28, after the D13a gate). This pass
implements the layout / fit / camera portion of
[ui-polish-direction.md](ui-polish-direction.md) on top of the D13a
docked shell. It owns card *geometry*, layout tuning, framing, semantic
thresholds, and every camera movement. It does NOT own card anatomy,
edge rendering, or selection emphasis (pass 3), nor dock content
(pass 4). Closes or discharges ui-polish issues #8, #9, #10, #11, #12,
#15 (see gate inputs).

### Card geometry (sizing only — anatomy is pass 3)

- Replace the fixed 250 × 168 card with per-Detail-level size tiers:
  uniform card **width** per level (starting values: System 280 px,
  Subsystem 260 px, Container / Component 240 px — level names per the
  2026-08-28 rename; tune against the acceptance checks), **height from
  content**. Uniform width within
  a level keeps ELK's layered ranks clean; content-driven height kills
  the ~80%-empty box.
- Names wrap to at most two lines within the tier width; a name may
  truncate only after two full lines (#10 — "a name never truncates
  while its box has empty rows" becomes structural: the box has no
  empty rows). The current card content (kind label, name, facts at
  FULL) is otherwise unchanged.
- Sizing is a pure function `cardSize(node, level, measure)` in a new
  module, where `measure(text, font) → px` is injected: production
  passes a shared offscreen-canvas measurer, tests pass a fixed-width
  stub so results are deterministic. `layout.ts` consumes per-node
  sizes; `NODE_WIDTH`/`NODE_HEIGHT` remain only as fallbacks.

### Layout tuning (ELK)

- Keep `elk.algorithm: layered`, `INCLUDE_CHILDREN`, and the fixed
  random seed. Add an aspect-ratio hint toward the visible canvas
  (`elk.aspectRatio` ≈ visible width / height, clamped to [1.2, 2.0]).
- Tighten spacing (starting values, tune to acceptance):
  `elk.spacing.nodeNode` 72 → 40,
  `elk.layered.spacing.nodeNodeBetweenLayers` 120 → 72.
- Boundary padding becomes proportional: top = boundary header height
  + 12 px; sides/bottom 20 px; nested boundaries do not multiply the
  top padding (only the outermost header needs the full clearance
  beyond its own).
- **Grid packing for sparse drill sets:** when the union graph for the
  current layout key has zero edges, skip ELK and pack leaf cards into
  a near-square grid (`ceil(sqrt(n))` columns, tier spacing), keeping
  boundary nesting. Deterministic order: existing node order.
- Layout input stays a function of `(timeline, level, drill)` only —
  Stage, Relationship, and tag changes must not recompute layout or
  move boxes (the existing `layoutKey` contract, now asserted by a
  test).

### Initial framing and Fit

- Fit rect is the *visible* canvas — the flex cell between the docks
  (#8, #9). The D13a shell already reserves dock space, so React
  Flow's `fitView` rect is correct by construction; this pass asserts
  it and removes any use of the full window.
- **Cold load / projection change:** fit the whole graph, capped at
  100% zoom — the first picture is always the complete landscape (P13
  rule, 2026-08-30, supersedes the earlier Read-floor rule; issue p18).
  Applies equally to hash-restored views without an explicit camera.
- **The explicit Fit button** always fits the whole graph.
- The framing decision is a pure function
  (`initialViewport(graphBounds, visibleRect)`) with tests.

### Semantic-zoom thresholds (#11)

Re-derive Far / Read / Full from the real card scale: Read is the zoom
where a card's name line renders at ≥ 11 screen px; Full is where body
text renders at ≥ 11 screen px. Derive the two constants from the
type-scale tokens, document the derivation in `zoom.ts`, and update the
`readingDepth` boundaries. Labels stay Far / Read / Full. The MAP→READ
mismatch (evidence baseline) must be gone: at cold-load framing of
acme's System level the view is at Read with readable names.

### Camera changes (replaces the D13a temporary refit)

One pure helper `shiftViewport(viewport, visibleRect, focusRect) →
viewport` computes the minimal pan (zoom unchanged) that brings the
focus rect inside the visible rect; returns the viewport unchanged when
it already is. Apply it to:

- **Dock open / close / resize** (including Data): preserve zoom, shift
  only enough to keep the focus visible — never a full Fit. Focus =
  the current selection's node (plus its direct neighbors when they fit),
  else the viewport center. Remove the D13a `fitView`-on-dock-change
  effect.
- **Selection / Info opening** (#12): when Info opens (canvas click,
  Data row, search, fragment restore), keep zoom and pan minimally so
  the selected node stays inside the visible canvas; if the selection's
  one-hop neighborhood cannot fit at the current zoom, fit to that
  neighborhood instead (the only sanctioned zoom change).
- **Viewport resize** (window or 1024 transition): same minimal-shift
  rule.

Chrome persistence (#15): no interaction may remove persistent chrome —
already structural after D13a (the vanishing time pill is gone); the
gate walkthrough re-checks it.

### Map

The minimap keeps its D13a attachment above the lower-left row and must
render the content-sized cards correctly (React Flow handles this; the
gate eyeballs it). No behavior change.

### Verification (gate inputs)

- Tests — exactly six new cases (plus mechanical updates to existing
  tests that assert the old fixed card size or thresholds):
  (1) `cardSize`: a long name wraps to two lines and grows the box; no
  truncation while spare height remains (stub measurer);
  (2) `initialViewport`: fits the whole graph, capped at 100% zoom
  (recut by P13 — the historical Read-floor vector is superseded);
  (3) `shiftViewport`: focus inside → unchanged; focus outside →
  minimal pan, zoom unchanged;
  (4) layout stability: position/aspect/lens changes leave the layout
  key and ELK input unchanged;
  (5) grid packing: an edgeless drill set packs into a non-overlapping
  near-square grid;
  (6) `readingDepth`: boundaries equal the derived constants.
  Projection vectors and all existing suites stay green.
- Rule-9 browser pass at 1440 × 900 AND 1024 × 720, light, `file://`:
  clean console, zero external requests; cold load centered with
  readable names (no dead-space fit — #8); opening/closing/resizing
  Data and Info preserves zoom and keeps the selection visible (#9,
  #12); Stage and Relationship switches move nothing; Container level
  readable at its default framing (#11); an edgeless drill set shows a
  grid. Screenshots for the gate: cold load at 1440 × 900 (before and
  after), cold load at 1024 × 720, Info open with a selection visible,
  Container level default framing.

## Polish contract — pass 3: graph elements (D13c)

Normative for D13c (authored 2026-08-28). This pass implements the
Cards / Containment and interfaces / Splines / Selection sections of
[ui-polish-direction.md](ui-polish-direction.md) on top of the D13b
canvas composition. It owns what cards, boundaries, ports, and edges
*look like and emphasize*; it does NOT own layout, framing, camera, or
thresholds (pass 2, unchanged) nor dock content (pass 4). Closes or
discharges ui-polish issues #1–#7 (see gate inputs).

### Card anatomy (within pass 2's geometry contract)

- One rounded rectangular card for every kind — actors, systems,
  containers, components. Remove the `entityIcon` glyph set and the
  kind-specific letterforms entirely; kind is conveyed by a **kind
  pill**, not an icon or shape (direction "Cards").
- Card content at each depth (semantic zoom, thresholds from pass 2):
  - **Far**: kind pill + full name.
  - **Read**: + one/two description lines + up to three high-value
    fact pills.
  - **Full**: + the remaining approved details (child / connection
    count when relevant) and neutral edge labels (see Splines).
- Name wraps to two lines before truncating (pass 2's rule); hover
  and Info always carry the full value.
- The content model feeds pass 2's `cardSize(node, level, measure)` —
  update its content model to this anatomy, keeping the injectable
  measurer and the per-level tier widths. Existing cardSize tests
  update mechanically; the "no truncation while spare height remains"
  invariant must keep holding.
- **Drill affordance**: boxes with children get a small *persistent*
  drill control (visible at every depth, not hover-only) with a real
  hit target (≥ 24 × 24 px), replacing the `⌕` glyph button. It stops
  propagation (drill, not select), and keeps its aria-label.
- **Boundary stubs** (external endpoints across a drill cut): never an
  empty box (#6's floaters) — render as a compact card: kind pill +
  name + an "external" marker. Same recipe, reduced content.
- **Stage-diff on cards** (#7 sibling rule): added / removed / changed
  render as pills and a narrow accent border marker — never opacity,
  never a fill wash (direction "Selection", last rule). The Δ
  change-popover stays as-is this pass (pass 4 moves field changes
  into Info and removes it).

### Containment boundaries

Boundaries render as subtle tinted regions — a light fill tint and a
1 px border distinct from any edge stroke — with a clear header
(name + kind pill + the drill control). Selectable; no in-place
expand/collapse. The header must remain readable at Read framing of
the Container level (D13b acceptance baseline).

### Splines (replaces orthogonal routing — kills #4/#5)

- **Path**: bezier splines are the only architecture edge style.
  Replace `getSmoothStepPath` with bezier paths between
  geometry-derived anchor points. No orthogonal segments remain.
- **Anchors**: replace the hash-mod-3 left/right handles with floating
  anchors computed from geometry — each endpoint anchors on the card
  border facing the other endpoint (any of the four sides), so routes
  head toward their target instead of detouring (#4). Parallel splines
  between the same pair separate by offsetting their anchor points.
  Pure function: `edgeAnchors(sourceRect, targetRect, laneIndex,
  laneCount) → {sourcePoint, targetPoint}` — testable without React
  Flow.
- **Routes avoid interiors**: with facing anchors and bezier control
  points perpendicular to the card border, routes must not cross card
  bodies except when endpoints overlap after layout (#5); no route may
  loop around empty space larger than the cards it avoids (#4's
  acceptance).
- **Direction split**: rendered splines are per-direction. Members of
  an aggregated (a, b) edge resolve their direction under the active
  Relationship; forward members render on one spline, reverse members
  on a second separated spline, and a bidirectional member counts on
  both. Each spline is independently selectable and animatable
  (direction "Splines"). Selecting either spline opens the shared
  member list in Info. Edge selection stays local (no payload row id —
  D13a rule unchanged).
- **Aggregation chips**: a spline whose direction group has more than
  one member shows a count chip on its label pill.
- **Contrast and arrowheads** (#1, #2): neutral splines use a real
  stroke (from the token palette, ~4.5:1 against the canvas at
  standard weight) with zoom compensation so an edge never renders
  below ~1.5 screen px; every spline ends in a visible arrowhead
  sized with the same compensation (custom marker — the React Flow
  default gray is superseded). Selected/emphasized splines gain weight
  and the accent.
- **Labels** (#3): label pills (name + count chip + diff icons) render
  for *neutral* splines at Full only; a selected or hovered spline
  shows its label at every zoom. The label pill is also the spline's
  primary click target (keep the existing wide hit path underneath).
- **Stage-diff on splines** (#7): base splines stay at full neutral
  legibility in every stage; added / removed / changed styling is an
  increment (diff hue + label icon, dashed for removed) on top of the
  base weight — the diff may never be more visible than the
  architecture.

### Interfaces as ports (#6)

Interfaces render as small labeled ports attached where a spline
connects to the owning (provider) card or containment boundary — a
small chip sitting on the border at the spline's anchor point. At Far
and Read a port is a dot; at Full, and whenever its spline is selected
or hovered, it shows the interface name (aggregated splines: one port,
name of the first interface + count). Never render a detached empty
interface box. Ports are part of the spline's hover/selection group.

### Selection emphasis (IcePanel one-hop model)

Refine the existing emphasis machinery to exactly the direction's
model, one hop, one accent color:

- selected card: strongest accent border;
- direct outgoing splines: accent + directional animation;
- direct incoming splines: same accent, static;
- direct neighbor cards: brightened;
- everything else: dimmed but readable (opacity floor — text still
  legible, never invisible);
- arrowheads keep direction without motion;
- `prefers-reduced-motion`: static emphasized splines both directions;
- emphasis priority: selection one-hop > tag lens > neutral (guided
  stories slot in above tags when D11 lands).

Switching Relationship re-resolves spline directions, animation, and
incoming/outgoing grouping — the picture visibly changes while no box
moves (pass 2's layout-stability contract already enforces the
latter).

### Mechanical consequences

- `entityIcon` is deleted; the dependency view and any other glyph
  call sites take the kind-pill treatment (content otherwise
  unchanged — the dependency view's own redesign is not this pass).
- The `.semantic-edge` CSS block is rewritten for splines; the D10b
  edge-anchor hash and its handle ids go away.

### Verification (gate inputs)

- Tests — exactly five new cases (plus mechanical updates to existing
  cardSize / emphasis / presentation tests):
  (1) `edgeAnchors`: anchors land on the facing borders of both rects
  (all four relative placements) and parallel lanes get separated
  points;
  (2) direction split: an aggregate with forward + reverse +
  bidirectional members yields two splines with correct member counts
  under each Relationship;
  (3) label visibility: neutral label only at Full; selected/hovered
  label at every depth (pure decision function);
  (4) emphasis classification: selection assigns
  outgoing/incoming/neighbor/unrelated correctly on a small graph,
  and tag-lens dim never overrides one-hop emphasis;
  (5) port assignment: interfaces map to the provider-side anchor,
  aggregated splines yield one port with a count.
  Projection vectors and all existing suites stay green.
- Rule-9 browser pass at 1440 × 900 AND 1024 × 720, light, `file://`:
  clean console, zero external requests; no orthogonal detours or
  interior crossings on acme at System and Container levels (#4, #5);
  every edge visibly stroked with an arrowhead at cold-load zoom (#1,
  #2); labels behave per depth/selection (#3); no detached empty
  boxes (#6); Stage switch shows diff as increments on a legible base
  (#7); selecting a card reproduces the IcePanel one-hop picture,
  including under forced `prefers-reduced-motion`; Relationship
  switch visibly changes arrows/animation with zero node movement.
  Screenshots for the gate: System level cold load, Container level,
  a selection with one-hop emphasis at 1440 × 900, the same selection
  under reduced motion, and a Stage-diff view.

## Polish contract — pass 4: View / Info / Data content and states (D13d)

Normative spec for the last 3P pass (authored 2026-08-29 after the D14
gate; decision source: ui-polish-direction.md "View dock" / "Data dock" /
"Info dock" + ui-polish.md #13, #16-rest, #20, #21, #22, #25, #26, #27).
Grounded in the post-D14 tree: the Info panel is `SidePanel` in App.tsx
(Details/Connections tabs, raw `ordinaryFields` kv, bare Contains count,
"Open dependency view" at the bottom of Connections), dock chrome is
`ResizablePanel.tsx` (text-label `panel-collapse` button, 34 px collapsed
strip), tables are `GridPanel.tsx` (AG Grid, five tabs incl. the D14
`subsystems` tab, no auto-size/empty-collapse), View is `ViewDock.tsx`.
Pass 2's layout/camera modules, pass 3's edge/card modules, and
projection.ts are OUT OF SCOPE — do not touch them.

### Shell (#25, #26)

- The app fills the browser viewport at every window size at or above the
  1024 × 720 floor: no fixed-size render, no outer page scroll, no dead
  band. Below the floor the app clamps to 1024 × 720 and the *page*
  scrolls (existing `min-width`/`min-height` behavior); at or above it,
  header, docks, and canvas flex to consume exactly 100vw × 100vh. Audit
  the generated single-file template's wrapper markup too — the fix must
  hold over `file://` in the generated report, not just `vite dev`.
- Dock chrome uses standard panel patterns. Each dock gets a slim header
  row: dock title, then an icon-only collapse chevron (`aria-label`,
  `title` tooltip) — the floating "Collapse View dock" / "Collapse Data
  dock" pills, the rotated-text "Open Info dock" gutter, and the "Open
  Data dock" text strip are all removed. A collapsed dock renders as a
  slim icon rail (vertical for View/Info, horizontal for Data) whose
  icon button reopens it; rails never overlap canvas content (they keep
  reserving layout space as today). Resize handles and double-click
  default-restore keep their D13a behavior.
- View-dock content rows restyle as compact list rows: the grouped
  diagram list (the oversized Canvas/Model map card becomes a list row
  with a small glyph), and the Copy view link footer row. Same type
  scale and row height as the rest of the dock.

### View dock (#27, direction "View dock")

- Controls with no meaningful choice hide: Stage hides when the active
  timeline has no milestones (Timeline already hides for a single
  timeline; Detail already hides Subsystem for subsystem-less models —
  keep both), Tags hides when the model has no tags. Relationship always
  renders. Guided-view controls render only when authored guides exist —
  none do until D11, so nothing renders (the hide rule IS this pass's
  deliverable; do not build guided-story UI).
- Tags caps at 5 visible rows, then scrolls internally inside a fixed
  max-height; the tag count column and lens behavior are unchanged; the
  rest of the View stack stays visible below it.

### Info dock (#13, #16-rest, #20, #21)

- **Details kv grid.** One label style: humanized Title-Case labels
  (snake_case converted, e.g. `end_in` → "End in",
  `availability_target` → "Availability target") for built-in fields and
  properties alike; a two-column grid where label and value can never
  collide (long values wrap under their own column). "Contains" stops
  being a bare count: it renders the contained rows as clickable chips
  (name, kind-colored) that select the child; cap at 8 chips + an
  "and N more" chip that expands.
- **Stage changes in Details.** When the selected row has a diff status
  at the current stage (added / removed / changed relative to the
  previous stage, same source as the Data Diff tab), Details shows a
  concise "Changes at this stage" section: status line, and for
  `changed` the changed fields as old → new rows. The canvas card's Δ
  `change-popover` is REMOVED (D13c intentionally left it for this
  pass); update the Escape handler that queries `.change-popover[open]`.
- **Connection Info.** A selected interface/relationship/spline gets
  tabs that make sense for its kind — Details only (plus the member list
  for aggregated splines); the "Connections" tab renders only for
  entities. Interface Details shows: both endpoints as linked rows
  (provider/consumer resolved to display names; click selects that
  entity), direction under the active Relationship (from
  `call_direction` / source→target), the interface name and id,
  relationship values (properties as the same humanized kv, tags as
  chips), and the lifecycle interval rendered from the payload
  `intervals` (live segments as stage names, e.g. "Base → 3 · Catalog
  and Search"; open end = "onward"). The payload already carries all of
  this (#21 precheck 2026-08-29) — no Python changes.
- **Navigation.** Info gets an internal Back action: after moving from
  an entity to a connection (via Connections rows or spline members),
  Back returns to the previous selection; it appears only when there is
  somewhere to go back to. "View dependencies" moves out of the
  Connections tab bottom into a persistent entry in Details (it opens
  the existing deps view; do not redesign the deps diagram itself).
- **Escape (#13).** Final order per the direction, one keydown handler:
  global search → open menus → selection + Info. With the change-popover
  gone, re-verify and keep the D13a tests green.

### Data dock (#22, direction "Data dock")

- Tabs become the direction's four: **Entities, Interfaces, Milestones,
  Diff** — the D14 `subsystems` tab is removed. Entities changes source:
  it lists ALL live entity rows at the current stage across kinds
  (systems, subsystems, containers, components, code, users — from
  `rawState`, not the projected nodes), with a `kind` column, so the
  table is level-independent and subsystems are always present. The
  direction's absent-from-diagram flow follows: selecting a row that is
  rendered at the current level highlights it on canvas; selecting one
  that is not offers a "Show on Canvas" action (switches Detail to the
  row's own level and selects it) instead of switching views silently.
- Column behavior: auto-size populated columns to their content, collapse
  columns whose every cell is empty by default (re-enable via the
  existing column menu), never truncate a header — headers get the same
  humanized labels as Info. Persisted per-tab layouts keep working; a
  persisted layout that hides a now-populated column stays as the user
  set it.
- Selection sync both ways: canvas → the matching row highlights and
  scrolls into view when its table is open (row → Info already works and
  stays).

### States and motion sweep

- Designed empty states: an empty table tab ("No interfaces at this
  stage"), global search with no matches, and the payload-diagnostics
  banner styled to the token system (no raw unstyled text). No failure
  state may render a blank panel.
- Consistency sweep: one transition duration/easing pair for dock
  collapse/expand and Info content swaps; `prefers-reduced-motion`
  disables every non-essential animation (docks, Info, search dialog —
  canvas already handled by D13c). This is the final 3P pass — leave no
  mixed paddings/radii/font sizes in the three docks.

### Out of scope

- The read-only Payload viewer and Attachments tabs: **deferred to the
  Phase 3S message-file attachments chunk** (architect decision
  2026-08-29 — the payload carries no file refs until the schema.md/
  sequence.md attachments design lands, and the syntax highlighter
  should ship once, with real data). The conditional rule "Attachments
  renders only when files exist" is trivially satisfied by rendering no
  such tab in this pass. plan.md's pass-4 bullet is amended accordingly.
- Guided-story playback UI (D11), the deps-diagram layout itself, dark
  theme, and everything in "Explicitly deferred".

### Prescribed tests (exactly these six, plus keeping every existing test green)

1. Info details kv: a row with `availability_target` renders the label
   "Availability target", no rendered `dt` contains an underscore, and
   Contains renders clickable child chips (clicking selects the child).
2. Interface Info: shows both endpoints resolved to names, the direction
   for the active Relationship, and a lifecycle interval derived from
   `intervals`; a connection selection renders no Connections tab.
3. Stage changes: an entity with status `changed` at the selected stage
   shows the "Changes at this stage" section with old → new field rows;
   `.change-popover` no longer exists in the card DOM.
4. Data columns: with a fixture where one optional column is entirely
   empty and another is populated, the empty column is collapsed by
   default and the populated one auto-sizes; the `subsystems` tab is
   gone and subsystem rows appear in Entities with `kind: subsystems`.
5. Dock chrome: a collapsed dock renders an icon rail (accessible name
   present, no text-pill button), and activating it reopens the dock.
6. Escape order with the popover removed: search open + selection active
   → first Escape closes search, second clears selection and closes
   Info (extends the D13a test).

## Polish contract — pass 5: canvas presentation (P11)

Normative spec (authored 2026-08-29; decision source: the user's
IcePanel comparison review — hub layout, at-rest labels, termination
ports, color economy, per-kind theme). Grounded in the post-D13d tree:
`layout.ts` (unionLayout + grid pack), `edgeAnchors.ts`,
`splinePath.ts`, `edgePresentation.ts`, `cardSize.ts`, `styles.css`,
and — for the theme block only — `model.py`, `yamlio.py`, `payload.py`,
`excel.py`, `validate.py` (schema.md "Theme" is the schema authority).
Supersedes, where they conflict: D13b's ELK-only layout rule for flat
levels, D13c's anchor projection and edge color rules, and every
teal-at-rest usage in the D13a token set. Out of scope: expansion/map
semantics (P12), `projection.ts`, Info/Data content, drill behavior.

### Topology-aware landscape layout

- **Star detection** (pure function, per layout key, computed on the
  projected graph): eligible when the projection renders zero
  boundaries and ≥ 6 nodes, and one node's incident edges are ≥ 40% of
  all rendered edges. Eligible → **radial layout**; otherwise the
  existing ELK layered path runs unchanged (boundary levels and the
  deps view never use radial).
- **Radial construction (deterministic, no ELK):** the hub at the
  center; its one-hop neighbors on a ring — `users` biased to the top
  arc, remaining neighbors ordered around the ring by (kind, connection
  count desc, name) to keep the order stable; ring radius = the radius
  at which adjacent cards keep ≥ 48 px clearance including label room
  (grows with node count). Nodes at two+ hops place outside their
  nearest one-hop anchor on the outward bearing with the same
  clearance; unconnected nodes pack below the ring via the existing
  grid-pack path. No two cards may overlap by construction.
- **Spacing everywhere:** minimum 48 px card-to-card clearance holds in
  both radial and layered modes (layered keeps its D13b ELK spacing
  values; radial guarantees it by construction).

### Edge termination and ports

- **Per-side distributed attachment** replaces the current projection
  anchors: for each node, each edge is assigned a side by bearing to
  its counterpart; a side's edges are ordered by bearing and placed
  along the side with ≥ 14 px separation, clamped ≥ 14 px from each
  corner. Attachment points never converge and never sit on corners.
- **Perimeter overflow (decision 2026-08-29, P12 open question 2):** a
  side has finite capacity (`floor((span − 28) / 14) + 1` anchors).
  When a batch exceeds it, the side sheds its outermost endpoints
  around the nearest corner: the bearing-sorted batch's low end spills
  to the adjacent side at that corner, the high end to the opposite
  one, most-extreme bearing first; a spilled endpoint's bearing is
  recomputed in the destination side's metric so it stays in perimeter
  order, and spills cascade deterministically (an endpoint never
  returns to a side it left). Card geometry never grows for edge
  count, and aggregation is unchanged. `RangeError` remains only for
  a node whose total demand exceeds its whole perimeter's capacity.
- **Normal stubs:** every spline begins and ends with a straight stub
  perpendicular to its card side (12 px at zoom 1); the curve runs
  between stub tips; arrowheads sit flush on the border.
- **Visible ports:** a small dot (5 px, `--border`-toned fill, card
  background ring) renders at every attachment point; ports of the
  selected/one-hop splines tint accent. Interface ports from D13c keep
  their labels and adopt the same dot geometry.

### At-rest edge labels

- Every rendered spline shows a **label pill at Read and Full** depth
  (at Far only when selected/hovered — D13c's selection rules are
  unchanged and sit on top). Pill: white background, 1 px `--border`,
  dark 10–11 px text, max-width ~180 px with ellipsis (`title` carries
  the full text). Content: the single member's `action` (relationships)
  or name (interfaces); aggregated splines show the first member's
  label in deterministic member order plus the existing count chip.
- Placement: arc-length midpoint, nudged along the spline (up to ±20%
  of arc length) to clear card bodies; a pill never renders clipped by
  a card — overlap with another pill resolves by alternating the nudge
  direction deterministically.
- **Collision invariant (P15, from issue p14 — supersedes any weaker
  reading above):** a pill never renders overlapping a card, a boundary
  header, or another pill, in ANY zoom / selection / expansion state —
  not just the at-rest layout. Selection- and hover-revealed pills
  (D13c's Far reveal, one-hop emphasis) participate in the same
  collision pass as at-rest pills, evaluated against the current
  frame's rendered rects (the selected/expanded card at its actual
  rendered size). Resolution order: nudge along the spline (±20%),
  then **hide** — hiding always beats stacking or clipping. A hidden
  pill's label stays reachable: hovering or selecting its spline
  reveals exactly that pill above everything else (a single direct
  reveal is exempt from the pass — one pill can always show). The pass
  re-runs on zoom-band, selection, and expansion changes.
- **Orphan suppression (rides from issue p18):** a pill renders only
  when at least one endpoint of its spline is in or near the viewport —
  no chips floating in empty space.

### Color economy and per-kind theme

- **Neutral-first surface:** cards white; card border, description,
  secondary text, and boundary washes in gray tokens; edges
  `--edge` neutral gray (≈ #98a4ad), zoom-compensated widths kept from
  D13c but arrowheads scaled ~0.8×. The animated dash remains reserved
  for one-hop outgoing.
- **Kind identity:** each of the six kinds (system, subsystem,
  container, component, code, user) has one base hue driving its kind
  pill (tinted bg + border + text), card border (1 px, ~55% mix toward
  `--border`), and boundary tint (≤ 6% alpha wash) — all derived from
  the one hue via `color-mix`. The D13d Info-chip palette becomes the
  single default set, exposed as CSS custom properties
  (`--kind-system`, …) so canvas pills/borders, Info Contains chips,
  and Data kind chips read identical tokens.
- **Model override:** the payload's `theme.kinds` (schema.md "Theme")
  merges over the defaults at app start — one hue per kind, partial
  allowed. Python scope: optional `theme` on the model, validation
  codes `unknown_theme_key` / `invalid_color` (located), YAML canonical
  position after `timelines`, payload pass-through, Excel `Settings`
  sheet (adapters.md sheet 12) with YAML↔Excel round-trip equality.
- **One accent:** the teal interaction accent appears ONLY on
  selection (card border/halo, one-hop splines + their ports + label
  emphasis), focus rings, and dock links/actions. Nothing at rest on
  the canvas uses it. Diff status colors (added/removed/changed) are
  unchanged. Dim floors from D13c are unchanged.
- **User cards compact:** `users` render a reduced card (kind pill +
  name; description only at Full), width tier 220 — no icons.

### Prescribed tests (exactly these six, plus keeping every existing test green)

1. Star detection: a flat fixture graph where one node carries ≥ 40% of
   edges lays out radially (hub at the bounding-box center, every
   one-hop neighbor within ±10% of one ring radius); a non-star fixture
   takes the ELK layered path with unchanged input options.
2. Attachment distribution: a node with three same-side edges gets
   three distinct attachment points ≥ 14 px apart, none within 14 px of
   a corner; the first and last spline segments are perpendicular to
   their card sides.
3. At-rest labels: at Read depth a single-member spline renders its
   action pill and an aggregated spline renders first-member label +
   count chip; at Far with no selection, no pill renders.
4. Theme plumbing (py): a model with `theme.kinds.system` round-trips
   YAML→Excel→YAML unchanged and reaches the payload verbatim; an
   invalid value produces located `invalid_color`; an unknown key
   produces `unknown_theme_key`.
5. Theme application (ts): with a payload theme override, the system
   kind's CSS custom property carries the override while unset kinds
   keep defaults.
6. Color economy: with nothing selected, rendered card borders, kind
   pills, and edge strokes resolve to non-accent tokens; selecting a
   node applies the accent to its border and one-hop splines only.

## Map contract — in-place C4 expansion (P12)

Normative spec (authored 2026-08-29; decision source: the user's map
directive — c4model.com "maps of your code" navigation; REVERSES
answered question Q5 of 2026-08-24, drill + uniform levels → in-place
expansion). Supersedes: "C4 zoom and drill (D10b)" (the level table,
drill projection, and breadcrumb), the Detail-dropdown-as-mode rows of
the pass-1 controls, and D13b's initial-framing rule where it assumed a
uniform level. Builds on P11 (radial landscape = the all-collapsed
map; layered runs inside expanded boundaries). Grounded in
`projection.ts`, `view.ts`, `layout.ts`, `camera.ts`, App wiring.

### View state: the expansion set

- `level` and `drill` retire. New fragment key `expand` = comma list of
  expanded entity ids (any kind from the containment matrix that has
  children). Unknown or childless ids are dropped with a console
  diagnostic. Old links: a `drill=<key>` fragment maps to
  `expand=<that id's ancestor chain + itself>` plus `select`; a
  `level=` fragment maps to the equivalent preset. Copy view link and
  saved views carry `expand`.
- **Detail dropdown becomes presets** (same control, new semantics):
  System = collapse all; Subsystem = expand all systems;
  Container = expand systems + subsystems; Component = expand systems +
  subsystems + containers. A preset writes the bulk expansion set in
  one history push. When the live set matches no preset the dropdown
  displays "Custom". The Subsystem option still hides for
  subsystem-less models.
- Expansion is **persistent and cumulative**: it survives stage,
  relationship, and tag changes (the layout key becomes
  `(timeline, expansion set)` — those switches move nothing, D13b
  rule carried over). Expand/collapse pushes history; browser Back
  walks expansion steps.

### Projection: tree-based rendering

- For each root (systems, users): collapsed → one card with the
  existing roll-up members; expanded → a **boundary** containing its
  live *direct children, whatever their kinds* (a system may show
  subsystem and container cards side by side), each child again
  collapsed or expanded, recursively. An expanded entity never renders
  as a card inside its own boundary. A childless entity offers no
  expansion (no affordance, invalid in `expand`).
- **Boundary identity:** kind pill + name header (selectable, as
  today) and the entity description at the bottom inside the boundary,
  small and muted.
- **Endpoint resolution (per endpoint, independent):** every
  interface/relationship endpoint attaches to the **deepest visible
  node on the defined endpoint's ancestor chain** — the defined entity
  itself when visible ("defined" attachment), else its deepest visible
  ancestor ("derived"). An interface defined on an entity that is
  itself expanded attaches to that boundary's border (this narrowly
  supersedes "boundaries are never edge endpoints" — only for
  interfaces defined on the expanded entity itself). Multiple members
  resolving to one visible pair aggregate into one spline with the
  count chip (P11 labels apply); expanding a side re-resolves and
  splits them. Both ends resolving to the same visible node = internal
  edge, not drawn (connection-count facts still include it). Direction,
  one-hop selection, tag lens, and diff semantics are unchanged — only
  attachment changes.

### Interaction

- Expand: the existing drill control becomes the expand control
  (magnifier + live child count), rendered only when live children
  exist; double-click on such a card also expands. Collapse: an
  icon-only control in the boundary header; collapsing prunes the
  entity and all its descendants from the set. Escape order is
  unchanged (Escape never collapses).
- **Collapse-control placement (P15, from issue p16):** the collapse
  control renders **inline with the boundary's own title** — immediately
  after the name + kind pill group, inside the header chrome, visually
  part of the boundary (header tint behind it) — and uses a collapse
  glyph (chevron or minus), never **×** (which reads as a close button).
  It never floats to a far corner and never repositions toward child
  cards at any zoom: if the boundary header is off-screen, so is the
  control. `aria-label` "Collapse <name>".
- The **drill view, breadcrumb, and Up control retire**. The deps view
  is untouched. "Focus a scope" = expand + camera fit to the boundary.

### Layout: local, stable growth

- Interior of an expanded boundary: ELK layered (`INCLUDE_CHILDREN`
  for nested expansions), boundary sized to its laid-out children +
  header/description inset.
- **Expanding must not re-lay the map.** On expand, every node outside
  the expanded entity keeps its position except those the grown
  boundary would overlap: overlapping neighbors displace along the
  vector from the expanded entity's pre-expansion center, the minimum
  distance that restores the P11 48 px clearance (deterministic,
  iterated until clear). Collapsing restores the pre-expansion
  positions exactly (positions cached per expansion set). Applying a
  preset is a deliberate bulk action and re-lays out fresh (P11 rules
  decide radial vs layered on the result).
- Camera: on expand/collapse the expanded entity's center stays fixed
  in screen space; zoom changes only via the existing explicit
  controls. Initial framing (D13b) applies to the preset/link-derived
  first layout.

### Acme showcase delta (authored in the P12 prompt)

One verified four-level path — Digital Commerce Platform →
`storefront-edge` → one of its containers → that container's
components — with meaningful names/descriptions at every hop, plus at
least one interface *defined* at subsystem level and one at component
level so derived→defined attachment sliding is demonstrable. Enrich
only where the existing fixture is thin; regenerate the wip acme
report.

### Prescribed tests (exactly these six, plus keeping every existing test green)

1. Mixed-kind expansion: a system with two subsystems and one direct
   container expands to a boundary containing exactly those three
   cards (kinds preserved); collapsed siblings keep their roll-up
   members.
2. Endpoint resolution ladder: interface `C → Sys2` with C's system
   collapsed attaches system→Sys2; expanding the system re-attaches
   subsystem→Sys2; expanding the subsystem attaches C→Sys2; the two
   derived stages carry aggregation counts when other members share
   the pair.
3. Internal edges: an interface wholly inside a collapsed system draws
   no spline; expanding until both endpoints are visible draws it.
4. Presets: the Container preset produces expand = all systems + all
   subsystems; a hand-modified set renders the dropdown as "Custom";
   preset application is one history entry.
5. Layout stability: expanding one entity changes only the positions of
   nodes its boundary displaced (all others exactly equal); collapsing
   restores the prior positions exactly.
6. Fragment round-trip: `expand` encodes/decodes losslessly; an unknown
   id is dropped with a diagnostic; a legacy `drill=` link resolves to
   the equivalent expansion + selection.

## Attachments and the Payload viewer (design landed 2026-08-30; viewer ships with P31)

Un-defers D13d's Payload viewer with real data (schema.md "Attachments",
sequence.md `attach`). The Python half (fields, parsing, resolution,
embedding) lands with P21; the viewer ships with P31 — one highlighter,
one chunk — and covers interface attachments on the canvas side too, not
just sequence messages.

- **Info · Attachments.** An interface's Details (canvas spline, member
  row, or table selection) and a sequence message's Info gain an
  **Attachments section** — rendered only when files exist — listing
  each file as a row: basename, format chip (json / xml / csv / yaml /
  text), human-readable size (computed from the embedded text).
  Clicking a row opens it in Data's Payload tab.
- **Data · Payload tab.** Conditional tab, present only while a payload
  file is open (the D13d conditional rule, now non-trivially
  satisfied). Read-only: full relative path as the header, a copy
  action, content rendered per format — `json` / `xml` / `yaml`
  syntax-highlighted by a **bundled** highlighter (ships inside the
  single-file bundle, zero external requests; Prism core + json/xml/
  yaml components, MIT, is the working choice — final call at the P31
  prompt), `csv` as a read-only AG Grid table (reusing the existing
  grid), `text` as plain monospace. Highlight colors come from the
  app's light-theme tokens, not a stock highlighter theme.
- Content comes exclusively from the payload's embedded `files` map —
  never from disk — so the viewer works under `file://` unchanged.

## Exports

Phase one exports are data-shaped and require no layout engine in Python:
YAML, Excel (via adapters), and the payload JSON. SVG/draw.io export runs
*from the report app* (serialize the laid-out scene client-side — the v2
`ArchitectureScene`-not-DOM rule still applies) with a download button.
Headless CLI export of SVG is deferred; if it becomes necessary, drive the
same bundle in managed Chromium rather than reintroducing a bespoke layout
boundary.

## Explicitly deferred

- ~~Sequence diagrams~~ — no longer deferred (2026-08-25): now a native
  aspect owned by [sequence.md](sequence.md). The POC verdict rejected
  *third-party* renderers; the adopted design is a custom layout + React
  renderer sharing this app's entity boxes, panels, and dimming rules.
- Saved Report Definition files, Confluence embedding, PDF.
- The confirmed direction's first-pass cuts (2026-08-27): dark theme,
  application fullscreen, Share, a Changes diagram view or Info tab,
  saved report creation, manual card positioning, viewer scope/hop
  controls, Technology/Status lenses, entity icons/logos, floating
  panels, viewports below 1024 × 720 — authoritative list in
  [ui-polish-direction.md](ui-polish-direction.md) "Deferred or removed".
- The v2 wip interaction catalog (`plans/arch/archive/v2-wip/interactions.md`, ~230
  requirements) was mined 2026-08-24: the useful clauses live in "Wave-2 UI
  contract — Interaction baseline" above and the doc is marked superseded.
  Journey playback/guided views are D11; route probe, radar, and the rest
  re-earn their place against real use.
