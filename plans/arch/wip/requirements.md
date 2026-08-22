# Architecture Pack v2 — Report and Rendering Requirements

Status: working requirements for the v2 report and rendering path.

This file is the complete, self-contained normative specification for the target report. An implementer does not need the interaction mock, a renderer candidate, or another project document to interpret it. Section 17 records design provenance only; those references do not add requirements.

Version and scope terms used throughout this document:

- **Architecture schema v2** is the existing canonical YAML/Excel model and is not replaced by this work.
- **Report v1** is the current LikeC4-based generated explorer and export presentation.
- **Report v2** is the target report, renderer, layout, export, and Confluence experience defined here.
- This document changes `arch.generate` and the rendering/export boundaries it shares with `arch.validate` and `arch.export`. Other public `arch` operations retain their existing schema-v2 contracts unless a requirement explicitly names them.

## 1. How to maintain this document

This file is the single requirement registry for Report v2.

- **MUST**, **MUST NOT**, **SHOULD**, and **MAY** are normative.
- Keep requirement IDs stable. Amend a requirement in place instead of restating it elsewhere.
- Put shared behaviour in a common requirement and use tables only for differences.
- Keep defaults in section 5. Do not repeat default values in feature sections.
- Acceptance scenarios reference requirement IDs rather than duplicating their text.
- Dependency names identify research candidates only. No renderer or layout engine is selected until the research and benchmark gates in sections 9 and 15 are complete.
- Accepted breaking contract changes move through `/opsx:new`. Do not add aliases, legacy-key detection, or compatibility shims.

## 2. Product outcome and boundaries

### Outcome

- **OUT-01** `arch.generate` MUST produce a polished, self-contained architecture-report application from a resolved OneTool workspace.
- **OUT-02** The report MUST let a user select systems, expand interface scope, move through roadmap states, inspect aligned tables and diagrams, and save the report configuration.
- **OUT-03** The report MUST use a simple three-screen workflow—Reports, Create/Edit Scope, and Report—with a crisp technical visual language and substantially better layout.
- **OUT-04** The generated report MUST be useful first as a standalone offline artifact and reusable later as the rendering core for low-priority Confluence delivery.

### Non-goals

- **OUT-05** The report is not an architecture editor. It MUST NOT modify the source YAML or Excel architecture.
- **OUT-06** The report is not a general model browser. It presents one saved or newly selected report scope.
- **OUT-07** A renderer-specific format, including Archify JSON or a React Flow graph, MUST NOT become a second architecture source of truth.
- **OUT-08** General-purpose manual diagram editing and WYSIWYG placement are outside the initial Report v2 scope.
- **OUT-09** Public report, saved-report, scene, and export contracts MUST remain renderer- and layout-neutral. Candidate-specific source formats, identifiers, or runtime APIs MUST NOT cross those boundaries.

### V2 direction at a glance

This table is a non-normative summary. The referenced requirement IDs are authoritative.

| Area | Report v1 baseline | Report v2 direction | Governing requirements |
| --- | --- | --- | --- |
| Experience | Explorer-oriented workspace | Report library, scope builder, and structured report | `OUT-02`–`OUT-04`, `FLOW-01`–`FLOW-16` |
| Data ownership | Canonical data translated through renderer-specific structures | OneTool projection and saved intent remain authoritative | `BOUND-01`–`BOUND-06`, `DATA-01`–`DATA-17` |
| Rendering | LikeC4 is the current adapter | Evidence-selected renderer behind neutral scene contracts | `OUT-09`, `RESEARCH-01`–`RESEARCH-05`, `DIAG-01`–`DIAG-05` |
| Layout | Current generic layout baseline | Evidence-selected, hierarchy-aware, measurable layout | `LAYOUT-01`–`LAYOUT-14`, `QUAL-01`–`QUAL-07` |
| State and inspection | Snapshot-oriented exploration | Coherent roadmap explanation, aligned grids, and diagrams | `DATA-07`–`DATA-09`, `FLOW-16`, `SELECT-01`–`SELECT-06` |
| Packaging and export | Per-report frontend build and divergent export paths | Prebuilt offline bundle and neutral, transactional exports | `EXPORT-01`–`EXPORT-05`, `OPS-01`–`OPS-06` |
| Delivery quality | Standalone explorer | Accessible, performant standalone delivery | `PERF-01`–`PERF-06`, `A11Y-01`–`A11Y-06` |
| Delivery extensions | Draw.io capability and Confluence options | Draw.io export and Confluence delivery at the same low priority | `PRIORITY-01`–`PRIORITY-03`, `DATA-16`, `EXPORT-01`, `EXPORT-04`–`EXPORT-05`, `CONF-01`–`CONF-07` |

### Delivery priority

- **PRIORITY-01** The standalone offline report and its SVG and PNG exports are the core Report v2 delivery path.
- **PRIORITY-02** Draw.io export and all Confluence delivery are equal low-priority extensions. These capabilities MUST NOT gate the initial Report v2 release.
- **PRIORITY-03** Low priority changes sequencing, not quality. When either extension is scheduled, its applicable data, security, fidelity, accessibility, and acceptance requirements MUST be met without introducing a parallel report or rendering architecture.

## 3. System boundary and ownership

```text
YAML / Excel
    -> OneTool load, validate, replay, select, and project
    -> canonical ViewGraph and presentation data
    -> layout input
    -> renderer-neutral scene/layout result
    -> selected renderer and report shell
    -> offline HTML / SVG / PNG
    -> low-priority Draw.io / Confluence delivery
```

| Concern | Owner | Persisted form |
| --- | --- | --- |
| Architecture entities, relationships, roadmap, and presentation metadata | OneTool workspace | YAML or Excel |
| Resolved state and selected projection | OneTool | Generated payload only |
| Saved report choices | Report configuration | YAML |
| Node placement, ports, routes, and label geometry | Layout subsystem | Derived cache or generated payload only |
| SVG and interactive viewer state | Renderer | Derived runtime state only |

