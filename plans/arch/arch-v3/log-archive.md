# Arch v3 — progress log archive

Older progress-log entries moved out of plan.md (reorg 2026-08-25).
Same append-only content, newest first; plan.md keeps only recent
entries. Continue archiving from plan.md as its log grows.

- **2026-08-28** — D14 subsystem level rename complete; worktree left dirty
  for architect review. Schema-v3 now models the strict System > Subsystem >
  Container > Component > Code chain: YAML, generated ids, resolver clipping,
  validation, the eleven-sheet Excel adapter, and report payloads all include
  Subsystems; container nesting is rejected. The report now uses System /
  Subsystem / Container / Component levels, hides the Subsystem option for
  empty datasets, rolls grouped and ungrouped containers per contract, nests
  Subsystem boundaries inside System boundaries, includes Subsystems in search
  and Data, and keeps D13c card and edge presentation unchanged. The acme model
  has the six prescribed Subsystems and 19 container rewires. Source budget:
  293/1,100 changed Python, TS/TSX, and acme-fixture lines, counted as additions
  plus deletions with tests and generated artifacts excluded. Tests: exactly
  five prescribed cases added; 36 frontend tests passed, arch Python 78 passed /
  540 deselected, smoke 27 passed / 3,209 deselected, and `just lint`,
  `just build-arch-report`, payload regeneration, and CLI acme report generation
  passed. Rule-9 Playwright passed on the regenerated `file://` report at
  1440 x 900: every pass had zero console errors and zero external requests;
  the Detail options were System / Subsystem / Container / Component; the
  Subsystem cold load showed all six Subsystems plus ungrouped container leaves;
  the Container level rendered six Subsystem boundaries nested within System
  boundaries; 44 entities live across the Stage 5 to 4 switch and the viewport
  kept identical transforms. Screenshots:
  `plans/arch/wip/d14-subsystem-cold-load.png` and
  `plans/arch/wip/d14-container-nested-boundaries.png`. Assumptions: the
  execution request confirms the proposed 1,100-line budget; the final
  no-commit instruction controls; rule 8 permits this progress entry as the
  sole design-doc write; schema.md's explicit five-kind chain supersedes the
  index.md summary typo that omits Container; "same dropdown/validation pattern
  as Containers" means the existing milestone validations, since Containers
  have no parent-id dropdown; a container parented to a container reports the
  existing `unresolved_parent` code because the allowed parent sets are now
  Systems and Subsystems; the required Subsystem cold load uses the final acme
  stage where all six prescribed rows are live; Stage stability compares rows
  live at both positions and excludes the intentional removal ghost. Open
  questions: none. Next action: architect gate review, then the #21 payload
  precheck and D13d authoring.

- **2026-08-28** — D13c architect gate PASSED; tree committed. Independently
  re-verified: 33 frontend tests including exactly the five prescribed D13c
  cases (four-side facing anchors + lane separation, direction split under
  all three Relationships with bidirectional counted on both, label
  visibility, one-hop emphasis over tag lens, provider-side grouped port),
  `just lint`, 77 arch py tests, `just build-arch-report` reproduces the
  tree's template byte-for-byte (shasum match), budget confirmed at
  797/1,600 changed source lines (453 tracked + 344 new modules). Code
  review of edgeAnchors.ts (pure four-side anchors, clamped lane offsets),
  splinePath.ts (deterministic visibility-graph obstacle routing, cubic
  path, arc-length label point), edgePresentation.ts (per-direction member
  split, selection > tag priority, port grouping) and the App.tsx wiring
  (entityIcon deleted, kind/external pills, SVG drill icon in the 28 px
  control, per-spline selection with direction, zoom-compensated strokes +
  custom markers, per-member diff statuses) conforms to the pass-3
  contract; CSS confirms readable dim floors (.32–.42), accent-border diff
  markers with no fill wash, subtle boundary tints, and the reduced-motion
  static fallback. Screenshots confirm spline routing with visible
  arrowheads, no orthogonal detours, one-hop selection, and stage-diff as
  increments on a legible base. Minor, not gate-blocking: the edges memo
  depends on `zoom`, so splines re-route on every zoom tick (fine on acme —
  revisit only if large models jank); a dead `getBezierPath` mock entry in
  App.test.tsx; one duplicated `.semantic-edge.is-*` CSS rule pair.
  ui-polish.md annotated: #1–#7 CLOSED; #12 edge-route-highlight residual
  CLOSED. Next action: user confirms the D14 budget (1,100 changed source
  lines proposed) and runs the delegation.md D14 prompt; after its gate,
  the architect runs the #21 payload precheck and authors D13d.

- **2026-08-28** — User screenshot feedback on the current build filed as
  ui-polish.md §7 (#25 shell must be responsive and fill the viewport,
  #26 dock chrome must use standard clean panel patterns instead of
  floating text pills / rotated-text gutters, #27 Tags list capped at 5
  visible rows then internal scroll). All three folded into the D13d
  pass-4 scope; the exit-gate issue sweep now includes them.

- **2026-08-28**: D13c graph elements complete; worktree left dirty for
  architect review. Cards now use the per-depth kind/name/description/fact/count
  anatomy with no entity icons, persistent 28 px drill controls, compact
  external stubs, and diff pills plus narrow markers. Containment boundaries
  use subtle tints and readable kind/name headers. Directional cubic splines
  use floating four-side anchors, separated lanes, deterministic obstacle
  routing, one wide hit rail, count labels, provider-side interface ports,
  zoom-compensated strokes and custom arrows. Selection follows the one-hop
  model with animated outgoing, static incoming, readable dimming, tag priority,
  and a static reduced-motion fallback. Source budget: 797/1,600 changed
  TS/TSX/CSS lines, counted as additions plus deletions with tests and the
  generated bundle excluded.
  Tests: exactly the five prescribed D13c cases added; 33 frontend tests passed,
  including untouched projection/vector suites. `just lint` passed, smoke 27
  passed / 3,208 deselected, arch Python 77 passed / 540 deselected, and
  `just build-arch-report` plus CLI acme regeneration passed. Rule-9 Playwright
  passed over `file://` at 1440 x 900 and 1024 x 720: zero console errors and
  only the local HTML request; System and Container probes found zero card-body
  crossings and zero orthogonal path commands; every cold edge had a custom
  arrow; the minimum 1024 cold-load stroke measured 1.499999 screen px; Full
  and hover labels, attached ports, legible-base Stage diffs, one-hop selection,
  and forced reduced motion all passed. Screenshots:
  `wip/test-results/d13c/system-cold-1440.png`, `container-1440.png`,
  `selection-1440.png`, `selection-reduced-motion-1440.png`, and
  `stage-diff-1024.png`. Relationship switches left every node transform
  unchanged. The acme payload assigns the same orientation under Calls, Data
  flow, and Ownership, so it cannot display an arrow reversal; the synthetic
  direction-split case verifies re-resolution and distinct member groups.
  Assumptions: the execution request confirms the 1,600-line budget; the final
  no-commit instruction controls; rule 8 permits this log entry as the sole
  design-doc write; relationship rows retain stored source-to-target direction
  outside Ownership while interfaces follow the selected direction field; a
  grouped port uses the first interface in deterministic order plus the distinct
  interface count. Open questions: none. Next action: architect gate review,
  then confirm D14's 1,100-line budget and run D14.

- **2026-08-28** — Subsystem level rename designed (user-directed); D14
  authored and slotted before D13c. New naming: System (the overall
  product/platform), Subsystem (optional — a cohesive business
  capability: a logical grouping of related containers), Container
  (independently runnable/deployable app or data store), Component
  (significant module inside a container), Code (implementation
  details). Subsystem is a real entity kind (`subsystems` collection,
  `parent` = a system, id prefix `ss`); containers no longer nest
  (`parent` = system or subsystem); ambiguous-parent validation moves
  to systems×subsystems. Frontend levels 'top-containers'/'containers'
  ("Container"/"Child Containers") → 'subsystems'/'containers'
  ("Subsystem"/"Container"), Subsystem option hidden when the model has
  none; cardSize tiers 280/260/240/240 re-keyed. Design amendments
  landed in schema.md (kinds table, id scheme, canonical YAML, eight
  collections, validation), adapters.md (eleven sheets — Subsystems is
  sheet 5), report.md (fragment table, C4 zoom table + boundary
  chains, Detail dropdown, D13b tier names), ui-polish-direction.md.
  Fact checked first: acme has NO container-in-container nesting (the
  old Child Containers level was vacuous there) and already carries 55
  components, so the component level needs no fixture work; the acme
  delta (authored in the D14 prompt) adds six subsystems inside
  Digital Commerce Platform matching the milestone waves
  (storefront-edge, platform-foundation, catalog-search,
  customer-cart-pricing, transaction-core, back-office-insight) and
  rewires 19 container parents, leaving single-container systems
  ungrouped to exercise the optional path. Sequencing correction made
  while designing: D13c executor work (edgeAnchors/splinePath/
  edgePresentation) appeared in the worktree mid-design — D13c was
  already in flight, so D14 runs AFTER the D13c gate on its baseline
  (D14's rename surface is level keys and kind lists; D13c's anatomy
  rules apply to subsystem cards automatically). Next action: D13c
  finishes and is gated; then the user confirms the D14 budget (1,100
  changed source lines proposed) and runs the delegation.md D14
  prompt.

