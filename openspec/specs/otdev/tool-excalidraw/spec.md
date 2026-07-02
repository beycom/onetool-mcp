# tool-excalidraw Specification

## Purpose

Live diagram manipulation on excalidraw.com via pydoll (Chrome CDP). Exposes
a `whiteboard` pack with tools to draw, annotate, save, load, clear, scroll,
and zoom diagrams using a Mermaid-compatible DSL. Requires Chrome/Chromium to
be installed on the host.

Pack name: `whiteboard` (used as `whiteboard.draw(...)`, `whiteboard.note(...)`, etc.)
Short alias: `wb` — `wb.draw(...)` is equivalent to `whiteboard.draw(...)`.

---

## Requirements

### Requirement: Draw diagram elements

`whiteboard.draw(input=, board=)` SHALL add shapes, edges, and subgraphs to the board state. State SHALL be persisted to a session file; no Playwright browser SHALL be launched by this call. It SHALL be additive — elements already in state are never removed or repositioned. New shapes receive column-based stacking positions: each subgraph's nodes are placed in a separate x column (300px apart); ungrouped nodes share one column. Edges are deduplicated by `(src, dst, label, startArrowhead, endArrowhead)`. Unknown edge endpoints are auto-created as shapes with their ID as label. New shapes are placed below existing canvas content. Call `whiteboard.layout()` to apply graph layout (topological layering via ELK).

The optional `board=` parameter specifies the named board to operate on. If omitted, the CWD-keyed default board is used.

#### Scenario: Add shapes and edges
- **WHEN** `whiteboard.draw(input='a["A"]\nb["B"]\na-->b')` is called
- **THEN** two rectangles and a directed arrow SHALL be added to the session state
- **AND** the return value SHALL match `"+2 shapes, +1 edge(s): edge-a-b"` (format: `"+N shapes[, M updated][, +P edge(s): ids][, +Q group(s)]"`)
- **AND** no browser SHALL be launched

#### Scenario: Additive — existing shapes untouched
- **WHEN** `whiteboard.draw(input='c["C"]')` is called after shapes `a` and `b` exist in session state
- **THEN** only shape `c` SHALL be added; `a` and `b` SHALL be untouched

#### Scenario: Named board
- **WHEN** `whiteboard.draw(input='box:A', board='myboard')` is called
- **THEN** state SHALL be written to `{CWD}/.onetool/state/whiteboard/myboard.json`

#### Scenario: Subgraph bounding rect
- **WHEN** the DSL includes a `subgraph ... end` block naming existing shapes
- **THEN** a bounding rectangle SHALL appear behind the member shapes
- **AND** subgraphs are redrawn on every call to reflect current member positions
- **AND** a subgraph label SHALL appear as bound text inside its bounding rect (`containerId` set on the text element, `boundElements` referencing the text on the rect), with `textAlign: 'center'` and `verticalAlign: 'top'`

#### Scenario: Subgraph groupIds are deduplicated
- **WHEN** `draw()` is called multiple times with the same subgraph
- **THEN** each member's `groupIds` array SHALL contain the group ID at most once (no duplicates)

#### Scenario: Multiple subgraphs in separate columns
- **WHEN** `draw()` receives DSL with two or more subgraphs in a single call
- **THEN** each subgraph's member nodes SHALL be auto-laid-out in a separate x column (300px apart)
- **AND** the bounding rectangles for each subgraph SHALL NOT overlap visually

#### Scenario: Edge deduplication
- **WHEN** `draw()` is called twice with the same edge
- **THEN** only one arrow SHALL be present in the session state

#### Scenario: Bidirectional and special arrowheads
- **WHEN** the DSL contains `a<-->b`, `a --o b`, or `a --x b`
- **THEN** arrows SHALL render with the correct arrowhead style at each end

#### Scenario: Undirected edge renders without arrowheads
- **WHEN** `a---b` is drawn
- **THEN** the rendered arrow SHALL have `startArrowhead: null` and `endArrowhead: null`
- **AND** the JS layer SHALL preserve explicit `null` values (not coalesce to `'arrow'`)