- **BOUND-01** OneTool MUST own validation, stable canonical IDs, roadmap replay, scope selection, graph projection, status derivation, and presentation resolution.
- **BOUND-02** The layout subsystem MUST consume a renderer-neutral OneTool graph. It MUST NOT browse or reinterpret source workspace files.
- **BOUND-03** The renderer MUST consume canonical data plus neutral geometry. It MUST NOT own architecture selection or roadmap logic.
- **BOUND-04** Every rendered node and edge MUST retain its canonical OneTool ID through SVG, selection, diagnostics, export, and Confluence rendering.
- **BOUND-05** The report runtime MAY use generated JSON as an internal serialization, but YAML remains the only portable saved-report format.
- **BOUND-06** Validation, report generation, and export MUST use the same load, replay, selection, projection, and presentation semantics. Structured errors and warnings, including source and identity details, MUST survive that preparation path without being converted to renderer-specific strings.

## 4. Data contracts

### 4.1 Source architecture model

YAML and Excel are authoring formats for the same architecture semantics. OneTool loads, validates, and replays them before the report is created.

| Record | Required semantics | Optional semantics |
| --- | --- | --- |
| System | ID, name | Description, tags, groups, properties |
| Application | ID, name, owning system/parent | Description, tags, properties, technology |
| Component | ID, name, owning application/parent | Description, tags, properties, technology |
| User/actor | ID, name, kind | Description, tags, properties |
| Interface | ID, provider, consumer, direction, type | Name, tags, properties, technology |
| Relationship | ID, source, target, direction | Name, description, tags, properties, type |
| Change | ID | Description, groups |
| Roadmap entry | Change ID, order | None |
| Delta record | Existing or new entity ID, change ID, change type | Changed fields, change note |

- **INPUT-01** YAML and Excel representations MUST resolve to the same canonical model, validation results, roadmap states, and stable IDs.
- **INPUT-02** Baseline records have no change reference. A delta record reuses a canonical ID, references one ordered change, and has the type `added`, `changed`, or `removed`.
- **INPUT-03** Replay MUST materialize additions, apply sparse changes without clearing omitted values, and remove entities at the referenced state. The report MUST consume the resolved result rather than reinterpret delta rows.
- **INPUT-04** Ownership references MUST resolve to the effective parent at each state: application to system and component to application. Invalid or cyclic ownership MUST fail validation before layout.
- **INPUT-05** An interface endpoint MAY reference a system, application, component, or user/actor. Provider, consumer, and direction semantics MUST survive replay and projection unchanged.
- **INPUT-06** Tags and groups MUST normalize to ordered string collections. Properties MUST preserve validated scalar, list, and map values so configured metadata such as owner, lifecycle, criticality, data classification, or delivery semantics can be filtered and inspected without becoming hard-coded schema fields.
- **INPUT-07** Users/actors MUST be first-class selectable endpoints and MUST remain visually distinct from architecture containers.
- **INPUT-08** Every resolved changed entity or interface MUST retain its change ID, change type, and available change note for report explanation and audit.
- **INPUT-09** Generic relationships MUST retain source, target, forward/reverse/bidirectional direction, type, and related change semantics independently from interfaces.

### 4.2 Canonical architecture projection

- **DATA-01** A projected node MUST provide: ID, entity kind, name, description, parent, children, transition status, context status, tags, groups, optional technology/icon/style, related changes and notes, optional source location, and properties.
- **DATA-02** A projected edge MUST provide: ID, kind, name, source, target, direction, transition status, context status, interface member IDs, tags, integration type, optional technology/style/source, related changes and notes, and properties.
- **DATA-03** Supported canonical kinds are `system`, `application`, `component`, `user`, `interface`, and `relationship`.
- **DATA-04** Direction MUST distinguish provider-to-consumer, consumer-to-provider, forward, reverse, and bidirectional semantics. Layout direction and arrow rendering MUST derive from this value rather than storage order.
- **DATA-05** A canonical ID is any non-empty trimmed string. Renderer-specific identifier restrictions MUST be handled internally without changing that canonical ID.
- **DATA-06** A projected graph MUST identify its graph, selection, resolved state, containers, focus, changes, comparison, tombstones, diagrams, and diagnostics.

### 4.3 Roadmap state

- **DATA-07** The generated payload MUST contain enough deterministic information to render Baseline and every ordered roadmap state without reading the workspace again.
- **DATA-08** An entity present at the active state MUST expose its derived status. Removed entities MUST be absent from ordinary state views after removal takes effect; a transition diagram MAY show them explicitly.
- **DATA-09** Changing roadmap state MUST update scope, boundary interfaces, counts, rows, layouts, diagrams, and selection coherently in one state transition.

### 4.4 Saved report configuration

The saved YAML contract contains only durable user intent:

| Group | Required values |
| --- | --- |
| Identity | Schema version, report ID, name, optional description |
| Scope | Normalized selection expression and interface-hop depth; the expression may include systems, system groups, changes, change groups, and tags |
| State | Roadmap state ID |
| Report view | Application level, solution detail level, active Other diagram ID |
| Appearance | Theme |
| Sections | Open/closed state by stable section ID |
| Grids | Column order, width, visibility, pinning, filter, sort, and current page by stable grid/column ID |

- **DATA-10** Loading saved YAML MUST resolve it against the current generated model and recompute all derived content.
- **DATA-11** Missing or inapplicable IDs MUST produce a clear diagnostic. The runtime MUST NOT substitute by display-name similarity.
- **DATA-12** Pan, zoom, transient hover, open popovers, layout coordinates, and renderer implementation details MUST NOT be persisted in saved report YAML.
- **DATA-13** Removed schema fields or values MUST fail schema validation. No legacy aliases or migration-only runtime paths are permitted.

