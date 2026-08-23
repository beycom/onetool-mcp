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
every state implicitly.

## One projection, in the app

Because a state is a filter, the report app derives everything client-side:

- **state at slider position** — one array filter;
- **diff between positions** — set arithmetic;
- **scope** (selected systems + hops) — BFS over live interfaces;
- **level** (system / subsystem / component) — roll-up of nodes and edges.

This deletes v2's three parallel pipelines (`viewgraph.py` 863 lines,
`projection.py` 450, `projection.ts` 385) and the Python/TS parity tests
between them. Python never builds a graph.

## The time slider is the hero

The single interaction v1 and v2 never delivered, and the one the interval
model makes nearly free:

- A milestone stepper/slider across the selected timeline (Current → … →
  End). Dragging it re-filters the canvas and tables in place.
- Nodes and edges animate in/out; a **diff overlay** toggle marks added
  (accent + badge), removed (ghosted, from the previous or compared
  position), and revised (badge with field-level popover) — colors always
  paired with icon/line-style per the v2 accessibility rule.
- A timeline picker appears when the architecture declares multiple
  timelines, making scenario comparison a two-click act.
- Progressive disclosure: with zero milestones (the common static case) the
  time and compare controls do not render at all — the report is a pure
  current-state explorer. One milestone brings the stepper; multiple
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
| Level | systems / subsystems / components |
| Time | timeline + slider position |
| Compare | off / vs current / vs position |
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
