# Architecture report UI direction

## Status and inputs

Confirmed on 2026-08-27. This file is the agreed product direction for the
Phase 3 report UI. It supersedes conflicting visual and interaction guidance
in earlier artboards and issue notes. Update the report and sequence contracts
to match it before implementation.

Inputs:

- `plans/arch/arch-v3/ui-polish.md`
- the `designs/` artboards and published design canvas (directory removed
  2026-08-27 — this document captures the decisions; files in git history)
- `plans/arch/arch-v3/issues/`
- `plans/arch/arch-v3/report.md`
- `plans/arch/arch-v3/sequence.md`
- the selected-node behavior in the supplied IcePanel diagram

The report and sequence contracts still define data and execution behavior.
The follow-up must reconcile their UI sections with this direction.

## Product priority

The first pass is a read-only architecture workbench. Optimize it for
tracing relationships, understanding containment, inspecting metadata,
following sequences, and comparing stages. Editing and diagram authoring are
later work.

Support light theme and viewports down to 1024 x 720. Keep the report a
single self-contained HTML file with zero external requests under `file://`.

## App shell

Option E supplies the app shell only. The Canvas uses the calmer Gallery and
IcePanel visual language.

| Region | Purpose | Default |
| --- | --- | --- |
| Header | Model identity and global search | Visible and compact |
| View, left | Diagram selection and view controls | Open |
| Info, right | Inspector for the current selection | Collapsed until selection |
| Data, bottom | Tables and message payloads | Collapsed |
| Canvas | Active diagram | Canvas view |

The View, Info, and Data docks reserve layout space. Each dock is resizable
and collapsible. Side docks collapse into attached rails and Data collapses
into a full-width bottom bar. Double-clicking a resize handle restores the
default size. The browser remembers sizes and collapsed state locally, but
shared links do not include pixel geometry.

At 1024 px, opening Info collapses View to its rail. During a guided story,
opening Info pauses playback, collapses View, and leaves an active-story
indicator on the rail. Closing Info restores View and the current story step.

Opening, closing, or resizing a dock preserves zoom and shifts the camera
only enough to keep the current focus visible. It does not run a full Fit.

The hard layout rule is docked by default. The only Canvas overlay is the
fixed lower-left Map, Fit, and Zoom cluster with its optional minimap.
Temporary menus, tooltips, and global search may float while active.

## Header

Keep the header short. It contains the OneTool identity, model name, and a
compact global search trigger with the `Cmd/Ctrl+K` shortcut.

Global search covers diagrams, entities, interfaces, and sequence messages.
Choosing a diagram opens it. Choosing a model item switches to Canvas when
needed, centers and selects the item, and opens Info.

The header does not contain theme, fullscreen, Share, view state, selection
actions, or panel controls. Copy view link belongs at the bottom of View.

## View dock

The dock title is **View**. It contains both diagram selection and the
controls that change the active diagram.

The diagram list is grouped and collapsible:

- Architecture contains Canvas, which is the default.
- Sequences contains each named authored sequence.
- Future authored diagram types get their own groups.

Add search inside this list only when its size warrants it. Dependencies is
not a general list item because it requires a focused entity.

Canvas controls appear in this order:

1. Diagram
2. Detail
3. Stage
4. Relationship
5. Tags
6. Guided views, when present
7. Copy view link

Hide controls that have no meaningful choice. Examples include Stage with
only Base, Tags with no tags, and Guided views with no authored guides.

### Detail

Detail is a dropdown for System, Subsystem, Container, and Component
(level model renamed 2026-08-28: Subsystem — a logical grouping of
related containers — replaces the former container-in-container "Child
Containers" level; the Subsystem option is hidden when the model
defines no subsystems).
Boxes with children also have a small persistent drill affordance. Drilling
changes focus and adds a breadcrumb. It does not expand children in place.

### Stage

Stage is a dropdown of named architecture stages. Selecting a stage updates
Canvas, Data, counts, and Info together. Additions, removals, and changes are
relative to the previous stage. Do not restore the timeline slider or a
separate Compare control.

### Relationship

Relationship is a dropdown for Calls, Data flow, and Ownership. Calls is the
default. Arrow direction, selection animation, and incoming or outgoing
grouping follow the selected relationship. Switching relationship does not
move boxes.

### Tags

Tags is the only lens in the first pass. Selecting a tag brightens matches
and dims nonmatches without hiding boxes or changing layout. Technology and
Status lenses are deferred.

### Guided stories

Guided stories are temporary presentation state applied to the active
diagram, but their controls live in View rather than over the Canvas. While
active, the top of View shows the title, caption, progress, Previous,
Play or Pause, Next, and Exit. Exiting restores the exact previous diagram
and controls.

