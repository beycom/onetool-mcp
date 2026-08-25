# Report v2 interaction requirements

Status: **SUPERSEDED** (2026-08-24). The useful clauses were mined into
`plans/arch/arch-v3/report.md` "Wave-2 UI contract — Interaction baseline",
which also records the overrides where v3 issue text or decisions won over
this contract. Kept for reference only; do not implement from this file.

This document expands the interaction requirements in `requirements.md` and the
navigation design in `design.md` into implementation-ready behaviour. It takes
the useful exploration patterns from Archify and LikeC4 without adopting either
application's domain model, persisted state, or monolithic viewer.

If this document conflicts with `requirements.md`, `requirements.md` wins until
the conflict is resolved explicitly. `MUST`, `SHOULD`, and `MAY` have their
ordinary normative meanings.

## 1. Product boundary

- **INT-BOUND-01** Interaction MUST remain inside one active report and its
  effective scope. Navigation MUST NOT silently add systems or widen scope.
- **INT-BOUND-02** Generated diagrams are read-only architecture views. Nodes,
  containers, ports, relationships, and layout geometry MUST NOT be manually
  repositioned or edited. Attached diagrams remain opaque presentation assets.
- **INT-BOUND-03** User-movable passports and probes are viewer chrome, not
  diagram geometry. Their position MUST NOT affect layout, export geometry, or
  saved architecture data.
- **INT-BOUND-04** The report is not a general model browser. Drill-down and
  authored navigation MUST resolve only to applicable projections or diagrams
  already available to the active report.
- **INT-BOUND-05** Every interaction MUST use canonical OneTool IDs. Renderer
  IDs, DOM indexes, display names, and geometry MUST NOT become navigation
  identity.
- **INT-BOUND-06** Generated architecture diagrams and presentation-only
  attachments MUST share a consistent outer frame and viewport controls.
  Canonical selection, semantic inspection, and graph navigation apply only to
  generated architecture diagrams.
- **INT-BOUND-07** Every interaction MUST work offline from `file://` without a
  network request, hosted service, telemetry call, or remote asset.

## 2. Interaction state model

Interaction state is divided by ownership and lifetime:

| State | Examples | Lifetime |
| --- | --- | --- |
| Durable report intent | Scope, state, detail, theme, sections, grids | Saved report YAML |
| Shared inspection | Canonical selection, focus, reach, route | Current report runtime |
| Per-diagram view | Camera, search, history, radar, panels | While the instance is mounted |
| URL-share state | Report, view, selection, mode, route | Validated URL fragment |
| Ephemeral state | Hover, menus, dragging, timers, notices | Until dismissed or superseded |

- **INT-STATE-01** One action MUST produce one coherent state transition. Scope,
  roadmap, detail, layout, counts, grids, selection, and diagram controls MUST
  never show a mixture of old and new state.
- **INT-STATE-02** Selection MUST be shared across grids and generated
  architecture diagrams. Pan, zoom, search position, radar state, and
  floating-panel position MUST remain local to one diagram instance.
- **INT-STATE-03** Transient viewer state MUST NOT be written to saved report
  YAML. URL-share state MUST be parsed separately from durable report intent.
- **INT-STATE-04** Switching a mounted tab MUST preserve its applicable local
  viewport, search result, and navigation history.
- **INT-STATE-05** A recomputed layout MUST retain selection and applicable
  transient modes by canonical ID. Invalid state MUST clear with an explanatory
  status rather than substitute another entity by name.
- **INT-STATE-06** A newer projection or layout request MUST supersede older
  work. A stale result MUST NOT move the camera, restore an obsolete selection,
  or reopen dismissed viewer chrome.
- **INT-STATE-07** Changing scope or roadmap state MUST pause playback and
  reconcile focus, routes, search results, history, and selection before
  publishing the new scene.

## 3. Application and report navigation

- **INT-APP-01** The application MUST expose three mutually exclusive screens:
  Reports, Create/Edit Scope, and Report.
- **INT-APP-02** Opening a report card MUST restore durable report intent,
  resolve it against current generated data, and enter Report without a page
  reload.
- **INT-APP-03** All reports MUST return to Reports without discarding a saved
  report. Unsaved report changes MUST produce an explicit choice before loss.
- **INT-APP-04** Edit scope MUST open a draft copied from committed scope.
  Cancel or Back MUST discard the draft; Generate MUST atomically commit it.
- **INT-APP-05** Browser Back and Forward MUST navigate meaningful application
  transitions: screen changes, report changes, and authored diagram/view
  navigation. They MUST NOT replay hover, pan, zoom, panel movement, or every
  selection change.
- **INT-APP-06** Opening a copied report link MUST enter the referenced report
  and restore valid share state after durable report resolution.
- **INT-APP-07** Report sections MUST be keyboard-operable disclosures. Closing
  one section MUST not reset selection or another diagram's local state.
- **INT-APP-08** Changing System Scope, Roadmap state, detail level, or Other
  diagram MUST not reload the page and MUST expose pending, success, and failure
  state without replacing usable content prematurely.
- **INT-APP-09** The active roadmap state explanation MUST let users navigate
  its affected items. Activating an item MUST select and reveal it without
  changing scope or roadmap state.
- **INT-APP-10** Theme control MUST update the shell, grids, every diagram,
  dialogs, and subsequent exports as one coherent action without changing
  layout, selection, or navigation state.
- **INT-APP-11** When no saved theme exists, the app MUST follow operating-
  system preference. A deliberate user choice MUST take precedence and persist
  locally.

### 3.1 Scope builder

- **INT-SCOPE-01** Scope selection MUST happen on the dedicated Create/Edit
  Scope screen rather than through selection controls in report grids.
- **INT-SCOPE-02** One filter MUST search system name, group, tags, and owner and
  update the paginated result set without clearing the draft selection.
- **INT-SCOPE-03** Activating either a row or its checkbox MUST toggle that
  system exactly once. Interactive content within a row MUST not trigger an
  additional toggle.
- **INT-SCOPE-04** Select all MUST affect only filtered rows on the current page
  and MUST expose checked, unchecked, and mixed states accurately.
- **INT-SCOPE-05** Draft selection MUST survive filtering, sorting, and
  pagination. A persistent summary MUST expose selected count and enough names
  or grouping context to detect accidental selection.
- **INT-SCOPE-06** Generate report MUST be disabled when no system is selected
  and MUST explain why. Activation commits the entire draft atomically.
- **INT-SCOPE-07** Editing scope MUST begin from the committed selection.
  Cancel, Back, or browser Back MUST leave the open report unchanged.