- **2026-08-28** — D13b architect gate PASSED; tree committed. Independently
  re-verified: 28 frontend tests including exactly the six prescribed D13b
  cases (cardSize wrap-and-grow, initialViewport small/large, shiftViewport
  inside/outside, layout-key + ELK-input stability across stage/relationship/
  lens, edgeless grid packing non-overlap, derived readingDepth boundaries),
  `just lint`, 77 arch py tests, `just build-arch-report` reproduces the
  tree's template byte-for-byte (shasum match), budget confirmed at 407/1,400
  changed source lines (296 tracked + 111 new modules). Code review of
  cardSize.ts (tier widths 280/260/240, injectable measurer, two-line clamp),
  camera.ts (fit/initial/shift pure functions, Read cap + center), layout.ts
  (aspect clamp [1.2,2], spacing 40/72, proportional boundary padding,
  deterministic grid pack with boundary nesting, applyPositions parentId
  guard), and the App.tsx camera wiring (initial framing per layout key,
  selection neighborhood fit as the sole zoom change, ResizeObserver minimal
  pan, D13a refit effect removed) conforms to the pass-2 contract; the
  explicit Fit button still fits the whole graph uncapped. Screenshots
  confirm 41% Far dead-space → 79% Read cold framing with full names at both
  resolutions, Container level readable at default, selection visible beside
  the open Info dock. Minor noted, not gate-blocking: the zoom pill can read
  "79% Far" right at the Read threshold after a neighborhood fit (display
  rounding); revisit only if it shows up in the exit-gate walkthrough.
  ui-polish.md annotated: #8, #9, #10, #11, #15, #17 CLOSED; #12 CLOSED for
  camera (edge-route highlight stays D13c). D13c prompt re-checked against
  the post-D13b tree — its anchors (getSmoothStepPath, entityIcon,
  hash-mod-3 handles) are intact, prompt unchanged and READY. Next action:
  user confirms the D13c budget (1,600 changed source lines proposed) and
  passes the delegation.md D13c prompt to the executor; the architect gates
  the result, then runs the #21 payload precheck and authors D13d.

- **2026-08-28** — D13b canvas composition complete; worktree left dirty for
  architect review. Per-level cards now use uniform widths and measured
  content heights with two-line names; ELK consumes those sizes with the
  specified aspect, spacing, boundary padding, and deterministic edgeless-grid
  path. Cold framing caps at Read, explicit Fit remains whole-graph, and dock,
  selection, and resize camera changes use minimal pan with selection-neighborhood
  fit as the sole automatic zoom change. Source budget: 407/1,400 changed
  TS/TSX/CSS lines (additions plus deletions, tests and generated bundle
  excluded). Tests: exactly 6 prescribed D13b cases added; frontend 28 passed,
  TypeScript/single-file build clean, `just lint` clean, smoke 27 passed / 3,208
  deselected, arch Python 77 passed / 540 deselected. The bundle and acme report
  were regenerated. Rule-9 Playwright passed at 1440 x 900 and 1024 x 720 over
  `file://`: zero console warnings/errors, only the local HTML request, cold
  System and Container framing at Read, 13 live Container cards visible,
  stage/relationship switches moved no common nodes or viewport, dock
  open/close/resize and viewport resize preserved zoom and selection visibility,
  and the edgeless observability drill rendered its deterministic grid path.
  Screenshots: `wip/test-results/d13b/1440-before.png`, `1440-after.png`,
  `1024-cold.png`, `info-selection-visible.png`, `container-default.png`.
  Assumptions recorded: the execution request confirms the proposed 1,400-line
  budget; the explicit "Do not commit" instruction controls over the earlier
  "including commit" wording; ELK samples the visible-cell aspect ratio when a
  `(timeline, level, drill)` key is first laid out so dock changes cannot move
  cards; cold whole-graph framing means the current live graph, so a
  stage-removed diff ghost does not displace the initial camera while explicit
  Fit still includes every rendered node. Open questions: none. Next action:
  architect gate review, then run the already-authored D13c prompt.

- **2026-08-28** — D13c authored ahead of the D13b run (user-directed;
  the prompt still waits for the D13b gate). Normative spec "Polish
  contract — pass 3: graph elements (D13c)" added to report.md,
  grounded in the current render layer: card anatomy per depth with
  kind pills and `entityIcon` deleted, persistent ≥24 px drill
  control, boundary stubs as compact external cards, subtle-tint
  containment boundaries, bezier-only splines with geometry-derived
  floating anchors (`edgeAnchors` pure function, lane separation)
  replacing the hash-mod-3 left/right handles, per-direction spline
  split of aggregated edges (bidirectional members count on both),
  zoom-compensated strokes + custom arrowheads, neutral-at-Full /
  always-on-selection label pills, provider-side interface ports,
  IcePanel one-hop selection with reduced-motion fallback, stage-diff
  as increments on a legible base; five prescribed tests. Scope
  boundaries fixed against neighbors: pass 2's layout/camera code and
  projection.ts untouched (direction split happens in App-side edge
  building); the Δ change-popover survives until pass 4 moves field
  changes into Info. D13c prompt READY in delegation.md, run-after =
  D13b gate, proposed budget 1,600 changed source lines (confirm
  before running). ui-polish #1–#7 are D13c's gate checklist. Next
  action unchanged for execution order: user confirms the D13b budget
  and runs D13b first; D13c follows its gate.

- **2026-08-28** — D13a architect gate PASSED; D13b authored; tree
  committed. Gate evidence, independently re-verified: 22 frontend tests
  (including exactly the four prescribed D13a cases), `just lint`, 77
  arch py tests, `just build-arch-report` reproduces the tree's
  template diff (38/38 lines), budget confirmed at 974/1,800 changed
  source lines (817 tracked + 157 new components). Code review of
  view.ts (retired keys + `select` validation, replaceState writes),
  layoutPreferences (schema v2, dock limits), App.tsx (Escape order
  search → menus → selection+Info, revealInfo/closeInfo, 1024 transient
  View collapse, hidden testid spans), ViewDock/GlobalSearch/Icons
  conforms to the pass-1 contract; dark theme fully absent from
  styles.css; screenshots at 1440×900 and 1024×720 confirm the docked
  shell with the selection visible beside the open Info dock. Residual
  ugliness (tiny truncating cards, orthogonal detours, snake_case Info
  labels) is pass 2/3/4 scope by design. ui-polish.md annotated: #14,
  #18, #19, #23 CLOSED, #16 chrome-half CLOSED, #24 WAIVED (dark theme
  deferral); #15/#17 stay for the D13b-gate walkthrough re-check. D13b
  authored the same day: normative spec "Polish contract — pass 2:
  canvas composition (D13b)" in report.md (card geometry via
  injectable-measurer cardSize, ELK tuning + grid packing for edgeless
  drill sets, initialViewport framing capped at Read, thresholds
  re-derived from the type scale, shiftViewport minimal-pan camera
  replacing the D13a refit effect, six prescribed tests) and the D13b
  prompt READY in delegation.md with a proposed budget of 1,400 changed
  source lines (confirm before running). Next action: user confirms the
  D13b budget and passes the delegation.md prompt to the executor; the
  architect gates the result, then authors D13c.

- **2026-08-27** — D13a rule-9 browser gate PASSED on retry. OneTool
  Playwright verified the regenerated `file://` acme report at 1440 x 900
  and 1024 x 720 in light theme: clean console in every pass; no external
  requests (the report file itself was the sole network entry); View and Data
  collapse/open, pointer resize, localStorage persistence, and double-click
  default restore all worked; Map opened and closed its attached minimap;
  Stage changed the fragment and projected node count; global search ranked
  and selected a live row, restored focus to its trigger, and obeyed the
  temporary-UI-first Escape order. At 1024, selecting Legacy Commerce wrote
  `select=systems:legacy-commerce`, opened Info, transiently collapsed View,
  and left the selected node fully inside the measured Canvas rectangle;
  closing Info cleared selection and restored View. Screenshots:
  `wip/test-results/d13a/1440-before.png` (baseline regenerated from
  c37e3d05), `1440-after.png`, and `1024-info-open.png`; visual inspection
  found no D13a shell defect (card density remains pass 2). Playwright closed.
  Open questions: none. D13a executor definition of done is complete; next
  action: architect gate review, then author D13b.

- **2026-08-27** — D13a app-shell implementation complete; browser gate
  blocked by a shared Playwright profile lock. The report now has the compact
  identity/search header, persisted View/Info/Data docks, responsive transient
  View collapse at 1024 px, dropdown-based Detail/Stage/Relationship controls,
  the tags lens and Copy view link in View, ranked global search, the lower-left
  Map/Fit/zoom row, light-only tokens and inline SVG chrome icons. Removed
  viewer fragments diagnose and ignore old keys; validated row selections use
  `select`. Source: 974 changed TS/TSX/CSS lines / 1,800 budget (additions plus
  deletions, tests excluded). Tests: exactly 4 prescribed D13a cases represented
  within 22 passing frontend tests; TypeScript and single-file build clean;
  `just lint` clean; smoke 27 passed / 3,208 deselected; arch Python 77 passed /
  540 deselected. Bundle rebuilt and acme report regenerated. Rule-9 evidence is
  incomplete: OneTool's Playwright proxy reports its shared Chrome profile is
  already in use by an older MCP process, including after the one allowed proxy
  restart, so the 1440 x 900 and 1024 x 720 interaction pass and required
  screenshots were not captured. Assumptions: the request to execute confirms
  the 1,800-line budget; the final no-commit instruction overrides any earlier
  commit wording; rule 8 is the explicit exception allowing this entry in the
  otherwise read-only design docs; dock defaults are View 280 px, Info 360 px,
  Data 280 px with existing practical bounds; search ranks exact, prefix, then
  substring matches case-insensitively; "at 1024 px" means 1024 px and below;
  responsive View collapse is transient so closing Info restores the persisted
  user state; the `select=<kind>:<id>` grammar covers payload-backed entity and
  interface rows, while aggregated spline selection stays local because it has
  no payload row id; searched interfaces center their rendered aggregate
  endpoints. Open questions: none. Blocker: release the shared Playwright
  browser profile, then run the rule-9 gate and capture the three screenshots
  before marking pass 1 complete.

