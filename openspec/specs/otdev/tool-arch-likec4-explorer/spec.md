# tool-arch-likec4-explorer Specification

## Purpose

Defines deterministic view generation, the renderer-neutral solution contract,
and the self-contained, accessible, offline OneTool architecture explorer. The
current pinned LikeC4 integration is an adapter, not the product contract.

## Requirements

### Requirement: Generated LikeC4 model and deterministic ViewGraph
The tool SHALL construct a deterministic `ViewGraph` from the production-loaded,
validated, resolved, and selected architecture. It SHALL contain selected nodes,
containers, edges, contextual statuses, source traces, stable IDs, resolved
icons/styles, layout hints, and diagram metadata. The tool SHALL generate the
LikeC4 logical model and standard views from that graph with deterministic
identifiers and SHALL expose canonical-to-LikeC4 ID mappings.

#### Scenario: Generate a structural view from real data
- **WHEN** the canonical 2027 system selection is generated
- **THEN** every rendered element and relationship originates in the production
  loader/resolver/ViewGraph path and carries its canonical stable ID

#### Scenario: Reject mock architecture in acceptance output
- **WHEN** an explorer acceptance path bypasses loaders or uses hard-coded
  architecture data
- **THEN** the production-path end-to-end test fails

### Requirement: Custom self-contained OneTool explorer
`arch.generate(input_path, output_path, selections=None, force=False)` SHALL
produce a self-contained OneTool React explorer using a pinned local renderer
adapter. It SHALL use OneTool-owned navigation, details, tables, overlays,
toolbars, and actions and SHALL provide one Solution page
whose system set can be selected by system, system group, impacted change,
change group, or tag.

#### Scenario: Browse explorer groups offline
- **WHEN** the generated report is opened with network access blocked
- **THEN** system, group, change, and tag navigation, local layout/navigation,
  details, filters, and export actions remain usable from bundled local assets

#### Scenario: Preserve endpoint while switching browse group
- **WHEN** the user switches from system A to change 2027 to a tag
- **THEN** the roadmap endpoint and comparison remain unchanged unless the user
  explicitly edits them

### Requirement: Local solution projection and layout
Generation SHALL precompute validated roadmap snapshots and roadmap-wide
selection indexes, but SHALL NOT precompute the cross-product of system set,
interface depth, snapshot, architectural level, and color. The browser SHALL
derive the requested projection and renderer-neutral layout locally. Its
normalized cache identity SHALL include roadmap, snapshot/model, sorted
selector, depth, level, topology-affecting theme, projection/schema version,
renderer-adapter version, and layout-schema version while excluding color.
Projection and layout caches SHALL use LRU bounds of 32 and 24 entries
respectively.

Projection SHALL expand the selected system set by the requested number of
undirected interface hops, include interfaces whose endpoint systems are both
included, and list boundary interfaces without adding their outside systems.
Relationships SHALL NOT create interface hops. SYS/APP/CMP rollup SHALL retain
self-collapsed interface metadata and aggregate only interfaces with identical
visible endpoints, direction, type, product status, and context status.
Snapshot graphs SHALL use the before/after union so removals remain visible.

#### Scenario: Expand one interface hop
- **WHEN** system A is selected at interface depth 1
- **THEN** directly connected systems and their internal interfaces are in the
  diagram, while interfaces leaving that expanded set are listed as boundary
  interfaces without expanding again

#### Scenario: Show a removal at its snapshot
- **WHEN** a snapshot removes system D and interface A-to-D
- **THEN** the projected before/after union can render D and A-to-D as removed

#### Scenario: Recolor without relayout
- **WHEN** the user changes Color by while snapshot, selector, depth, and level
  remain unchanged
- **THEN** the cached topology and layout are reused and only styles change

#### Scenario: Refit after graph or container changes
- **WHEN** a roadmap selection changes the graph or navigation content changes
  the embedded canvas dimensions
- **THEN** the viewport refits the active diagram so every rendered node remains
  visible without requiring the full-screen explorer workaround