## Data dock

The bottom dock is named **Data** because it contains tables and payload
files. It spans the full application width beneath View, Canvas, and Info.

Its default tabs are Entities, Interfaces, Milestones, and Diff. Tables
support sort, search, filters, column configuration, and locally persisted
layouts. Auto-size populated columns, collapse all-empty optional columns by
default, and never truncate headers.

Selecting a row opens the item in Info. If the item is present in the active
diagram, highlight it there. If it is absent, offer Show on Canvas rather
than changing views without consent. Diagram selection selects the matching
row when its table is open.

Linked request, response, JSON, XML, and CSV files open in a Payload tab.
Info lists the files, while Data provides the full-width read-only viewer.
When both request and response exist, show them as sub-tabs. Preserve the
source text and line endings. Provide syntax highlighting, line numbers,
search, wrap, copy, and download. Do not silently reformat files or convert
CSV into a grid.

Architecture interfaces and sequence messages use the same attachment flow.

## Info dock

Info is one adaptive inspector for Canvas entities, containment boundaries,
interfaces, splines, sequence participants, and sequence messages. It opens
on selection and replaces its content in place when selection changes.

Entity Info has Details and Connections. Stage changes appear as a concise
section in Details rather than a separate Changes tab. Interfaces and
messages add Attachments only when files exist. Never render irrelevant or
empty tabs.

Connections splits rows into Incoming and Outgoing under the active
Relationship. Each row names the other endpoint. Selecting a row selects the
spline and keeps Info open. Info provides an internal Back action to return
to the entity.

Dependencies opens from a selected entity through View dependencies. The
dependency diagram places the focus in the center, incoming dependencies on
the left, and outgoing dependencies on the right. Selecting a neighboring
box opens Info. A separate Focus dependencies here action recenters the
view. App or browser Back returns to the previous diagram and selection.

Single-click always selects. Do not show a floating selection toolbar.

## Canvas visual language

Use a light, near-white, plain background. Do not render a hatch or visible
grid. Use neutral cards and chrome with one OneTool teal accent for active
controls, links, selection, and emphasized splines. Tag, lifecycle, and diff
colors stay in pills or narrow indicators rather than full-card fills.

Use readable sans-serif typography for names and prose. Reserve monospace
for IDs, numeric values, and technical metadata.

### Cards

Cards are larger, text-led, and use one rounded rectangular shape for actors,
systems, containers, and components. Do not show vendor logos, generic entity
icons, or kind-specific card shapes. Use pills for kind and high-value facts.

At Read and Full, a card contains:

- parent or kind context
- full name
- one or two description lines
- at most three high-value fact pills
- a child or connection count when relevant

Use a consistent size tier per Detail level. Wrap long names to two lines.
Only after two lines may a name truncate, with the full value available on
hover and in Info. Do not widen one card enough to distort layout.

Semantic zoom has three levels:

- Far shows kind and full name.
- Read adds description and key pills.
- Full shows all approved card details and neutral edge labels.

Initial framing fits the whole graph only when it stays at Read. Otherwise it
caps at Read, centers the graph, and relies on Map for offscreen context. The
explicit Fit action may show the entire graph at Far.

### Containment and interfaces

At Container and Component detail, parent systems and containers render as
subtle tinted boundaries with clear headers. Boundaries are selectable but
do not expand or collapse in place.

Interfaces render as small labeled ports attached to the owning card or
containment boundary where a spline connects. Never render detached empty
interface boxes.

### Splines

Splines are the only architecture edge style. Neutral splines use restrained
contrast. Selected splines gain weight and the selection accent. Anchors
distribute around card borders, routes avoid card and boundary interiors,
and parallel paths remain visually separated.

Connections with the same endpoints and direction aggregate into one spline
with a count chip. Connections in both directions render as two separated
splines so each direction remains selectable and animatable.

Selected or hovered spline labels appear at every zoom. Neutral labels appear
only at Full.

### Selection

Selection follows the supplied IcePanel reference and stops at one hop:

- the selected card gets the strongest accent border
- direct outgoing splines use the accent and animate in their direction
- direct incoming splines use the same accent without animation
- direct neighbor cards brighten
- unrelated cards and splines dim but remain readable
- arrowheads retain direction without relying on motion

One accent color covers both directions. Motion is the extra outbound cue.
Under `prefers-reduced-motion`, use static emphasized splines for both.

When Info opens, preserve zoom and pan only enough to keep the selection and
its direct neighborhood visible. Refit only when that neighborhood cannot
fit.

Emphasis priority is:

