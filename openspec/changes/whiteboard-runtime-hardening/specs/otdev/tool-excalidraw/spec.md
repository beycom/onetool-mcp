# tool-excalidraw Delta — whiteboard-runtime-hardening

> Main spec: `openspec/specs/otdev/tool-excalidraw/spec.md`.

## ADDED Requirements

### Requirement: Named board selection across tools

Every board-touching tool SHALL accept an optional `board: str | None = None` parameter: `draw`, `erase`, `clear`, `layout`, `screenshot`, `share` (existing) and `note`, `save`, `load`, `sync`, `style`, `read_scene`, `embed_dsl` (added by this change). Semantics SHALL be uniform:

- `board=None` SHALL reproduce the tool's previous behavior exactly (CWD-keyed default board; no extra canvas rerender).
- With an explicit `board`, session-state reads and writes SHALL target `{CWD}/.onetool/state/whiteboard/{board}.json`.
- Tools that read the live canvas (`save`, `style`, `read_scene`) SHALL, when given an explicit `board`, first rerender that board's persisted state onto the canvas before operating.
- Invalid board names (characters outside `A-Za-z0-9_-`) SHALL raise `ValueError` (existing `session_path` validation).

Per-tool effect of an explicit `board`:

| Tool | Effect |
|---|---|
| `note(input=, background=, board=)` | Notes are stored in and placed relative to (`canvas_max_y`) the named board's state |
| `embed_dsl(board=)` | Embedded DSL text is built from the named board's state |
| `save(file=, board=)` | The `__otDSL` element is built from the named board's state; the named board is rerendered before the scene snapshot |
| `load(file=, board=)` | The restored DSL state is written to the named board's session file |
| `sync(board=)` | The synced state is written to the named board's session file |
| `style(ids=, style=, board=)` | The named board is rerendered first; styling then applies to the live canvas (still visual-only, not persisted) |
| `read_scene(info=, board=)` | The named board is rerendered first; the report reflects that board |

#### Scenario: note writes to a named board
- **WHEN** `whiteboard.note(input="n1[note:\nhi\n]", board="myboard")` is called
- **THEN** element `n1` SHALL be stored in `{CWD}/.onetool/state/whiteboard/myboard.json`
- **AND** the CWD-keyed default board SHALL be unchanged

#### Scenario: load restores into a named board
- **WHEN** `whiteboard.load(file="arch.excalidraw", board="myboard")` is called
- **THEN** the restored DSL state SHALL be written to `myboard.json`, not the default board

#### Scenario: save snapshots a named board
- **WHEN** `whiteboard.save(file="out.excalidraw", board="myboard")` is called
- **THEN** the canvas SHALL be rerendered from `myboard.json` before the snapshot
- **AND** the written `__otDSL` element SHALL contain `myboard`'s DSL

#### Scenario: sync writes to a named board
- **WHEN** `whiteboard.sync(board="myboard")` is called and a `__otDSL` element is on canvas
- **THEN** the parsed state SHALL be saved to `myboard.json`

#### Scenario: read_scene renders the named board first
- **WHEN** `whiteboard.read_scene(board="myboard")` is called
- **THEN** the canvas SHALL be rerendered from `myboard.json` before the element report is produced

#### Scenario: Omitted board preserves current behavior
- **WHEN** any of `note`, `save`, `load`, `sync`, `style`, `read_scene`, `embed_dsl` is called without `board=`
- **THEN** the tool SHALL behave exactly as before this change (default board; `style`/`read_scene` operate on the live canvas without a rerender)

#### Scenario: Invalid board name rejected
- **WHEN** `whiteboard.sync(board="../evil")` is called
- **THEN** a `ValueError` SHALL be raised and no session file SHALL be touched

## MODIFIED Requirements

### Requirement: Graph layout via ELK.js

`whiteboard.layout(...)` SHALL run ELK.js in the browser to compute and apply
graph layout positions. It SHALL read the live canvas scene (not DSL state) to
build the ELK graph, inject the **bundled** `elkjs@0.11.0` asset
(`src/otdev/tools/_excalidraw/elk.bundled.js`, shipped with the pack) into the
page over CDP if `window.ELK` is not already defined, await `elk.layout()`,
patch node and text-child positions, recompute subgraph bounding boxes, and
call `fit()` to zoom to content.

**No network fetch:** ELK SHALL be loaded exclusively from the bundled asset —
`layout()` SHALL NOT fetch ELK from any CDN or remote URL. Injection is
guarded (once per page load); if the bundle fails to define `window.ELK`, the
tool SHALL return an `"Error: ..."` string identifying the injection failure.
The vendored bundle SHALL ship with its EPL-2.0 license text and provenance
(package name, version, source).

**Position write-back:** After patching the canvas, layout() SHALL write the
computed `x`/`y` back into the session-state shapes (and update
`canvas_max_y`) so subsequent rerenders (screenshot/share/reload) preserve
the layout instead of re-gridding.

**Selection scope:** If elements are selected (`appState.selectedElementIds`
is non-empty), only selected nodes are laid out; edges between selected nodes
are included. Edges with one endpoint inside the selection and one outside
(**boundary arrows**) are excluded from ELK but SHALL have their selected-side
endpoint updated to the node's new position after layout, while the unselected-side
endpoint remains at its original coordinates. If nothing is selected, all eligible
scene nodes are laid out.

