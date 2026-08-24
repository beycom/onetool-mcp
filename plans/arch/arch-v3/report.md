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
- **level** (system / container / component) — roll-up of nodes and edges.

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

| Control | Values |
| --- | --- |
| Scope | selected systems + `system_hops` |
| Level | systems / containers / components |
| Time | timeline + slider position |
| Compare | off / vs base / vs position |
| Aspect | ownership / call direction / data flow |
| Mode | MAP / PATH / LENS (POC) |
| Theme | light / dark |

Saved Report Definitions (YAML files holding these fields) come later; the
URL fragment *is* the saved view in phase one. No coordinates, pan, or zoom
are ever persisted — reaffirming the v2 decision and closing the saved-
placement conflict the wip docs left open: v3.0 is auto-layout only, and any
future layout-hint feature is a new schema discussion, not a report feature.

## Canvas and look

- React Flow v12, custom nodes/edges in the Archify profile: faint technical
  grid, outlined rounded nodes with kind icons, dashed containment
  boundaries, orthogonal edges with pill labels, mono diagram labels, glow
  reserved for selection/route.
- elkjs layered layout in a web worker inside the report (deterministic:
  fixed seed, sorted inputs). Running layout in the viewer removes v2's
  unresolved "ELK needs a JS runtime in the CLI" gate entirely.
- Passport panel, minimap, keyboard operability, light/dark — carried from
  the POC as proven.
- AG Grid Community tables (entities, interfaces, milestones, diff), always
  consistent with the canvas because both read the same filtered arrays.

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
- The v2 wip interaction catalog (~230 requirements, journey playback, radar,
  lens legend algebra) is **not** carried into v3 scope. The POC's proven
  interactions plus the time slider are the 3.0 surface; everything else
  re-earns its place against real use.