#### Scenario: Dashed edges
- **WHEN** the DSL contains `a-.->b` (dashed directed) or `a-.-b` (dashed undirected)
- **THEN** arrows SHALL render with a dashed stroke style

#### Scenario: Auto-create unknown nodes
- **WHEN** an edge references a node not declared as a shape (e.g. `a-->typo`)
- **THEN** the unknown node SHALL be auto-created with its ID as the label

#### Scenario: ID pre-normalisation
- **WHEN** an ID contains spaces, hyphens, `+`, or uppercase letters (e.g. `api gateway["API Gateway"]`)
- **THEN** the ID SHALL be pre-normalised before parsing: non-word characters stripped, lowercased
- **AND** the label SHALL be preserved as written (label content is never modified)
- **AND** `api gateway --> lambda fn` SHALL parse as an edge from `apigateway` to `lambdafn`

#### Scenario: Subgraph return count
- **WHEN** `whiteboard.draw()` creates one or more new subgraphs
- **THEN** the return value SHALL include `, +N group(s)` at the end

#### Scenario: State not committed on JS failure
- **WHEN** the browser call raises an exception
- **THEN** persisted board state SHALL remain unchanged

#### Scenario: Multi-element draw returns one summary
- **WHEN** `whiteboard.draw()` is called with multiple shapes and edges
- **THEN** the call SHALL return one summary covering all added or updated elements

#### Scenario: Inline x/y positions new shapes
- **WHEN** `draw()` is called with `a["Foo"] x:100,y:200` (inline position props)
- **THEN** shape `a` SHALL be placed at `x=100, y=200` instead of auto-layout coordinates
- **AND** `x`/`y` SHALL be consumed from the style dict and NOT forwarded into `styleProps`

### Requirement: share requires browser

`whiteboard.share()` and `whiteboard.export()` SHALL load state from the session file, launch a Playwright browser, render the board, and return the result.

#### Scenario: share loads session state

- **WHEN** `wb.share()` is called after prior `wb.draw()` calls in separate processes
- **THEN** all shapes from the session file SHALL appear in the rendered output
- **AND** a shareable URL or exported content SHALL be returned

#### Scenario: share does not modify session state

- **WHEN** `wb.share()` is called
- **THEN** the session file SHALL be unchanged after the call completes

### Requirement: Insert ASCII text notes

`whiteboard.note(input=, background=)` SHALL parse tagged blocks and render each as a
code-font rectangle placed below any existing diagram content (100px below the
current canvas content). The background colour
defaults to beige (`#f5f5dc`).

#### Scenario: Table note
- **WHEN** a `table` block with CSV content is provided
- **THEN** a `tabulate` ASCII grid table SHALL appear on canvas with the first row as header

#### Scenario: Tree note
- **WHEN** a `tree` block with indented lines is provided
- **THEN** a unicode-connector tree (├──, └──, │) SHALL appear on canvas
- **AND** depth is detected from leading `-`, `.`, `_`, or space characters

#### Scenario: Sequence diagram note
- **WHEN** a `seq` block with `Actor -> Actor: label` lines is provided
- **THEN** an ASCII box-and-arrow sequence diagram SHALL appear on canvas

#### Scenario: Timeline note
- **WHEN** a `timeline` block with `name,start,duration` lines is provided
- **THEN** a Gantt-style bar chart SHALL appear on canvas
- **AND** non-integer start or duration SHALL return an error string

#### Scenario: Plain text note
- **WHEN** a `note` block with paragraph text is provided
- **THEN** word-wrapped text (default 60 chars) SHALL appear on canvas

#### Scenario: Note persists in session state
- **WHEN** `whiteboard.note(input="n1[note:\nhello\n]")` is called
- **THEN** element `n1` SHALL be stored in the session state
- **AND** `whiteboard.erase(ids=["n1"])` SHALL remove it by ID