### 4.5 Layout and scene contracts

- **DATA-14** Layout input MUST include graph identity, detail level, target viewport/aspect, node dimensions, canonical hierarchy, correctly oriented edges, selected/focused IDs, visual simplification groups, and optional previous geometry.
- **DATA-15** Layout output MUST include request/graph/selection identity, node and container bounds, ports, routed edge sections, label bounds, overall bounds, shared route-lane IDs where used, and structured diagnostics.
- **DATA-16** Layout output MUST be independent of the SVG implementation and reusable by SVG, PNG, Draw.io, and static Confluence export.
- **DATA-17** Renderer DOM MUST expose stable semantic hooks including `data-node-id`, `data-edge-id`, entity kind, status, and selection state.

## 5. Defaults

This table is the only source for Report v2 defaults.

| Setting | Default |
| --- | --- |
| Initial application screen | Reports |
| Available System Scope values | Selected only (0) through selected + 3 interface hops |
| New report scope | Selected systems plus 1 interface hop |
| Roadmap state | Workspace-generated default |
| Applications section mode | Applications |
| Solution detail | System |
| Systems page size | 10 |
| Applications/components page size | 20 |
| Interfaces page size | 20 |
| Scope-builder page size | 20 |
| Theme | Saved user choice when present; otherwise operating-system preference |
| Layout direction | Derived by view preset and topology |
| Suggested maximum bends per routed edge | 2 |
| Suggested maximum route stretch | 1.35 times the Manhattan distance between endpoints |
| Suggested minimum interior route segment | 16 px |
| Micro-segment threshold | Less than 8 px |
| Warning projection size | More than 160 nodes or 320 edges |
| Hard projection size | More than 500 nodes or 1,000 edges |

## 6. Derived report logic

- **DERIVE-01** Selected systems are the systems explicitly committed in the scope builder.
- **DERIVE-02** Effective system scope is selected systems plus systems reachable within the configured number of interface hops at the active roadmap state.
- **DERIVE-03** Only interfaces contribute scope hops. Generic relationships MUST NOT expand scope.
- **DERIVE-04** Every in-scope system, application, and component MUST expose why it is present: Selected or its shortest hop distance.
- **DERIVE-05** An active interface with both endpoints in effective scope is Internal.
- **DERIVE-06** An active interface with exactly one endpoint in effective scope is Boundary. It remains visible in the Interfaces grid and MUST terminate in the Solution Diagram at a compact labelled boundary stub or equivalent external port; its outside system MUST NOT be added to effective scope solely because of that interface.
- **DERIVE-07** Counts, rows, diagrams, and exports MUST derive from the same resolved projection. The UI MUST NOT maintain parallel mock or presentation-only counts.
- **DERIVE-08** Parallel interfaces with the same visible endpoints, direction, integration type, and status MAY be visually aggregated. Every canonical member ID MUST remain discoverable and selectable.
- **DERIVE-09** Application/component projection MUST preserve parents and calculate the lowest common ancestor of every visible edge for layout and routing.
- **DERIVE-10** The normalized selection contract MAY include explicit systems, system groups, changes, change groups, and tags. All selector forms MUST resolve through the same effective-scope calculation and retain stable identity.
- **DERIVE-11** The Report v2 scope builder MAY initially expose only explicit system selection. Opening a saved or ad hoc report with other selector forms MUST preserve the normalized expression until the user explicitly confirms conversion to an equivalent explicit-system selection.

## 7. Application flow

The application has three mutually exclusive screens and uses the browser page as its scroll container.

### 7.1 Reports

- **FLOW-01** Reports MUST show a responsive library of saved-report cards and a visually distinct Create report card.
- **FLOW-02** A saved-report card MUST show name, description, current state/freshness, System/Application/Interface counts, and an unambiguous Open action.
- **FLOW-03** The whole card MUST be one keyboard-operable control.
- **FLOW-04** Opening a report MUST restore durable configuration before recomputing its content against the active model.

### 7.2 Create or edit scope

- **FLOW-05** Scope selection MUST be a dedicated screen, not checkboxes in the report's Systems grid.
- **FLOW-06** The screen MUST provide Back to reports, one filter across System/group/tags/owner, a paginated selection table, selection summary, and Generate report.
- **FLOW-07** Row and checkbox activation MUST toggle the system. Select all MUST apply to filtered rows on the current page and accurately expose checked, unchecked, and mixed states.
- **FLOW-08** Draft selection MUST survive filtering and pagination. Generate MUST be disabled when nothing is selected.
- **FLOW-09** Editing scope MUST begin from committed selection and MUST NOT alter the open report until confirmed.

### 7.3 Report

- **FLOW-10** The report header MUST provide All reports, report title/context, System Scope, Roadmap state, Edit scope, Save report, and theme control.
- **FLOW-11** A summary strip MUST show current Systems, Applications, Components, and Interfaces counts.
- **FLOW-12** The report MUST contain these independently collapsible sections in this order:

  1. Systems.
  2. Applications and Components.
  3. Interfaces.
  4. Solution Diagram.
  5. Other diagrams.

- **FLOW-13** Collapsing a section MUST hide only its body and preserve its state.
- **FLOW-14** Transitions between screens, scope, detail, and roadmap state MUST not reload the page.
- **FLOW-15** The app MUST not create a fixed-height nested workspace or a second page-level scroll area.
- **FLOW-16** The active roadmap state MUST have a compact explanation showing its name, description, groups, added/changed/removed counts, and a keyboard-accessible list of affected items and available change notes. Baseline MUST be labelled explicitly as having no applied changes.

## 8. Grid requirements

### 8.1 Common grid contract