### Requirement: Independent solution controls
The Solution page SHALL provide history, breadcrumbs, summary, and search. Roadmap
snapshot, interface depth, architectural level, and coloring SHALL be
independent persistent controls. Solution history SHALL retain at most 100
entries. The architectural-level dropdown SHALL contain
only System, Application, and Component. Clicking the diagram SHALL open a
full-screen solution explorer whose canonical inspector exposes properties and
relationships from the active runtime `ViewGraph`. Runtime projections SHALL
not depend on finding their nodes in an unrelated precompiled LikeC4 model.

#### Scenario: Change architectural level
- **WHEN** the user changes Application to Component
- **THEN** the current system selector, roadmap snapshot, interface depth, and
  coloring remain unchanged while the projection is regenerated

#### Scenario: Select a coloring mode
- **WHEN** the user selects Change status, Integration type, or Tag
- **THEN** `tools.arch` YAML palettes determine colors; change status supports
  No Change, Changed, Added, and Removed separately for systems, applications,
  components, and interfaces

#### Scenario: Inspect a runtime-projected element
- **WHEN** the user opens the full explorer and selects a system, nested element,
  or interface from a locally projected diagram
- **THEN** canonical properties and direct or nested relationships are shown
  without Views, Structure, or Deployments sections

### Requirement: Clean accessible node presentation
The bundled `clean` theme SHALL render simple rounded nodes with concise names,
subtle hierarchy and relationships, details outside the node, and status
treatment using text or markers and borders in addition to color. State-only
views MAY be neutral; contextual views SHALL use the approved status palette.

#### Scenario: Render all contextual states accessibly
- **WHEN** a ViewGraph contains out-of-scope, future, new, changed, unchanged,
  and decommissioned content
- **THEN** the corresponding approved fill/border tokens and non-color cues are
  applied consistently in the canvas and details

### Requirement: Bidirectional interface diagram and table linkage
Diagram relationships and interface table rows SHALL represent the same
canonical interfaces and expose the same ID, endpoints, direction, type,
description, status, and trace. Edge/row selection, hover, search, and filters
SHALL synchronize in both directions.

#### Scenario: Select A-to-D from the diagram
- **WHEN** the user selects diagram edge `A-to-D`
- **THEN** interface details open and the matching table row is selected and
  scrolled into view

#### Scenario: Select A-to-D from the table
- **WHEN** the user selects table row `A-to-D`
- **THEN** the explorer opens a containing view, centers or fits the edge, and
  highlights the edge and its endpoints

#### Scenario: Select a merged edge
- **WHEN** one rendered edge represents multiple canonical interface IDs
- **THEN** edge selection filters the table to that set and row selection marks
  the shared edge while identifying the selected interface

#### Scenario: Navigate an interface hidden at the current level
- **WHEN** a selected interface is not visible at the current semantic level
- **THEN** the explorer offers and performs **Open containing view**

### Requirement: Configurable AG Grid Community tables
Every entity table SHALL use a locally bundled pinned AG Grid Community engine
behind a shared OneTool wrapper. It SHALL support search, sort, multi-sort,
typed column and external filtering, resizing, drag reorder, show/hide, pinning,
density, reset, selection, copying, keyboard navigation, and export of
current-view or all rows and columns. The wrapper SHALL provide its own
searchable column chooser and explicit copy/export actions using Community APIs;
generated output SHALL contain no AG Grid Enterprise code or license dependency.
Extension columns SHALL appear unless excluded by a valid preset. The grid SHALL
share the explorer's typography, spacing, radii, surfaces, focus treatment, and
light/dark color scheme; it SHALL use restrained separators and status marks
rather than boxed cells, decorative striping, or whole-row status fills.

#### Scenario: Configure and export the current interface table
- **WHEN** a user searches, filters, sorts, reorders, hides, and pins interface
  columns and selects current-view export
- **THEN** export contains filtered/sorted rows and visible columns in current
  order while retaining stable IDs and raw values