#### Scenario: Unknown block type
- **WHEN** a block type not in `{table, tree, seq, timeline, note}` is used
- **THEN** an error string naming the unsupported type SHALL be returned
- **AND** no shape SHALL be inserted

#### Scenario: No blocks found
- **WHEN** the input contains no valid `id[type:\ncontent\n]` blocks
- **THEN** an error string SHALL be returned

#### Scenario: Renderer error propagates
- **WHEN** a renderer returns a string starting with `Error:`
- **THEN** `note()` SHALL return the error string with the block ID prepended
- **AND** no shape SHALL be inserted for that block

#### Scenario: Note placed below existing content
- **WHEN** `note()` is called on a board with existing content
- **THEN** the note SHALL be placed below the existing canvas content

#### Scenario: Multi-block note renders all blocks
- **WHEN** `note()` is called with multiple `id[type:\ncontent\n]` blocks in one call
- **THEN** each block SHALL render as a separate note on the canvas
- **AND** the return value SHALL reflect the total count, e.g. `"inserted 4 note(s)"`

#### Scenario: Indented triple-quoted input
- **WHEN** `note()` is called with a triple-quoted string that has common leading indentation
- **THEN** common indentation SHALL be ignored before parsing
- **AND** trailing whitespace on each line (including the closing `]`) SHALL be stripped
- **AND** blocks SHALL be parsed correctly regardless of surrounding whitespace
- **AND** all blocks SHALL be found even when block IDs have leading whitespace

### Requirement: Embed DSL as canvas element

`whiteboard.embed_dsl()` SHALL insert the current DSL text as a grey code-font
rectangle with id `"dsl"` placed below existing canvas content (100px below canvas max-y). Calling again overwrites
the previous embed (idempotent). The element is excluded from `save()`
snapshots. Returns `"nothing to embed — canvas is empty"` when state is empty.

#### Scenario: Embed current DSL text
- **WHEN** `whiteboard.embed_dsl()` is called with non-empty board state
- **THEN** the canvas SHALL contain one grey code-font element with id `"dsl"`
- **AND** repeated calls SHALL replace the previous embedded DSL element

### Requirement: Erase elements

`whiteboard.erase(ids=)` SHALL remove the specified element IDs from the canvas and
Python state. Edges that become dangling (src or dst in the erased set) SHALL
be removed automatically. Silently ignores IDs not currently rendered.

#### Scenario: Erase shape removes dangling edges
- **WHEN** `whiteboard.erase(ids=["b"])` is called and edges `a-->b` and `b-->c` exist
- **THEN** both edges SHALL be removed from state and canvas
- **AND** the return value SHALL be `"erased 1 element(s), 2 dangling edge(s) removed"`

#### Scenario: Erase unknown ID
- **WHEN** `whiteboard.erase(ids=["nonexistent"])` is called
- **THEN** the return value SHALL be `"erased 0 element(s)"`

#### Scenario: Erase with no dangling edges
- **WHEN** `whiteboard.erase(ids=["a"])` is called and `a` has no connected edges
- **THEN** the return value SHALL be `"erased 1 element(s)"` (no dangling mention)

### Requirement: Save diagram to file

`whiteboard.save(file=)` SHALL write the current diagram as a native `.excalidraw` JSON
file (format: `{"type":"excalidraw","version":2,"elements":[...],...}`). Before
writing, it SHALL upsert a `__otDSL` text element containing the current DSL so
that `whiteboard.load()` and `whiteboard.sync()` can restore Python state. The file can be
opened directly in excalidraw.com. Conventionally uses the `.excalidraw` extension.

#### Scenario: File written in native .excalidraw format
- **WHEN** `whiteboard.save(file="arch.excalidraw")` is called
- **THEN** the file SHALL be valid JSON with `"type": "excalidraw"`
- **AND** `elements` SHALL include a `__otDSL` text element containing the DSL
- **AND** the file SHALL be openable directly in excalidraw.com

### Requirement: Load diagram from file

