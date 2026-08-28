# UI polish issues — acme report walkthrough

Evidence: 2026-08-25 Playwright session against `plans/arch/wip/acme-report.html`
(fresh build, 1440×900 and 1024×720, light + dark, System/Container levels,
time position 0 and 4, compare vs base). Complements the Phase 3P evidence
baseline in plan.md; issues tagged with the 3P pass that should absorb them.

Tracking: when a pass gates, the architect appends `— CLOSED (D13x,
date)` or `— WAIVED (reason, date)` to each issue it covered. The 3P
exit gate requires every issue closed or waived and a re-run of this
walkthrough confirming the behavior defects (#12–#17) don't reproduce.

## Direction (2026-08-27) — supersedes conflicting expectations

[ui-polish-direction.md](ui-polish-direction.md) is the confirmed product
direction for the report UI and the decision source for every 3P pass spec.
Where an issue's "Expected" clause below conflicts with the direction, the
direction wins — the issues stay as walkthrough evidence, not as
requirements. Chrome-level consequences: the shell is Option E's docked
View / Info / Data layout, the Map / Fit / Zoom cluster is the fixed
lower-**left** canvas overlay (not a bottom-right stack), and there is no
floating legend, floating selection toolbar, or dark theme in the first
pass; the responsive floor is 1024 × 720. The D13a–D13d tags below predate
the direction; pass ownership is reassigned as the architect re-authors
each pass spec against the direction (plan.md "Phase 3P") — issues whose
chrome no longer exists are closed by the shell restructure and carry a
supersession note below (#14, #16, #18, #24).

## 0. Control simplification (2026-08-26 design review of the artboards, since removed — git history)

Decisions from the artboard review. These read as visual polish but each one
changes behavior/state, so they bind the 3P passes the same way the numbered
issues do:

- **Detail level is a dropdown, not a segmented tab bar.** One "Detail"
  dropdown (System / Container / Child / Component), styled like the tags
  dropdown, defaulting to **System**. Rationale: it is a select-one view
  setting, not navigation; a dropdown has a fixed footprint at any label
  length and viewport, and keeps the context row to one control style.
- **Time slider replaced by a "Stage" dropdown.** One entry per stage
  ("0 · Base", "4 · Transaction Core", …). Rationale: stages are discrete
  named states, not a continuum — a slider invites scrubbing between
  meaningless intermediate positions, needs fixed-width slots to avoid
  reflow (#17), and hides the stage names. A dropdown shows every stage by
  name, jumps directly, and makes #17's reflow problem structurally
  impossible for this control.
- **Compare dropdown removed.** Each stage inherently describes its changes
  against the previous stage, so diff styling (where shown) is a property of
  the selected stage, not a separate mode to configure. Removes a whole
  state dimension (compare target × position) and the inverted-emphasis
  trap it produced (#7 stays for stage-diff rendering).
- **Scope control removed from the viewer.** How scope should interact with
  the live display was never clear; scope is a *report generation* concern
  (what the report was built to cover), not a canvas toggle. If it returns,
  it belongs in report configuration, not viewer chrome.
- **"Base · Systems" title badge removed.** It duplicated the Detail and
  Stage controls' current values as static text — dead weight in the title
  bar that had to be kept in sync.
- **Status-bar readouts removed.** "N nodes · N connections · scope …" and
  "ELK UNION LAYOUT · OFFLINE · POSITION …" are debug/engine internals with
  no user decision attached; counts also went stale against filters. The
  status bar goes away entirely unless a future item earns its place.

Net effect on the issue list: #15 and #17 lose their hardest cases (the
time pill and compare dropdown no longer exist); #7 is reinterpreted as
stage-diff styling; the fixed-width-slots remedy in #17 applies only to
whatever chrome remains.

## 1. Connectors (worst area — D13c, routing in D13b)

1. **Edges are invisible.** Every edge is a 1px `#B1B1B7` stroke — the React
   Flow default, unstyled. At the 21–40% zoom the report actually opens at,
   edges effectively disappear; in dark theme they are worse.
   Expected: themed stroke with real contrast in both themes,
   zoom-compensated width so an edge is always ≥1px on screen.
2. **No arrowheads.** `marker-end` is null on all 17 edges; direction is
   unreadable. The Call-direction aspect changes nothing visible.
   Expected: visible arrowheads at every target, sized with zoom; aspect
   switch must produce a visibly different picture.
3. **No edge labels.** Zero edge labels render at any zoom (`labelCount: 0`).
   Connection names exist (they show in the side panel) but never on canvas.
   Expected: label pills at FULL depth and on selection/hover.
4. **Routing draws phantom boxes.** Orthogonal routes take huge rectangular
   detours across empty canvas (e.g. analytics-provider's edge loops around
   a ~700×250px empty rectangle). These outlines read as boundary boxes, not
   edges. Expected: direct routes, no detour larger than the nodes it avoids.
5. **Edges cross node interiors and chrome.** Routes pass under the Customer
   node, under the collapsed legend strip, and under the minimap.
   Expected: routes avoid node bodies and never rely on areas covered by
   overlays.
6. **Empty stub boxes float next to nodes.** Small empty rounded rects sit
   detached beside Warehouse Operator, Enterprise Order Management, and on
   the left rank — they look like broken labels. Expected: interface stubs
   (if that is what they are) get a glyph/label and attach visually to their
   node, or don't render at this level.
7. **Inverted emphasis in compare mode.** Added edges render bold teal with
   arrowheads while the entire base architecture stays 1px pale gray — the
   diff is more legible than the architecture itself. Expected: base edges
   legible always; diff styling an increment on top, not the only visible ink.

## 2. Layout and fit (D13b)

8. **Initial fit is broken.** Cold load lands at 31% zoom with the graph
   crammed bottom-left and the top half of the canvas empty; after level
   switches it strands content right-of-center with a dead left third.
   Expected: fit centers the graph with even margins at a zoom where names
   are readable (small graphs land at READ depth).
9. **Fit ignores overlays.** With legend or tables open, Fit uses the full
   canvas rect, so fitted content hides behind panels; opening the tables
   panel (65% height) or details panel (50% width) never re-fits.
   Expected: fit and re-fit against the *visible* canvas whenever an overlay
   opens, closes, or the viewport resizes.
10. **Node cards waste their space.** Uniform 171×115 cards are ~80% empty
    yet still truncate names ("Legacy Commerce Platfo…") — at every zoom.
    Expected: size from content per depth; a name never truncates while its
    box has empty rows.
11. **Container level is unreadable.** 42 nodes at 21% with near-invisible
    group borders and 6px labels. Expected: per-level sizing/threshold so the
    default view of any level is readable, and boundary containers visually
    distinct (fill tint + label) from edge routes.

## 3. Interaction (D13b/D13c for canvas, D13d for panels)

12. **Selection hides the selected thing.** Clicking a node opens the 50%
    details panel without panning — the selected node ends up underneath the
    panel or offscreen. Same for edges: no visible highlight remains in view.
    Expected: on select, pan/zoom the selection into the remaining visible
    canvas and highlight it; on edge select, highlight the full route.
13. **Escape doesn't close the details panel.** Only the small ✕ does.
    Expected standard keys: Escape closes topmost overlay / clears selection.
14. **Legend state is unstable.** Collapsed legend re-expands by itself when
    a node is selected; expanded, it floats over the diagram; collapsed, it
    renders as a full-height strip mid-canvas that covers nodes and the
    minimap. Expected: panel state changes only on user action; collapsed
    state is a small docked affordance at the canvas edge; open panels
    participate in fit (see #9).
    *Superseded (2026-08-27): the floating legend is removed entirely —
    Tags is a View-dock control that brightens matches and dims
    nonmatches (direction). The evidence stands; the remedy is the
    docked shell.* — CLOSED (D13a, 2026-08-28: no floating legend;
    Tags lives in the View dock).
15. **Time toolbar vanishes.** After a select/close-details sequence the
    entire time pill (slider + compare) disappeared and only a full reload
    restored it. Expected: persistent chrome never disappears as a side
    effect.
16. **Contextual controls jump into unrelated groups.** A "Dependencies"
    button appears inside the level-tabs bar only while a node is selected.
    Expected: selection-scoped actions live with the selection, not
    spliced into a global control group.
    *Superseded remedy (2026-08-27): no floating selection toolbar exists
    — Dependencies opens contextually from the Info dock's "View
    dependencies" action (direction).* — CLOSED for chrome (D13a,
    2026-08-28: the level bar is gone; Dependencies opens from Info).
    Info content itself remains pass 4 (#20/#21).
17. **Controls shift as values change.** The time pill re-flows when the
    position label changes width ("0. Base" → "4. Transaction Core"),
    moving the compare dropdown; the COMPARE label is crammed against it.
    Expected: fixed-width slots so nothing jumps while scrubbing.

## 4. Overlapping chrome (D13a/D13b)

18. **Bottom-right pile-up.** The zoom rail sits on top of the minimap; at
    1024×720 both sit on top of graph nodes, and the collapsed legend strip
    overlaps the minimap. Expected: one bottom-right stack (minimap above,
    zoom rail below), never overlapping each other, panels, or fitted
    content.
    *Superseded remedy (2026-08-27): nothing docks bottom-right — the
    confirmed direction has one fixed lower-left `Map | Fit | Zoom` row
    with the optional minimap attached directly above it.* — CLOSED
    (D13a, 2026-08-28: lower-left row shipped; minimap attaches above
    it, closed by default).
19. **Floating toolbars overlap the canvas contents.** The time pill and
    level bar float over the diagram and cover nodes at small viewports.
    Expected: reserve their space in the canvas fit (or dock them).
    — CLOSED (D13a, 2026-08-28: all controls live in docks that reserve
    layout space; the only canvas overlay is the lower-left cluster).

## 5. Panels (D13d)

20. **Details panel field rendering.** Label and value collide
    ("availability_targe99.9%"); raw snake_case keys (`end_in`,
    `availability_target`) mixed with humanized labels (Status, Contains);
    "Contains: 1" is a bare count with no link to what it contains.
    Expected: kv grid that never overlaps, one label style, counts as
    links/chips to the contained items.
21. **Connection details are near-empty.** An edge's Details tab repeats the
    title plus the raw id and nothing else, and the panel offers a
    "Connections" tab for a connection. Expected: show endpoints (linked),
    direction, interface, aspect values, lifecycle interval; tabs that make
    sense for the entity kind.
22. **Tables panel column sizing.** id/name/status columns truncate while
    six empty columns (data class, lifecycle, availability, criticality,
    group, ownership) consume width and force a horizontal scrollbar;
    header labels themselves truncate ("data clas…", "availabili…").
    Expected: auto-size to content, hide or collapse all-empty columns,
    headers never truncate.
23. **Debug-pill affordances.** "Open Tables panel" / "Collapse Tables
    panel" / "Collapse Legend panel" are unstyled default-button pills stuck
    to edges. Expected: the docked-bar affordance already specified in
    pass 1. — CLOSED (D13a, 2026-08-28: docks collapse into styled
    rails and the full-width Data bar).

## 6. Theme (D13a)

24. **Dark theme is canvas-only.** Toggling dark restyles nodes/canvas while
    the header, time pill, level bar, zoom rail, minimap, tables button, and
    status bar all stay light. Expected: every surface themes together.
    *Superseded (2026-08-27): dark theme is deferred out of the first
    pass (direction "Deferred or removed") — the issue is moot until
    dark theme returns, and this evidence binds it when it does.*
    — WAIVED (D13a, 2026-08-28: dark theme and its toggle removed with
    the deferral; this evidence binds any future dark pass).

## Fixed-baseline notes

- Console is clean on file:// load (the favicon 404 appears only when served
  over HTTP).
- Connections list content (incoming/outgoing with described flows) is good;
  Diff table content is good — these need only the cosmetic fixes above.