- **INT-SCOPE-08** Keyboard users MUST be able to filter, traverse rows, toggle
  selection, operate Select all, paginate, review the summary, and generate
  without entering a second inaccessible navigation model.
- **INT-SCOPE-09** A scope commit that exceeds projection thresholds MUST show
  the applicable warning or hard-limit recovery before unsafe layout begins.

### 3.2 Report grids and row details

- **INT-GRID-01** Each grid MUST support quick filtering, per-column filtering,
  single and multi-sort, resizing, header-drag ordering, keyboard navigation,
  row selection, and pagination using AG Grid Community behavior.
- **INT-GRID-02** Clicking a non-interactive part of a row or activating it from
  the keyboard MUST update shared canonical selection without changing scope.
- **INT-GRID-03** When a diagram selects an applicable row, the corresponding
  grid section SHOULD open, navigate to the required page, reveal the row, and
  preserve the user's filters and column configuration.
- **INT-GRID-04** Quick filters and column filters MUST expose active state,
  result count, clear actions, and accessible labels that identify the grid.
- **INT-GRID-05** Multi-sort order and direction MUST be visible and keyboard
  operable. Reset MUST restore the defined default ordering.
- **INT-GRID-06** Column resizing and drag ordering MUST not make the pinned
  identity column unreachable. Keyboard alternatives MUST exist for ordering,
  visibility, and pinning through the shared column dialog.
- **INT-GRID-07** The column dialog MUST support show/hide and left/right
  pinning with Reset, Cancel, and Apply. Cancel MUST leave the grid unchanged;
  Apply MUST commit the complete draft atomically.
- **INT-GRID-08** Pagination MUST expose current page, total pages or rows,
  Previous, Next, and direct page choice where practical. It MUST be hidden when
  all filtered rows fit on one page.
- **INT-GRID-09** Grid rows MUST use auto height rather than nested vertical
  scrolling. Narrow grids MAY provide contained horizontal scrolling while the
  page remains the vertical scroll owner.
- **INT-GRID-10** Switching Applications ↔ Applications + components MUST
  preserve applicable filters, selection, sort, columns, and page position and
  update visible and accessible filter labels.
- **INT-GRID-11** Row details MUST expose complete available metadata without
  forcing it into columns. Empty fields MUST be omitted, and source/change links
  MUST be keyboard operable and safely validated.
- **INT-GRID-12** Closing row details MUST restore focus to the invoking row and
  retain shared selection.

### 3.3 Save report interaction

- **INT-SAVE-01** Save report MUST open a modal containing report name, concise
  capture summary, readable YAML preview, Download YAML, Cancel, and Save.
- **INT-SAVE-02** The capture summary MUST distinguish durable report intent
  from transient viewer state that will not be saved.
- **INT-SAVE-03** YAML preview MUST update from validated draft values. Invalid
  names or configuration MUST disable Save/Download and expose field-linked
  diagnostics.
- **INT-SAVE-04** Cancel and Escape MUST close the modal without modifying the
  saved report. Save MUST create or update the local report card atomically.
- **INT-SAVE-05** Download YAML MUST use the same validated representation as
  local Save and provide deterministic filename and success/failure feedback.
- **INT-SAVE-06** Closing the modal MUST restore focus to Save report. Reopening
  a saved report MUST recompute derived content before restoring interaction
  state.

## 4. Shared diagram frame

Every generated architecture diagram and attachment viewer uses one
independently owned `DiagramFrame`.

Semantic controls in sections 4–13 apply to generated architecture views.
Attachment viewers expose only the applicable frame, viewport, full-screen,
metadata, failure, and original-file behavior defined in sections 14–16.

- **INT-FRAME-01** Each frame MUST own its DOM references, viewport API,
  keyboard scope, overlays, and local state. Multiple frames MUST coexist
  without global queries or singleton viewer state.
- **INT-FRAME-02** The frame MUST expose a consistent toolbar containing the
  applicable subset of mode, search, fit/reset, zoom, radar, export, help, and
  full-screen controls.
- **INT-FRAME-03** Controls MUST expose text or accessible names, current state,
  disabled state, and keyboard shortcuts. Icon meaning MUST NOT depend on a
  tooltip alone.
- **INT-FRAME-04** In generated architecture views, PATH, MAP, and LENS are
  mutually exclusive primary modes:
  MAP shows the complete scene, PATH traces an authored architecture route,
  and LENS changes emphasis without changing the projection.
- **INT-FRAME-05** Canonical selection is orthogonal to PATH, MAP, and LENS.
  Changing mode MUST retain a still-valid selection and its passport.
- **INT-FRAME-06** Inline frames MUST prioritize ordinary page reading. Full
  screen MAY expose richer gestures and floating controls.
- **INT-FRAME-07** Controls that are inapplicable to a diagram or state MUST be
  hidden or disabled with an accessible reason; they MUST NOT fail silently.
- **INT-FRAME-08** Narrow layouts MAY collapse secondary controls into a menu,
  but applicable mode, fit, search, selection-dismissal, and full-screen-exit
  controls MUST remain reachable.
- **INT-FRAME-09** A frame MUST expose loading, empty, warning-size, hard-limit,
  and rendering-error states without leaving a blank canvas.

## 5. Viewport, pan, zoom, and reading depth

- **INT-VIEW-01** Fit MUST place the complete scene inside the available
  viewport with readable padding. Fit changes only the camera; it does not clear
  selection, focus, route, or lens state.
- **INT-VIEW-02** Reset view MUST clear transient focus, reach, route,
  lens, and search emphasis, restore the default camera, and preserve any valid
  shared canonical selection.
- **INT-VIEW-03** Zoom MUST be bounded, animate only when motion is allowed, and
  expose the current percentage and semantic reading depth.
- **INT-VIEW-04** Toolbar zoom controls and focused-diagram keyboard shortcuts
  MUST work independently of pointer-wheel support.
- **INT-VIEW-05** Focused diagrams MUST support LikeC4-compatible
  `Ctrl`/`Cmd` + `+`, `Ctrl`/`Cmd` + `-`, and `Ctrl`/`Cmd` + `0` for zoom in,
  zoom out, and viewport reset. They MUST prevent browser zoom only while the
  diagram itself has focus.
- **INT-VIEW-06** Inline diagrams MUST NOT consume ordinary page-wheel events.
  Full screen MAY support wheel zoom, trackpad pan, pinch zoom, and one-pointer
  pan when those gestures are discoverable.