`whiteboard.load(file=)` SHALL restore a diagram from a native `.excalidraw` JSON file.
It SHALL pass all elements to `updateScene`, then read the `__otDSL` element to
restore Python DSL state. If `__otDSL` is absent, the canvas is restored but
a warning is included in the return value.

#### Scenario: Restore from .excalidraw file
- **WHEN** `whiteboard.load(file="arch.excalidraw")` is called
- **THEN** all elements SHALL be restored to the canvas at saved positions
- **AND** Python state SHALL be restored from the embedded `__otDSL` element
- **AND** the return value SHALL be `"loaded N shapes, M edges"`

#### Scenario: File missing __otDSL element
- **WHEN** the file does not contain a `__otDSL` element
- **THEN** the canvas SHALL be restored and the return SHALL include a warning
- **AND** the return format SHALL be `"loaded N element(s) [warning: no __otDSL element — ...]"`

#### Scenario: File not found
- **WHEN** the file path does not exist
- **THEN** `"Error: file not found: <path>"` SHALL be returned

#### Scenario: Invalid JSON
- **WHEN** the file is not valid JSON
- **THEN** `"Error: invalid JSON in <path>: ..."` SHALL be returned

#### Scenario: Wrong format
- **WHEN** the JSON does not have `"type": "excalidraw"`
- **THEN** `"Error: not a valid .excalidraw file - ..."` SHALL be returned

### Requirement: Clear diagram

`whiteboard.clear()` SHALL remove all elements from the canvas and reset
stored board state to empty.

#### Scenario: Clear resets canvas and state
- **WHEN** `whiteboard.clear()` is called
- **THEN** all canvas elements SHALL be removed
- **AND** stored board state SHALL be empty

### Requirement: Open whiteboard

`whiteboard.open()` SHALL ensure excalidraw.com is open and bootstrapped, then always
start fresh — reset Python state and clear canvas — regardless of existing
canvas content. Untracked content warnings from `_ensure_ready()` are non-fatal.
Returns `"whiteboard ready"` on success.

#### Scenario: Open starts a fresh board
- **WHEN** `whiteboard.open()` is called
- **THEN** excalidraw.com SHALL be available and bootstrapped
- **AND** Python state and canvas content SHALL be cleared
- **AND** the return value SHALL be `"whiteboard ready"`

### Requirement: Close whiteboard

`whiteboard.close()` SHALL reset all Python state unconditionally, then close the
browser process. If the browser is not running, only Python state is reset.

An `atexit` handler SHALL be registered when the browser is first opened, so that
the Chrome process is closed automatically on interpreter exit even if
`whiteboard.close()` is not called explicitly. The handler SHALL tolerate
already-closed state (no-op if browser was already shut down).

#### Scenario: Close resets state
- **WHEN** `whiteboard.close()` is called
- **THEN** Python state SHALL be reset
- **AND** the browser process SHALL be closed when it is running

### Requirement: Hard reset

`whiteboard.hard_reset()` SHALL reset Python state unconditionally and attempt canvas
clear if the browser is available. Returns `"hard reset: state cleared, canvas
cleared"` or `"hard reset: state cleared (browser unavailable)"`.

#### Scenario: Hard reset without browser
- **WHEN** `whiteboard.hard_reset()` is called and the browser is unavailable
- **THEN** Python state SHALL be cleared
- **AND** the return value SHALL be `"hard reset: state cleared (browser unavailable)"`

### Requirement: Screenshot

`whiteboard.screenshot(file=)` SHALL capture the current canvas as a PNG image.
Without `file`, returns the raw image content for inline display.
With `file`, saves the image to the given path on disk.

#### Scenario: Screenshot saved to file
- **WHEN** `whiteboard.screenshot(file="board.png")` is called
- **THEN** the current canvas SHALL be captured as PNG
- **AND** the image SHALL be written to `board.png`

### Requirement: Scroll and zoom

`whiteboard.scroll(dx=, dy=)` SHALL pan the canvas by the given pixel offsets.
`whiteboard.zoom(level=)` SHALL set the zoom level; passing `0` SHALL fit all elements
in view. Negative levels SHALL return an error string without calling the browser.
`whiteboard.fit()` SHALL delegate to `whiteboard.zoom(level=0)`.