- **GRID-01** The three report tables MUST use AG Grid Community and MUST NOT require Enterprise features.
- **GRID-02** Each grid MUST provide quick filtering, column filtering, sorting/multi-sort, resizing, header-drag ordering, keyboard navigation, row selection, and pagination.
- **GRID-03** A shared column dialog MUST support show/hide and left/right pinning with Reset, Cancel, and Apply.
- **GRID-04** Grid rows and columns MUST have stable IDs suitable for saved configuration.
- **GRID-05** Grids MUST use auto-height rows with pagination rather than a nested vertical scrollbar. Narrow viewports MAY scroll horizontally inside the section.
- **GRID-06** Pagination controls MUST be hidden when every row fits on one page.
- **GRID-07** Clicking a row MUST change shared report selection; it MUST NOT change report scope.

### 8.2 Grid-specific contract

| Grid | Rows | Required columns | Special behaviour |
| --- | --- | --- | --- |
| Systems | Active systems in effective scope | System, Scope, System groups, Tags, Status, Lifecycle, Owner | System pinned left; no selection checkboxes |
| Applications | Active applications belonging to effective-scope systems | Application, System, Reach, Status, Technology, Tags | Application pinned left |
| Applications + components | Active applications and components in a flat hierarchy | Entity, Kind, Parent, System, Reach, Status, Technology, Tags | Entity pinned left; components visually subordinate |
| Interfaces | Active interfaces with at least one endpoint in effective scope | Interface, Source system, Source entity, Target system, Target entity, Direction, Type, Technology, Scope, Status | Interface pinned left; Boundary clearly marked |

- **GRID-08** The Applications section MUST switch between the two modes without Enterprise tree data.
- **GRID-09** Changing Applications mode MUST retain applicable filter, selection, and column state and update the filter's visible and accessible label.
- **GRID-10** Each grid MUST provide stable row lookup by canonical ID so shared selection can reveal the row as required by `SELECT-04`.
- **GRID-11** Every grid MUST provide a shared row-details action that exposes the full description, hierarchy, tags, groups, properties, technology, source reference, and applicable change note without forcing all metadata into columns. Empty fields MUST be omitted rather than rendered as blank labels.

## 9. Diagram and layout requirements

### 9.1 Renderer and layout decision status

No renderer or layout engine is selected by this document. Renderer interaction/rendering and graph layout are separate decisions even when a library offers both.

| Candidate | Required research role |
| --- | --- |
| Current LikeC4 adapter | Production baseline and a candidate if it can meet the target contracts and quality gates |
| `tt-a1i/archify` or scoped reuse of its MIT-licensed parts | Candidate for visual language, SVG composition, routing, interaction, and export techniques |
| React Flow with an independent layout engine | Candidate for interaction and rendering; React Flow is not itself a layout solution |
| Purpose-built SVG/Canvas or another evidence-backed option | Permitted when evaluated through the same contracts and fixtures |

- **RESEARCH-01** Renderer and layout engine selection MUST be evaluated and recorded as two explicit decisions. A combined stack MAY win both decisions, but one decision MUST NOT be inferred from the other.
- **RESEARCH-02** Research MUST evaluate, at minimum, the current LikeC4 baseline, an Archify-derived approach, and a React Flow approach against the same canonical scenes. Layout research MUST separately compare viable hierarchy-aware placement and routing engines or algorithms.
- **RESEARCH-03** Candidate evaluation MUST cover layout quality, roadmap stability, interaction capability, accessibility, export fidelity, offline bundle size, performance, licensing/attribution, maintenance surface, Confluence reuse, and implementation complexity. Results MUST be weighted by the delivery priorities in section 2; Draw.io and Confluence considerations MUST NOT outweigh core report and layout quality.
- **RESEARCH-04** A decision record MUST identify the selected production renderer and layout path before candidate-specific implementation becomes the production path. Production MUST have one selected path rather than runtime fallback engines or renderers.
- **RESEARCH-05** Research spikes MUST consume and return the neutral contracts in sections 3 and 4. Spike-only identifiers, persisted formats, and APIs MUST NOT leak into saved reports or public pack contracts.

- **DIAG-01** The report MUST use the renderer selected by `RESEARCH-01`–`RESEARCH-04` behind the renderer-neutral scene contract. No candidate is preferred merely because it is named in this document.
- **DIAG-02** The renderer MUST support multiple independent diagram instances on one report page without global DOM queries or singleton viewer state.
- **DIAG-03** Reused candidate code SHOULD be scoped to well-owned modules such as visual primitives, geometry/routing, text fit, legends, semantic hooks, interaction modules, exports, and composition diagnostics.
- **DIAG-04** A candidate's monolithic application/template, fixed placement assumptions, domain model, or persisted document format MUST NOT become the report architecture.
- **DIAG-05** Fonts, icons, renderer code, layout code, and workers MUST be bundled locally.

### 9.2 Layout pipeline

The required layout pipeline is a staged subsystem rather than a single generic engine call:

1. Normalize hierarchy, dimensions, direction, and edge ownership.
2. Aggregate visual edges and assign semantic zones.
3. Place children recursively from the innermost container outward.
4. Place the quotient graph of containers and top-level nodes.
5. Assign deterministic boundary ports and route edges through reserved corridors.
6. Place labels, validate composition, and repair eligible geometry.
7. Return neutral geometry and structured diagnostics.