**Eligible nodes:** Non-deleted, non-text, non-arrow scene elements.

**Eligible edges:** Non-deleted arrows where both `startBinding.elementId` and
`endBinding.elementId` are present and both endpoints are in the node set.

**Groups:** Elements sharing a `groupIds[0]` are treated as a single atomic ELK
node sized to their combined bounding box computed from member **positions and
sizes** (`min(x)..max(x+w)` / `min(y)..max(y+h)`), not sizes alone; all members
translate as a unit.

The return string reflects scope: `"layout applied to N nodes"` (all) or
`"layout applied to N nodes (selection)"` (selection-scoped).

The browser JS SHALL return the `{nodes, edges}` object directly (not as a
`JSON.stringify`-encoded string) so the CDP bridge does not double-encode the result.

Parameters:

| Param | Default | Choices |
|---|---|---|
| `direction` | `"DOWN"` | `RIGHT` `DOWN` `LEFT` `UP` |
| `gap_layer` | `80` | int px |
| `gap_node` | `40` | int px |
| `algorithm` | `"layered"` | `layered` `stress` `mrtree` `radial` `force` |
| `node_placement` | `"NETWORK_SIMPLEX"` | `BRANDES_KOEPF` `NETWORK_SIMPLEX` `LINEAR_SEGMENTS` `SIMPLE` |
| `crossing_min` | `"LAYER_SWEEP"` | `LAYER_SWEEP` `MEDIAN_LAYER_SWEEP` `NONE` |
| `cycle_breaking` | `"GREEDY"` | `GREEDY` `DEPTH_FIRST` `MODEL_ORDER` |
| `arrow_type` | `None` | `None` `curve` `sharp` `elbow` — patch all layout arrows after positioning |
| `elk_options` | `None` | `dict` of raw ELK key→value (merged last, overrides all above) |
| `board` | `None` | named board for state load/write-back (existing parameter, unchanged) |

Invalid `direction`, `algorithm`, `node_placement`, `crossing_min`, `cycle_breaking`,
or `arrow_type` values SHALL return an `"Error: ..."` string without calling the browser.

When `algorithm != "layered"`, `node_placement`, `crossing_min`, and
`cycle_breaking` are omitted from the ELK options object.

When `algorithm == "stress"`, `elk.stress.desiredEdgeLength` SHALL be set to
`gap_node * 3` to reduce node overlap.

#### Scenario: ELK loaded from bundled asset, no CDN
- **WHEN** `whiteboard.layout()` runs on a page where `window.ELK` is undefined
- **THEN** the bundled `elk.bundled.js` asset SHALL be injected over CDP and `window.ELK` defined
- **AND** no request SHALL be made to unpkg.com or any other remote URL to obtain ELK

#### Scenario: ELK injection is once per page
- **WHEN** `whiteboard.layout()` is called twice without a page reload
- **THEN** the bundle SHALL be injected at most once (`window.ELK` guard)

#### Scenario: Bundle injection failure reported
- **WHEN** the injected bundle fails to define `window.ELK`
- **THEN** `layout()` SHALL return an `"Error: ..."` string identifying the ELK injection failure

#### Scenario: Layout applies to selected nodes
- **WHEN** `whiteboard.layout(...)` is called with selected elements
- **THEN** only selected eligible nodes SHALL be laid out
- **AND** the return string SHALL include `(selection)`

#### Scenario: Boundary arrows use per-edge containment
- **WHEN** a selection layout has multiple boundary arrows with different containment (one arrow's source inside the selection, another arrow's destination inside)
- **THEN** each arrow's connection sides and endpoint ordering SHALL be derived from that arrow's own containment value, never from another edge's

#### Scenario: Layout positions persisted
- **WHEN** `whiteboard.layout()` completes and a laid-out node exists in session state
- **THEN** the node's new `x`/`y` SHALL be written to the session file
- **AND** a subsequent `screenshot()` or `share()` rerender SHALL restore the node at that position

#### Edge repositioning

After layout, arrows SHALL connect to the appropriate side of each repositioned
node based on layout direction:

| `direction` | Start point | End point |
|---|---|---|
| `RIGHT` | `(src.x + src.w, src.y + src.h/2)` | `(dst.x, dst.y + dst.h/2)` |
| `LEFT` | `(src.x, src.y + src.h/2)` | `(dst.x + dst.w, dst.y + dst.h/2)` |
| `DOWN` | `(src.x + src.w/2, src.y + src.h)` | `(dst.x + dst.w/2, dst.y)` |
| `UP` | `(src.x + src.w/2, src.y)` | `(dst.x + dst.w/2, dst.y + dst.h)` |

This ensures arrow lines remain connected to repositioned node boxes after
layout.

#### Layout offset

For full (non-selection) layout, the ELK output origin is shifted by a fixed
canvas padding of `offsetX = offsetY = 60` px.

For selection-scoped layout, the offset SHALL be the bounding box top-left of
the currently selected nodes (`min_x` / `min_y` across all selected nodes),
so the repositioned group stays roughly at its current canvas position rather
than jumping to the canvas origin.