When `zoom(0)` is called, the fit behavior SHALL compute bounds from
the current canvas scene so that elements placed with explicit x/y coordinates
are correctly included in the viewport.

#### Scenario: Fit zoom includes explicit coordinates
- **WHEN** `whiteboard.zoom(level=0)` is called
- **THEN** the viewport SHALL fit the bounds of all current canvas elements

#### Scenario: Negative zoom rejected
- **WHEN** `whiteboard.zoom(level=-1)` is called
- **THEN** an error string SHALL be returned without calling the browser

### Requirement: Automatic browser lifecycle management

Every public tool that needs the live canvas SHALL ensure the browser and canvas
are ready before executing. If excalidraw.com is not open or the API is missing, the tool SHALL
transparently navigate, bootstrap, and re-render from the current Python state.

#### Scenario: First call opens browser
- **WHEN** no browser session is active and any excalidraw tool is called
- **THEN** excalidraw.com SHALL be opened and bootstrapped automatically

#### Scenario: Recovery after page reload
- **WHEN** the user reloads excalidraw.com mid-session and then calls `draw()`
- **THEN** `draw()` SHALL re-bootstrap and re-render existing shapes from Python state
- **AND** the new shape SHALL also appear

#### Scenario: Bootstrap failure
- **WHEN** `bootstrap.js` returns `false` (React API not found)
- **THEN** the tool SHALL return `"Error: excalidraw bootstrap failed — React API not found on page"`

#### Scenario: Browser not available
- **WHEN** the browser cannot be launched and any excalidraw tool is called
- **THEN** the tool SHALL return an error indicating the browser is not available

#### Scenario: Untracked canvas content warning
- **WHEN** the canvas is ready but tracked board state is empty and the canvas has untracked elements
- **THEN** mutating tools SHALL return a non-fatal warning where applicable

### Requirement: DSL syntax

The DSL accepted by `draw()` SHALL support a strict subset of Mermaid flowchart syntax.
Lines may be separated by newlines or semicolons. Node IDs are normalised to
lowercase with non-word characters stripped.

#### Supported shape types
| Syntax | Shape |
|--------|-------|
| `id["Label"]` | Rectangle (only supported shape in DSL) |
| `id["Line1\nLine2"]` | Multiline label |

> **Note:** Ellipse `((...))` and diamond `{...}` syntax raise an error directing the user to `whiteboard.style()`. `classDef`/`class` syntax is also unsupported in the DSL; use `whiteboard.style()` for colours and shapes after drawing.

#### Supported edge types
| Syntax | Meaning |
|--------|---------|
| `a-->b` | Directed arrow |
| `a-->|label|b` | Directed arrow with label |
| `a---b` | Undirected (no arrowheads) |
| `a<-->b` | Bidirectional arrows |
| `a --o b` | Dot arrowhead at end |
| `a --x b` | Bar arrowhead at end |
| `a-.->b` | Dashed directed arrow |
| `a-.-b` | Dashed undirected |
| `a["X"] --> b["Y"]` | Combined shape+edge declaration (labels preserved, edge uses bare IDs) |

#### Scenario: Mermaid header ignored
- **WHEN** DSL starts with `flowchart TD` or `graph LR`
- **THEN** the header SHALL be silently ignored

#### Scenario: Comment lines ignored
- **WHEN** DSL lines begin with `%%` or `#`
- **THEN** those lines SHALL be treated as comments and ignored

#### Scenario: Multiline labels
- **WHEN** a shape is defined as `id["Line1\nLine2"]`
- **THEN** the shape label SHALL contain a newline character

### Requirement: Graph layout via ELK.js

