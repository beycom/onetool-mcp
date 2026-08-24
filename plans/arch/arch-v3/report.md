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

- **state at slider position** — one array filter;
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

### Row serialization

Model fields dumped as authored (`start_in`/`end_in` carry the authored
milestone id or `base` — kept for the passport panel), omitting `null`s,
empty `tags`/`properties`, and `call_direction`/`data_flow_direction` when
equal to their schema defaults (the client applies the defaults). Plus one
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

## The time slider is the hero

The single interaction v1 and v2 never delivered, and the one the interval
model makes nearly free:

- A milestone stepper/slider across the selected timeline (Base → … →
  End). Dragging it re-filters the canvas and tables in place.
- Nodes and edges animate in/out; a **diff overlay** toggle marks added
  (accent + badge), removed (ghosted, from the previous or compared
  position), and revised (badge with field-level popover) — colors always
  paired with icon/line-style per the v2 accessibility rule.
- A timeline picker appears when the architecture declares multiple
  timelines, making scenario comparison a two-click act.
- Progressive disclosure: with zero milestones (the common static case) the
  time and compare controls do not render at all — the report is a pure
  base-state explorer. One milestone brings the stepper; multiple
  timelines bring the picker.
- Layout stability across positions: layout the **union graph** (all rows,
  all positions) once with elkjs, then keep node positions fixed while
  filtering — absent nodes collapse/ghost rather than trigger re-layout.
  This sidesteps v2's roadmap-displacement quality gates by construction; a
  per-position re-layout is an explicit user action ("re-fit this state").

## Views (dynamic, all URL-fragment encoded)

A view is a client-side configuration, shareable via copy-link (POC pattern):

| Control | Fragment key | Values |
| --- | --- | --- |
| Scope | `scope`, `hops` | selected systems + `system_hops` |
| C4 level | `level` | `systems` / `top-containers` / `containers` / `components` |
| Drill | `drill` | `<kind>:<id>` (child projection; pushes history) |
| Dependency focus | `deps` | `<kind>:<id>` (dedicated in/out view) |
| Time | `timeline`, `time` | timeline + slider position |
| Compare | `compare`, `compare-at` | off / vs base / vs position |
| Aspect | `aspect` | ownership / call direction / data flow |
| Lens | `lens` | selected tags (legend) |
| Theme | `theme` | light / dark |
| *(reserved)* | `view` | guided views — D11 |

The `mode` key (MAP/PATH/LENS) is retired in wave 2 — see "Wave-2 UI
contract". Panel sizes, collapsed state, table layouts, and fullscreen are
session-local (localStorage / transient), never fragment state.

Saved Report Definitions (YAML files holding these fields) come later; the
URL fragment *is* the saved view in phase one. No coordinates, pan, or zoom
are ever persisted — reaffirming the v2 decision and closing the saved-
placement conflict the wip docs left open: v3.0 is auto-layout only, and any
future layout-hint feature is a new schema discussion, not a report feature.

## Canvas and look

- React Flow v12, custom nodes/edges. Wave 2 revises the visual profile:
  **plain near-flat background** (the faint technical grid is gone),
  information-carrying entity boxes, nested containment boundary boxes,
  visible orthogonal edges with pill labels and wide hit rails, graduated
  dimming for every emphasis state, glow reserved for selection. The
  normative spec and the measured Archify style values are in "Wave-2 UI
  contract" below.
- elkjs layout in a web worker inside the report (deterministic: fixed
  seed, sorted inputs; hierarchical `INCLUDE_CHILDREN` from wave 2 for
  boundary boxes). Running layout in the viewer removes v2's unresolved
  "ELK needs a JS runtime in the CLI" gate entirely.
- Docked details side panel (wave 2 — replaces the floating passport),
  minimap, keyboard operability, light/dark.
- AG Grid Community tables (entities, interfaces, milestones, diff) at v2
  feature parity (wave 2), always consistent with the canvas because both
  read the same filtered arrays.

## Wave-2 UI contract (v1)