- **2026-08-27** — UI direction reconciled into the contracts
  (architect). `ui-polish-direction.md` (confirmed 2026-08-27) is now
  the decision source for the report/sequence UI; registered in Ground
  truth. report.md: new "Confirmed UI direction" section; "The time
  slider is the hero" replaced by the Stage-dropdown section; fragment
  table loses `scope`/`hops`, `compare`, `theme` and gains `select`;
  the Wave-2 UI contract is banner-superseded where it conflicts
  (zoom rail placement, fullscreen, dark theme, floating legend,
  500 px target); the D13a "Polish contract — pass 1" is marked
  superseded pre-run. sequence.md: SEQ-* contract rewritten to the
  direction — controls move into View (Scenario dropdown, compact
  playback, local search, participant eye-hide), Map opens a vertical
  overview, Info/Data own message details and payload files; SEQ-GROUP
  (C4 bands, group collapse, merged lifelines, retargeting, self-loop
  aggregation), SEQ-NAV (floating navigator), and the `collapse`
  fragment key are removed; SEQ-PART records the containment-as-
  header-context rule. plan.md/delivery.md: 3P passes re-scoped to
  implement the direction (pass 1 = app shell; D13a spec/prompt
  superseded — re-author before issuing), the 500 px target replaced
  by the 1024 × 720 floor, 3S gate updated. delegation.md: D13a
  status → SUPERSEDED, prompt body collapsed. ui-polish.md: direction
  note added; #14/#16/#18/#24 carry supersession notes. designs/:
  REMOVED entirely (user-directed, same day) — the direction doc is
  the sole design source; all artboards, canvas.json, and the
  published report-ui-polish.html bundle remain in git history
  (d7db02a0). D13a re-authored the same day: normative spec "Polish
  contract — pass 1: app shell (D13a)" in report.md, prompt READY in
  delegation.md with a proposed budget of 1,800 changed source lines
  (confirm before running). Next action: user confirms the D13a
  budget and passes the delegation.md prompt to the executor; the
  architect gates the result with screenshots at 1440×900 and
  1024×720, then authors D13b.

- **2026-08-26** — New capability registered (user request): sequence
  messages and model interfaces can link to message files — sample
  request/response payloads (xml, json, csv) — rendered
  syntax-highlighted in the report. Tracked as a new Phase 3S architect
  design item (amendments to schema.md, sequence.md, report.md); the
  held D12a prompt gets re-scoped to include the refs before it runs;
  the 3S gate now checks a highlighted message file opens. No 3P
  impact — polish passes proceed unchanged; next action still: user
  confirms the D13a budget and runs it.

