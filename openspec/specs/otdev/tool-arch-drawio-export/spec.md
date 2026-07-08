# tool-arch-drawio-export Specification

## Purpose

Defines the draw.io-editable diagram output contract for the `arch` tool: embedding an
`mxfile` model in generated system/project diagram SVGs (structure fidelity, geometry
fidelity, fallback behavior), the report export affordance, inline-markup stripping, and
the `drawio_export` profile toggle.

## Requirements

### Requirement: Embedded draw.io model in generated diagram SVGs
`arch.generate` SHALL embed a draw.io (`mxfile`) model in the root `<svg>` element's `content` attribute of every generated system-level and project-stage diagram SVG, in the format produced by draw.io's "Export As SVG → Include a copy of my diagram" (XML-escaped, uncompressed `<diagram>` payload), such that the file opens as an editable diagram in draw.io.

#### Scenario: System diagram SVG carries an embedded model
- **WHEN** `arch.generate(...)` renders a system diagram SVG for any level (`sys`, `app`, `cmp`)
- **THEN** the SVG file written under `solution/images/` SHALL carry a `content` attribute on its root element
- **AND** the decoded attribute value SHALL be a well-formed `<mxfile>` document containing exactly one `<diagram>` with uncompressed `<mxGraphModel>` XML

#### Scenario: Project stage diagram SVG carries an embedded model
- **WHEN** `arch.generate(...)` renders a project stage diagram SVG
- **THEN** that SVG file SHALL carry an embedded `<mxfile>` model under the same contract as system diagrams

#### Scenario: Workbook-supplied diagrams are excluded
- **WHEN** `arch.generate(...)` renders a diagram sourced from the workbook `diagram` sheet
- **THEN** the resulting SVG SHALL NOT carry a `content` attribute

#### Scenario: Provenance stamp
- **WHEN** an embedded model is written
- **THEN** the `<mxfile>` element SHALL carry `host="onetool-arch"`

#### Scenario: Visual rendering is unchanged
- **WHEN** an SVG with an embedded model is displayed by a browser or image viewer
- **THEN** it SHALL render identically to the same SVG without the `content` attribute

### Requirement: Embedded model structural fidelity
The embedded model SHALL reproduce the diagram's structure from the render context: one vertex per rendered node, container nesting via parent references, and one edge per rendered interface bound to its endpoint vertices by id.

#### Scenario: Nodes map to vertices with labels
- **WHEN** the rendered diagram contains user, external-system, system, app, or component nodes
- **THEN** the embedded model SHALL contain one vertex cell per node whose `id` is the node's diagram path and whose value is the node's label

#### Scenario: Nesting maps to parent references
- **WHEN** a rendered node is contained in another (component in app, app in system)
- **THEN** its vertex SHALL reference the container's cell as its parent, with geometry relative to that parent

#### Scenario: Edges bind to endpoint vertices
- **WHEN** the rendered diagram contains an interface edge
- **THEN** the embedded model SHALL contain an edge cell whose `source` and `target` reference the endpoint vertex ids and whose value is the interface label
- **AND** moving an endpoint vertex in a draw.io editor SHALL keep the edge attached

### Requirement: Embedded model geometry fidelity
The embedded model SHALL position vertices using the layout geometry of the rendered SVG, so the diagram opens in draw.io arranged as rendered; when geometry cannot be extracted, generation SHALL fall back to deterministic placement instead of failing.

#### Scenario: Layout matches the rendered SVG
- **WHEN** geometry for a rendered node is extractable from the SVG produced by the render engine
- **THEN** the corresponding vertex geometry SHALL reflect that node's rendered position and size

#### Scenario: Geometry extraction fallback
- **WHEN** geometry cannot be extracted from a rendered SVG (for any or all nodes)
- **THEN** `arch.generate` SHALL still succeed
- **AND** affected vertices SHALL receive deterministic non-overlapping placeholder positions

### Requirement: Inlined SVG markup excludes the embedded model
Diagram SVG markup inlined into generated HTML pages SHALL NOT include the `content` attribute; the embedded model SHALL exist only in the standalone SVG files.

#### Scenario: HTML pages carry stripped markup
- **WHEN** a system or project page inlines a diagram SVG that has an embedded model on disk
- **THEN** the inlined `<svg>` markup in the HTML SHALL NOT contain a `content` attribute

### Requirement: Export affordance on report pages
Each system and project diagram panel in the generated report SHALL offer an "Export to draw.io" control that downloads the standalone diagram SVG under a `*.drawio.svg` filename.

#### Scenario: Export button downloads the editable SVG
- **WHEN** a user activates the export control on a diagram panel
- **THEN** the browser SHALL download that diagram's standalone SVG file
- **AND** the suggested filename SHALL end in `.drawio.svg`

#### Scenario: Downloaded file is editable in draw.io
- **WHEN** the downloaded file is opened in a draw.io editor
- **THEN** it SHALL open as an editable diagram whose boxes can be moved with edges remaining connected

#### Scenario: Workbook diagram panels have no export control
- **WHEN** a diagram panel shows a workbook-supplied diagram
- **THEN** the panel SHALL NOT show the draw.io export control

### Requirement: Profile toggle for draw.io export
The `drawio_export` boolean profile `data` option SHALL control the feature, defaulting to enabled.

#### Scenario: Enabled by default
- **WHEN** a profile does not set `drawio_export`
- **THEN** generated system/project diagram SVGs SHALL carry embedded models and report pages SHALL show export controls

#### Scenario: Disabled by profile
- **WHEN** the active profile sets `drawio_export: false`
- **THEN** generated SVGs SHALL NOT carry a `content` attribute
- **AND** report pages SHALL NOT show draw.io export controls

#### Scenario: Invalid value rejected
- **WHEN** `drawio_export` is set to a non-boolean value
- **THEN** `arch.generate` SHALL fail with an explicit configuration error
