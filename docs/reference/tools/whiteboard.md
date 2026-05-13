# Whiteboard

Live diagram manipulation on [excalidraw.com](https://excalidraw.com) via pydoll (Chrome CDP). Draw, annotate, save, and restore diagrams using a Mermaid-compatible DSL.

Short alias: `wb`

## Highlights

- Mermaid-compatible DSL for shapes, edges, subgraphs, and inline styling
- ELK.js auto-layout with five algorithms (layered, stress, mrtree, radial, force)
- ASCII note overlays: tables, trees, sequence diagrams, timelines
- Save/load native `.excalidraw` files and generate shareable links

## Quick Start

```python
whiteboard.open()
whiteboard.draw(input='a["API"]; b["DB"]; a-->b')
whiteboard.style(ids=["b"], style="bc:blue,sc:#1d4ed8")
whiteboard.screenshot()
whiteboard.save(file="diagrams/arch.excalidraw")
```

## Functions

Source of truth: `src/otdev/tools/excalidraw.py` (`__all__` + function docstrings).

<!-- BEGIN GENERATED:WB_HELP_SUMMARY -->
| Function | Summary |
|---|---|
| `whiteboard.align(*, ids: list[str], axis: str) -> str` | Align or distribute a set of shapes using Excalidraw's built-in actions. |
| `whiteboard.boards() -> str` | List all active whiteboard session boards. |
| `whiteboard.clear(*, board: str | None = None) -> str` | Delete the session file for the given board and optionally clear the canvas. |
| `whiteboard.close() -> str` | Close the excalidraw browser and reset all Python state. |
| `whiteboard.draw(*, input: str, board: str | None = None) -> str` | Add or update diagram elements from DSL. Always additive — never clears. |
| `whiteboard.embed_dsl() -> str` | Embed the current DSL as a note element on the canvas. |
| `whiteboard.erase(*, ids: list[str], board: str | None = None) -> str` | Remove individual elements from the canvas and Python state. |
| `whiteboard.fit() -> str` | Fit all elements in view. |
| `whiteboard.hard_reset() -> str` | Reset Python DSL state unconditionally; attempt canvas clear if browser is available. |
| `whiteboard.help() -> str` | Return the full DSL and style reference. Call this before using whiteboard.draw or whiteboard.style. |
| `whiteboard.layout(*, direction: str = 'DOWN', gap_layer: int = 80, gap_node: int = 40, algorithm: str = 'layered', node_placement: str = 'NETWORK_SIMPLEX', crossing_min: str = 'LAYER_SWEEP', cycle_breaking: str = 'GREEDY', arrow_type: str | None = None, elk_options: dict[str, str] | None = None, board: str | None = None) -> str` | Apply ELK.js graph layout to the current whiteboard. |
| `whiteboard.load(*, file: str) -> str` | Restore diagram from a native ``.excalidraw`` file. |
| `whiteboard.note(*, input: str, background: str = '#f5f5dc') -> str` | Insert ASCII-rendered text annotations onto the canvas. |
| `whiteboard.open() -> str` | Open excalidraw.com and start with a clean canvas. |
| `whiteboard.read_scene(*, info: str = 'default') -> str` | Return a structured text summary of all canvas elements. |
| `whiteboard.save(*, file: str) -> str` | Save current diagram to a native ``.excalidraw`` JSON file. |
| `whiteboard.screenshot(*, file: str | None = None, board: str | None = None) -> Any` | Take a screenshot of the current canvas as PNG. |
| `whiteboard.scroll(*, dx: int = 0, dy: int = 0) -> str` | Pan the canvas by (dx, dy) pixels. |
| `whiteboard.share(*, board: str | None = None) -> str` | Generate a shareable Excalidraw link for the current canvas. |
| `whiteboard.style(*, ids: list[str], style: str) -> str` | Apply visual style properties to existing canvas elements in bulk. |
| `whiteboard.sync() -> str` | Sync Python DSL state from the ``__otDSL`` canvas element. |
| `whiteboard.zoom(*, level: float) -> str` | Set zoom level. Pass 0 to fit all elements in view. |
<!-- END GENERATED:WB_HELP_SUMMARY -->

## Requires

- Chrome or Chromium installed on the host
- `onetool-mcp[whiteboard]` extra (provides `pydoll-python`; not included in `[all]`)

## Configuration

### Required

- No required `tools.whiteboard` settings.

### Optional

- This pack does not define any pack-specific keys under `tools.whiteboard`.

### Defaults

- OneTool uses the built-in defaults for whiteboard layout, DSL state, and save/load behavior.
- Requires Chrome/Chromium installed on the host. No external MCP server needed.

## Tools

### `open()`

Open excalidraw.com and start with a clean canvas. Resets all Python state.

```python
whiteboard.open()
# Returns: "whiteboard ready"
```

### `draw(input)`

Add or update diagram elements from DSL. Additive — never clears existing elements.

- **New shapes** get auto-layout positions.
- **Existing shapes** (by ID) are patched — label and inline style props are updated, position and size are preserved.
- Edges are deduplicated by `(src, dst, label, startArrowhead, endArrowhead)`.

```python
whiteboard.draw(input='a["Service A"]; b["DB"]; a-->b')
# Returns: "+2 shapes, +1 edge(s): edge-a-b"
```

Inline style props can be appended after the closing `]`:

```python
whiteboard.draw(input='a["API"] bc:blue,sc:#1d4ed8,sw:2')
```

### `style(ids, style)`

Apply visual style properties to existing canvas elements. Never changes position or size unless `x`, `y`, `w`, `h` are given.

```python
whiteboard.style(ids=["a", "b"], style="bc:green,sc:#16a34a")
whiteboard.style(ids=["c"], style="shape:d")   # change to diamond
# Returns: "styled 2 element(s)"
```

Style shorthand reference (all keys and values are **case-insensitive**):

| Key | Excalidraw property | Notes |
|-----|---------------------|-------|
| `bc` | backgroundColor | hex (requires `#`: `bc:#ff0000`) or named colour (`bc:green`) |
| `sc` | strokeColor | hex (requires `#`: `sc:#1d4ed8`) or named colour (`sc:blue`) |
| `sw` | strokeWidth | number |
| `ss` | strokeStyle | `solid`, `dashed`, `dotted` |
| `r` | roughness | 0-2 |
| `o` | opacity | 0-100 |
| `f` | fontFamily | `hand`, `normal`, `mono`, `excalidraw` |
| `fs` | fontSize | number |
| `ta` | textAlign | `left`, `center`, `right` |
| `va` | verticalAlign | `top`, `middle`, `bottom` |
| `shape` | element type | `r`=rect, `d`=diamond, `c`=circle |
| `x`/`y` | position | pixels |
| `w`/`h` | width/height | pixels |

New shapes are **auto-sized** from their label content: width scales with the longest line, height with the number of lines (minimum 160×60 px). Use `w`/`h` to override the auto-computed size: `a["Label"] w:300,h:80`.

Named colours: `green`, `blue`, `red`, `purple`, `yellow`, `orange`, `pink`, `gray`, `white`, `black`.

> **Colour format:** Hex colours require the `#` prefix (`bc:#ff0000`). Named colours do not (`bc:green`). All values are case-insensitive (`bc:Green` and `bc:green` are equivalent).

### `help()`

Return the full DSL syntax and style shorthand reference as plain text. No browser required. Call this before using `whiteboard.draw()` or `whiteboard.style()` for the first time.

```python
whiteboard.help()
# Returns: full DSL and style reference as a string
```

### `note(input, background)`

Insert ASCII-rendered text annotations below any existing diagram content. Notes are stored in session state and can be removed with `whiteboard.erase(ids=[...])` using the note block ID.

```python
whiteboard.note(input="""
t[table:
Name,Role
Alice,Dev
Bob,QA
]
""")
```

### `erase(ids)`

Remove elements by ID. Dangling edges (whose src or dst is erased) are removed automatically.

Edge IDs use the format `edge-{src}-{dst}` (plus optional label and arrowhead suffix). The `draw()` return value lists newly created edge IDs.

```python
whiteboard.erase(ids=["a", "edge-a-b"])
# Returns: "erased 2 element(s)"

whiteboard.erase(ids=["b"])  # b has edges a-->b and b-->c
# Returns: "erased 1 element(s), 2 dangling edge(s) removed"
```

### `align(ids, axis)`

Align or distribute a set of shapes using Excalidraw's built-in alignment actions.

```python
whiteboard.align(ids=["a", "b", "c"], axis="top")        # snap top edges
whiteboard.align(ids=["a", "b", "c"], axis="hcenter")    # centre horizontally
whiteboard.align(ids=["a", "b", "c"], axis="hdistribute") # even horizontal spacing
# Returns: "aligned 3 element(s) (top)"
```

| `axis` | Effect |
|--------|--------|
| `left` | Snap left edges |
| `hcenter` | Centre on vertical axis |
| `right` | Snap right edges |
| `top` | Snap top edges |
| `vcenter` | Centre on horizontal axis |
| `bottom` | Snap bottom edges |
| `hdistribute` | Even horizontal spacing |
| `vdistribute` | Even vertical spacing |

### `layout(...)`

Apply ELK.js graph auto-layout to the canvas. Loads ELK.js from CDN (once per session), runs the chosen algorithm in the browser, patches every node position, recomputes subgraph bounding boxes, and calls `wb.fit()`. Works on the full canvas or a selection.

```python
whiteboard.layout()                                         # layered, top-to-bottom
whiteboard.layout(direction="RIGHT", gap_layer=120)         # left-to-right pipeline
whiteboard.layout(algorithm="stress")                       # spring-based, undirected
whiteboard.layout(algorithm="mrtree", direction="DOWN")     # tree with clear root
whiteboard.layout(direction="RIGHT", arrow_type="elbow")    # post-layout elbow arrows
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `algorithm` | `"layered"` | `layered`, `stress`, `mrtree`, `radial`, `force` |
| `direction` | `"DOWN"` | `DOWN`, `RIGHT`, `UP`, `LEFT` (`layered` only) |
| `gap_layer` | `80` | Pixels between layers (`layered` only) |
| `gap_node` | `40` | Pixels between nodes in the same layer |
| `node_placement` | `"NETWORK_SIMPLEX"` | `BRANDES_KOEPF`, `LINEAR_SEGMENTS`, `SIMPLE` (`layered` only) |
| `crossing_min` | `"LAYER_SWEEP"` | `MEDIAN_LAYER_SWEEP`, `NONE` (`layered` only) |
| `cycle_breaking` | `"GREEDY"` | `DEPTH_FIRST`, `MODEL_ORDER` (`layered` only) |
| `arrow_type` | `None` | After layout, patch all arrows to `"curve"`, `"sharp"`, or `"elbow"` |
| `elk_options` | `None` | `dict[str, str]` of raw ELK key→value pairs; merged last, overrides all named params |

**Algorithms:**

| Algorithm | Best for |
|-----------|----------|
| `layered` | DAGs and pipelines — ranks nodes into layers, minimises edge crossings |
| `stress` | Undirected or exploratory graphs — spring-based, increase `gap_node` for dense graphs |
| `mrtree` | Trees with a clear single root — minimal-spanning-tree layout |
| `radial` | Radial tree centred on one node |
| `force` | Clustered undirected graphs — force-directed |

### `read_scene(info)`

Return a structured text summary of all canvas elements. Use to verify `draw()`, `style()`, and `erase()` results without a screenshot.

```python
whiteboard.read_scene()                  # default detail
whiteboard.read_scene(info="min")        # one-line count only
whiteboard.read_scene(info="full")       # all style properties
```

| `info` | Output |
|--------|--------|
| `"min"` | `Scene: N shapes, M edges` — count only |
| `"default"` | Per-element: id, type, label, bc, sc, text-sc, groupIds; edges: arrowheads, stroke style |
| `"full"` | All of default + sw, ss, roughness, opacity, fillStyle, corners, font, textAlign, position, size |
| `"debug"` | All of full + deleted elements, `__otDSL`, `deleted:` flag, arrow `points:`, bound text with `containerId` |

A `⚠ TEXT=BG` warning appears when a shape's text colour matches its background (invisible label).

### `sync()`

Sync Python DSL state from the `__otDSL` canvas element. Use this after loading a file directly in the Excalidraw UI or drag-and-dropping an `.excalidraw` file.

```python
whiteboard.sync()
# Returns: "synced: 4 shapes, 3 edges"
```

### `save(file)`

Save the diagram to a native `.excalidraw` file (JSON). Also embeds the current DSL as a `__otDSL` text element on the canvas for state restoration.

```python
whiteboard.save(file="diagrams/arch.excalidraw")
```

### `load(file)`

Restore a diagram saved by `save()`. Reads the native `.excalidraw` JSON and restores Python state from the embedded `__otDSL` element.

```python
whiteboard.load(file="diagrams/arch.excalidraw")
# Returns: "loaded 4 shapes, 3 edges"
```

> If the file has no `__otDSL` element (e.g. created outside `whiteboard.save()`), the canvas is still restored but Python state will be empty and the return includes a warning. Call `whiteboard.sync()` after manually adding a DSL element.

### `share()`

Generate a shareable Excalidraw link. Encrypts the full scene client-side (AES-GCM, 128-bit) and uploads to Excalidraw's storage. Returns a URL anyone can open in a browser.

```python
whiteboard.share()
# Returns: "https://excalidraw.com/#json={id},{key}"
```

### `embed_dsl()`

Insert the current DSL as a grey code-font box on the canvas. Idempotent. Excluded from `save()` snapshots.

```python
whiteboard.embed_dsl()
# Returns: "embedded DSL (5 lines)"
```

### `clear()`

Clear all elements from the canvas and reset Python state.

```python
whiteboard.clear()
```

### `screenshot(file)`

Take a PNG screenshot of the current canvas.

```python
whiteboard.screenshot()                            # return inline image
whiteboard.screenshot(file="diagrams/canvas.png") # save to disk
```

### `scroll(dx, dy)`

Pan the canvas.

```python
whiteboard.scroll(dx=200, dy=0)
```

### `zoom(level)`

Set zoom level. Pass `0` to fit all elements in view.

```python
whiteboard.zoom(level=0.5)   # 50%
whiteboard.zoom(level=0)     # fit all
```

### `fit()`

Fit all elements in view. Equivalent to `whiteboard.zoom(level=0)`.

```python
whiteboard.fit()
```

### `close()`

Close the excalidraw browser and reset all Python state. An atexit handler also closes the browser automatically on interpreter exit.

```python
whiteboard.close()
```

### `hard_reset()`

Reset Python state unconditionally; attempt canvas clear if browser is available. Use to recover from broken state.

```python
whiteboard.hard_reset()
```

---

## Draw DSL

The `draw()` input uses a Mermaid-compatible syntax. Statements can be separated by **semicolons** (preferred) or newlines.

### Shapes

Only rectangles are supported:

```
id["Label"]               rectangle
id["Label"] bc:blue       rectangle with inline style props
id["Line1\nLine2"]        multiline label
id bc:blue                style-only update (label unchanged)
```

> **Note:** Ellipse `((...))` and diamond `{...}` syntax raise a `ValueError`. Use `whiteboard.style(ids=[...], style="shape:c")` or `shape:d` to change shape after drawing.

### Edges

```
a-->b                     directed arrow
a-->|label|b              directed arrow with label
a---b                     undirected (no arrowheads)
a<-->b                    bidirectional arrows
a --o b                   dot/circle arrowhead at end
a --x b                   bar/cross arrowhead at end
a-.->b                    dashed directed arrow
a-.->|label|b             dashed directed arrow with label
a-.-b                     dashed undirected
```

### Subgraphs

```
subgraph grp ["Group Label"]
  a
  b
end
```

Draws a bounding rectangle around the listed members.

### Headers (ignored)

```
flowchart TD
graph LR
```

Mermaid direction headers are accepted and silently skipped.

### Comments

```
%% this is a comment
# this is also a comment
```

---

## Note DSL

The `note()` input uses tagged blocks:

```
id[type:
content...
]
```

One or more blocks per call. Each becomes a code-font rectangle placed below the diagram and is addressable by its block ID.

### `table` — CSV grid

First row is the header. Columns separated by commas; rows by newlines or semicolons.

```python
whiteboard.note(input="""
t[table:
Task,In,Out
compare:base,33,273
compare:mcp,3261,92
]
""")
```

Output:

```
+----------------+------+------+
| Task           |   In |  Out |
+================+======+======+
| compare:base   |   33 |  273 |
+----------------+------+------+
| compare:mcp    | 3261 |   92 |
+----------------+------+------+
```

### `tree` — directory / hierarchy

Depth indicated by leading `-`, `.`, `_`, or spaces. One character = one level (for spaces, the smallest non-zero indent is the unit).

```python
whiteboard.note(input="""
tr[tree:
root/
-src/
--main.py
--utils.py
-tests/
]
""")
```

Output:

```
root/
├── src/
│   ├── main.py
│   └── utils.py
└── tests/
```

Space-indented trees also work:

```
root/
  src/
    main.py
  tests/
```

### `seq` — sequence diagram

One message per line: `Actor -> Actor: label`. Label is optional.

```python
whiteboard.note(input="""
s[seq:
Client -> Server: request
Server -> DB: query
DB -> Server: rows
Server -> Client:
]
""")
```

Output:

```
+--------+      +--------+    +----+
| Client |      | Server |    | DB |
+--------+      +--------+    +----+
    |                |            |
    |---request----->|            |
    |                |---query--->|
    |                |<--rows-----|
    |<---------------|            |
+--------+      +--------+    +----+
| Client |      | Server |    | DB |
+--------+      +--------+    +----+
```

### `timeline` — Gantt bar chart

One task per line: `name,start,duration` (integers, 1-indexed).

```python
whiteboard.note(input="""
g[timeline:
Design,1,4
Build,3,8
Test,9,4
]
""")
```

Output:

```
Design  [####........]
Build   [..########..]
Test    [...........####]
```

### `note` — plain text

Word-wrapped paragraph text (default wrap at 60 chars).

```python
whiteboard.note(input="""
n[note:
This is a plain text annotation that will be
word-wrapped and displayed in a code-font box.
]
""")
```

---

## Examples

### Architecture diagram with styling

```python
whiteboard.open()
whiteboard.draw(input='api["API Gateway"]; auth["Auth Service"]; users["Users DB"]; api-->auth; auth-->users')
whiteboard.style(ids=["api", "auth"], style="bc:#dae8fc,sc:#6c8ebf")
whiteboard.style(ids=["users"], style="bc:#d5e8d4,sc:#82b366")
whiteboard.note(input="""
t[table:
Service,Latency,Owner
API Gateway,12ms,Platform
Auth Service,8ms,Security
]
""")
whiteboard.fit()
whiteboard.screenshot()
```

### Save and restore

```python
whiteboard.save(file="diagrams/arch.excalidraw")
# ... later ...
whiteboard.open()
whiteboard.load(file="diagrams/arch.excalidraw")
```

### Incremental drawing

```python
whiteboard.draw(input='a["Start"]; b["Process"]')
whiteboard.draw(input='c["End"]; b-->c')   # additive, positions relative to existing
```

### Upsert — update label or style without moving

```python
whiteboard.draw(input='a["API"]; b["DB"]')
whiteboard.draw(input='a["API Gateway"] bc:blue')   # updates label and colour; position preserved
```

### Share a diagram

```python
whiteboard.draw(input='a["Hello"]; b["World"]; a-->b')
whiteboard.share()
# Returns a URL like: https://excalidraw.com/#json=abc123,key456
```
