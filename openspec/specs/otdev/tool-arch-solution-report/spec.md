# tool-arch-solution-report Specification

## Purpose

Defines the presentation contract for the `arch` tool's generated solution report: change-type visualization, cross-page navigation and cross-links, clickable diagram nodes, interaction-type styling with explicit visual-channel separation, diagram legends, index summary cards, and global searchable entity tables. This capability is layered on top of the model-derived render context defined by `tool-arch-model-centric-rendering`.

## Requirements

### Requirement: Project change-type visualization
Project pages SHALL visually distinguish `project_scope.change_type` values in both stage diagrams and the scope table, using one dedicated style per enum value (`new`, `changed`, `removed`, `impacted`, `dependency`) and neutral default styling for `existing`.

#### Scenario: Scoped node styled by change type
- **WHEN** a project stage diagram renders a system, app, or component whose scope row for that stage has `change_type` of `new`, `changed`, `removed`, `impacted`, or `dependency`
- **THEN** the node SHALL carry the D2 class corresponding to that change type
- **AND** each of the five change types SHALL be visually distinct from the others and from unscoped/neutral styling

#### Scenario: Scoped interface styled by change type
- **WHEN** a project stage diagram renders an interface whose scope row for that stage has a non-`existing` change type
- **THEN** the edge SHALL carry the D2 class corresponding to that change type

#### Scenario: Existing items keep neutral styling
- **WHEN** a scope row has `change_type` of `existing`, or a rendered item has no scope row for the current stage
- **THEN** the node or edge SHALL render with the same styling used before this capability existed

#### Scenario: Change type varies by stage
- **WHEN** the same item appears in multiple stages with different `change_type` values
- **THEN** each stage diagram SHALL style the item according to that stage's scope row

#### Scenario: Scope table change-type badge
- **WHEN** a project page scope table renders the `change_type` column
- **THEN** each cell SHALL render as a colored badge whose color matches the diagram styling for that change type

### Requirement: Cross-page navigation
Every generated system and project page SHALL link back to the solution index, system pages SHALL list the projects that scope them, and project scope tables SHALL link items to their owning system page.

#### Scenario: Back link to index
- **WHEN** any system or project page is generated
- **THEN** the page header SHALL contain a link to `index.html`

#### Scenario: System page lists related projects
- **WHEN** a system page is generated and at least one `project_scope` row references that system or any of its apps or components
- **THEN** the system page SHALL show a "Projects" section listing each such project with a link to its project page

#### Scenario: System page with no related projects
- **WHEN** no `project_scope` row references a system or its apps/components
- **THEN** the system page SHALL omit the "Projects" section entirely

#### Scenario: Scope table links items to system pages
- **WHEN** a project scope table row's `item_id` resolves to a system, or to an app or component owned by a system
- **THEN** the item cell SHALL link to that system's HTML page

#### Scenario: Unresolvable scope item has no link
- **WHEN** a scope row's `item_id` does not resolve to an entity with a generated page (e.g. an interface or user)
- **THEN** the cell SHALL render as plain text without a link

### Requirement: Clickable diagram nodes
D2 diagram nodes representing systems, apps, and components SHALL carry `link` attributes targeting the owning system's HTML page, using relative URLs, so that generated SVGs navigate on click.

#### Scenario: System node links to system page
- **WHEN** a diagram renders a node for a system that has a generated system page
- **THEN** the node SHALL carry a D2 `link` attribute with the relative URL of that system page

#### Scenario: App and component nodes link to owning system page
- **WHEN** a diagram renders an app or component node
- **THEN** the node SHALL link to the HTML page of the system that owns it

#### Scenario: Unknown endpoints have no link
- **WHEN** a diagram renders a node synthesized from an unresolved interface endpoint (an id not present in any entity sheet)
- **THEN** the node SHALL NOT carry a `link` attribute

#### Scenario: Links survive inlining and panzoom
- **WHEN** a diagram SVG containing links is inlined into a generated HTML page
- **THEN** clicking a linked node SHALL navigate to the target page
- **AND** dragging to pan the diagram SHALL NOT trigger navigation

### Requirement: Interface interaction-type styling
Diagram edges SHALL express `interaction_type` through a stroke-pattern channel that is independent of the existing focus-direction color channel, with a neutral fallback for absent or unrecognized values.

#### Scenario: Known interaction types are visually distinct
- **WHEN** an interface has an `interaction_type` matching a recognized value (`api`, `event`, `queue`, `batch`, `file`, `pubsub`, case-insensitive)
- **THEN** the edge SHALL render with the stroke pattern assigned to that value
- **AND** stroke patterns SHALL differ between recognized values

#### Scenario: Direction color channel is preserved
- **WHEN** an interface with a recognized `interaction_type` is rendered on a system diagram where focus-direction coloring applies
- **THEN** the edge SHALL simultaneously show its focus-direction color (`Interface` / `InterfaceFromFocus` / `InterfaceToFocus`) and its interaction-type stroke pattern

#### Scenario: Unrecognized or missing interaction type falls back
- **WHEN** an interface has no `interaction_type`, or a value outside the recognized set
- **THEN** the edge SHALL render with the neutral (solid) stroke used before this capability existed
- **AND** generation SHALL NOT fail because of the unrecognized value

#### Scenario: Interfaces table shows interaction type badge
- **WHEN** a system page interfaces table renders the `interaction_type` column
- **THEN** recognized values SHALL render as badges and unrecognized values as plain text

### Requirement: Diagram legend
Generated pages that contain diagrams SHALL include a legend explaining node classes, focus-direction edge colors, interaction-type stroke patterns, and — on project pages — change-type styling.

#### Scenario: System page legend
- **WHEN** a system page is generated
- **THEN** it SHALL include a collapsible legend describing node classes (person, external system, system, app, component types) and edge styling (direction colors, interaction-type stroke patterns)

#### Scenario: Project page legend includes change types
- **WHEN** a project page is generated
- **THEN** its legend SHALL additionally describe the change-type styles (`new`, `changed`, `removed`, `impacted`, `dependency`)

### Requirement: Index summary cards
The solution index SHALL display aggregate count cards derived from model entities.

#### Scenario: Summary cards rendered
- **WHEN** the solution index is generated from a model containing entities
- **THEN** it SHALL show counts of systems by system type, projects by status, and interfaces by interaction type, plus total counts for systems, apps, components, interfaces, and projects

#### Scenario: Empty groups omitted
- **WHEN** an aggregation group has zero members (e.g. no projects exist)
- **THEN** the corresponding card or breakdown SHALL be omitted rather than rendered with zero

### Requirement: Global entity tables on index
The solution index SHALL include searchable tables listing all systems, apps, components, interfaces, and projects with links to their pages.

#### Scenario: Entity tables rendered
- **WHEN** the solution index is generated
- **THEN** it SHALL contain one table per entity kind (systems, apps, components, interfaces, projects) populated from model entities, each in a collapsible section

#### Scenario: Table rows link to pages
- **WHEN** a table row represents a system, an app/component owned by a system, or a project
- **THEN** the row SHALL contain a link to the corresponding system or project HTML page

#### Scenario: Tables are filterable
- **WHEN** a user types into a table's search input or uses column filters
- **THEN** rows SHALL filter client-side without a page reload