- **LAYOUT-01** The chosen engine MUST be selected by the benchmark in section 15, not by renderer convenience.
- **LAYOUT-02** The layout spike MUST compare the current production baseline with viable hierarchy-aware placement and routing approaches, including Dagre/AntV-style recursion, ELK, Archify-derived or custom routing, and other justified candidates. This candidate set is for research and expresses no preference.
- **LAYOUT-03** The production path MUST contain one layout implementation after the spike. Do not retain runtime fallback engines.
- **LAYOUT-04** Cross-container edges MUST route through deterministic boundary ports derived from peer container, direction, and integration class.
- **LAYOUT-05** Cross-container relationships MUST NOT stretch or reorder unrelated internal container content unnecessarily.
- **LAYOUT-06** Disconnected children MUST use a deliberate compact strip or grid within their parent.
- **LAYOUT-07** Identical input and configuration MUST produce identical geometry.
- **LAYOUT-08** When previous geometry is available, unchanged nodes SHOULD retain position and relative order. Added nodes SHOULD appear near their parent and strongest neighbours.
- **LAYOUT-09** Layout MUST run without blocking ordinary report interaction. Warning and hard-size graphs MUST use a worker or equivalent off-main-thread execution where supported.

### 9.3 View presets

| Detail | Required layout intent | Default label policy |
| --- | --- | --- |
| System | Context flow: users/inbound, selected core, downstream dependencies, with peers/support in a secondary lane | Show system and important interface labels |
| Application | Recursive compound flow with the selected systems dominant and external systems compact at the perimeter | Show application labels; reduce low-priority edge labels |
| Component | Recursive local layouts with bundled boundary corridors and strong semantic zoom | Show node labels; reveal most edge labels on hover/focus/selection |

- **LAYOUT-10** View direction MUST derive from topology and preset. The report MUST NOT force every graph to LR or TB.
- **LAYOUT-11** Selected systems MUST remain visually prominent without relying on colour alone.
- **LAYOUT-12** External actors and external systems MUST remain visually distinct from architecture containers.
- **LAYOUT-13** Message buses or other high-fan-out integration hubs MAY receive a dedicated lane when topology and integration type justify it.
- **LAYOUT-14** At dense detail, semantic zoom, selective labels, edge aggregation, and focus modes MUST be used instead of shrinking all content to illegibility.

### 9.4 Composition quality

- **QUAL-01** No node may overlap another node, escape its parent, or be covered by a visible label.
- **QUAL-02** No edge may cross a node interior or obscure a container heading.
- **QUAL-03** The layout checker MUST report proper crossings, ambiguous shared corridors, container-border runs, label-route clearance, bend count, route stretch, and short segments.
- **QUAL-04** Default report diagrams SHOULD target a width-to-height ratio between 1.4 and 2.2. Ratios above 2.5 require a topology diagnostic and usable pan/zoom.
- **QUAL-05** On the Report v2 fixture suite, the selected implementation MUST reduce the weighted crossing/congestion score by at least 30% from the current production baseline and must not regress any hard correctness gate.
- **QUAL-06** For adjacent roadmap states, unchanged-node median displacement SHOULD be at most 5% of the layout diagonal and P95 at most 15%, after normalizing translation and scale.
- **QUAL-07** Visible edge labels MUST have adequate clearance or be hidden/replaced by an accessible compact marker.

### 9.5 Diagram interaction

- **DIAG-06** Solution Diagram MUST always be available and switch among genuine System, Application, and Component projections.
- **DIAG-07** Every generated architecture diagram MUST support fit/reset, pan, zoom, search/find, focus, upstream/downstream reach, route tracing, export, and full screen when applicable. Generated diagrams larger than the viewport MUST provide an overview map or equivalent orientation aid.
- **DIAG-08** Full screen MUST occupy the available viewport, lock background scroll, close on Escape, refit after transition, trap focus, and restore focus on close.
- **DIAG-09** Diagram controls MUST not hijack normal page scrolling. Pointer, keyboard, and touch interaction MUST be explicit and discoverable.
- **DIAG-10** Diagram selection events MUST publish canonical IDs through the shared selection contract in section 10; renderer-specific identifiers MUST remain internal.
- **DIAG-11** Hover, focus, selection, and route tracing MUST use a non-colour cue. Reduced-motion mode MUST disable ambient and flow animations.
- **DIAG-12** Layout or rendering failure MUST show a concise error and diagnostic action; it MUST NOT leave a blank canvas.

### 9.6 Other diagrams

- **DIAG-13** Other diagrams MUST remain a separate section with one accessible tab list and one visible panel.
- **DIAG-14** Tabs MUST be generated only for applicable authored diagrams and use report-facing titles.
- **DIAG-15** Generated architecture/context views MUST retain their native semantics. Other authored diagrams, including sequence diagrams produced by any external tool, are presentation-only local attachments; Report v2 MUST display validated SVG attachments without parsing, reconstructing, or claiming their internal semantics.
- **DIAG-16** Each generated diagram or attachment viewer MUST preserve its local viewport while its tab remains mounted and MUST offer the shared full-screen contract.
- **DIAG-17** A generated architecture view MAY provide a semantic lens that summarizes visible entities by kind, status, scope, integration type, tag, or owner without changing the underlying projection.
- **DIAG-18** Generated authored architecture views MAY define guided chapters or stories. Guidance MUST remain optional, keyboard operable, and separate from saved architecture data.

## 10. Shared selection and focus

- **SELECT-01** The report MUST have one canonical selected entity/edge ID and one optional focus context.
- **SELECT-02** A System row selects its system; an Application/Component row selects that entity; an Interface row selects its edge and endpoints.
- **SELECT-03** If the selected entity is not visible at the current detail, the diagram MUST select its nearest visible ancestor and identify that projection.
- **SELECT-04** Selecting a diagram element SHOULD scroll/reveal its corresponding grid row without changing scope or roadmap state.
- **SELECT-05** Focus, reach, and route modes MUST be reversible and MUST not mutate the saved architecture or effective system scope.
- **SELECT-06** Selection MUST survive a layout recomputation when the canonical target still exists; otherwise it MUST clear with an explanatory status.

## 11. Look and feel

### 11.1 Visual direction