- **INT-VIEW-07** Pointer and touch panning MUST start only from the canvas, not
  from a node, edge hit target, label, panel, toolbar, or scrollbar.
- **INT-VIEW-08** Camera movement initiated by search, selection, focus, route,
  radar, or history MUST reveal the target without unnecessary zoom changes.
- **INT-VIEW-09** If a target is already fully visible, selection SHOULD avoid
  moving the camera.
- **INT-VIEW-10** Reading depth MUST use three understandable states:
  MAP for overview, READ for normal labels, and FULL for fine metadata.
- **INT-VIEW-11** The initial thresholds SHOULD match the Archify pattern:
  below 100% is MAP, 100% through 174% is READ, and 175% or above is FULL.
  Thresholds MUST be centralized visual configuration rather than scattered
  component constants.
- **INT-VIEW-12** Selected, focused, routed, or story-relevant facts
  MUST remain available regardless of the current reading depth.
- **INT-VIEW-13** Layout recomputation, tab restoration, container resize, and
  full-screen entry/exit MUST clamp or refit the viewport so content cannot
  become irretrievably off-screen.
- **INT-VIEW-14** Each frame MUST provide an Archify-style zoom rail with
  Fit/Reset, zoom out, current MAP/READ/FULL depth and percentage, and zoom in.
  The current depth MUST update during button, keyboard, wheel, pinch, radar,
  and programmatic camera changes.
- **INT-VIEW-15** Semantic zoom MUST progressively reveal relationship labels,
  node context, tags, and annotations instead of scaling every fact into
  illegibility. Facts hidden at the current depth MUST remain available through
  selection, keyboard focus, passports, and accessible descriptions.

## 6. Keyboard canvas navigation

- **INT-KEY-01** A diagram MUST be one predictable page-level tab stop before
  its internal navigation is entered.
- **INT-KEY-02** Arrow-key spatial navigation MUST move among visible
  architecture nodes using scene geometry and a deterministic tie-breaker.
- **INT-KEY-03** `Enter` or `Space` MUST select the focused architecture node or
  edge proxy. Selection and drill-down MUST not share an ambiguous single
  action.
- **INT-KEY-04** Selectable edges MUST have keyboard-reachable semantic proxies,
  either on-canvas or through the active passport/relationship list.
- **INT-KEY-05** `Home` and `End` MUST move to the first and last item in an
  ordered result, route, tab list, or menu when that
  control owns focus.
- **INT-KEY-06** Shortcuts MUST be active only while the frame has focus and no
  text field, menu, or dialog is consuming input.
- **INT-KEY-07** Shortcut actions MUST be available through visible controls;
  shortcuts are accelerators, not the only interaction path.

## 7. Selection, intent preview, and passports

- **INT-SELECT-01** A single click or keyboard activation on an architecture
  node or edge MUST publish its canonical selection and open the appropriate
  passport.
- **INT-SELECT-02** Hover and keyboard focus SHOULD preview the target with a
  non-colour intent cue before selection. Preview MUST not alter shared state,
  URL state, history, or export.
- **INT-SELECT-03** Selecting blank canvas MAY clear selection after other
  active picking modes have declined the event.
- **INT-SELECT-04** Grid selection MUST reveal the nearest visible diagram
  projection. Diagram selection SHOULD reveal the corresponding grid row.
- **INT-SELECT-05** If a selected entity is below the active detail level, the
  frame MUST select its nearest visible ancestor and clearly identify the
  projection.
- **INT-SELECT-06** A Semantic Passport MUST show the selected entity's
  canonical ID, kind, name, description, technology, tags/groups, status,
  hierarchy, scope/reach reason, source/change note, and incoming/outgoing
  counts when present.
- **INT-SELECT-07** A Relationship Passport MUST show direction, source and
  target, label/type, technology, member interface IDs, status, route position,
  source/change note, and adjacent relationships.
- **INT-SELECT-08** Passport relationship lists MUST be keyboard navigable.
  Activating a listed entity or relationship MUST replace selection and reveal
  the new target.
- **INT-SELECT-09** A passport MUST have explicit Close and Copy link actions.
  Escape and a true outside activation MAY close it, but activating another
  selectable diagram target MUST replace rather than briefly close it.
- **INT-SELECT-10** Closing a passport MUST clear shared canonical selection. It
  MUST NOT clear report scope, roadmap state, route, lens, or saved data.
- **INT-SELECT-11** Only one passport may be active in a frame. Shared selection
  MUST prevent contradictory entity and relationship passports.
- **INT-SELECT-12** A stale or removed selection MUST close with an explanatory
  live status and restore focus to a stable frame control.
- **INT-SELECT-13** Architecture nodes MUST expose a visible selectable body,
  selected state, keyboard focus state, and sufficiently large pointer and
  touch target. Nested icons or text MUST resolve to the same canonical item.
- **INT-SELECT-14** Relationship lines MUST be directly selectable, not only
  their labels. A wider invisible hit path MAY be used, but the authored visible
  line and canonical relationship identity MUST remain unchanged.
- **INT-SELECT-15** Activating a relationship label, arrow, or hit path MUST
  produce the same canonical edge selection. Overlapping lines MUST
  provide a disambiguation list rather than choose by DOM order.
- **INT-SELECT-16** Parallel or visually aggregated interfaces MUST expose every
  canonical member in the Relationship Passport. Selecting one member MUST not
  pretend that the aggregate line represents only that member.

## 8. Floating and docked panels

These rules apply to passports, route probes, journey probes, radar panels,
guides, and other viewer-owned surfaces.

- **INT-PANEL-01** Inline report mode SHOULD use a compact popover, dock, or
  adjacent disclosure that does not hide normal report reading.
- **INT-PANEL-02** Full-screen mode MAY use floating panels over the canvas.
  The initial position MUST avoid primary toolbar, navigation rail, selection,
  and other open panels where possible.
- **INT-PANEL-03** A floating panel MUST expose a visible drag grip with an
  accessible name and touch-safe target.
- **INT-PANEL-04** Pointer dragging MUST use pointer capture and remain within
  the frame viewport. It MUST not pan the diagram underneath.
- **INT-PANEL-05** A focused drag grip MUST support arrow-key movement, a larger
  Shift+arrow step, and Home or double-click to reset.
- **INT-PANEL-06** Panel positions MUST be clamped after viewport resize,
  full-screen transitions, content resize, and browser text scaling.
- **INT-PANEL-07** Panel movement MUST remain transient to the mounted diagram.
  It MUST NOT enter saved YAML, copied links, canonical export, or layout input.