`whiteboard.layout(...)` SHALL run ELK.js in the browser to compute and apply
graph layout positions. It SHALL read the live canvas scene (not DSL state) to
build the ELK graph, inject `elkjs@0.11.0` from CDN if not already loaded,
await `elk.layout()`, patch node and text-child positions, recompute subgraph
bounding boxes, and call `fit()` to zoom to content.

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
node sized to their combined bounding box; all members translate as a unit.

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

Invalid `direction`, `algorithm`, `node_placement`, `crossing_min`, `cycle_breaking`,
or `arrow_type` values SHALL return an `"Error: ..."` string without calling the browser.

When `algorithm != "layered"`, `node_placement`, `crossing_min`, and
`cycle_breaking` are omitted from the ELK options object.

When `algorithm == "stress"`, `elk.stress.desiredEdgeLength` SHALL be set to
`gap_node * 3` to reduce node overlap.

#### Scenario: Layout applies to selected nodes
- **WHEN** `whiteboard.layout(...)` is called with selected elements
- **THEN** only selected eligible nodes SHALL be laid out
- **AND** the return string SHALL include `(selection)`

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

### Requirement: Align elements

`whiteboard.align(ids=, axis=)` SHALL apply Excalidraw's built-in alignment or
distribution actions to the specified element IDs.

| `axis` | Action |
|---|---|
| `"left"` | `alignLeft` |
| `"hcenter"` | `alignHorizontallyCentered` |
| `"right"` | `alignRight` |
| `"top"` | `alignTop` |
| `"vcenter"` | `alignVerticallyCentered` |
| `"bottom"` | `alignBottom` |
| `"hdistribute"` | `distributeHorizontally` |
| `"vdistribute"` | `distributeVertically` |

Invalid `axis` values SHALL return an `"Error: ..."` string without calling the browser.

#### Scenario: Align selected IDs on an axis
- **WHEN** `whiteboard.align(ids=["a", "b"], axis="left")` is called
- **THEN** Excalidraw's left-alignment action SHALL be applied to those element IDs

#### Scenario: Invalid alignment axis
- **WHEN** `whiteboard.align(ids=["a"], axis="diagonal")` is called
- **THEN** an error string SHALL be returned without calling the browser

### Requirement: Style resolution

Style strings SHALL use comma-separated `key:value` pairs. Shorthand keys are
expanded to Excalidraw style property names. Unknown keys SHALL be passed
through as-is.

The following new shorthands are supported:

| Key | Expanded property | Valid values | Applies to |
|-----|-------------------|-------------|------------|
| `fi` | `fillStyle` | `solid`, `hachure`, `cross-hatch`, `dots`, `zigzag`, `zigzag-line` | shapes and arrows |
| `cr` | `corners` | `round`, `sharp` | shapes only |
| `at` | `arrowType` | `curve`, `sharp`, `elbow` | arrows only |

Invalid values for `fi`, `cr`, and `at` SHALL raise `ValueError` (unlike other
properties which are passed through).

#### Scenario: Style shorthand expands
- **WHEN** style string `fi:solid,cr:round,at:elbow` is parsed
- **THEN** it SHALL resolve to Excalidraw `fillStyle`, `corners`, and `arrowType` properties

#### Scenario: Invalid style value rejected
- **WHEN** `fi:not-a-style` is parsed
- **THEN** a `ValueError` SHALL be raised

### Requirement: Note DSL

The `note()` input uses `id[type:\ncontent\n]` blocks. Supported types:

| Type | Renderer | Input format |
|------|----------|-------------|
| `table` | ASCII grid via `tabulate` | CSV (first row = header; `;` as row separator) |
| `tree` | Unicode tree (├──, └──) | Indented lines; `-`, `.`, `_`, or spaces as depth |
| `seq` | ASCII sequence diagram | `Actor -> Actor: label` lines |
| `timeline` | Gantt bar chart | `name,start,duration` (integers, 1-indexed) |
| `note` | Word-wrapped text | Plain paragraph text (wrap at 60 chars) |

All renderers accept `;` as a line separator in addition to newlines.

#### Scenario: Table note block
- **WHEN** `whiteboard.note(input="t1[table:\nA,B;1,2\n]")` is called
- **THEN** a table note SHALL be rendered on the canvas

