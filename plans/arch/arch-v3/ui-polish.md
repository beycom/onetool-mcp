# UI polish issues — acme report walkthrough

Evidence: 2026-08-25 Playwright session against `plans/arch/wip/acme-report.html`
(fresh build, 1440×900 and 1024×720, light + dark, System/Container levels,
time position 0 and 4, compare vs base). Complements the Phase 3P evidence
baseline in plan.md; issues tagged with the 3P pass that should absorb them.

Tracking: when a pass gates, the architect appends `— CLOSED (D13x,
date)` or `— WAIVED (reason, date)` to each issue it covered. The 3P
exit gate requires every issue closed or waived and a re-run of this
walkthrough confirming the behavior defects (#12–#17) don't reproduce.

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
15. **Time toolbar vanishes.** After a select/close-details sequence the
    entire time pill (slider + compare) disappeared and only a full reload
    restored it. Expected: persistent chrome never disappears as a side
    effect.
16. **Contextual controls jump into unrelated groups.** A "Dependencies"
    button appears inside the level-tabs bar only while a node is selected.
    Expected: selection-scoped actions live with the selection (side panel
    or a selection toolbar), not spliced into a global control group.
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
19. **Floating toolbars overlap the canvas contents.** The time pill and
    level bar float over the diagram and cover nodes at small viewports.
    Expected: reserve their space in the canvas fit (or dock them).

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
    pass 1.

## 6. Theme (D13a)

24. **Dark theme is canvas-only.** Toggling dark restyles nodes/canvas while
    the header, time pill, level bar, zoom rail, minimap, tables button, and
    status bar all stay light. Expected: every surface themes together.

## Fixed-baseline notes

- Console is clean on file:// load (the favicon 404 appears only when served
  over HTTP).
- Connections list content (incoming/outgoing with described flows) is good;
  Diff table content is good — these need only the cosmetic fixes above.