- **INT-PANEL-08** Opening or expanding a panel MUST use deterministic collision
  avoidance. A user-moved panel SHOULD retain its position unless it no longer
  fits.
- **INT-PANEL-09** Drag handles, Close, Clear, Copy link, and panel content MUST
  be separate hit targets. Dragging MUST not accidentally activate them.
- **INT-PANEL-10** The active or dragged panel MUST rise above other viewer
  chrome without covering application dialogs or full-screen exit controls.
- **INT-PANEL-11** Semantic and Relationship Passports, Route and Journey
  Probes, Semantic Radar, and Diagram Guide MUST use the shared movable-panel
  behavior whenever they float. Individual implementations MUST not invent
  conflicting drag, keyboard, constraint, or reset behavior.

## 9. Search and find

- **INT-FIND-01** Search MUST cover visible canonical IDs and labels. It SHOULD
  also cover descriptions, kinds, technology, tags, owner, interface labels,
  relationship labels, and source references that are present in the payload.
- **INT-FIND-02** Search indexes MUST derive from canonical architecture data,
  not renderer DOM or text extracted from presentation-only attachments.
- **INT-FIND-03** Search results MUST identify result kind and enough hierarchy
  or endpoint context to disambiguate duplicate names.
- **INT-FIND-04** Results MUST be keyboard navigable with arrows, Home, End,
  Enter, and Escape. Previous/next controls MUST cycle deterministically.
- **INT-FIND-05** Activating a result MUST select it, reveal it, and open its
  passport without changing report scope.
- **INT-FIND-06** A result outside the current projection MUST offer the nearest
  applicable projection or an explicit detail/view navigation action. It MUST
  not silently widen scope.
- **INT-FIND-07** No-result and stale-result states MUST be announced and MUST
  leave the current scene usable.
- **INT-FIND-08** Route endpoint selection MUST reuse search with contextual
  prompts and reachable-target filtering rather than maintain a second search
  implementation.
- **INT-FIND-09** Closing search MUST restore focus to its invoking control or
  selected result. Search query and active result MAY persist while the diagram
  tab remains mounted.

## 10. Focus, authored reach, and semantic lens

- **INT-FOCUS-01** Focus MUST emphasize one selected target and the minimum
  relevant context without changing the underlying projection.
- **INT-FOCUS-02** Entering and leaving focus MUST be reversible and retain the
  canonical selection.
- **INT-FOCUS-03** Upstream and downstream reach MUST follow authored, correctly
  oriented semantics rather than screen direction or geometry.
- **INT-FOCUS-04** Reach results MUST expose counts and keyboard-accessible node
  and relationship lists. Activating an item selects and reveals it.
- **INT-FOCUS-05** Reach language MUST remain factual: upstream, downstream,
  producer, consumer, or authored reachability. It MUST NOT claim runtime
  impact, blast radius, breakage, or causality.
- **INT-FOCUS-06** LENS MUST filter emphasis by applicable kind, status, scope,
  integration type, tag, or owner while retaining complete scene
  geometry.
- **INT-FOCUS-07** Active lens criteria MUST be visible, individually removable,
  keyboard operable, and represented in copied link state.
- **INT-FOCUS-08** Focus, reach, lens, and PATH dimming MUST combine colour with
  stroke, opacity, pattern, shape, or labelling cues.
- **INT-FOCUS-09** Reset view MUST clear focus, reach, and lens emphasis without
  changing scope, roadmap state, or canonical architecture data.
- **INT-FOCUS-10** When a node is selected, its passport and frame MUST provide
  separate Show inbound interfaces and Show outbound interfaces controls with
  truthful direct-interface counts.
- **INT-FOCUS-11** Inbound/outbound interface controls MUST support inbound,
  outbound, both, and neither. They emphasize direct authored interfaces and
  their opposite endpoints; they MUST remain distinct from recursive upstream
  and downstream reach.
- **INT-FOCUS-12** The active interface direction MUST be visibly pressed,
  keyboard operable, and described without relying on arrow orientation alone.
  Activating an emphasized line or list item opens its Relationship Passport.
- **INT-FOCUS-13** If an interface direction has no members, its control MUST be
  disabled with a zero count rather than produce an empty unexplained mode.
- **INT-FOCUS-14** Direct inbound/outbound emphasis MAY enter copied-link state
  and survive a mounted tab switch. It MUST NOT enter saved report YAML or alter
  the recursive upstream/downstream reach result.

### 10.1 Semantic Lens and interactive legend

- **INT-LEGEND-01** Every generated architecture frame MUST provide a compact
  semantic legend for the kinds, statuses, scopes, and integration types
  that are actually present in the active scene.
- **INT-LEGEND-02** Legend entries MUST be buttons or equivalent controls with
  labels, counts, symbols or line patterns, and selected state. Colour swatches
  alone are insufficient.
- **INT-LEGEND-03** Activating a legend entry MUST select or deselect that
  criterion in the Semantic Lens. The complete scene geometry remains present;
  unmatched items are de-emphasized rather than removed.
- **INT-LEGEND-04** Multiple legend entries MAY be selected. The frame MUST show
  the active combination and provide Select all, Deselect all/Clear lens, and
  Reset actions with unambiguous results.
- **INT-LEGEND-05** Selecting all entries or clearing the final criterion MUST
  return to ordinary MAP emphasis rather than leave every item dimmed.
- **INT-LEGEND-06** Legend selection MUST be keyboard operable with visible
  focus and pressed state. Counts and active criteria MUST be available to
  assistive technology.
- **INT-LEGEND-07** Entries with zero applicable items MUST be omitted or
  disabled. Legend counts MUST come from the active canonical projection, not
  the rendered DOM.
- **INT-LEGEND-08** Legend and Semantic Lens state MUST remain local viewer
  emphasis, survive mounted tab switches, enter copied links, and stay out of
  saved report YAML and canonical exports.
- **INT-LEGEND-09** Selecting a legend entry MUST not change grids, report scope,
  roadmap state, selection, or layout.
- **INT-LEGEND-10** Multiple entries within one legend category use OR semantics;
  active criteria across different categories use AND semantics. The frame MUST
  explain this rule in the Diagram Guide and active-lens summary.

## 11. Architecture route probe and journey

- **INT-ROUTE-01** PATH mode MUST trace the shortest authored directed route
  between exactly two selected endpoints. It MUST never infer connectivity from
  proximity, edge geometry, or layout order.
- **INT-ROUTE-02** Entering PATH with a selected eligible node SHOULD use it as
  the proposed source. Otherwise the probe MUST ask for a source.