#### Scenario: Semicolon line separator
- **WHEN** a note block uses `;` between logical lines
- **THEN** the renderer SHALL treat those separators as newlines

### Requirement: Apply visual styles

`whiteboard.style(ids=, style=)` SHALL apply Excalidraw style properties to existing
canvas elements in bulk. Styling is a visual operation and SHALL NOT rewrite the
diagram DSL persisted for save/load/sync. The `style` string uses the same
shorthand key:value format as `whiteboard.draw` inline styles. All keys and
values are case-insensitive.

Shape changes (`shape:d`, `shape:c`) SHALL use delete+recreate with the same ID
so arrow connections survive.

#### Scenario: Apply colour
- **WHEN** `whiteboard.style(ids=["a"], style="bc:green")` is called
- **THEN** shape `a` SHALL have `backgroundColor` set to `#bbf7d0`

#### Scenario: Case-insensitive values
- **WHEN** `whiteboard.style(ids=["a"], style="bc:Green,ss:Solid,f:Hand,shape:R")` is called
- **THEN** the values SHALL resolve identically to their lowercase equivalents

#### Scenario: Named colours
- **WHEN** the style string uses a named colour (e.g. `bc:blue`)
- **THEN** it SHALL resolve to the corresponding hex value (`#bfdbfe`)
- **AND** hex colours with `#` prefix SHALL be passed through unchanged

#### Scenario: x/y moves shape and its text label together
- **WHEN** `whiteboard.style(ids=["a"], style="x:100,y:200")` is called
- **THEN** both shape `a` and its bound text child SHALL be moved by the same delta
- **AND** the text SHALL remain visually attached to the box at its new position

#### Scenario: Accurate styled count
- **WHEN** `whiteboard.style(ids=["a", "doesnotexist"], style="bc:red")` is called and only `a` exists
- **THEN** the return value SHALL be `"styled 1 element(s)"` (count reflects actual matches, not input length)

#### Scenario: All IDs missing
- **WHEN** `whiteboard.style(ids=["x", "y"], style="bc:red")` is called and neither exists
- **THEN** the return value SHALL be `"styled 0 element(s)"`

### Requirement: Inspect canvas elements

`whiteboard.read_scene(info=)` SHALL return a structured text summary of all
non-deleted canvas elements (excluding `__otDSL` and deleted elements). The
`info` parameter controls detail level.

| `info` | Output |
|--------|--------|
| `"min"` | One-line summary: `"Scene: N shapes, M edges"` |
| `"default"` | Per-element listing: id, type, label, bc, sc, text-sc, groupIds; edges show arrowheads and stroke style |
| `"full"` | All of default plus sw, ss, roughness, opacity, fillStyle, corners, fontSize, fontFamily, textAlign, verticalAlign, x, y, w, h; edges add sc, sw, opacity, arrowType, position, dimensions |
| `"debug"` | All of full plus: deleted elements and `__otDSL` are included (not filtered); each element shows `deleted:true/false`; arrows show raw `points:[...]`; bound and standalone text elements listed in a separate `Text elements:` section with `containerId` |

Invalid `info` values SHALL raise `ValueError` without calling the browser.

A `⚠ TEXT=BG` warning SHALL appear when a shape's text `strokeColor` matches
its `backgroundColor` (invisible label).

#### Scenario: Read empty scene
- **WHEN** `whiteboard.read_scene()` is called with no elements on canvas
- **THEN** the return SHALL start with `"Scene: 0 shapes, 0 edges"`

#### Scenario: Read scene with shapes and edges
- **WHEN** canvas has shapes `a`, `b` and edge `a→b`
- **THEN** the return SHALL list both shapes with their properties and the edge with arrowhead info

#### Scenario: Invisible label warning
- **WHEN** a shape's text `strokeColor` equals its `backgroundColor`
- **THEN** the shape line SHALL include `⚠ TEXT=BG`