Normative for D10 (D10a chrome/panels/tables, D10b canvas semantics and
visuals). Applies after the wave-1 (D9) gate. It **extends** "Client
projection contract (v1)": where this section names a change, this section
wins; everything it does not name is unchanged. Sources reconciled here
(2026-08-24): the twelve `p2-*` issues, the binding lists and measured
values in `research/ui/ui-research-findings.md`, and the mined subset of
`plans/arch/wip/interactions.md` (now superseded — see "Interaction
baseline"). Quoted pixel/opacity/duration values are the Archify-measured
styling reference — tune only by eye at the gate, never invent different
mechanisms.

### Chrome and layout (D10a)

- **One compact header line**: brand mark, model name, current-view
  summary, global actions (theme, copy link, fullscreen). No second
  full-width control bar; the canvas starts directly below the header.
- Controls sit in **grouped clusters** on/around the canvas: the time
  strip (timeline picker + slider + compare toggle) as one visual unit at
  the top of the canvas; the projection cluster (C4 zoom, scope, aspect)
  adjacent to the canvas; the **zoom rail** bottom-right (fit, zoom out,
  current percentage + reading depth, zoom in, fullscreen toggle).
- Related controls share one card/pill container; unrelated controls never
  share a row. Every control has a visible label or tooltip.
- Narrow viewports: clusters collapse into menus, never wrap into stacked
  full-width rows; the page never gains horizontal overflow down to 500 px
  (research #9; INT-RESP-01). Fit, time, and fullscreen-exit controls stay
  reachable at every width.
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

### Fullscreen (D10a)

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

The flat level selector becomes a four-level **C4 zoom** control. Internal
level ids (fragment tokens and the `rollUp` level argument) with their UI
labels:

| Level id | UI label | Node set |
| --- | --- | --- |
| `systems` | System | contract-v1 systems roll-up; flat, no boundaries |
| `top-containers` | Container | **new roll-up level**: representative = the nearest ancestor container whose `parent` is a system; everything below rolls into it |
| `containers` | Child Containers | contract-v1 containers level (every live container stays itself) |
| `components` | Component | contract-v1 components level |

Users stay plain nodes at every level. `rollUp`'s edge rules (unordered
pair key, self-pairs dropped, member id lists, direction from members) are
unchanged; only the representative function gains the `top-containers`
case. Existing projection vectors keep their level names and stay green.

**Boundary boxes** (presentation, IcePanel profile): ancestors above the
active level render as containment group boxes — thin rounded outline
(~8–10 px radius), restrained fill, small icon + name label at the top
left (no solid title bar), generous inset around children. At
`top-containers`: systems with displayed children are boundary boxes,
childless systems are plain nodes. At `containers`: system boundaries plus
parent-container boundaries, nested. At `components`: the full
system/container ancestor chain. Boundary boxes are selectable (open the
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
disabled while drilled.

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

### Legend and tag lens (D10b)

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

`plans/arch/wip/interactions.md` is **superseded**. These are the clauses
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

## Exports

Phase one exports are data-shaped and require no layout engine in Python:
YAML, Excel (via adapters), and the payload JSON. SVG/draw.io export runs
*from the report app* (serialize the laid-out scene client-side — the v2
`ArchitectureScene`-not-DOM rule still applies) with a download button.
Headless CLI export of SVG is deferred; if it becomes necessary, drive the
same bundle in managed Chromium rather than reintroducing a bespoke layout
boundary.

## Explicitly deferred

- Sequence diagrams: per the POC verdict, no native renderer; sanitized SVG
  attachments only, post-3.0.
- Saved Report Definition files, Confluence embedding, PDF.
- The v2 wip interaction catalog (`plans/arch/wip/interactions.md`, ~230
  requirements) was mined 2026-08-24: the useful clauses live in "Wave-2 UI
  contract — Interaction baseline" above and the doc is marked superseded.
  Journey playback/guided views are D11; route probe, radar, and the rest
  re-earn their place against real use.
