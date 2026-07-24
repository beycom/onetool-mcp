# Solution on a Page — Design Requirements

## 1. Purpose

Generate a compact, clean, interactive Solution on a Page (SoaP) architecture
report from the resolved architecture model. The page starts with data tables
that define and explain the active scope, followed by the diagrams generated
from that same scope.

The SoaP is a report first and an explorer second. It must be readable from top
to bottom, while still supporting selection, filtering, synchronized diagram
highlighting, pan/zoom, and full-screen diagram inspection.

## 2. Page Structure

The default section order is fixed:

1. Systems
2. Applications
3. Interfaces
4. Diagrams

Every section can be independently collapsed and reopened. The page may also
provide a compact section navigator, but navigation must not replace or reorder
the report sections.

The Systems, Applications, and Interfaces sections use AG Grid and provide
consistent search, filtering, sorting, multi-sort, column
resizing/reordering, column visibility, keyboard navigation, and selection.
The Diagrams section does not use a table or catalog grid.

Tables remain in full-width page sections. They are not moved into dashboard
sidebars, permanent rails, or split-screen panels. Layout alternatives may
change section navigation, density, or disclosure, but preserve the ordered
page-section reading model.

The report uses the full available browser width and responds continuously to
viewport changes. Responsive gutters may change by breakpoint, but no desktop
max-width may make the report look like a narrow embedded panel.

The document uses normal browser page scrolling. The complete report must not
be placed inside a fixed-height, nested scrolling workspace. AG Grid row and
column viewports may scroll inside their owning page sections.

The Diagrams section contains:

1. The generated **Solution Design** as the first, largest, and permanently
   present diagram.
2. An optional secondary diagram region beneath it. Tabs switch between
   applicable sequence, integration, transition, and other diagrams.

Every diagram can be opened in a full-screen presentation.

## 3. Global Controls

The page starts with a report title. A clean, consistent control row appears
directly under the title and contains exactly:

- View
- System Scope

### 3.1 System scope

System scope originates from checked rows in the Systems grid. Checked systems
are called **selected systems**.

The generated report may restore an initial selection from generated defaults
or fragment state. Changing the checked systems updates the Applications,
Interfaces, and Diagrams sections without reloading the page.

### 3.2 System Scope

**System Scope** controls the number of interface hops included from the
checked systems.

Help text:

> Include systems up to this many interface hops from the selected systems.

Values:

- Selected systems only
- Selected + 1 interface hop
- Selected + 2 interface hops
- Selected + 3 interface hops

The **effective system scope** is the selected systems plus systems reachable
within the chosen number of interface hops.

The page distinguishes:

- Selected systems
- Systems included at 1 hop
- Systems included at 2 hops
- Systems included at 3 hops

Reach is structural and based on interfaces, not generic relationships.

### 3.3 Views

Users can save the current SoaP as a named **Saved View** and reload it later.

A Saved View captures:

- Stable IDs of checked systems
- System Scope in interface hops
- Applications or Applications + Components mode
- AG Grid filter, sort, column order, column width, visibility, pinning, page,
  and density state for the three grid sections
- Open or collapsed report sections
- Active optional diagram tab
- Current highlighted entity or interface
- Applicable diagram pan and zoom state where practical

The View control provides:

- A searchable View selector
- Save as new view
- Update current view
- Rename view
- Delete view with confirmation or undo
- Reset to the generated default view

Saved Views work offline and are persisted in YAML. The browser can retain
personal views locally, and every view config can be exported and imported as a
portable `.yaml` file so the configuration is not locked to one browser
profile.

The YAML is the canonical persisted representation, not a generated JSON cache.
It uses stable grid and column IDs and retains column order explicitly.

Example shape:

```yaml
view:
  id: core-commerce-cutover
  name: Core commerce cutover
  selected_systems:
    - commerce-platform
    - commerce-edge
  system_scope_hops: 1
  active_diagram: place-order-sequence
  application_grid_mode: applications_and_components
  grids:
    systems:
      column_order: [select, system, groups, tags, status, owner]
      hidden_columns: [owner]
      widths:
        system: 240
        groups: 180
      sort:
        - column: system
          direction: asc
      filters: {}
```

Equivalent grid entries are retained for Applications and Interfaces.

Reloading a Saved View validates stable IDs against the active generated
architecture. Missing or inapplicable IDs are reported clearly; they are not
silently replaced with similarly named entities.

## 4. Systems Section

The Systems section uses AG Grid and displays all systems available at the
active roadmap state.

Required behavior:

- Checkbox selection is enabled on every system row.
- A header checkbox selects or clears all currently filtered rows.
- Checkbox state defines the selected systems.
- Search, filtering, sorting, column resizing, and keyboard navigation remain
  available.
- The grid remains compact and does not use decorative whole-row status fills.
- The grid displays at most 10 rows per page.
- Additional systems use AG Grid pagination, not vertical row scrolling.

Required columns:

- Select
- System
- System groups
- Tags
- Status

Recommended optional columns:

- Owner
- Lifecycle
- Related changes

System groups and tags support multiple values and remain searchable/filterable.

## 5. Applications Section

The Applications section uses AG Grid and derives its rows from the effective
system scope.

The grid displays at most 20 rows per page. Additional applications or
components use AG Grid pagination, not vertical row scrolling.

Required columns:

- Application
- System
- Reach
- Status
- Tags

The **Reach** column displays:

- Selected
- 1 hop
- 2 hops
- 3 hops

The section has a two-state view switch:

- Applications
- Applications + Components

In Applications mode, each row represents an application.

In Applications + Components mode, application and component rows are both
visible. The grid must expose entity kind and parent application without
depending on AG Grid Enterprise-only behavior. A flat, indented, or otherwise
Community-compatible presentation is acceptable.