- **VIS-01** The product MUST combine a readable full-width report of controls, summary counts, grids, and collapsible sections with a crisp technical-diagram language of subtle grids, precise outlines, semantic strokes, and compact monospace metadata.
- **VIS-02** The application MUST provide coordinated dark and light themes. The theme choice MUST apply to the shell, grids, diagrams, exports, dialogs, and Confluence macro and MUST persist locally.
- **VIS-03** The dark theme SHOULD use a deep navy technical canvas, subtle grid, luminous but restrained semantic strokes, high-contrast labels, and outlined panels.
- **VIS-04** The light theme SHOULD use an off-white/slate canvas, faint technical grid, crisp semantic strokes, and the same information hierarchy as dark mode.
- **VIS-05** Diagram headings, IDs, technical metadata, controls, and badges SHOULD use a bundled readable monospace family. Long-form report text and dense grids SHOULD use a bundled readable sans-serif family.
- **VIS-06** Radius, shadow, glow, and gradients MUST be restrained. Glow is reserved for active focus/route/selection rather than ordinary cards.
- **VIS-07** Colour MUST be semantic and consistent across report and diagram. Status, scope, kind, and integration type MUST also have text, pattern, icon, or line-style cues.

### 11.2 Shell and density

- **VIS-08** The report MUST use the full browser width with responsive gutters and no desktop max-width that makes it resemble an embedded dashboard panel.
- **VIS-09** Report library cards, report controls, summary statistics, diagrams, and dialogs MAY use panels. Data grids MUST remain visually flatter and MUST not be nested in multiple cards.
- **VIS-10** Sections MUST have stable numbering and clear expand/collapse controls. Headings, controls, counts, and data MUST form an obvious reading hierarchy.
- **VIS-11** Summary counts MUST be compact and subordinate to the report title and controls.
- **VIS-12** Diagram canvases MUST feel purpose-built: bounded surface, technical grid, integrated legend/toolbar, and clear separation from surrounding report content.
- **VIS-13** The renderer MUST use a small semantic palette resolved from OneTool presentation settings, not hard-coded entity-specific colours.

### 11.3 Responsive behaviour

- **VIS-14** Saved report cards MUST collapse to one column on narrow screens.
- **VIS-15** Header controls, settings, and grid toolbars MUST wrap or stack without becoming unreachable.
- **VIS-16** Summary statistics MUST reduce from four columns to two and then one as space requires.
- **VIS-17** The page MUST have no horizontal overflow. Grids and diagram canvases MAY have contained horizontal navigation where fit/zoom cannot preserve readability.
- **VIS-18** Full-screen diagrams and all primary report actions MUST remain usable on touch-sized viewports.

## 12. Saved reports and exports

- **SAVE-01** Save report MUST open a modal containing report name, a concise capture summary, readable YAML preview, Download YAML, Cancel, and Save.
- **SAVE-02** Saving locally MUST create or update the Reports card and store canonical YAML for offline reuse.
- **SAVE-03** Download MUST produce a portable `.yaml` file using the same validated representation.
- **SAVE-04** Reopening MUST restore durable configuration before data recomputation and report rendering.
- **EXPORT-01** Canonical data plus the renderer-neutral scene/layout result MUST be the authoritative source for core SVG and PNG export and low-priority Draw.io export. A renderer or rasterizer MAY materialize the output, but renderer DOM/runtime state MUST NOT become export data.
- **EXPORT-02** Static image export MUST preserve the active theme, visible legend, semantic labels, and attribution.
- **EXPORT-03** The generated report MUST be assembled from a versioned prebuilt application bundle included in the installed OneTool distribution. Report generation MUST NOT require Node.js, npm, a developer checkout, local `node_modules`, or a per-report frontend build.
- **EXPORT-04** Static exports MUST preserve canonical IDs, hierarchy, edge direction and arrowheads, contextual status, supported node/edge styles, resolved icons and links, labels, and complete non-clipping bounds. Unsupported semantic loss MUST fail with a structured diagnostic before publication.
- **EXPORT-05** Report and export generation MUST stage and validate the complete owned artifact set and ownership manifest before changing the destination. Publication MUST be atomic or provide complete rollback: failure leaves the prior artifact set unchanged, the visible manifest always describes the visible artifacts, and user-owned files are never removed or replaced without explicit force.

## 13. Offline, accessibility, and delivery

### Offline and security

- **OPS-01** The generated application MUST work from `file://` with no network requests.
- **OPS-02** No runtime feature may require a CDN, remote font, telemetry endpoint, or hosted layout service.
- **OPS-03** Generated data inserted into HTML/SVG MUST be escaped and MUST never be interpreted as executable markup.
- **OPS-04** Projection limits MUST prevent accidental unbounded layout. Hard-limit views MUST offer scope/detail reduction rather than attempting an unsafe render.
- **OPS-05** Every authored or attached diagram format declared as supported MUST be rendered locally into its intended visual form. Source text MUST NOT be presented as a successfully rendered diagram.
- **OPS-06** Attached HTML, SVG, or compiled diagram output MUST pass parser-based allowlist validation before embedding. Scripts, event handlers, navigation, active content, external resources, unsafe URLs, CSS imports/URLs, and unsupported markup MUST be rejected with source-located diagnostics; restrictive CSP/sandboxing and per-file/aggregate size limits MUST provide defence in depth.

### Performance and request safety

- **PERF-01** Scope, roadmap, detail, and theme input MUST update visible control state within 100 ms while expensive derivation or layout continues asynchronously.
- **PERF-02** On a documented reference machine, a warning-size layout SHOULD complete within 1 second P95 after its worker is ready. A hard-size diagnostic/overview SHOULD complete within 3 seconds P95.
- **PERF-03** A newer projection or layout request MUST cancel or supersede older work. A stale result MUST never replace the active graph.
- **PERF-04** Projection and layout caches MUST be bounded and keyed by schema version, graph identity, selection, state, detail, theme-affecting dimensions, and layout configuration.
- **PERF-05** Reopening an already cached diagram SHOULD restore usable geometry within 100 ms.
- **PERF-06** Performance tests MUST record worker startup separately from layout duration and MUST report serialized payload and generated artifact size.