- **INT-ROUTE-03** Source and target picking MUST support pointer, keyboard,
  search, passport relationships, and radar activation.
- **INT-ROUTE-04** After source selection, ineligible or unreachable targets
  MUST be disabled or clearly distinguished. Search SHOULD show directed hop
  distance for reachable targets.
- **INT-ROUTE-05** Route resolution MUST use deterministic directed traversal.
  Equal-length choices MUST use stable canonical ordering so identical input
  produces the same route.
- **INT-ROUTE-06** An unreachable, stale, conflicting, or self route MUST show a
  concise reason and allow either endpoint to be changed without leaving PATH.
- **INT-ROUTE-07** A resolved route MUST expose an ordered breadcrumb of nodes
  and relationship labels, directed hop count, and a factual shortest-authored-
  route description.
- **INT-ROUTE-08** Activating a breadcrumb, route node, or route edge MUST select
  it, reveal it, and update the passport without losing the route.
- **INT-ROUTE-09** The complete diagram MUST remain as dimmed context. Route
  nodes and edges MUST have strong, non-colour ordered cues.
- **INT-ROUTE-10** Journey controls MUST provide Previous, Next, Overview,
  Play/Pause, and Clear. Previous and Next step through ordered route positions;
  Overview restores the complete resolved route.
- **INT-ROUTE-11** Route playback MUST be explicitly started, finite, pausable,
  stale-safe, and disabled or made instantaneous for reduced motion.
- **INT-ROUTE-12** Escape during endpoint picking cancels the current pick.
  Escape with a resolved route stops playback first and then clears PATH on a
  subsequent activation according to the dismissal order in section 21.
- **INT-ROUTE-13** Clearing PATH MUST return to MAP, restore the complete scene,
  and retain a valid canonical selection.
- **INT-ROUTE-14** Copy link MUST encode both endpoints and enough route identity
  to recompute and validate the same authored route. It MUST not encode derived
  geometry.
- **INT-ROUTE-15** Route computation and journey state MUST remain outside the
  renderer. The renderer receives emphasized canonical ID sets and ordered step
  metadata only.

## 12. Semantic radar and orientation

- **INT-RADAR-01** Diagrams larger than the viewport MUST provide a Semantic
  Radar or equivalent overview. Smaller diagrams MAY let users open it.
- **INT-RADAR-02** Radar geometry MUST derive from the active neutral scene and
  viewport. It MUST not become a second layout or selection source of truth.
- **INT-RADAR-03** The radar MUST distinguish semantic kinds and show the current
  viewport window with non-colour cues.
- **INT-RADAR-04** Activating a radar item MUST reveal and select the canonical
  target. Activating empty radar space MUST recenter the camera.
- **INT-RADAR-05** Dragging the radar viewport rectangle MAY pan the camera. It
  MUST be bounded and MUST not initiate diagram selection.
- **INT-RADAR-06** Keyboard users MUST be able to traverse radar targets with
  arrows and activate them with Enter or Space.
- **INT-RADAR-07** The radar MUST track camera movement, resize, restored tabs,
  reading depth, and full-screen transitions.
- **INT-RADAR-08** Radar visibility MUST be toggleable, Escape-dismissible, and
  excluded from canonical SVG/PNG output.
- **INT-RADAR-09** Presentation-only attachments MAY use a non-semantic
  thumbnail or viewport rectangle for orientation, but it MUST NOT infer or
  expose selectable internal elements.

## 13. C4 detail and authored view navigation

- **INT-C4NAV-01** Solution Diagram MUST expose explicit System, Application,
  and Component detail controls. Changing detail requests a genuine projection,
  not a visual expansion of hidden renderer nodes.
- **INT-C4NAV-02** A node's primary activation selects it. Drill-down MUST use a
  distinct Open detail/Open view action exposed from the node, passport, or
  keyboard action menu.
- **INT-C4NAV-03** Drill-down MUST resolve only to an applicable in-scope detail
  projection or authored diagram. If none exists, the action MUST be unavailable
  with a concise reason.
- **INT-C4NAV-04** Drill-up MUST select the appropriate visible ancestor and
  preserve focus where possible.
- **INT-C4NAV-05** Authored `navigateTo` behavior on a node or relationship MAY
  open an applicable named diagram or dynamic view. It MUST NOT reinterpret a
  single click that is already used for selection.
- **INT-C4NAV-06** Each frame MUST maintain Back, Forward, and Up/breadcrumb
  navigation for detail projections and authored views. History entries MUST use
  stable report, diagram, view, and canonical IDs.
- **INT-C4NAV-07** Back and Forward MUST restore the view/detail, selection,
  focus context, and a usable viewport. They SHOULD restore a still-valid local
  viewport without persisting geometry outside runtime state.
- **INT-C4NAV-08** Browser history MUST synchronize meaningful authored view
  changes. Selection, zoom, pan, hover, and floating-panel movement MUST use
  replacement or runtime state rather than create history spam.
- **INT-C4NAV-09** Search results, passports, relationships, route steps, and
  roadmap affected-item lists MAY offer Open detail/Open view when the target
  has an applicable destination.
- **INT-C4NAV-10** View navigation MUST never mutate report scope. A destination
  requiring broader scope MUST offer Edit scope as an explicit separate action.
- **INT-C4NAV-11** When more than one authored view is applicable to the active
  report, the frame MUST expose an in-scope view chooser from its navigation or
  breadcrumb controls. The chooser MUST search stable view ID, title, and path,
  distinguish duplicate titles by type and hierarchy, support arrows, Home, End,
  Enter/Space, and Escape, and MUST NOT list or load views outside the active
  report's effective scope.
- **INT-C4NAV-12** Drill-down, drill-up, and authored view navigation SHOULD
  preserve spatial continuity by temporarily anchoring the source entity to its
  corresponding canonical entity or visible ancestor in the destination before
  settling on the destination viewport. If no valid correspondence exists, the
  frame MUST use an ordinary bounded reveal or fit. Reduced-motion mode MUST
  apply the final viewport without an animated transition.
- **INT-C4NAV-13** Per-frame authored-view history MUST be bounded and MUST store
  stable view/detail identity plus applicable selection, focus, and local
  viewport context. Navigating from an older entry MUST discard its
  obsolete forward branch. Restoration MUST validate every identity and omit
  stale optional state rather than substitute by display name.

## 14. Attached diagram viewing

- **INT-ATTACH-01** Report v2 MUST treat locally bundled SVG diagrams as
  presentation-only attachments. Sequence diagrams may be produced by Mermaid,
  PlantUML, ZenUML, LikeC4, or another external tool before report generation.