Selecting an application or component highlights it in every compatible
diagram. If a diagram cannot display the selected entity, its nearest visible
containing application or system is highlighted.

## 6. Interfaces Section

The Interfaces section uses AG Grid.

The grid displays at most 20 rows per page. Additional interfaces use AG Grid
pagination, not vertical row scrolling.

It lists:

- Interfaces whose source and target systems are both in the effective system
  scope.
- Boundary interfaces leaving the effective system scope, clearly marked as
  boundary interfaces without silently adding the outside system to the
  diagram.

Required columns:

- Interface
- Source system
- Source application or container
- Target system
- Target application or container
- Direction
- Integration type
- Reach or scope
- Status

Selecting an interface highlights its diagram edge and both visible endpoints.
Selecting a merged diagram edge identifies every canonical interface
represented by that edge.

## 7. Diagrams Section

### 7.1 Solution Design

The generated Solution Design is the first and largest diagram. It is always
present and is not one of the optional diagram tabs.

It displays:

- Every effective-scope system and the application or container detail required
  by the active View.
- Interfaces between effective-scope systems.
- Accessible status and reach cues that do not depend on color alone.

Required interactions:

- Pan
- Zoom in and out
- Fit to view
- Reset view
- Full-screen pop-out
- Select a node or edge

The default embedded diagram must be large enough to use without entering
full-screen mode.

### 7.2 Selection synchronization

Selection is shared across tables and diagrams:

- Selecting a System grid row highlights the system in diagrams.
- Selecting an Application or Component grid row highlights that entity or its
  nearest visible container.
- Selecting an Interface grid row highlights the edge and endpoints.
- Selecting a diagram node or edge selects and reveals the corresponding grid
  row where practical.

Changing system checkboxes changes scope. Selecting a row only changes the
current highlight; it does not change scope.

### 7.3 Additional diagrams

One optional diagram region follows the Solution Design. A tab list switches
the region between applicable diagrams, including:

- Sequence diagrams
- Context or integration diagrams
- Roadmap or transition diagrams
- Authored LikeC4 views
- Portable attached diagrams

Each optional diagram:

- Has a descriptive title and type.
- Can be opened full-screen.
- Retains its own pan/zoom state where supported.
- Uses the shared selected entity or interface when it can represent it.

## 8. Section Visibility and Persistence

Users can:

- Collapse or reopen each report section.
- Switch the active optional diagram tab.

The page should remember:

- Checked systems
- System Scope in interface hops
- Applications grid mode
- Open or collapsed sections
- Active optional diagram tab
- Current selected entity or interface

State must remain fragment-safe and usable in the standalone offline report.
Named Saved Views persist and restore this state as described in section 3.3.

## 9. Layout and Visual Design

The page is compact and clean:

- Dense but readable AG Grid tables.
- Flat presentation with restrained separators, minimal borders, no bevels, and
  no unnecessary cards.
- Clear section hierarchy.
- A title followed by the View and System Scope controls.
- Minimal permanent side panels.
- No unexplained renderer-owned action buttons or colored tag bars.
- Red is reserved for errors, destructive actions, and explicitly removed
  architecture content.
- Selection, reach, and status always have non-color cues.

At narrow widths:

- Sections remain in the same logical order.
- Grids can scroll within their section without overflowing the page.
- The report remains full-width with responsive page gutters.
- Diagram controls remain reachable.
- Full-screen diagrams remain usable.

## 10. Offline and Accessibility Requirements

- The generated page works from `file://` with no network requests.
- AG Grid Community and all diagram runtime assets are bundled locally.
- Saved View YAML import, export, save, and reload work without a server.
- Every control has an accessible name.
- Icon-only controls have tooltips or equivalent labels.
- Section and diagram disclosure uses native button semantics.
- Keyboard focus is visible.
- Grid and diagram selection do not depend on pointer input or color alone.
- Full-screen pop-outs trap and restore focus correctly.

## 11. Acceptance Criteria

1. Checking two systems in the Systems grid and selecting the one-hop System
   Scope updates the
   Applications and Interfaces grids and the Solution Design to the same
   effective system scope.
2. Every Applications grid row identifies its owning System and Reach.
3. Switching to Applications + Components adds component rows without losing
   sorting, filtering, or the current selection.
4. Selecting a system, application/component, or interface row visibly
   highlights the corresponding diagram element.
5. The embedded Solution Design supports pan, zoom, fit, reset, and full-screen
   pop-out.
6. The Solution Design is always present; tabs switch the optional diagram
   region beneath it and each optional diagram can open full-screen.
7. Systems shows no more than 10 rows per page; Applications and Interfaces
   show no more than 20 rows per page; additional rows use pagination rather
   than vertical grid scrolling.
8. Every report section can be collapsed and restored.
9. Restoring a copied fragment reopens the same scope, grid mode, section
   visibility, active optional diagram, and selection offline.
10. Saving a named view, changing the scope and grid layouts, and reloading the
    saved view restores the checked systems and complete report configuration.
11. The Diagrams section contains no table or catalog grid.
12. Desktop and narrow browser tests show no section overlay, unreachable
    controls, page-level horizontal overflow, or unexplained red node controls.

## 12. Terminology

| Term | Meaning |
| --- | --- |
| Selected systems | Systems checked in the Systems grid |
| System Scope | Selected systems plus the configured number of interface hops |
| Effective system scope | Selected systems plus systems included by System Scope |
| Reach | Why an application or system is present: Selected, 1 hop, 2 hops, or 3 hops |
| Row selection | Current highlighted system, application/component, or interface |
| Scope selection | Checked System rows that drive report content |