- **2026-08-25** — UI walkthrough evidence captured (architect,
  user-directed): full Playwright pass over the acme report per
  wip/notes/test-ui.md (both themes, System/Container levels, time
  scrub, compare, tables, node+edge selection, 1440×900 and
  1024×720). Result: `ui-polish.md` — 24 observed→expected issues
  tagged D13a–D13d, registered in Ground truth. Confirms the 3P
  baseline and adds measured edge values (all edges 1px `#B1B1B7`,
  no marker-end, zero labels) plus six behavior defects now folded
  into the pass bullets: selection hidden behind the details panel,
  legend self-expanding on select, time toolbar vanishing after
  select/close, time-pill reflow while scrubbing (→ pass 2 with
  tests); Escape not closing overlays, "Dependencies" spliced into
  the level bar (→ pass 4). Pass-4 precheck added: confirm the
  payload carries edge endpoint/interface data before speccing the
  connection-details fix (#21). Exit gate now requires every
  ui-polish.md issue closed or waived and a re-run of the
  walkthrough. D13a is untouched by all this and stays READY —
  next action unchanged: user confirms the D13a budget and runs it;
  the architect folds the tagged issues into each pass spec as it
  is authored.

- **2026-08-25** — plans/arch reorg (user-directed). Deleted
  `react-flow-poc/` (198M incl. node_modules; superseded by the
  implemented app, tracked files in git history). Created
  `plans/arch/archive/` holding the arch-v2 design history and the
  v2-era wip docs (design/ideas/requirements/mocks + superseded
  interactions.md); `wip/` keeps only acme-report.html and
  acme-arch-v2.xlsx. arch-v3 tracking compacted: phases 0–3R waves 1–2
  collapsed to a summary section, older log entries moved to
  log-archive.md (keep ~10 inline, archive the rest — new standing
  rule), answered open questions compacted, ground-truth table
  refreshed. delegation.md 873→~290 lines: completed prompt bodies
  (D1–D10b) collapsed to outcome headers (full prompts in git
  history), status table refreshed, standard rules updated (v2 donor
  harvesting closed, v1 references removed), all forward gates renamed
  to the Phase 3P exit gate. issues/ split: resolved p1/p2 files →
  issues/resolved/ (relative links fixed), index rewritten; reference
  screenshots stay (cited by 3P specs). `git worktree prune` cleared
  the dead arch-v2 entry. Next action: unchanged — user confirms the
  D13a budget and runs it.

- **2026-08-25** — Phase-3 re-gate user half folded into the 3P exit
  gate (user decision); the wave-2 checkboxes are closed on that
  basis. D13a authored: normative spec added to report.md ("Polish
  contract — pass 1: visual foundation" — tokens, mono-for-data
  typography split, one shared card recipe, inline-SVG chrome icons,
  dark/light contrast targets, humanised footer with visually-hidden
  node-id dump, docked tables bar; pure presentation, npm test must
  pass unchanged) and the D13a prompt registered READY in
  delegation.md with a proposed budget of 700 changed source lines
  (confirm before running). D13b–D13d remain GATED pending their
  specs. Next actions: user confirms the D13a budget and runs it;
  architect gates D13a with before/after screenshots, then authors
  D13b (canvas composition — the highest-risk pass).

- **2026-08-25** — Phase 3P (UI polish) planned, user-directed: the
  wave-2 UI works but is clunky, so D11, D12 (both halves; the issued
  D12a prompt is ON HOLD), and D8 are delayed until polish completes.
  Architect critique captured from fresh acme-report screenshots
  (dead-space fit at 37%, 80%-empty 250×168 nodes that still truncate
  names, rectangular edge detours reading as phantom boundaries,
  content hidden behind the legend, meaningless single-color legend
  swatches, dev-tool chrome, MAP→READ threshold mismatched to layout
  scale). Four passes registered as D13a–D13d: (1) tokens / type /
  chrome, (2) canvas composition — layout, fit, density (highest
  risk), (3) graph elements — nodes / edges / boundaries, (4) panels,
  overlays, empty states + motion sweep; exit gate re-runs the
  phase-3 story test with a "looks deliberate" bar. Next actions:
  architect authors the D13a spec (report.md amendment) + prompt with
  a budget agreed with the user; the phase-3 re-gate user half can run
  on the current build or fold into the 3P exit gate at the user's
  choice.

- **2026-08-25** — Gate findings fixed (architect, user-directed), left
  uncommitted with the D10 tree. (1) Drill root carve-out: `drillAt`
  now keeps the drilled entity as a leaf endpoint inside its own
  boundary when a connection is authored on the entity itself (same
  carve-out as `withBoundaries`); drilling Commerce Monolith shows
  24 nodes / 12 connections instead of 11 / 0. Regression test added
  (22 frontend tests). (2) The finding-2 "legend overlap" was
  re-diagnosed: no geometric overlap existed (the measurement had
  caught scrolled-out legend rows); the real defect was the
  Dependencies / Reset view cluster buttons missing the themed control
  styling (raw light-grey in dark theme) — fixed by adding
  `.cluster-content > button` to the control selector. (3) NEW, found
  while verifying: a cross-state layout race (pre-existing D10b, INT-
  STATE-06 violation) — on drill/level/timeline transitions the new
  projection rendered against the previous layout's positions,
  giving React Flow parentIds for boundaries absent from the new
  graph (114 buffered "Parent node … not found" console warnings,
  reproducible via drill → Back → level switch). Fixed by keying the
  layout result (`layoutResult {key, positions}`) and applying
  positions only when the key matches the current
  timeline/level/drill; the transition sequence is now console-clean.
  Checks: 22 frontend tests, tsc clean, `just lint`, 77 arch py tests,
  bundle rebuilt, acme-report.html regenerated and browser-verified
  (fresh tab: zero console messages, zero external requests; note
  file:// caches aggressively — hard-reload when eyeballing).
  Next action: user half of the phase-3 re-gate.

- **2026-08-25** — Architect half of the phase-3 re-gate run on the
  uncommitted D10a+D10b tree. Re-verified independently: 21 frontend
  tests, `just lint`, 77 arch py tests, `just build-arch-report`
  (rebuild reproduces the tree's template byte-diff), acme report
  regenerated. Code review of the semantic files (projection, layout,
  view, types, zoom) conforms to the Wave-2 UI contract. Browser
  spot-check on the acme report over file://: console clean and zero
  external requests across every interaction; four C4 levels with
  contract labels; nested boundary boxes with the
  system-as-edge-endpoint leaf carve-out working; drill with
  breadcrumb/Up/Back, `drill` fragment, history push, scope disabled;
  docked side panel Details/Connections with member rows and Open
  dependency view; deps view (columns, totals, picker, `deps` fragment,
  history); legend lens with `lens` fragment, Clear, dim-not-hide;
  dark theme flat; retired-at-position selection shows empty live
  connections correctly. Two findings for the joint gate: (1) MEDIUM —
  `drillAt` drops connections whose inside endpoint is the drilled
  entity itself (`directChildRepresentative` returns null for the
  root); acme authors every interface on containers, so drilling any
  leaf-childful container (e.g. Commerce Monolith) shows its children
  with 0 connections in a single column — the withBoundaries leaf
  carve-out should extend to drillAt. (2) MINOR — with the side panel
  open at ~1100 px the floating legend panel overlaps the projection
  cluster's Dependencies/Reset view buttons (two floating overlays
  collide as the canvas shrinks). Also worth a reading check at the
  gate: legend counts include rolled-up member tags, so component tags
  appear at System level. Next action: user half of the gate; decide
  whether findings 1–2 are fixed pre- or post-commit.

- **2026-08-25** — D10b complete and left uncommitted for gate review. The
  report now has the four-level C4 projection, hierarchical ELK containment
  boundaries, direct-child drill with history and breadcrumbs, five-part
  depth-gated entity boxes, distributed edge anchors and selection flow,
  a persisted tag-lens legend, and the dependency focus view. Source: 639
  changed TS/TSX lines / 1,900 budget (additions + deletions, tests excluded,
  measured above the 785-line D10a baseline). Tests: 3 added; `npm test` 21
  passed, `just lint` clean, `uv run pytest tests/unit/tools -k arch` 77 passed
  / 540 deselected, and `just build-arch-report` clean. The CLI-regenerated
  acme report passed the rule-9 `file://` browser gate: all four C4 levels and
  deeper-level boundaries, drill / Up / Back, outgoing animation and static
  incoming emphasis, reduced-motion fallback, tag OR lens without hiding,
  dependency columns / totals / picker, FULL-depth facts and edge labels,
  500 px responsive controls, clean console, and zero external requests.
  Assumptions: D10a's complete, gate-verified worktree state satisfies D10b's
  "committed" prerequisite because D10a was deliberately left uncommitted for
  the same review; the user's final no-commit instruction overrides the
  introductory request for a commit; users remain plain nodes when connected
  across a drill boundary because the C4 contract keeps users plain at every
  level, while non-user external endpoints become system boundary stubs; a
  childful ancestor that is itself a canonical edge endpoint keeps a distinct
  leaf endpoint nested inside its boundary so the boundary box never becomes
  an edge endpoint; adding the legend to layout schema v1 intentionally makes
  older stored layouts without that required panel fail validation and reset.
  Open questions: none. Next action: phase-3 re-gate by architect and user.

- **2026-08-25** — D10a complete and left uncommitted for gate review. The
  report now has one-line chrome, canvas control clusters, a fit/zoom/depth/
  fullscreen rail, plain light/dark backgrounds, a docked Details/Connections
  panel with aggregated-edge members, reusable persisted resize/collapse/reset
  panels, and the v2-parity AG Grid table controls. MAP/PATH/LENS and the
  `mode` fragment key are removed; fragment restoration filters unknown ids
  through console diagnostics and keeps local layout/camera values out of the
  URL. Source: 785 changed TS/TSX lines / 1,400 budget (additions + deletions,
  tests excluded). Tests: 4 added; `npm test` 18 passed, `just lint` clean,
  `uv run pytest tests/unit/tools -k arch` 77 passed / 540 deselected, and
  `just build-arch-report` clean. The CLI-regenerated acme report passed the
  rule-9 `file://` browser check: compact and 500 px layouts, panel resize /
  collapse / double-click reset persistence, fullscreen and Escape ordering,
  quick filter / multi-sort / hide / pin persistence, both plain themes,
  aggregated-edge selection, clean console, and no external requests.
  Assumptions: the explicit no-commit instruction and rule 8 override the
  prompt's introductory mention of a commit; AG Grid Community's custom
  kind/status checkbox filters satisfy the set-filter requirement without an
  Enterprise runtime dependency; the existing three-level roll-up contract
  governs the D10a C4 control despite `Views` reserving `top-containers`; the
  bottom panel starts collapsed, preserving the prior closed-table state;
  invalid stored column ids reject that table layout as a whole and restore
  defaults; double-click resets size without changing collapse state; the
  disabled dependency action uses an `aria-describedby` reason until D10b.
  Open questions: none. Next action: architect gate review, then D10b.

- **2026-08-25** — D12a parser-vector fixture authored (architect) and the
  D12a prompt issued (READY; run serially with D10a/D10b — payload.py
  overlap). Fixture at `tests/unit/tools/fixtures/arch/sequence/`:
  minimal model.yaml (validates 0 errors; its 3 unused-milestone warnings
  are expected — milestones are referenced only by flow docs), eight flow
  docs + a crossdoc duplicate-id pair, expected.json (findings as
  severity/code/line, compiled entries by deep equality), README with the
  driver contract. Coverage: the full compositional arrow matrix with
  kind derivation, activation-mode switching, frames/aliases/dividers/
  notes/multiline, deferred + external endpoints, all 15 reserved-word
  errors, and the four vector-pinned warnings. Line anchors were computed
  by content lookup (scratch tooling, not kept), and each spot-checked.
  Design decisions taken while authoring, folded into sequence.md same
  day: finding-code registry (reuse missing_required/duplicate_id/
  unresolved_milestone/invalid_interval; new reserved_keyword,
  parse_error, invalid_id, unresolved_participant, unresolved_interface,
  unpaired_defer; warnings implicit_participant, dangling_interval,
  crossed_reply, unmatched_activation, large_scenario with pinned >30
  participants / >300 items thresholds); auto-activation pairing = LIFO
  per direction pair over flattened document order, crossed_reply only in
  auto scenarios; `+` only on the receiving end and `-` only on the
  sending end (wrong-end/bidi markers are parse errors); at least one
  arrow head required and no `x` with a left head; right-edge external
  messages carry `edge: "right"`; implicit ad-hoc participants compile
  id-only; docs process in sorted filename order and `sequences` sorts by
  flow id, with the key OMITTED when empty — existing payloads and the
  report bundle stay byte-identical, keeping D12a off D10's surface.
  Budget carried into the prompt: 500 changed source lines (the
  provisional ~500 from sequence.md; adjust before running if needed).
  Next actions: user runs D10a (then D10b), D12a any time serially with
  them; architect's next artifacts are the D12b layout vectors + acme
  flow docs (after the phase-3 re-gate).

- **2026-08-25** — Wave-1 gate PASSED. The Excel hand-edit half was run by
  the architect as the scripted equivalent (openpyxl standing in for hand
  edits, at the user's request; this also closes the folded-in phase-2
  hand-run). Exercise on the exported ten-sheet acme workbook: added
  milestone `acme-2032-fraud-consolidation` (+ Timelines row), retired
  `fraud-provider` via inclusive `end_in: acme-2031-complete-cutover`,
  added a complete-record revision row for `search-service`
  (name + description), added a blank-id container, added a user `Notes`
  sheet. Import assigned `c-0001` and reported it under `assigned_ids`
  with the row index; diff 2031→2032 shows exactly the edits and the
  correct cascade — removed fraud-provider with `clipped_by:
  fraud-provider` on `fraud-api`, `provider-fraud-models`, and
  `payment-to-fraud`; changed search-service on name/description only;
  added c-0001; nothing spurious. Imported YAML validates 0 errors / 27
  warnings (3 new clipping advisories from the retirement). In-place
  export preserved the Notes sheet, resized the Containers table ref to
  the two new rows, and the workbook re-imports model-equal to the YAML.
  Residual caveat (not a blocker): the `arch_end_milestones`
  VSTACK/FILTER dropdown is still unverified in real Excel — eyeball it
  next time a generated workbook is opened there. Next actions: user runs
  D10a (READY); architect authors the D12a parser-vector fixture.

- **2026-08-25** — D9b architect gate review PASSED; committed by architect
  (rule 8). Re-verified: 77 arch tests, 14 vitest, `just lint` clean,
  standalone import loads zero runtime modules, template rebuild
  byte-identical, both checked-in payloads (projection fixture + acme dev
  payload) regenerate identically via the CLI, acme validates 0 errors /
  24 clipping warnings. Code review: ten C4 sheets with renamed headers;
  blank-id import builds a `model_construct` draft, runs
  `assign_missing_ids`, writes ids back into raw with id-cell source
  locations, and reports the map as `assigned_ids`; per-field direction
  dropdowns (allow-blank = omitted default); payload live/clip segments
  inclusive with the `base` selector at position 0; projection `within`
  inclusive, kind-qualified id index, cycle-guarded parent walk through
  Code, ancestor-of-kind roll-up. Q7 conversion confirmed in the vector
  model (`sysL` `end_in: m1`, `subG` `end_in: base`). All four executor
  assumptions ACCEPTED: `assigned_ids` key naming (adapters.md names no
  key), Code kept empty in the projection fixture (nested/Code round-trip
  covered by the new Excel test), `end_in` dropdown as a VSTACK/FILTER
  defined name prepending `base` (noted: dynamic-array functions need
  Excel 365; elsewhere the validation degrades, cells stay editable), and
  no-commit per rule 8. Wave-1 gate: architect half done — remaining is
  the user's Excel hand-edit of the exported acme workbook (the folded-in
  phase-2 hand-run). Next actions: user runs the hand-edit gate exercise,
  then D10a (READY); architect's next artifact is the D12a parser-vector
  fixture (unblocked now).

- **2026-08-25** — Sequence DSL: notes / logic / dividers / multiline
  closed out (user follow-up on the davidje13 feature set). Adopted:
  `note left of` / `note right of` placements (Mermaid parity), davidje13
  `if`/`else if`/`else` and `repeat` as aliases normalized to alt/loop,
  a `group` labeled frame (vertical message-run annotation — distinct
  from Mermaid's reserved `box`, which is horizontal participant grouping
  and stays model-owned), divider types `line`/`space`/`delay`/`tear`,
  and multiline labels via `\n` / `<br/>` escapes (labels stay single
  physical lines). Rejected with named errors or deferred: `note
  between`, `state over`, `text left/right`, `divider … with height`
  (layout owns spacing), inline markdown in labels. Payload: frame kind
  `group`, note `placement`/`at`, divider `style`, pre-unescaped line
  breaks. sequence.md DSL / payload / deferred sections updated.

- **2026-08-25** — Sequence DSL revised (user decision, supersedes the
  "mermaid-adjacent" tokens in the entry below): **union grammar** — the
  Mermaid sequence syntax base (`participant … as`, `actor`, alt/opt/loop,
  `note over`, comments) with arrows generalized **compositionally**
  (optional left head `<`/`<<`, line `-`/`--`/`~`, optional right head
  `>`/`>>`/`)`/`x`) so every form either tool publishes is valid: `->`,
  `->>`, `-->>`, `-)`, `-x`, reversed `<-`, bidirectional `<->`/`<<-->`,
  wavy `~>`, unlabeled arrows. Kind derives by rule (x → lost, `)`/`~` →
  async, `--` → reply, else sync); left heads reverse direction. Explicit
  `+`/`-` activation markers are **supported** (per-scenario manual mode —
  any marker disables auto-activation for that scenario); davidje13
  extensions adopted: `[`/`]` external endpoints both directions,
  `...id` deferred async delivery (crossing, rendered diagonal),
  `divider [delay]: label`. Reserved words with named parser errors:
  par/critical/break/box/autonumber/activate-deactivate statements/create/
  destroy/rect/link; simultaneity markers rejected (break the monotonic
  order playback and `step` depend on). Confirmed stance: entity ids,
  interface links (`[i-…]`), and self-defined ad-hoc participants coexist
  in one flow. Licensing recorded in sequence.md "Donors and licensing":
  grammars reimplemented from published syntax docs only — LGPL davidje13
  code never copied; MIT geometry fragments harvestable with attribution.
  sequence.md DSL / compilation / payload / SEQ-KIND / deferred sections
  updated. Parser-vector fixture (next architect artifact) must cover the
  compositional arrow matrix, activation-mode switching, and
  reserved-word errors.

- **2026-08-25** — Sequence-diagram aspect added (user-directed):
  new design doc sequence.md joins the set (index.md table, delivery.md
  rule 1 now "six documents"), new Phase 3S here, D12a/D12b registered
  GATED in delegation.md, report.md deferred-list entry reversed and its
  Views table extended with the sequence fragment keys, delivery.md gains
  the Phase 3S entry and drops "sequence attachments" from phase 4.
  Decisions: flows are Markdown docs in `sequences/` beside the model YAML
  (frontmatter id/name/interval, `##` headings = scenarios, ```seq fences)
  — never carried by Excel; DSL is mermaid-adjacent (`->` sync, `-->`
  reply, `-)` async, `[i-…]` interface links, alt/opt/loop, auto-
  activation); Python parses/validates/compiles a `sequences` payload
  section (parser vectors = D12a control); renderer is **custom**: pure
  deterministic `seqlayout.ts` + React header row reusing the canvas
  entity-box component + one SVG layer — library survey (2026-08-25 web
  re-survey + the 2026-08-11 POC spike) rejected davidje13/SequenceDiagram
  (LGPL-3.0), Mermaid (multi-MB black-box SVG, no coordinate API), ZenUML
  (own React 19 + Tailwind, 869 KB gzip POC-measured, fragile hooks), and
  js-sequence-diagrams (dead, remote fonts); no off-the-shelf option
  supports custom participant boxes + the interaction list. SEQ-* contract
  covers playback, sticky headers, C4 group collapse (canvas boundary
  styling), focus, hide/show (recorded divergence from the canvas
  dim-only rule), scenario tabs, navigator, vertical minimap, search,
  sync/async arrow shapes, side-panel + time-slider integration.
  Provisional budgets ~500 py / ~2,200 TS/TSX — re-agreed at prompt
  authoring. Next action for the aspect: architect authors the parser
  vectors (D12a runnable after the wave-1 gate); D12b waits for the
  phase-3 re-gate. The immediate plan sequence (D9b gate → D10a/D10b) is
  unchanged.

- **2026-08-24** - D9b complete and left uncommitted for gate review. Excel
  now exports and imports the ten C4 sheets, assigns blank ids through
  `assign_missing_ids`, reports the assignment map, and supplies the new
  interval and direction dropdowns. Payload compilation emits seven
  collections with inclusive live/clip segments and omitted direction
  defaults. The frontend uses systems/containers/components/code, walks
  nested containment through Code, treats segment ends as inclusive, exposes
  Base at position 0, and uses the new direction defaults. Projection and
  acme payload fixtures plus the bundled report were regenerated. Source
  churn: 334 / 600 lines. Tests: Excel 2 existing + 2 new, payload 2, full
  focused suite 77 passed, vitest 14 passed, smoke 27 passed; `just lint` and
  `just build-arch-report` clean. File report verification reached position 2,
  compare=base, level=containers, and one-system scope; console errors 0 and
  external requests 0. Assumptions: the import result key is `assigned_ids`;
  Code stays empty in the projection fixture; the `end_in` dropdown uses a
  defined dynamic range that prepends `base`; per the user's answer to Q7,
  inclusive schema behavior updates the alternate-timeline expectations; no
  commit or staging under the user's final instruction. Open questions: none.

- **2026-08-24** - D9b paused at open question 7 after the first vector run.
  Partial implementation converts Excel, payload compilation, frontend
  projection, and fixtures to the wave-1 schema. Python Excel/payload tests:
  6 passed. Vitest: 12 passed, 2 failed only because the mandated `sysL`
  conversion changes the alternate-timeline state and diff. Source churn is
  315 / 600 lines. Assumptions made before the conflict: (1) the Excel import
  result exposes the exact `assign_missing_ids` map as `assigned_ids`; (2)
  `code: []` satisfies the projection fixture's new KINDS entry because adding
  a Code row would change expected id sets; (3) the `end_in` dropdown uses a
  workbook defined name that prepends `base` to the milestone range; (4) the
  user's final instruction overrides the prompt's commit wording, so no commit
  or staging will occur. Open question: 7. No commit or staging performed.

- **2026-08-24** — D9a interim architect review PASSED; committed by architect
  (rule 8). The formal wave-1 gate still reviews D9a+D9b together after D9b —
  this interim pass unblocks D9b on a clean tree. Re-verified: 71 arch tests
  pass with exactly the 4 contracted D9b failures (excel ×2, payload ×2);
  `just lint` clean; standalone import loads zero runtime modules; acme CLI
  validate: 0 errors / 24 clipping warnings; old names survive only in
  D9b-owned excel.py/payload.py. Code review: inclusive-bound governing_row,
  base=0 position mapping, recursive nested-container clipping with cycle
  guard, advance's governing-row-at-through keep + end_in:through→base
  rewrite, ambiguous-parent/containment-cycle/reserved-base validation, and
  ids.py max+1 scheme all match schema.md; resolver suite conversion is
  faithful (renames + 4 new tests, no assertion dropped; from==until became
  the base-end rejection case). Fixture conversion spot-checked: `until: m` →
  previous-milestone `end_in`, both first-milestone retirements → `end_in:
  base`; acme story intact (edge foundation +23/−2, cutover −27, tail diff
  empty). All three executor assumptions ACCEPTED (D9b-file exclusion per
  prompt; budget = source churn excl. tests/fixtures, 557/700; ids API shape
  — model_construct for blank-id rows is the intended D9b import pattern).
  Next action: user runs D9b (prompt READY in delegation.md).

- **2026-08-24** — D9a landed uncommitted: renamed the core model to C4
  systems/containers/components/code, replaced temporal fields with inclusive
  `start_in`/`end_in` over position-0 `base`, added Provider/Consumer direction
  defaults, generalized resolver clipping through nested containers and code,
  added containment/parent/base validation, updated baseline advance, and added
  `ids.py` generated-id assignment. The acme fixture was mechanically converted
  and validates with 0 errors (24 expected clipping warnings). Assumptions:
  (1) D9b-owned `excel.py`, `payload.py`, their tests, frontend sources, and the
  generated report bundle are excluded from D9a's clean sweep because the prompt
  explicitly requires their tests to remain broken until D9b; (2) the 700-line
  budget counts source diff churn (additions + deletions), excluding tests and
  fixtures; (3) `next_id(kind, ...)` takes canonical plural collection names,
  and `assign_missing_ids` mutates the supplied Architecture while returning the
  specified assignment map, omitting collections with no assignments. Source
  churn: 557 / 700 lines. Existing collected
  tests before -> after: model 1 -> 1, yamlio 6 -> 8, resolver 42 -> 46,
  validate 11 -> 14, facade 1 -> 1; new ids suite: 1 (71 focused tests total,
  all pass). Verification: `just lint` clean; scoped mypy clean for seven core
  source files; full `pytest tests/unit/tools -k arch`: 71 passed,
  4 expected D9b failures (2 Excel, 2 payload). Open questions: none. No commit
  or staging performed per user instruction.

- **2026-08-24** — Wave-2 architect step complete: report.md gains the
  normative "Wave-2 UI contract (v1)" (D10a chrome/panels/tables + D10b
  canvas subsections), the Views fragment table is reworked (four C4
  `level` tokens, `drill`/`deps`/`lens` keys, `mode` retired), and "Canvas
  and look" reflects the wave-2 profile. Design decisions taken while
  folding: C4 zoom maps to internal rollUp levels systems /
  **top-containers (new: representative = nearest ancestor container whose
  parent is a system)** / containers / components so the read-only
  projection vectors keep their level names; drill = direct-children
  projection with system-representative boundary stubs, fragment-encoded
  and history-pushing; MAP/PATH/LENS mode buttons removed (LENS → tag
  legend lens, PATH → D11, MAP = default — resolves the D7 gate note);
  reading depth MAP/READ/FULL at <100/100–174/≥175% gates entity-box
  content; measured Archify edge/opacity/duration values adopted as the
  styling reference; facts line = two most frequent property keys in
  scene. interactions.md mined per Q6: adopted clauses in the contract's
  "Interaction baseline", five recorded overrides (tags-only legend,
  dependency view over INT-FOCUS-10..14, docked panel over the
  Relationship Passport and the floating-panel machinery, mode removal);
  doc header marked SUPERSEDED. delegation.md: D10a/D10b prompts issued
  (READY after the wave-1 gate; budgets 1,400/1,900 changed TS/TSX lines
  — agreed with the user same day). Next action: user runs
  D9a → D9b → wave-1 gate, then D10a → D10b → phase-3 re-gate.

- **2026-08-24** — Outstanding-questions review with the user; all resolved
  except Q3 (stays deferred to the phase-3 re-gate). Q2 marked answered
  as-shipped. Wave-2 decisions (recorded in the issue files and in open
  questions 4–6; folded into report.md at the D10 architect step): legend
  **dims only**, graduated tiers, driven by **tags** as the first pass —
  no hide/solo mode; nested groupings get **no in-place expand/collapse** —
  drill navigation stays, plus a 4-level **"C4 zoom"** control (System /
  Container / Child Containers / Component) replacing the flat level
  selector; `wip/interactions.md` is mined for its useful INT-* clauses
  into report.md and left superseded, issue text winning on conflict.
  Phase-2 user hand-check folded into the Phase 3R wave-1 gate (hand-edit
  against the new ten-sheet schema). delegation.md D10 entry updated to
  carry the decisions; D10 remains gated only on the report.md
  reconciliation. Next action: user runs D9a then D9b; architect does the
  report.md reconciliation + D10 authoring in parallel or after the D9
  gate.

- **2026-08-24** — Wave-1 design closed with the user; schema.md rewritten,
  ripple folded into adapters.md + report.md (index.md/delivery.md touched
  up); D9a/D9b prompts issued. Decisions:
  1. **C4 kinds:** systems / containers / components / code (Code is a full
     modelled kind, usually empty). Container.parent references a System OR
     a Container (nested containers are ordinary Containers); new validation:
     ambiguous parent, containment cycles.
  2. **Ids:** per-kind prefixed sequential scheme (s-/c-/cp-/cd-/u-/i-/r-,
     zero-pad 4, max+1, gaps permanent), auto-assigned on Excel import and
     init; slugs stay legal; milestones always authored.
  3. **Intervals:** `start_in`/`end_in`, BOTH inclusive — chosen over the
     issue's from/to candidates after the flip surfaced a gap ("live in the
     base only, gone at the first milestone" has no last-alive milestone to
     name; acme has two such rows). Resolution (user-approved): position 0
     is renamed from "current" to **base** everywhere (selector, payload,
     UI), and `base` is an ordinary position reference — `end_in: base`
     covers the gap and the `advance` rewrite with no special mechanism
     beyond reserving the milestone id. `start_in == end_in` is now legal.
     Accepted cost: the removing milestone is no longer named on the row
     (`end_in` names the last survivor state), so raw-YAML grep attribution
     of retirements shifts one milestone earlier; diffs still report
     removals at the right position.
  4. **Provider/Consumer (simplified per user):** roles stay
     provider/consumer; NO relationship-type enum; `call_direction`
     (consumer_to_provider default | provider_to_consumer) + renamed
     `data_flow_direction` (provider_to_consumer default |
     consumer_to_provider | bidirectional); "unspecified" removed —
     defaults omitted in dumps. schema.md absorbed provider-consumer.md's
     definitions, principle, and examples.

- **2026-08-24** — Plan restructured for the gate rework: added Phase 3R
  tracking the three issue waves (issues/ stays the requirements source),
  annotated the phase-3 gate as failed-first-run with re-gate after waves
  1–2, split wave 3 into view-mode items vs deferred edit-mode items (edit
  mode also added to Phase 4). UI research
  (`research/ui/ui-research-findings.md`) incorporated as binding wave-2
  design input (top-10 / do-not-copy lists, measured styles); its two
  contract conflicts (legend hide vs dim, nested expand vs drill) and the
  status of the v2-era `wip/interactions.md` INT-* contract recorded as
  open questions 4–6 — architect resolves them before wave-2 prompts.
  Delegation model extended to the rework: chunks registered as D9 (wave 1),
  D10 (wave 2), D11 (wave 3 view-mode items) in delegation.md, all GATED on
  their architect artifacts; executors work from design docs + prompt only,
  never from issue files directly. Next action: agree wave-1 scope + budget
  with the user, then update schema.md and author D9.

- **2026-08-24** — Write-path decision (user): the report app gets two
  modes — **view** (standalone `file://`, read-only, as today) and **edit**
  (a local server owning the YAML write path). The edit-mode server design
  is deliberately deferred until Schema, Report, and File Import are
  complete. Clarification (same day): report definitions are effective
  *views* of the data, not edits — the define/use flow belongs to view mode;
  only persisting a definition into the model rides the edit path. Recorded
  in issues/ (p3-edit-save-back, p3-report-definitions,
  p3-ui-manual-positions, index note).

- **2026-08-24** — Phase-3 gate: user review found many parts missing or not
  working as required — gate NOT passed. Feedback captured as 20 fleshed-out
  issues in `issues/` (index: `issues/issues.md`), named `px-cat-desc` by
  provisional wave: wave 1 schema (C4 naming, auto ids, inclusive from/to,
  provider/consumer model), wave 2 report UI (nested groupings, side panel,
  resizable panels, layout density, plain background, legend, flow
  animation, dependency focus view, entity boxes, edge rendering,
  fullscreen, v2-parity tables), wave 3 capabilities (saved report
  definitions, edit + save-back, manual positions, guided views). Reference
  screenshots renamed meaningfully and embedded; v2 report/table behavior
  inventoried as input (v2 had authored `views:` + AG Grid table config, no
  save/edit UI). Next action: user + architect agree wave scoping and
  budgets, then design-doc updates and executor prompts per wave.

- **2026-08-24** — D7 gate PASSED (architect review); committed by architect
  (rule 8) with one architect fix. Re-verified: projection.ts matches the
  contract clause-by-clause (half-open liveAt, resolver-mirroring diff with
  b-state clipped_by, live-interfaces-only scope BFS with boundary stubs,
  unordered-pair edge keys fixing D6's duplicate-edge-id note, ever-live
  union graph); 14 vitest tests pass and the rollup vectors pin exact node
  sets; `payload` CLI regeneration of the projection fixture is identical;
  template rebuild byte-identical before the fix; 65 arch + 27 smoke tests,
  `just lint` clean. Fix found via the user's minimap report: the app is a
  controlled React Flow with no onNodesChange, so user nodes never received
  measured dimensions — MiniMap rendered zero node rects (blank panel) and
  initial fitView framed the graph wrong. Fixed by putting explicit
  `width`/`height` (the same 240x112 ELK already assumes, now shared
  NODE_WIDTH/NODE_HEIGHT constants in layout.ts) on the node objects;
  App.test.tsx layout mock exports them too. Headless Playwright re-check
  (OneTool's playwright proxy would not connect — needs an MCP restart;
  drove the cached Playwright directly per test-ui.md discipline): minimap
  shows the graph in both themes, all 14 current systems fit the viewport,
  scrub to Edge Foundation + vs-current shows the added Digital Commerce
  Platform, changed Legacy Commerce Platform (badges + popover) and ghosted
  removed edges at stable positions, components level renders 43 nodes,
  legacy-commerce + 1 hop yields a collapsed Warehouse Operator boundary
  stub, the copied fragment URL reopens the identical node set, AG Grid
  entities table is populated, console has 0 errors, and the only request
  is the local file. Accepted with a note: MAP/PATH/LENS buttons currently
  encode into the fragment and a data-mode attribute with no visual effect
  (no styling hooks yet) — user may veto at the phase-3 gate. Next action:
  phase-3 gate (user reads the acme story in the report).

- **2026-08-24** — D7 complete. Added the pure TypeScript projection pipeline
  (`liveAt`, `clipAt`, `stateAt`, `diffStates`, `scopeAt`, `rollUp`, and
  `unionGraph`) and drove all 13 read-only vector cases through it. The report
  now has timeline and milestone controls, current/position diff overlays,
  stable union layout with explicit state re-fit, system-hop scope, three
  roll-up levels, collapsed boundary stubs, four AG Grid tables, aspect and
  mode controls, and complete URL-fragment views with copy-link. Source is
  1,274 TS/TSX lines / 2,500 budget; tests are 13 projection vectors plus one
  slider interaction. The concurrent tooling refresh moved the bundle rename
  to Vite's supported `emitFile` API and the final gates use its upgraded
  dependency set. Verification: `npm test` 14 passed; npm audit reports 0
  vulnerabilities; `just build-arch-report` and `just lint` are clean; 65 arch
  tests and 27 smoke tests passed. Regenerated the acme report and verified it
  from `file://` through OneTool Playwright: scrubbing changed the node set,
  current diff showed added/removed markers, component level and scoped hops
  produced a collapsed boundary stub, the copied URL reopened the same state,
  AG Grid mounted, every console check had 0 errors, and no external requests
  occurred. Assumptions: the user's final no-commit instruction and rule 8
  override the earlier request wording; `vs current` compares position 0 to
  the selected position while `vs position` compares its chosen reference to
  the selected position; the fragment uses named query parameters including
  `compare-at` and never stores coordinates; MAP/PATH/LENS are encoded view
  modes over the same projection because the contract defines no distinct
  PATH/LENS projection semantics. No open questions. Changes are deliberately
  uncommitted for the phase-3 gate.

- **2026-08-23** — D6 gate PASSED (architect review); committed by architect
  (rule 8). Re-verified: 65 arch tests, `just lint` clean, standalone
  `generate_report` loads zero runtime modules, template holds exactly one
  payload token with no external `src`/`href` refs, `just build-arch-report`
  rebuild is byte-identical (sha256 match), checked-in
  `fixture-payload.json` equals `payload_file(acme)`. Code review: payload
  compiler follows the contract's normative algorithm (per-position
  `resolve()` sweep, `governing_row` identity, no reimplemented interval
  semantics); segments coalesced, in-domain, `null`-unbounded; clip runs
  split on cause change; `_serialize` drops per contract. report.py
  validates-then-refuses like export, `</`-escapes, atomic replace. Both
  D6 assumptions accepted (position mapping matches the contract verbatim;
  direct-connections-only rendering is D7's job). Noted for D7: revision
  rows sharing an id produce duplicate React Flow/ELK edge ids in the
  scaffold's `connectionEdges` — harmless now (acme console clean), but D7's
  roll-up must key edges properly. Next action: run D7 (prompt READY in
  delegation.md).

- **2026-08-23** — D6 complete. Added the deterministic payload compiler,
  atomic report generator, `generate` / `payload` CLI commands,
  `arch.generate`, the React Flow single-file bundle, checked-in acme dev
  payload, and the report build recipe. Source: Python 224 / 400 lines;
  TS/TSX 291 / 2,500 lines. Tests: 2 new payload/report controls; 65 arch
  tests pass, 540 deselected; 27 smoke tests pass, 3,196 deselected;
  `just lint` and `npm run build` are clean. The build emits one 1.93 MB
  HTML template with one payload token and no external assets; a wheel-only
  build contains that template and rebuilding it is byte-identical. Manual
  `file://` check at 1440x900 and 390x844: 10 current systems render after
  ELK union layout, selecting `legacy-commerce` opens its passport, light /
  dark switching works, the console is clean, and the only network request
  is the local HTML file. Assumptions: payload position 0 maps to resolver
  `current`, and payload position i+1 maps to milestone i; D6 renders only
  direct system-ended connections because endpoint roll-up belongs to D7;
  elkjs's bundled embedded worker satisfies the inline-worker requirement;
  the user's final "Do not commit" instruction and delegation rule 8
  override the earlier request wording that mentioned a commit. No open
  questions. Next action: architect D6 gate review; changes deliberately
  left uncommitted.

- **2026-08-23** — Client projection contract v1 committed (architect,
  authored in parallel with the user's executor running D6; no D6-owned
  files touched). report.md gains the contract: pure-function pipeline
  stateAt → scopeAt → rollUp (+ liveAt/clipAt, diffStates, unionGraph),
  node keys `kind:id`, diff mirroring the Python resolver exactly (KINDS
  order, clipped_by from the b-state, properties per-key, tags whole,
  equal-content revisions unreported), scope = system-level BFS over live
  interfaces with retained-connection + boundary-stub rules, roll-up =
  representative-at-level with unordered aggregated edges (self-pairs
  dropped, members carry direction), union graph = same roll-up over
  ever-live rows for one-shot elkjs layout. Authoritative vectors in
  tests/unit/tools/fixtures/arch/projection/ (model.yaml + payload.json +
  vectors.json + README): synthetic 2-timeline model hitting gap
  reintroduction, off-timeline from/until, clip chains, content revision,
  and a systems-level self-loop; state/diff expectations computed by the
  Python resolver, scope/rollup by reference tooling encoding the contract
  (scratch, not kept); all 13 cases verified against hand analysis. D7
  flipped to READY in delegation.md (2,500 TS/TSX budget, vitest vector
  suite as the control mechanism, payload cross-check against D6's
  build_payload). Next action: D6 gate review when the executor finishes,
  then run D7.

- **2026-08-23** — Payload contract v1 committed (architect); D6 flipped to
  READY with its full prompt in delegation.md. Design: per-timeline integer
  position space (0 = Current, i+1 = i-th milestone; slider index ==
  position); each row carries `intervals` parallel to the materialized
  timelines array, holding half-open effective-liveness segments (revision
  succession + clipping folded in, `end: null` = unbounded) plus clip
  segments with the authored root cause — so client state-at-position is one
  array filter and no resolver semantics are reimplemented in TS (the
  compiler is specced as a per-position resolve() sweep). No per-position
  states, no diffs, no timestamps in the payload; byte-deterministic
  generate; `</`-escaped compact JSON in a `<script type="application/json">`
  block. Open question 1 answered: bundle source `frontend/arch-report/`,
  built single-file template committed at `_arch/v3/_bundle/
  report-template.html` (`just build-arch-report`); Node never required at
  wheel-build or generate time. D6 adds CLI `generate` + `payload`
  subcommands, `arch.generate`, and two control tests (acme payload
  invariants, generate smoke). Next action: user runs D6; architect's next
  artifact is the client projection spec (unblocks D7), which can be
  authored while D6 runs.

- **2026-08-23** — Phase-2 gate PASSED (architect review); D5 committed by
  architect (rule 8). Re-verified: 63 arch tests, `just lint` clean, CLI +
  excel module import with zero runtime modules loaded. Gate exercise run
  scripted (openpyxl standing in for hand edits): exported acme, added
  milestone `acme-2032-fraud-consolidation` (+ Timelines row), retired
  `fraud-provider` via `until`, added a `tax-api` revision row → import →
  diff(2031→2032) shows exactly the retirement (system + 3 descendants
  correctly `clipped_by: fraud-provider`) and the name/description revision;
  nothing spurious. A first attempt that left the revision row's property
  cells blank correctly diffed those properties as removed — complete-record
  semantics working as designed. In-place export back onto the edited
  workbook preserved the user `Notes` sheet and resized the table ref.
  Code review: adapter sound; one noted minor limitation — in update mode a
  hand-authored DataValidation object spanning several controlled columns
  collapses to the last matched column (generated workbooks use one
  validation per column, unaffected); accept, revisit only if a real
  workbook trips it. User may repeat the gate edit by hand in Excel and
  veto. Next action: Phase 3 — architect payload JSON spec (unblocks D6).

- **2026-08-23** — D5 complete. Added the schema-v3 Excel reader, new-workbook
  writer, atomic in-place updater, generated template, standalone CLI commands,
  and `arch.import_excel` / `arch.convert` / `arch.export` facade tools. Source:
  `excel.py` 752 lines, CLI +20, facade +36 = 808 / 900 budget. Tests: 2 new
  control tests; 63 arch tests pass. `just lint` is clean. Manual checks also
  confirmed user-sheet and cell-style preservation, facade and CLI round trips,
  and runtime-independent imports. Assumptions: the dated in-place contract in
  adapters.md supersedes v2's new-workbook-only export rule; Milestone `tags` is
  reserved in Excel because the required acme model-equality round trip contains
  milestone tags; user-added sheets are ignored on read and preserved on update;
  CLI operands are `import-excel WORKBOOK YAML`, `export YAML WORKBOOK`, and
  `template WORKBOOK`, while facade tools use `input_path` / `output_path`;
  template generation refuses to overwrite; an existing workbook must have one
  table per canonical sheet and all property columns needed by the model because
  update-in-place keeps headers unchanged. No open questions. Next action:
  architect phase-2 gate; changes deliberately left uncommitted for review.

- **2026-08-23** — Design decision (user + architect): `write(arch, target)`
  gains an update-in-place mode — existing workbook keeps formatting,
  structured tables, validation, and user sheets; only data rows are
  replaced and table/validation refs resized. Charts/images are refused,
  not silently dropped (openpyxl loses them on save). Recorded in
  adapters.md "Write modes"; added to the D5 checklist (~+100 lines within
  the 900 budget).

- **2026-08-23** — v1 cutover complete (architect, inline). Deleted the 11 v1
  `_arch` modules, v1 tests (`tests/otdev/{unit,integration}/tools/test_arch.py`,
  the arch-only root `tests/otdev/conftest.py`, `tests/otdev/fixtures/arch/`),
  the four v1 arch specs (`tool-arch-{drawio-export,model-centric-rendering,
  solution-report,validation-warnings}`) + INDEX row, and the v1 config assets
  (`global_templates/arch.yaml`, `arch-templates/`, their `ot/paths.py` init
  entries). Rewrote `docs/reference/tools/arch.md` for v3, updated the
  prompts.yaml pack description and pack-index row, `just docs-sync`
  regenerated `tool-index.md`/`llms.txt`. Full docs page authoring stays a
  backfill item. Verification: full unit suite 3,022+ passed after fixing the
  one paths test that asserted `templates/arch` is copied on init; lint and
  docs registry check clean. Phase 1 is DONE. Next action: D5 — Excel adapter
  (`adapters.md`), preceded by no architect artifact; entire chunk is one
  delegation.

- **2026-08-23** — Phase-1 gate PASSED (architect review). 61 arch tests
  green, `just lint` clean. Acme validates: 0 errors, 24 warnings (clipping
  advisories). All six adjacent-state diffs correct by inspection: edge
  foundation adds the strangler edge/BFF/eventing tree and retires direct
  customer→monolith interfaces; each domain phase adds its services while
  legacy modules turn into facades (name/description revisions); transaction
  core severs every monolith external integration; complete cutover retires
  the whole legacy-commerce tree; last-milestone→end diff is empty. Line
  counts: phase-1 source 1,564 / 1,800 budget (D4: 496 / 500). Code review:
  validate.py finding pipeline, weakref source-mark registry in yamlio.py,
  and CLI/facade wiring all sound. Architect committed D4 (rule 8). Next
  action: cutover step — delete v1 `_arch` modules, update specs/docs
  referencing v1 (arch.py facade already replaced in D4).

- **2026-08-23** — D4 complete. Added location-aware structural validation
  and advisory warnings, shared file operations, standalone CLI commands, and
  the v3-only `arch` facade. Source: `validate.py` 320 lines, `api.py` 98,
  `arch.py` 78 = 496 / 500 D4 budget; `__main__.py` 109 and `yamlio.py` 287;
  phase-1 source is 1,564 / 1,800. Verification: 61 arch tests passed (12 new),
  540 deselected; `just lint` clean; acme validates with 0 errors and 24
  advisory clipping warnings; CLI JSON parses and standalone import loads no
  runtime modules. Assumptions: stable finding codes are category-level;
  adjacent revisions follow authored order; "live on no timeline" means
  effectively live after clipping; timeline membership does not count as a
  row reference for the unused-milestone warning; in-memory models use
  `<memory>:1:1` when no YAML source mark exists; `diff` accepts independent
  `at_a`/`at_b` selectors and optional timelines; `init` refuses to overwrite
  an existing file. No open questions. Next action: architect phase-1 gate.

- **2026-08-23** — D3 complete, gate PASSED (architect review). Executor
  implemented timeline/state selection, revision grouping and governing-row
  resolution, liveness clipping with authored root causes, ordered
  field-level diffs, and deterministic baseline advance. Source: 548 lines /
  600 budget. Architect verification: 49 arch tests passed (all 42
  authoritative resolver tests unchanged), `just lint` clean, CLI-standalone
  run loads zero runtime modules, acme smoke checks correct by inspection
  (adjacent-milestone diffs surface the facade revisions; current→end shows
  them as removed because the whole legacy-commerce tree retires by `end`;
  advance preserves end-state identity). Process note: the executor
  committed despite rule 8; that commit was reverted and the architect
  committed after review — rule 8 stands. Next action: run D4.

- **2026-08-23** — D2 gate PASSED (architect review: tests/lint green, acme
  fixture round-trips with model equality + idempotent dump, CLI runs with
  zero runtime modules loaded; executor's `components: []` schema.md example
  fix accepted). D3 spec committed by architect: `resolver.py` signatures +
  docstrings (selector, timeline view, revision grouping, clipping with
  root-cause `clipped_by`, diff, advance) and the 42-test authoritative
  suite `test_arch_v3_resolver.py` (all failing NotImplementedError, as
  intended). Design decisions encoded: sole declared timeline is the default
  selector target (schema.md updated); `end` == `current` at zero
  milestones; clip causes name the authored root (provider-before-consumer,
  source-before-target tie-break); diff excludes id/from/until, properties
  diffed per-key; advance drops emptied timelines. Process change: executors
  no longer commit — they leave the worktree dirty and the architect commits
  after the gate review (delegation.md rule 8). D3 flipped to READY. Next
  action: run D3.

- **2026-08-23** - D2 complete. Added schema-v3 Pydantic models, strict
  location-aware YAML loading, deterministic YAML writing, and the seed
  `check` CLI. The canonical example now includes the required empty
  `components` collection; omitted entity collections remain invalid. Source:
  428 lines / 700 budget. Tests: 7 passed (`tests/unit/tools -k arch`), 540
  deselected; `just lint` and targeted strict mypy clean. No new open
  questions.

- **2026-08-23** — Phase 0 complete. Layout confirmed as the recommended
  default. D1 executed inline by the architect (skeleton
  `src/otdev/tools/_arch/v3/__init__.py`; all 7 sheets dumped to
  `fixture-src/` + README). Canonical fixture designed and generated at
  `tests/unit/tools/fixtures/arch/acme.yaml` (1,920 lines): 5 milestones
  (2027–2031 strangler migration), 1 explicit timeline `program`, 11 systems /
  30 subsystems / 55 components / 4 users / 63 interfaces / 2 relationships;
  7 revision rows across 6 ids, 15 authored `until` retirements, and the
  legacy-commerce `until` exercising computed clipping of the whole monolith
  tree. Conversion decisions: v2 sparse `changed` patches materialized into
  complete revision rows; sparse `removed` rows folded into `until` on the
  newest revision; `technology`/`type`/`group` columns → properties; bool/int
  property values stringified; `change_note`/`kind`/`direction`(→
  `call_direction`) mapped or dropped; milestone names authored by the
  architect; the 2 relationships are architect-invented (source workbook had
  none) — veto at the phase-1 gate if unwanted. Fixture proto-validated
  (refs, revision rules, no nulls, property types, timeline order). Converter
  was throwaway scratchpad tooling. Tooling hint added: use `__ot excel` /
  `__ot convert` for interactive workbook reading and conversions. Next
  action: run D2 (models + YAML I/O).

- **2026-08-23** — Out-of-pack changes permitted when they're the better
  fix (e.g. extend an otpack utility rather than work around it):
  executor proposes or the prompt names the file; touched shared modules
  run their own tests too. Runtime-independence remains the one hard limit.

- **2026-08-23** — Import stance relaxed: leverage onetool/otpack code and
  existing deps whenever it accelerates; the invariant is now
  runtime-independence (CLI runs with no server/executor loaded) + never
  modifying code outside the pack, not import purity. Prompts updated.

- **2026-08-23** — Decoupling adopted: `_arch/v3/` core is import-clean
  (stdlib + pydantic + yaml + openpyxl; no ot.*/otpack), `arch.py` is the
  only onetool touchpoint, and a `__main__.py` dev CLI (seeded in D2, grown
  in D4/D5/D6) is the primary iteration loop — no MCP server needed.
  Verification stays pack-scoped (`pytest -k arch`); full suite never runs.

- **2026-08-23** — Speed mode adopted: OpenSpec and docs skipped until
  post-phase-3 stabilisation; tests trimmed to the control-mechanism set
  (resolver spec suite, round-trips, atomicity, projection vectors, facade
  smoke). Deferred breadth tracked as Phase 4 backfill. Delegation prompts
  D2/D4/D5 trimmed to match; executors barred from writing unlisted tests.

- **2026-08-23** — Delegation model added: execution chunks tagged `→ D1..D8`
  with ready-to-paste executor prompts in delegation.md; architect keeps
  resolver semantics, fixture design, payload/projection specs, and gate
  reviews. D1 and D2 are runnable now (D2 after D1 commits).
- **2026-08-23** — Plan created. v3 design docs committed (`97d09bd8`).
  v2 worktree confirmed stuck-but-safe: clean, pushed to origin
  (`feature/arch-v2`, head `e242fbb5`). No v3 code exists yet. Next action:
  Phase 0 — skeleton package + hand-port acme fixture to v3 YAML.