- **INT-ATTACH-02** Attachment preparation MUST validate media type, ownership,
  local references, scripts, event handlers, and external resources before the
  asset enters the report bundle.
- **INT-ATTACH-03** The viewer MUST provide a report-facing title, optional
  description, intrinsic dimensions, fit/reset, pan, zoom, full screen, and a
  download or open-original action.
- **INT-ATTACH-04** The viewer MUST NOT parse SVG structure, scrape labels,
  manufacture canonical IDs, or claim semantic selection, search, passports,
  routes, transcripts, playback, or fragment navigation.
- **INT-ATTACH-05** Attachment viewport and full-screen state MUST remain local
  to the mounted tab. It MUST NOT enter saved architecture data or alter shared
  canonical selection.
- **INT-ATTACH-06** The attachment wrapper MUST expose accessible title and
  description text plus an equivalent download/open-original action. Meaningful
  alternatives beyond that metadata remain the attachment author's
  responsibility.
- **INT-ATTACH-07** A rejected, missing, or unsupported attachment MUST show a
  concise diagnostic and safe recovery action rather than a blank panel.

## 15. Other diagrams and tabs

- **INT-TAB-01** Other diagrams MUST use one accessible tab list and one visible
  tab panel. Only applicable authored diagrams receive tabs.
- **INT-TAB-02** Arrow keys move tab focus; Home and End move to the first and
  last tab; Enter or Space activates a tab unless automatic activation can occur
  without noticeable work.
- **INT-TAB-03** Switching tabs MUST preserve each mounted instance's applicable
  local viewport and navigation state. Generated architecture views share
  canonical selection; presentation-only attachments do not participate in it.
- **INT-TAB-04** When shared selection is not representable in the new tab, the
  tab MUST show the nearest applicable projection or a clear not-present state.
- **INT-TAB-05** Workflow, sequence, dataflow, and lifecycle/transition diagrams
  supplied as safe local SVG attachments retain their authored appearance. They
  share only applicable frame, viewport, full-screen, and download contracts.
- **INT-TAB-06** Presentation-only attachments MUST be labelled as such and MUST
  not simulate canonical selection or other semantic interaction.

## 16. Full screen and presentation

- **INT-FULL-01** Full-screen entry MUST preserve active diagram, selection,
  applicable mode, route, lens, search result, and local view history.
- **INT-FULL-02** After the transition, the frame MUST resize and fit or clamp
  its current camera before accepting navigation input.
- **INT-FULL-03** Full screen MUST lock background scroll, trap focus, expose a
  persistent exit action, and close on Escape after higher-priority overlays are
  dismissed.
- **INT-FULL-04** Exiting full screen MUST restore the invoking control's focus
  and a usable inline viewport.
- **INT-FULL-05** Floating passports, probes, radar, and guides MUST remain
  movable, bounded, dismissible, and keyboard operable in full screen.
- **INT-FULL-06** A presentation treatment MAY simplify viewer chrome, but it
  MUST not change authored geometry, selection semantics, or export truth.
- **INT-FULL-07** Touch-sized full-screen layouts MUST keep exit, mode, fit,
  search, and selection dismissal reachable without precision pointing when
  those controls apply.

## 17. Copy links, URL restoration, and history

- **INT-LINK-01** Copy link MUST encode report ID, roadmap state, diagram ID,
  active detail/view, canonical selection, mode, and applicable focus, lens,
  or route.
- **INT-LINK-02** Links MUST NOT encode source data, report YAML, rendered HTML,
  layout geometry, pan, zoom, open menus, copied acknowledgement, or floating-
  panel position.
- **INT-LINK-03** Opening a link MUST validate every referenced ID against the
  resolved report payload before applying interaction state.
- **INT-LINK-04** Invalid or missing IDs MUST produce a diagnostic, apply the
  remaining valid state where safe, and never substitute by display name.
- **INT-LINK-05** Link restoration MUST apply in this order: report, roadmap
  state, diagram/view/detail, projection, selection, mode, focus/lens/route,
  then reveal camera.
- **INT-LINK-06** Copy success and failure MUST be announced without moving
  focus. A local fallback MUST exist when the asynchronous Clipboard API is not
  available.
- **INT-LINK-07** Meaningful screen, report, and authored view changes MUST push
  browser history. Selection and mode changes SHOULD replace current URL state
  so Back is useful rather than noisy.
- **INT-LINK-08** Browser Back/Forward restoration MUST be stale-safe and MUST
  not rerun obsolete layout results over the current state.

## 18. Export interactions

- **INT-EXPORT-01** Every generated architecture frame MUST offer SVG and PNG
  export through a keyboard-operable menu or dialog. Attachment viewers MUST
  offer the validated original-file action instead.
- **INT-EXPORT-02** Export Diagram MUST use complete neutral scene bounds rather
  than the current viewport crop and preserve active theme, semantic labels,
  legend, attribution, direction, and canonical IDs.
- **INT-EXPORT-03** Canonical diagram export MUST exclude hover, search chrome,
  passports, probes, radar, guide, panel positions, camera, playback, and other
  temporary viewer state.
- **INT-EXPORT-04** If route export is implemented, it MUST be a distinct
  explicit action. It MUST use the already resolved ordered route,
  preserve dimmed context, and fail closed when stale or conflicting.
- **INT-EXPORT-05** Export controls MUST expose pending, success, filename,
  format, and structured failure state without freezing ordinary interaction.
- **INT-EXPORT-06** Exporting MUST not clear selection, close useful panels, or
  alter the diagram camera.

## 19. Diagram guide and discoverability

- **INT-GUIDE-01** Every frame MUST provide a Diagram Guide listing the actions
  and shortcuts currently available for that diagram and state.
- **INT-GUIDE-02** The guide SHOULD summarize factual diagram counts and offer
  direct actions for Find, Route, Radar, applicable guidance, Full screen,
  Export, Theme, and Reset.
- **INT-GUIDE-03** Unavailable actions MUST be omitted or disabled with a reason;
  the guide MUST not advertise unauthored stories or unsupported semantics.
- **INT-GUIDE-04** Guide controls MUST support arrows, Home, End, Enter/Space,
  and Escape and restore focus to the invoking control on close.
- **INT-GUIDE-05** Tooltips MAY supplement controls but MUST not contain unique
  instructions that keyboard, touch, or screen-reader users cannot obtain.

## 20. Authored guidance and walkthroughs

These interactions apply only when an authored diagram declares valid guidance.