1. selection and its one-hop neighborhood
2. the active guided-story stop
3. tag emphasis
4. neutral content

Stage changes use pills and narrow border markers rather than opacity, so
they remain visible under every emphasis mode.

### Map, Fit, and Zoom

Keep one fixed horizontal control row at the lower left:

`Map | Fit | minus | percentage and semantic level | plus`

Map toggles the minimap, which attaches directly above the row and remains
closed by default. The semantic label is Far, Read, or Full. Controls never
move as values change.

Remove the status bar. Show a temporary Laying out indicator beside these
controls only while layout work is active.

## Sequence diagrams

When a sequence is active, View contains the sequence picker, Scenario,
local search, compact playback, and participant controls. It replaces the
current floating participant navigator and header entry.

Scenario is a dropdown. With one scenario, show its name without an active
control. Scenario changes preserve participant focus and visibility when the
same participants remain.

The compact playback row contains Previous, Play or Pause, Next, and the
current step count. Put First, Last, and speed in an overflow menu or keyboard
shortcuts. The active message and its two participants have full emphasis,
and the sequence scrolls to keep that message visible.

Local sequence search lives in View and uses `Cmd/Ctrl+F`. It searches
message text, participant names, IDs, and linked interfaces, with match count
and previous or next controls. Global search remains `Cmd/Ctrl+K`.

Participant headers remain sticky during vertical scrolling. Horizontal
scroll keeps headers, lifelines, and messages aligned. Each participant is
an individual lifeline. Show containment as muted parent context in its
header and Info only.

Remove C4 group bands, collapsed groups, merged lifelines, retargeted group
messages, and group self-loop aggregation.

Participants can be hidden through an explicit eye control in View. Hiding
removes the lifeline and converts affected message runs to gap markers.
Participant Focus is separate and compresses unrelated messages without
hiding the focused lifeline.

The shared Map control opens a vertical sequence overview with message ticks,
the current step, search matches, and a draggable viewport.

## Interaction and shared links

Escape closes the topmost temporary UI first, then clears selection and
closes Info, then exits an active guided story. It does not collapse docks or
leave Dependencies. App or browser Back handles view navigation.

Copy view link preserves:

- active diagram
- Detail, Stage, Relationship, and tag emphasis
- drill or dependency focus
- sequence scenario, step, focus, and hidden participants
- guided-story step
- current selection

It excludes pan, zoom, dock geometry, collapsed state, searches, open menus,
and Data table layout.

## Deferred or removed

The first pass does not include:

- dark theme or a theme toggle
- application fullscreen
- Share in the header
- a Changes diagram view
- a Changes tab in Info
- saved report creation or management
- manual card positioning
- scope or hop controls in the viewer
- Technology or Status lenses
- vendor logos or generic entity icons
- floating selection, legend, participant, or guided-story panels
- sequence C4 grouping and group collapse
- viewports below 1024 x 720

## Acceptance checks

Verify the direction at 1440 x 900 and 1024 x 720 under `file://`:

- zero external requests and a clean console
- all docks resize, collapse, restore, and preserve camera intent
- opening Info never hides the selected item
- View auto-collapses at 1024 when Info opens
- large cards remain readable at initial framing
- spline direction, labels, anchors, aggregation, and hit targets are clear
- one-hop selection matches the IcePanel behavior
- reduced-motion selection is fully understandable
- Data tables do not waste width on empty columns
- Payload renders JSON, XML, and CSV source without reformatting
- sequence headers stay aligned while scrolling
- sequence search, playback, focus, hide, and Map remain in View
- every interaction works without floating panels over diagram content

## Follow-up

Reconcile this direction into the contract and planning files before code
changes:

1. Update `plans/arch/arch-v3/ui-polish.md` and its D13 pass ownership.
2. Update the shell, view, panel, selection, responsive, and deferred sections
   in `plans/arch/arch-v3/report.md`.
3. Update the SEQ interaction contract in
   `plans/arch/arch-v3/sequence.md`, including removal of group bands.
4. Update `plans/arch/arch-v3/plan.md` and delivery prompts to reflect the
   1024 px floor and the scope cuts.
5. Resolved by removal (2026-08-27): the `designs/` directory — including
   the Option E artboard with its rejected choices (icons, a selection
   toolbar, bottom-right controls, dark-theme controls, permanent sequence
   grouping) — is deleted. This document is the sole design source; the
   artboards remain in git history.
6. Run an architect review for conflicts with payload, URL-fragment, and test
   contracts before implementation begins.

## Design tuning

Pixel sizes, animation timing, and exact color tokens remain design-tuning
work, done against the implementation at 1440 x 900 and 1024 x 720 without
changing the behavior above.