### Accessibility

- **A11Y-01** Every control MUST have an accessible name, visible keyboard focus, and an appropriate native or ARIA role.
- **A11Y-02** Report cards, disclosures, dialogs, tabs, tab panels, grids, pagination, full-screen views, and diagram elements MUST be keyboard operable.
- **A11Y-03** Dialogs and full-screen views MUST trap focus while open and restore it on close.
- **A11Y-04** Diagram nodes and selectable edges MUST expose concise accessible labels including entity kind, name, status, and connection direction where applicable.
- **A11Y-05** Status, reach, selection, and edge meaning MUST not depend on colour or motion alone.
- **A11Y-06** The report MUST respect reduced motion, forced colours, and browser text scaling.

### Confluence — low priority

- **CONF-01** Every report MUST be able to produce a static SVG or PNG suitable for attachment and document export.
- **CONF-02** The standalone interactive report MAY be hosted over HTTPS and embedded with a Confluence iframe where framing policy, authentication, and data classification allow it.
- **CONF-03** The preferred Confluence Cloud integration is a Forge Custom UI macro that bundles the same renderer and reads a validated data/report attachment.
- **CONF-04** A Forge macro MUST render a static image representation for PDF/Word export and MUST not execute arbitrary attached HTML.
- **CONF-05** Viewer and data MUST be separable: the viewer is installed/bundled once, while page-specific report data is stored as an attachment.
- **CONF-06** Confluence Data Center SHOULD use a vetted macro/plugin or allowlisted hosted iframe. Raw HTML macros MUST NOT be a required deployment path.
- **CONF-07** Confluence delivery MUST inherit page access controls, MUST NOT transmit report data outside the approved Confluence or explicitly approved hosting boundary, and MUST support an export allowlist or masking policy for sensitive properties and classifications. Static and interactive forms MUST apply the same policy.

## 14. Migration from the current implementation

The stage table is an initial, non-normative sequence expected to evolve as research resolves the implementation. The `MIG-*` requirements below it are normative. Migration is complete only when each selected stage's exit condition is met.

| Stage | Work | Exit condition |
| --- | --- | --- |
| 0. Baseline | Capture current System/Application/Component layouts, metrics, report behaviour, and performance | Repeatable fixture and metric report exists |
| 1. Neutral contracts | Finalize layout input/result, structured diagnostics, and semantic SVG hooks | Contracts cover the browser, SVG, and PNG without LikeC4 types and leave a neutral extension point for later delivery formats |
| 2. Renderer/layout research | Spike renderer and layout candidates independently against neutral contracts and shared fixtures | Decision record selects one renderer and one layout path using section 15 evidence |
| 3. Selected rendering stack | Build the selected renderer/layout modules, themes, interactions, and exports | Multiple independent diagrams work with shared selection and no candidate contract leakage |
| 4. Report shell | Apply the target visual system to the three-screen workflow, grids, save/load, and state transitions | Acceptance scenarios pass offline |
| 5. Remove unselected paths | Delete superseded renderer/layout packages, scripts, payload mappings, tests, and public values | Only the selected production path remains; no compatibility aliases or runtime fallbacks remain |
| 6. Low-priority delivery | Add Draw.io export and package the Confluence static attachment flow and Forge macro using the shared viewer | Draw.io acceptance passes; interactive macro and static document export pass |

- **MIG-01** Migration MUST preserve OneTool YAML/Excel inputs, architecture semantics, scope calculation, roadmap replay, saved-report YAML, and stable IDs.
- **MIG-02** Removal of an unselected or superseded renderer/layout path MUST be clean. Former public values, payload fields, parameters, and config keys MUST fail through current validation rather than act as aliases.
- **MIG-03** Any copied or derived third-party code MUST retain required upstream copyright and licence notices, include applicable licences in distributions, maintain an inventory of derived files, identify the source and pinned upstream revision in source headers or adjacent documentation, and include a user-visible `NOTICE` entry where required.
- **MIG-04** Every selected renderer and layout dependency MUST receive a licence, distribution, maintenance, and security review. Code with incompatible obligations MUST NOT be copied into OneTool merely to avoid a dependency.

## 15. Verification and acceptance

### 15.1 Layout fixture suite

The benchmark suite includes:

- Representative System, Application, and Component scopes containing external actors, a selected core, nested containers, and cross-boundary integrations.
- A 12–20 dependency hub.
- Three hierarchy levels with cross-system component edges.
- A bidirectional cycle.
- A message bus with many publishers and consumers.
- Parallel interfaces and disconnected elements.
- Adjacent roadmap states with about 10% entity change.
- Warning-size and hard-size projections from section 5.

Each candidate is measured for:

- Hard geometry failures from `QUAL-01` and `QUAL-02`.
- Crossings, corridors, border runs, clearance, bends, route stretch, and short segments from `QUAL-03`.
- Aspect ratio and packing efficiency.
- Determinism and roadmap stability.
- Worker duration, serialized size, and main-thread blocking.
- Blind task review: find a dependency, trace one integration path, and identify roadmap change.

A candidate with any `QUAL-01` or `QUAL-02` failure fails the benchmark. For candidates that pass those gates, calculate each count per 100 visible edges and use:

```text
weighted score =
    3 * proper crossings
  + 2 * ambiguous shared corridors
  + 2 * visible label-clearance failures
  + 1 * container-border runs
  + 1 * bends above the suggested maximum
  + 1 * route-stretch excesses
  + 1 * micro-segments
```