- **INT-STORY-01** Authored architecture chapters or stories MUST use stable
  canonical node or relationship IDs and MUST not own parallel topology.
- **INT-STORY-02** A chapter rail MUST expose named stops, current position,
  Previous, Next, Overview, Play/Pause, and Clear.
- **INT-STORY-03** Adjacent story stops MUST describe only the exact authored
  relationship: forward, reverse, multiple, or grouped/no direct connection.
  Story order MUST not imply causality.
- **INT-STORY-04** Story activation MAY move the camera and focus the stop, but
  MUST not mutate report scope, roadmap state, architecture data, or layout.
- **INT-STORY-05** Playback MUST be reader-started, finite, pausable, stale-safe,
  and motion-governed. Focus entering story controls SHOULD pause playback.
- **INT-STORY-06** A diagram with no authored guidance MUST not show an enabled
  story action.
- **INT-STORY-07** Story state MAY enter a copied link but MUST not enter saved
  report YAML or canonical export.

## 21. Dismissal, precedence, and conflicting interactions

Escape dismisses only the highest active layer in this order:

1. Menu, tooltip with interaction, or transient confirmation.
2. Modal dialog, finder, guide, or expanded relationship list.
3. Active route source/target picking.
4. Active route or story playback; the first Escape pauses it.
5. Radar or floating auxiliary panel.
6. Passport.
7. PATH/LENS/focus emphasis.
8. Full screen.

- **INT-DISMISS-01** One Escape activation MUST perform at most one visible
  dismissal step and restore focus predictably.
- **INT-DISMISS-02** Opening a modal dialog MUST pause playback and make canvas
  interaction inert until the dialog closes.
- **INT-DISMISS-03** Opening Finder for route endpoint selection MUST retain the
  route probe and return the chosen result to it.
- **INT-DISMISS-04** Opening Guide SHOULD close unrelated menus and Finder while
  retaining canonical selection and resolved route state.
- **INT-DISMISS-05** Selecting a diagram element takes precedence over blank-
  canvas clearing and canvas panning. A route-picking mode takes precedence over
  ordinary selection but MUST still publish the chosen endpoint visibly.
- **INT-DISMISS-06** A node or relationship with an authored navigation target
  MUST still use primary activation for selection; navigation is a distinct
  secondary action.
- **INT-DISMISS-07** Full-screen exit MUST occur only after its child dialogs,
  pickers, and transient playback states have handled Escape.

## 22. Accessibility and input equivalence

- **INT-A11Y-01** Every control and selectable diagram element MUST have an
  accessible name, appropriate role/state, visible focus, and equivalent
  pointer, keyboard, and touch operation where applicable.
- **INT-A11Y-02** Architecture node labels MUST include kind, name, status, and
  hierarchy or technology context. Architecture edge labels MUST include
  direction and endpoints.
- **INT-A11Y-03** Selection, focus, reach, route order, status, and edge meaning
  MUST not depend on colour or animation alone.
- **INT-A11Y-04** Dynamic selection, search, route, playback, error, and copied
  states MUST produce concise live announcements without repeatedly announcing
  the entire diagram.
- **INT-A11Y-05** Dialogs and full-screen views MUST trap focus and restore it.
  Non-modal passports and probes MUST not trap focus.
- **INT-A11Y-06** Forced-colour mode MUST preserve boundaries, selection,
  direction, route order, and focus. Browser text scaling MUST not hide primary
  actions or produce page-level horizontal overflow.
- **INT-A11Y-07** Reduced-motion mode MUST remove ambient movement, animated
  camera transitions, route flow, and autoplay. Static ordered meaning MUST
  remain complete.
- **INT-A11Y-08** Touch targets SHOULD be at least 44 by 44 CSS pixels where
  space permits and MUST not require hover.
- **INT-A11Y-09** Large generated architecture diagrams MUST provide search,
  relationship lists, radar, and textual summaries so users are not forced
  through hundreds of tab stops.
- **INT-A11Y-10** Attachment viewers MUST expose their title, description, file
  type, and download/open-original action without presenting the SVG's internal
  drawing objects as report-owned interactive semantics.

## 23. Responsive and touch behaviour

- **INT-RESP-01** The page MUST never gain horizontal overflow from viewer
  chrome. A bounded diagram or grid MAY manage its own horizontal navigation.
- **INT-RESP-02** On narrow inline layouts, passports and probes SHOULD dock or
  become adjacent disclosures rather than obscure the whole diagram.
- **INT-RESP-03** Floating panels MUST remain entirely recoverable after
  orientation change, browser resize, virtual keyboard appearance, and text
  scaling.
- **INT-RESP-04** Generated architecture diagrams on touch MUST distinguish tap
  selection, deliberate pan, pinch zoom, scrollbar movement, and panel dragging
  without timing-only gestures. Attachment viewers MUST distinguish viewport
  pan/zoom from ordinary page scrolling.
- **INT-RESP-05** Inline touch interaction MUST allow ordinary page scrolling at
  the diagram boundary. Full screen MAY claim richer gestures after explicit
  entry.
- **INT-RESP-06** Generated architecture hover previews MUST be omitted on
  coarse pointers without removing the facts available through focus,
  selection, or passports.
- **INT-RESP-07** Applicable radar, search, mode, fit, and full-screen exit
  controls MUST remain usable on touch-sized viewports.

## 24. Loading, limits, and failure recovery

- **INT-FAIL-01** During projection or layout, the active request MUST be visible
  and incompatible controls MUST be disabled without discarding the last usable
  scene.
- **INT-FAIL-02** Empty projections MUST explain why nothing is visible and
  offer an applicable scope/detail recovery action.
- **INT-FAIL-03** Warning-size diagrams MUST remain usable and disclose that
  interaction may be slower.
- **INT-FAIL-04** Hard-limit diagrams MUST not attempt unsafe layout. They MUST
  offer explicit scope or detail reduction.
- **INT-FAIL-05** Rendering or layout failure MUST retain report navigation and
  provide a concise diagnostic action and retry where safe.
- **INT-FAIL-06** Search, selection, route, history, and copied-link
  restoration MUST fail closed when identity or semantic evidence is stale or
  conflicting.
- **INT-FAIL-07** A failed interaction MUST restore an operable control and MUST
  not leave focus in removed DOM.

## 25. Shortcut baseline

Shortcuts apply only while the diagram frame is focused and no text-entry
control owns the key.