#### Scenario: info=min returns summary only
- **WHEN** `whiteboard.read_scene(info="min")` is called
- **THEN** the return SHALL be a single line `"Scene: N shapes, M edges"` with no element details

#### Scenario: info=full includes all properties
- **WHEN** `whiteboard.read_scene(info="full")` is called
- **THEN** each shape SHALL include sw, ss, r, o, cr, x, y, w, h, and text properties (f, fs, ta, va)
- **AND** each edge SHALL include sc, sw, o, at, x, y, w, h

#### Scenario: info=debug shows all elements including deleted
- **WHEN** `whiteboard.read_scene(info="debug")` is called
- **THEN** deleted elements and `__otDSL` SHALL be included in the output
- **AND** each element SHALL show `deleted:true` or `deleted:false`
- **AND** arrows SHALL show their raw `points:[...]` array
- **AND** bound text elements SHALL appear in a `Text elements:` section with `containerId`

#### Scenario: Invalid info raises
- **WHEN** `whiteboard.read_scene(info="bad")` is called
- **THEN** a `ValueError` SHALL be raised

### Requirement: Sync Python state from canvas

`whiteboard.sync()` SHALL read the `__otDSL` text element from the current Excalidraw
canvas and restore Python DSL state. Returns `"synced: N shapes, M edges"` on
success. If no `__otDSL` element is found, returns an explanatory message.

#### Scenario: Sync restores state
- **WHEN** `whiteboard.sync()` is called and a `__otDSL` element is present
- **THEN** stored board state SHALL be restored from the embedded DSL text

#### Scenario: No __otDSL element
- **WHEN** `whiteboard.sync()` is called and no `__otDSL` element is on canvas
- **THEN** a message explaining the absence SHALL be returned (no error)

### Requirement: __otDSL canvas element

The `__otDSL` element is a hidden text element on the Excalidraw canvas that
stores the current DSL text. It SHALL be:

- Written (upserted) by `whiteboard.save()` before file output
- Read by `whiteboard.load()` and `whiteboard.sync()` to restore Python state
- Excluded from `whiteboard.save()` scene snapshots (id starts with `__`)
- Written by `whiteboard.embed_dsl()` as a visible code-font element with id `"dsl"`
  (separate from the `__otDSL` hidden element)

#### Scenario: __otDSL written on save
- **WHEN** `whiteboard.save()` is called
- **THEN** a `__otDSL` text element SHALL be upserted on canvas with the current DSL

#### Scenario: __otDSL absent on load
- **WHEN** `whiteboard.load()` is called on a file with no `__otDSL` element
- **THEN** the canvas SHALL be restored and the return SHALL include a warning about empty Python state

### Requirement: DSL and style reference tool

`whiteboard.help()` SHALL return the full DSL syntax and style shorthand reference as a
plain-text string. No browser interaction is required. The content is loaded
from the bundled `dsl-reference.md` asset file.

#### Scenario: Returns non-empty string
- **WHEN** `whiteboard.help()` is called
- **THEN** a non-empty string covering DSL syntax and style shorthands SHALL be returned

### Requirement: Inline style props in draw()

Shape declarations in `whiteboard.draw()` MAY include style props after the closing `]`:

```
a["Label"] bc:green,sw:2
```

Edge declarations MAY include style props in a trailing `{key:value,...}` block:

```
a --> b {at:elbow,sc:red,sw:2}
a --> b {at:sharp,ss:dashed}
```

These props are applied to the element alongside position. The same shorthand
key:value format used by `whiteboard.style()` is supported. Values are
case-insensitive.

#### Scenario: Edge inline style block
- **WHEN** `draw()` is called with `a --> b {at:elbow,sc:red}`
- **THEN** the arrow SHALL render with elbow routing (`elbowed: true`) and red stroke
- **AND** the arrow element SHALL carry a standard 2-point seed path `[[0,0],[dx,dy]]`
  so Excalidraw has valid geometry to display; `elbowed: true` together with
  `startBinding`/`endBinding` causes Excalidraw to re-route it orthogonally