#### Scenario: Restore after schema change
- **WHEN** remembered browser layout refers to an older column schema
- **THEN** the table discards the incompatible state and uses the typed
  workspace default without modifying the source workbook

#### Scenario: Copy selected interface rows
- **WHEN** a user selects interface rows and invokes **Copy selected rows**
- **THEN** the wrapper copies stable columns and raw values in visible-column
  order without requiring an Enterprise clipboard module

#### Scenario: Run with Community modules only
- **WHEN** the generated explorer dependency and browser acceptance checks run
- **THEN** search, filters, column choice/order/size/pinning, selection, copy,
  and both export modes pass with no Enterprise package, watermark, or license

#### Scenario: Present a clean integrated grid
- **WHEN** the interface table is shown beside its diagram in light, dark,
  comfortable, or compact mode
- **THEN** typography and controls align with the explorer, data remains the
  visual focus, hover/focus/selection/status remain distinguishable without
  color alone, and grid chrome does not resemble a boxed spreadsheet

#### Scenario: Reject invalid workspace table configuration
- **WHEN** configuration references an unknown table or column ID
- **THEN** validation fails with the configuration location

### Requirement: Shared controls and complete interaction states
The explorer SHALL give tables and surrounding buttons, dropdowns, inputs,
segmented controls, tabs, menus, dialogs, and tooltips clean shared typed tokens
for size, spacing, typography, borders, foreground/background, hover, selected,
disabled, error, and focus. Every visible action SHALL perform its documented
behavior and expose applicable loading, empty, error, disabled, focused, and
selected states. The document SHALL provide a skip link and semantic landmarks;
controls SHALL use native button or link behavior where applicable and icon-only
actions SHALL have accessible names.

#### Scenario: Operate without pointer or color dependence
- **WHEN** a keyboard-only user navigates explorer controls, grids, menus, and
  dialogs
- **THEN** focus is visible, labels and tooltips identify icon actions, target
  sizes and contrast are sufficient, and no required meaning depends on hover
  or color alone

#### Scenario: Search a long navigation list
- **WHEN** a systems, groups, changes, tags, or columns list exceeds the practical
  menu length
- **THEN** the user can search it with an accessible search field

### Requirement: Coherent responsive explorer workspace
The explorer SHALL prioritize the diagram in a stable workspace with browse
navigation, canvas, contextual details, and an on-demand data region. Supporting
regions SHALL collapse or adapt without covering required canvas controls or
making the active selection unreachable. Shell, diagram, grid, dialog, and
print presentation SHALL share the selected light or dark color scheme,
typography, spacing, interaction states, and semantic status treatment.

#### Scenario: Inspect a system without losing canvas context
- **WHEN** a user opens details and the related interface table for a selected
  system
- **THEN** the selection remains visible or recoverable on the canvas and the
  details and data regions can be hidden and reopened

#### Scenario: Use the explorer at a narrow viewport
- **WHEN** the viewport cannot show navigation, canvas, details, and table side
  by side
- **THEN** supporting regions become stacked regions,
  required actions remain reachable, and content does not overflow the viewport

#### Scenario: Restore an external diagram
- **WHEN** the initial normalized selection names an applicable external SVG
- **THEN** the Diagram view control restores that entry and the explorer renders
  its embedded content without generated nodes or network access

#### Scenario: Change the color scheme
- **WHEN** the user selects light, dark, or system color scheme
- **THEN** the shell, LikeC4 canvas, grid, menus, dialogs, focus indicators, and
  status cues change coherently without losing non-color meaning

### Requirement: Responsive and stale-safe runtime
The explorer SHALL avoid constructing hidden diagrams, tables, and attachment
viewers until required, SHALL keep long browse collections operable, and SHALL
preserve input responsiveness while searching or changing non-urgent filters.
Projection/layout requests SHALL have renderer-neutral identities, yield to the
interaction path, ignore stale completions, and never cache failed results.
Configurable warning and hard node/edge limits SHALL be evaluated before layout
and SHALL offer a safe depth reduction. Loading, empty, warning, and failure
states SHALL be accessible. Activating an embedded feature SHALL not require a
network request.