| Shortcut | Action |
| --- | --- |
| `Ctrl`/`Cmd` + `+` or `=` | Zoom in |
| `Ctrl`/`Cmd` + `-` or `_` | Zoom out |
| `Ctrl`/`Cmd` + `0` | Reset viewport |
| `/` | Open Find |
| `?` | Open Diagram Guide |
| `R` | Start or focus Route/Journey Probe |
| `M` | Toggle Semantic Radar |
| `F` | Fit complete diagram |
| Arrow keys | Move within the active spatial or ordered control |
| `Home` / `End` | First/last item in ordered controls; Home resets a focused panel grip |
| `Enter` / `Space` | Activate or select focused item |
| `Escape` | Dismiss one layer using section 21 precedence |

- **INT-SHORT-01** The final shortcut set MUST be collision-tested against
  browser, screen-reader, grid, and operating-system shortcuts.
- **INT-SHORT-02** Unmodified letter shortcuts MUST not fire while focus is in a
  text input, menu, dialog, or editable browser surface.
- **INT-SHORT-03** The Diagram Guide MUST list the actual configured shortcuts,
  not duplicate them as unrelated hard-coded help text.

## 26. Required acceptance journeys

The implementation is not interaction-complete until these journeys pass with
pointer, keyboard, and applicable touch input:

1. Open a saved report, change roadmap state, select a grid row, reveal it in
   the Solution Diagram, inspect its passport, return to Reports, and use browser
   Back to restore the report.
2. Switch System → Application → Component, use the in-scope view chooser,
   drill into an applicable view with spatial continuity, then use Up, Back, and
   Forward across a bounded branched history without changing report scope.
3. Search for a duplicate label, distinguish results by hierarchy, select one,
   center it, inspect it, and close search with focus restored.
4. Select a route source and reachable target, inspect the deterministic route,
   step and play its journey, copy its link, clear it, and restore it from the
   link.
5. Attempt an unreachable and a stale route and recover without leaving PATH or
   losing the usable scene.
6. Apply a semantic lens and upstream/downstream reach, navigate result lists,
   then reset without changing scope or selection.
7. Open, move, keyboard-move, resize around, reset, and close a floating
   passport and probe without panning the underlying diagram.
8. Use radar to orient, select, recenter, and pan a diagram larger than the
   viewport, including at browser text scaling.
9. Enter full screen, operate nested search/passport/route panels, dismiss them
   in precedence order, exit, and restore invoking focus.
10. Open a large externally generated sequence SVG, fit, pan, zoom, enter full
    screen, download the original, and verify that no internal element is
    presented as canonically selectable or searchable.
11. Switch repeatedly among generated C4 and attachment tabs and verify
    per-instance viewport state without leaking canonical selection into an
    attachment.
12. Run two diagram frames on one page and verify no selection, viewport,
    shortcut, overlay, or DOM ownership leaks between them.
13. Use forced colours, reduced motion, 200% text scaling, keyboard only, and a
    screen reader through architecture selection/search/route, attachment
    metadata and download, full screen, and error recovery.
14. Export SVG and PNG from a panned, zoomed, searched, selected, and routed
    frame and verify full canonical bounds and removal of viewer-only chrome.
15. Trigger overlapping projection/layout requests and prove that only the
    newest request can alter scene, camera, selection reconciliation, or status.
16. Select architecture nodes from their body, select relationships from
    visible lines, labels, and keyboard proxies, and disambiguate overlapping
    lines.
17. Show inbound interfaces, outbound interfaces, both, and neither for one
    selection; inspect an emphasized line and distinguish direct interfaces from
    recursive upstream/downstream reach.
18. Select and deselect individual and multiple legend entries, use Select all
    and Clear lens, switch tabs, restore from a copied link, and prove that scene
    geometry and report scope never change.
19. Use the Archify-style zoom rail and keyboard zoom to cross MAP, READ, and
    FULL thresholds while selected and routed facts remain available.

## 27. Explicitly excluded or deferred interactions

These Archify/LikeC4 capabilities are not required for the initial Report v2
interaction contract unless separately promoted:

- General model-wide browsing outside the active report scope.
- Direct node, edge, container, port, or route editing.
- Persisted manual layout, viewport, floating-panel coordinates, or WYSIWYG
  document state.
- Automatic scope expansion caused by drill-down, search, selection, or route.
- Continuous ambient architecture animation or autoplay on page load.
- Treating layout proximity, story order, or route visuals as runtime causality.
- Archify-specific social Share Cards, JPEG/WebP export, trace WebM recording,
  and release-presentation assets. Core SVG/PNG and copy links remain required.
- A second hidden renderer, layout engine, search index, or navigation model as
  a compatibility fallback.
- Mobile-only product features beyond responsive containment and touch access to
  the same report interactions.
- Native sequence parsing, layout, rendering, canonical message selection,
  transcript, outline, radar, stepping, or playback. The bounded ZenUML spike is
  retained as post-V2 research and may be reconsidered only after Report v2 is
  complete.

## 28. Traceability sources

- `arch-v3-wip/requirements.md`: `FLOW-*`, `DIAG-*`, `SELECT-*`, `VIS-*`,
  `EXPORT-*`, `PERF-*`, and `A11Y-*` requirements.
- `arch-v3-wip/design.md`: shared `DiagramFrame`, React Flow viewport,
  Archify-inspired architecture navigation, presentation-only attachment
  viewer, state model, and verification strategy.
- `scratch/archify/archify/references/viewer-runtime.md`: Diagram Guide,
  reading depth, lens, intent trace, finder, passports, radar, relationship pin,
  route probe, guided views, presentation, and viewer/export separation.
- `scratch/archify/archify/test/`: executable interaction evidence for route
  picking/journeys, semantic radar, passports, semantic zoom, guide, story
  navigation, keyboard behavior, reduced motion, and export cleanup.
- [LikeC4 views](https://likec4.dev/dsl/views/): scoped views and node navigation.
- [LikeC4 relationships](https://likec4.dev/dsl/relationships/): authored
  relationship `navigateTo` behavior.
- [LikeC4 React components](https://likec4.dev/tooling/react/): focus, search,
  relationship browsing/details, navigation buttons, walkthroughs, viewport
  controls, events, and keyboard zoom shortcuts.
- `scratch/likec4/packages/diagram/src/navigationpanel/NavigationPanelDropdown.tsx`:
  searchable view and folder navigation with scoped keyboard traversal.
- `scratch/likec4/packages/diagram/src/likec4diagram/state/machine.state.navigating.ts`:
  corresponding-node transition anchoring, bounded history, and restoration of
  valid focus, walkthrough, variant, and viewport context.