An edge is a route-stretch excess when its routed length exceeds the section 5 maximum. A bend or segment count contributes only the amount above its section 5 threshold. Compare candidates on identical projections, dimensions, labels, direction presets, and viewport targets.

### 15.2 Acceptance scenarios

| Scenario | Required coverage |
| --- | --- |
| Open and create reports without reload | `FLOW-01`–`FLOW-09` |
| YAML and Excel replay to equivalent stable architecture states | `INPUT-01`–`INPUT-09`, `DATA-01`–`DATA-09` |
| Renderer and layout choices are evidence-based and contract-neutral | `RESEARCH-01`–`RESEARCH-05`, `LAYOUT-01`–`LAYOUT-03` |
| Validation, report generation, and export share one semantic preparation boundary | `BOUND-01`–`BOUND-06`, `DERIVE-07` |
| Scope changes and selector forms update every dependent view consistently | `DERIVE-01`–`DERIVE-11`, `FLOW-10`–`FLOW-15` |
| Roadmap state explains affected items and change notes | `FLOW-16`, `INPUT-08`, `DATA-07`–`DATA-09` |
| Roadmap changes remain coherent and visually stable | `DATA-07`–`DATA-09`, `LAYOUT-07`–`LAYOUT-09`, `QUAL-06` |
| Grids provide the common and grid-specific behaviour using Community features | `GRID-01`–`GRID-11` |
| System/Application/Component diagrams are readable and materially better than current | `LAYOUT-01`–`LAYOUT-14`, `QUAL-01`–`QUAL-07` |
| Grid and diagram selection stay synchronized | `SELECT-01`–`SELECT-06` |
| The technical light/dark experience is coherent | `VIS-01`–`VIS-18` |
| Saved YAML round-trips durable intent | `DATA-10`–`DATA-13`, `SAVE-01`–`SAVE-04` |
| Core SVG and PNG exports preserve semantics and publish coherently | `BOUND-04`, `DATA-16`, `EXPORT-01`–`EXPORT-05` |
| Standalone report and attachments work safely with networking disabled | `OPS-01`–`OPS-06` |
| Rapid control changes cannot show stale layouts or grow caches without bound | `PERF-01`–`PERF-06` |
| Keyboard, zoom, text scaling, and reduced motion remain usable | `A11Y-01`–`A11Y-06` |
| Draw.io export preserves the neutral graph and export semantics (low priority) | `PRIORITY-02`–`PRIORITY-03`, `DATA-16`, `EXPORT-01`, `EXPORT-04`–`EXPORT-05` |
| Static and interactive Confluence delivery use the shared renderer (low priority) | `PRIORITY-02`–`PRIORITY-03`, `CONF-01`–`CONF-07` |
| Only the selected renderer/layout path remains in production | `OUT-09`, `RESEARCH-04`, `MIG-01`–`MIG-04` |

### 15.3 Requirement traceability

- **TEST-01** Before each Report v2 capability is released, every applicable normative `MUST` requirement ID MUST map to at least one automated production-path test or to a named review gate where automation cannot establish the result. Requirements that apply only to the low-priority extensions in `PRIORITY-02` do not gate the initial core release.
- **TEST-02** The normal project check MUST reject missing, duplicate, stale, skipped, or nonexistent mappings. Merely finding a referenced test name in source text is not sufficient evidence that the requirement is exercised.

## 16. Terminology

| Term | Meaning |
| --- | --- |
| Selected systems | Systems explicitly committed in the scope builder |
| System Scope | Configured interface-hop expansion from selected systems |
| Effective system scope | Selected systems plus reachable systems included by System Scope at the active state |
| Reach | Why an entity is present: Selected or shortest interface-hop distance |
| Boundary interface | Active interface with exactly one endpoint in effective system scope |
| Roadmap state | Baseline or ordered architecture milestone used to resolve model content |
| Projection | Renderer-neutral subset of the resolved model for one report/detail selection |
| Scene/layout result | Neutral node, port, route, label, bounds, and diagnostic geometry |
| Visual aggregation | One visual edge representing multiple canonical interfaces without losing their IDs |
| Saved report | Named YAML configuration that restores user intent and recomputes content |
| Authored diagram | Explicit architecture view or presentation-only local attachment distinct from the generated Solution Diagram; sequence diagrams are externally generated attachments in Report v2 |
| Architecture schema v2 | Existing canonical YAML/Excel workspace format retained by this work |
| Report v1 | Current LikeC4-based generated explorer and export presentation |
| Report v2 | Target report, renderer, layout, export, and Confluence experience |
| ViewGraph | Canonical, renderer-neutral resolved graph produced by OneTool for one normalized selection |
| Focus context | Reversible inspection state used to emphasize a selected neighbourhood or route without changing scope |
| Comparison | Structured difference between resolved states used for status and roadmap explanation |
| Tombstone | Minimal identity retained for an entity removed from an explicit transition/comparison view |
| Route stretch | Routed edge length divided by the Manhattan distance between its endpoints |
| Boundary stub | Compact labelled diagram endpoint representing an interface that leaves effective scope without adding the outside system |

## 17. Non-normative provenance

These references explain where the Report v2 direction came from. They are not required to interpret, implement, or accept this specification.

- Interaction mock: `arch-v3-wip/mocks.html`
- Representative Excel architecture and roadmap data: `arch-v3-wip/acme-arch-v2.xlsx`
- Current neutral boundary: `dev/project/arch/solution-renderer-boundary.md`
- Current renderer contract: `src/otdev/tools/_arch/frontend/src/solution/renderer/types.ts`
- Archify source review: `scratch/archify` at commit `5875dc81b5c77c7004d7c1d297dda470fce97f50`
- Archify composition checks: `scratch/archify/archify/scripts/check-render-output.mjs`
- Attribution policy: `dev/project/guides/attribution.md`