#### Scenario: Search a large prepared report
- **WHEN** a user types into search while a large prepared diagram and entity
  collection are available
- **THEN** text entry, focus, and cancellation remain responsive while results
  update and the active diagram is not needlessly reconstructed

#### Scenario: Open an initially hidden data region offline
- **WHEN** a user opens a table or attachment viewer that was not initially
  visible while networking is blocked
- **THEN** the feature initializes from embedded assets and preserves the
  current explorer selection

#### Scenario: Ignore a slower obsolete layout
- **WHEN** an older request completes after a newer selector request
- **THEN** only the newer request may update the active diagram and export geometry

#### Scenario: Stop an oversized projection before layout
- **WHEN** projected node or edge count exceeds the configured hard limit
- **THEN** layout is not dispatched and the explorer explains the selector/depth and offers depth reduction

### Requirement: Fragment-safe linkable explorer state
The explorer SHALL encode selected state/roadmap point, comparison origin,
system-selector kind and subject, interface depth, semantic level, coloring,
visibility, displayed statuses, search, diagram ID, and selected stable
entity/interface ID in fragment-safe state.

#### Scenario: Reopen a copied interface link
- **WHEN** a user copies and reopens a link to interface `A-to-D`
- **THEN** the same prepared state, view, filters, containing diagram, and
  interface selection are restored offline

### Requirement: Typed themes, icons, and style precedence
The explorer SHALL resolve theme precedence as view override, workspace theme,
configured default, then bundled clean; element precedence SHALL be kind,
tag/predicate, entity, then view. It SHALL support the pinned LikeC4 `aws`,
`azure`, `bootstrap`, `gcp`, and `tech` icon namespaces, `none`, and sanitized
local SVG under `assets/icons/` through `@icons` references.

#### Scenario: Render every pinned namespace offline
- **WHEN** fixtures reference every valid icon name exposed by the pinned icon
  versions
- **THEN** validation and rendering succeed without runtime network access

#### Scenario: Resolve a nested local SVG safely
- **WHEN** an entity references a safe nested `@icons/domain/icon.svg`
- **THEN** the icon is sanitized, rendered consistently, embedded in standalone
  output, and retained in the workspace bundle

#### Scenario: Reject unsafe icon references
- **WHEN** an icon is remote, missing, unknown, unsafe SVG, path-traversing, or
  resolves outside `assets/icons/`
- **THEN** validation rejects it with source and entity locations

#### Scenario: Apply documented style precedence
- **WHEN** kind, tag, entity, and view styles set the same supported field
- **THEN** the view value wins and all non-conflicting approved OneTool tokens
  remain applied

### Requirement: Portable offline and print behavior
Generated reports SHALL bundle versioned scripts, fonts, icons, styles, data,
and other assets, use safe relative paths and CSP, and SHALL issue no CDN or
render-time network request. Layout, tables, and details SHALL have defined
responsive and print presentation. The CSP SHALL permit only the local
WebAssembly execution needed by the bundled Graphviz layouter.

#### Scenario: Copy report to a spaced path
- **WHEN** a report is copied to a directory whose path contains spaces and all
  network access is blocked
- **THEN** every route, diagram, control, font, icon, table, and print view
  remains usable

### Requirement: Renderer adapter containment
OneTool SHALL own normalized selection, projected `ViewGraph`, canonical event
IDs, and `SolutionLayoutResult` geometry. `ComputedView`, `DiagramView`, model
references, private renderer fields, generated renderer IDs, and compatibility
casts SHALL remain inside the explicit renderer/build/compatibility allowlist.
An automated boundary check SHALL reject new low-level imports elsewhere.

#### Scenario: Replace the renderer boundary conceptually
- **WHEN** the current adapter is reviewed
- **THEN** selection, projection, history, URL state, inspectors, tables, and Draw.io do not require renderer model browsing

#### Scenario: Detect an import leak
- **WHEN** a product module imports a low-level LikeC4 package or private field
- **THEN** the frontend boundary verification fails with that file
