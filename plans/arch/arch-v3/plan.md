# Arch v3 — Execution Plan

Tracking document for implementing v3. The **design** lives in the six sibling
docs (index, schema, report, sequence, adapters, delivery) — this file never
restates it, only tracks execution. Update the checkboxes and the progress log as work
lands; a fresh session should be able to resume from this file alone.

## How to use this file

- **Resuming:** read this file, then index.md, then the doc owning the
  phase you are in (report.md for 3P/3R, sequence.md for 3S). Check the
  progress log for the last entry; older entries are in log-archive.md.
- **Stopping:** append a progress-log entry saying what state the tree is in
  and the next action. Commit WIP rather than leaving dirty trees. When the
  inline log grows past ~10 entries, move the older ones to log-archive.md
  (append-only content, archived periodically — reorg rule 2026-08-25).
- **Exploring a different direction:** branch off `feature/arch-v3`, note the
  branch and question under "Exploration branches" below. Design changes go
  into the six docs (replacing text, not adding files — delivery.md rule 1),
  with a log entry here.

## Ground truth

| What | Where |
| --- | --- |
| Working tree / branch | this worktree, `feature/arch-v3` (worktree `arch-v3`) |
| Design docs | `plans/arch/arch-v3/` (index, schema, report, sequence, adapters, delivery) |
| Implementation | `src/otdev/tools/arch.py` facade + `src/otdev/tools/_arch/v3/`; report app source `frontend/arch-report/` (v1 deleted at cutover 2026-08-23) |
| Canonical v3 fixture | `tests/unit/tools/fixtures/arch/acme.yaml` |
| Fixture source of record | `plans/arch/wip/acme-arch-v2.xlsx` (dumped to `plans/arch/arch-v3/fixture-src/`) |
| Open issues (wave 3) | `plans/arch/arch-v3/issues/` — p3-* files + index; resolved p1/p2 files in `issues/resolved/`; Archify/IcePanel reference screenshots stay in `issues/` (cited by the 3P pass specs) |
| UI research (IcePanel/Archify) | `plans/arch/arch-v3/research/ui/ui-research-findings.md` + evidence captures |
| Progress-log archive | `plans/arch/arch-v3/log-archive.md` |
| Archived history (reference only) | `plans/arch/archive/` — `arch-v2/` design history incl. `grill/`; `v2-wip/` (v2-era design/ideas/requirements/mocks + superseded interactions.md, mined into report.md "Wave-2 UI contract") |
| v2 donor code | HARVEST COMPLETE — branch `feature/arch-v2` on origin (head `e242fbb5`); worktree removed 2026-08-25. The dead patch/replay list ("must NOT return") lives in delivery.md |
| react-flow-poc | DELETED 2026-08-25 (superseded by the implemented app; in git history if ever needed) |

**Tooling hints (interactive/architect work):** use the OneTool `excel` pack
(`__ot excel`) to read/inspect workbooks and the `convert` pack (`__ot
convert`) for format conversions — don't hand-roll openpyxl scripts for
inspection. (In-pack _arch/v3 code still uses openpyxl directly, per the
design docs.) For UI verification (report app, phase 3+ gates), follow
`wip/notes/test-ui.md` — Playwright driven through `__ot playwright.*` for
snapshots, clicks, console/network inspection, and screenshots; console
inspection belongs in every pass.

**Standing practice (user request 2026-08-25):** after every landed feature
that touches the report (bundle, payload, or fixture), regenerate the
user's test artifact so progress is always inspectable:
`uv run python -m otdev.tools._arch.v3 generate
tests/unit/tools/fixtures/arch/acme.yaml plans/arch/wip/acme-report.html`
(stays untracked; part of every gate-review wrap-up).

## Layout decision (recommended default)

New code goes in `src/otdev/tools/_arch/v3/` with `arch.py` as the pack
facade. The core is runtime-independent (see "Moving fast" rules below) so
this location is a packaging convenience; it could still be lifted out later
(`otpack` is itself a standalone wheel), but leveraging onetool libraries is
preferred over purity whenever it speeds delivery. v1 modules in `_arch/` stay untouched until the phase-1 gate passes,
then `arch.py` cuts over to v3 and v1 modules are deleted in one commit (clean
break, no aliases). Report app source lives in `frontend/arch-report/` (or
similar) and ships as a prebuilt bundle inside the wheel — never built at
generate time. Revisit only if the repo has a stronger convention.

## Delegation model

Execution is split between this session (architect) and cheaper executor
models the user runs with the prompts in [delegation.md](delegation.md):

- **Architect:** design decisions, the resolver semantics test suite, the
  acme fixture's change story, payload + client-projection specs, gate
  reviews of every delegated chunk, budget enforcement, and authoring the
  gated prompts when their inputs exist.
- **Executor (tags `→ Dn` below):** well-specified implementation chunks.
  Prompts carry the contract; executors stop and ask rather than improvise.
- **Rule:** no delegated chunk feeds the next phase until the architect has
  reviewed it at the gate. Remaining sequence (D1–D10 done — see the DONE
  section): Phase 3P (per-pass: architect spec → D13x → gate) → 3P exit
  gate → then D12a, and (D11 ∥ D12b ∥ D8) as their architect artifacts
  land. Historical sequencing detail: log-archive.md.

## Speed mode (agreed 2026-08-23)

To move fast, formal ceremony is deferred until the design stabilises
(post phase-3 gate). Backfill items are tracked in Phase 4.

- **OpenSpec: skipped entirely.** No change proposals, no spec deltas during
  the build. Backfilled once v3 ships.
- **Docs: skipped.** The six design docs remain the only design writing;
  no user docs, no docstring polish beyond what code clarity needs.
- **Tests: kept only where they do work now, breadth backfilled.**
  - KEEP — tests that are the control mechanism for executor models or the
    phase gates: the resolver semantics suite (it IS the D3 spec),
    round-trip equality tests (YAML and Excel), import atomicity, the
    projection test vectors (D7 spec), one facade smoke test.
  - DEFER — coverage breadth: error-location assertions, exhaustive
    validation-code cases, header-normalization matrices, template tests.
  - Executors write only the tests their prompt lists — no extra coverage.

## Moving fast inside the large project (agreed 2026-08-23)

onetool-mcp is stable and is NOT under test here; the arch pack barely needs
it. Three rules keep iteration fast:

1. **Runtime-independent core, pragmatic imports.** Everything under
   `_arch/v3/` must run as plain `python -m` with no onetool *runtime*
   (server, tool loader, executor, ctx) loaded — that is the invariant, not
   import purity. Leveraging existing code and dependencies is encouraged
   when it accelerates: any dependency already in the project, `otpack`
   utilities (logging, paths, pathsec, text), and stable `ot` library
   helpers (e.g. config/path resolution, used from the facade) are all fair
   game. Never re-implement something onetool already provides just to stay
   "clean". What stays out of the core: runtime modules (`ot.executor`,
   server, MCP plumbing) and anything that needs a running server. The
   `arch.py` facade remains the only *tool-registration* touchpoint and
   stays thin.
2. **Direct CLI, no MCP.** `_arch/v3/__main__.py` exposes the same
   operations as the pack tools:
   `uv run python -m otdev.tools._arch.v3 validate|resolve|diff|advance|
   import-excel|export|generate <args>`. Grows with the phases (D2 seeds
   it, D4 fills it, D5/D6 extend it). This is the primary dev/demo loop;
   the MCP facade is verified once per phase via the smoke test, not used
   for iteration.
3. **Verification scales with blast radius.** Default: arch code only
   *uses* onetool libraries, so `uv run pytest tests/unit/tools -k arch` +
   lint on touched paths is sufficient and the full suite never runs.
   Changing shared project code IS allowed when it's the better fix (e.g.
   extending an otpack utility instead of working around it) — but such a
   change is architect-reviewed, and that change alone widens verification
   to the touched module's own tests. Executors propose out-of-pack
   changes; they don't make them unprompted. Rule 1's invariant is checked
   at each gate by running the CLI standalone.

## Phases 0–3R waves 1–2 — DONE (details: log-archive.md + design docs)

All build phases through the wave-2 rework are complete and committed
(latest: c37e3d05). Budgets were respected throughout. One-line record:

- **Phase 0 — setup**: `_arch/v3/` skeleton; canonical acme fixture
  (`tests/unit/tools/fixtures/arch/acme.yaml`). `→ D1`
- **Phase 1 — model/resolver/YAML** (1,800 py budget): Pydantic models,
  deterministic YAML I/O, architect-authored resolver semantics suite,
  resolver (state-at-position, clipping, diff, advance), located
  validation, dev CLI, pack facade; v1 modules deleted at cutover.
  `→ D2–D4`
- **Phase 2 — Excel adapter** (900 py): ten-sheet round-trip with header
  normalization, in-place mode-aware write, atomic located errors,
  `arch.import_excel` / `arch.export`. `→ D5`
- **Phase 3 — report app** (5,000 TS/TSX + 400 py): payload + client
  projection contracts (report.md), single-file bundle (React Flow +
  elkjs + AG Grid), client projection + union layout, time slider +
  diff overlay, tables, fragment views. `→ D6, D7` *Gate first run
  2026-08-24 NOT passed → the 20 issues in `issues/`; closure now rides
  the Phase 3P exit gate.*
- **Phase 3R waves 1–2 — gate rework**: wave 1 schema (C4 naming, auto
  ids, inclusive intervals, provider/consumer interface model,
  ten-sheet Excel) `→ D9a, D9b`; gate PASSED 2026-08-25 including the
  scripted Excel hand-edit exercise. Wave 2 UI (chrome / panels /
  tables + canvas semantics) `→ D10a, D10b` plus architect gate fixes,
  commit c37e3d05; re-gate architect half PASSED, user half folded
  into the Phase 3P exit gate. Residual caveat: the
  `arch_end_milestones` VSTACK/FILTER dropdown is still unverified in
  real Excel — eyeball it next time a generated workbook is opened.

## Phase 3R wave 3 — new capabilities (DELAYED until Phase 3P completes —
user directive 2026-08-25: polish the existing UI before any new big
pieces)

Write-path decision (2026-08-24): the app has **view** mode (standalone
`file://`, read-only) and **edit** mode (local server owning the YAML write
path). Edit-mode work is deferred until Schema, Report, and File Import are
complete.

- [ ] `p3-report-definitions` — named reports; view-mode flow. Starting
      point: export the config as a ready-to-paste `views:` YAML entry;
      only persist-to-model rides the deferred edit path. `→ D11`
- [ ] `p3-ui-guided-view` — authored, playable guided views; resolves the
      MAP/PATH/LENS placeholders left by D7. `→ D11`
- [ ] `p3-edit-save-back` — DEFERRED (edit mode).
- [ ] `p3-ui-manual-positions` — DEFERRED (edit mode).

## Phase 3P — UI polish passes (before D11/D12/D8 — user-directed 2026-08-25)

The wave-2 build is functionally complete but reads as clunky and
poorly designed. Four polish passes clean up look and feel, each
independently gateable, ordered so later passes build on earlier ones.
**No new features land during 3P**; D11, D12 (both halves — the issued
D12a prompt is ON HOLD), and D8 wait until the 3P exit gate. Passes are
executor chunks `D13a–D13d`; the architect authors each pass's
normative spec (folded into report.md as amendments to the Wave-2 UI
contract) plus the prompt, with budgets agreed per pass. Design
references: the measured Archify/IcePanel values and binding lists in
`research/ui/ui-research-findings.md` + the evidence captures, and the
reference screenshots in `issues/`.

Evidence baseline (architect critique, 2026-08-25, from the acme
report): default fit strands the graph in a corner of a mostly-empty
canvas at 37% zoom; nodes are uniform 250×168 cards that are ~80%
empty at MAP depth yet still truncate their names; edges route as huge
orthogonal rectangular detours that read as phantom boundary boxes and
cross node interiors, with near-invisible strokes and no visible
arrowheads; fitted content hides behind the floating legend; the
legend is a full-height list of identical teal swatches (mostly
count-1 tags) with no meaning in the color; chrome is dev-tool-styled
(8–10px mono uppercase labels everywhere, ASCII glyph buttons ⌘◐↗⌕⌁,
raw node-id dump visible in the footer, debug-pill "Open Tables
panel"); the MAP→READ threshold (100%) does not match layout scale, so
the useful 40–90% range shows only names in oversized boxes.

- [ ] **Pass 1 — visual foundation: tokens, type, chrome.** `→ D13a`
      (spec: report.md "Polish contract — pass 1"; prompt READY in
      delegation.md; budget 700 changed source lines, proposed
      2026-08-25 — confirm before running.)
      Design-token pass (spacing / radius / shadow / type scale), one
      shared card style for clusters, panels, rail, and minimap; mono
      reserved for data (ids, counts) with UI labels in a readable
      sans scale; real inline-SVG icon set replacing ASCII glyphs;
      dark-theme contrast pass; footer humanised (node-id dump hidden
      from view, kept for tests); tables toggle styled as a proper
      docked-bar affordance. CSS-dominant, low risk — do first.
- [ ] **Pass 2 — canvas composition: layout, fit, density.** `→ D13b`
      Per-depth/level node sizing (names never truncate before the box
      does); ELK tuning — tighter spacing, aspect-ratio hint, edge
      routing that kills the giant rectangular detours and interior
      crossings, proportional boundary padding (compact single-child
      boundaries); fit that accounts for open overlays (legend / side
      panel / cluster insets) and lands small graphs at READ depth;
      reading-depth thresholds re-derived from real node scale; grid
      packing for sparse/edgeless drill sets; minimap repositioned
      clear of the zoom rail and legend. Highest-risk pass; existing
      projection vectors and tests must stay green.
- [ ] **Pass 3 — graph elements: nodes, edges, boundaries.** `→ D13c`
      Entity-box redesign per reading depth (MAP compact chip, READ
      card, FULL facts) with kind accenting and person-styled users;
      drill affordance with a real hit target; edge contrast pass —
      zoom-compensated stroke, visible arrowheads, label pills scoped
      to FULL/selection; boundaries visually distinct from edge routes
      (fill tint, label placement, nested shading); dimming tiers
      re-tuned against the Archify reference values.
- [ ] **Pass 4 — panels and overlays: legend, side panel, tables,
      empty states.** `→ D13d` Legend becomes meaningful: per-tag
      deterministic categorical colors, count-descending sort,
      singleton tags grouped under an expandable rare section, compact
      rows, height respecting rail/minimap; side-panel hierarchy
      (title block, kv grid, directional connection chips); tables
      toolbar/density polish; designed empty and failure states (drill
      with no connections, layout failure, laying-out skeleton); final
      motion/consistency sweep with a reduced-motion audit.
- [ ] **Exit gate (architect + user):** the phase-3 gate question —
      open acme's report cold and the story reads without explanation,
      but now also *looks* deliberate: no dead-space fit, no phantom
      rectangles, readable nodes at default zoom, meaningful legend,
      coherent chrome in both themes. Browser pass stays console-clean
      and offline. Only after this gate do D11/D12b/D8 resume (and the
      held D12a run).

## Phase 3S — Sequence diagrams (budgets provisional: ~500 py + ~2,200 TS/TSX)

Owner doc: sequence.md (added 2026-08-25, user-directed — replaces the
"sequence attachments" deferral). Flows are Markdown docs in `sequences/`
beside the model YAML, referencing entity/interface ids plus ad-hoc
participants; renderer is a custom deterministic layout + React with the
canvas entity-box component as participant headers (library survey and
rationale in sequence.md). Budgets are re-agreed with the user when each
prompt is authored.

- [x] **Architect:** sequence.md v1 — source-doc format, DSL, compilation
      + payload shape, renderer decision, SEQ-* interaction contract
      (playback, sticky headers, C4 group collapse, focus, hide/show,
      scenarios, navigator, minimap, search, sync/async), verification
      plan. (2026-08-25)
- [x] **Architect:** parser-vector fixture
      (`tests/unit/tools/fixtures/arch/sequence/`) — the D12a control
      mechanism. (2026-08-25; D12a prompt issued the same day)
- [ ] Python: parser, validation findings, `sequences` payload, CLI +
      facade wiring. `→ D12a` (prompt issued but ON HOLD until the
      Phase 3P exit gate — user directive 2026-08-25)
- [ ] **Architect:** layout vectors + 2–3 acme flow docs (multi-scenario,
      interval-carrying, ad-hoc participant) — the D12b control mechanism.
- [ ] Frontend: `seqlayout.ts`, SVG layer, entity-box header row, SEQ-*
      interactions, fragment keys. `→ D12b` (after the phase-3 re-gate
      AND the Phase 3P exit gate; ∥ D11/D8)
- [ ] **Gate (architect + user):** open an acme flow, play it through,
      collapse a system band, focus a participant, hide one, switch
      scenario — the story reads without explanation; sticky headers hold;
      console clean; zero external requests from `file://`.

## Phase 4 — Polish and second adapters (per-item budgets)

- [ ] Client-side SVG / draw.io download from the report. `→ D8`
- [ ] SQLite adapter (one table/kind + properties side table). `→ D8`
- [ ] SharePoint transport reusing the Excel mapping.
- [ ] Migration converter from v2 YAML — only if a real v2 dataset exists to
      migrate; otherwise skip (throwaway tooling).
- [ ] Revisit deferred items (Confluence; saved report definitions moved to
      Phase 3R wave 3; sequence diagrams promoted to Phase 3S) against
      demonstrated need only.
- [ ] Edit mode: local-server write path + `p3-edit-save-back` +
      `p3-ui-manual-positions` (design deferred until Schema, Report, and
      File Import are complete — see Phase 3R wave 3).

### Backfill (speed-mode debt — do once v3 is stable)

- [ ] OpenSpec: author the v3 spec (`openspec/specs/.../tool-arch/`) from the
      shipped behavior; archive/replace v1 spec content.
- [ ] Test breadth: validation codes with location assertions, YAML/Excel
      error locations, header-normalization cases, model field-rule cases,
      template generation. `→ Dn` (mechanical; prompt written then)
- [ ] Docs: user-facing pack docs / docs-site page for the arch pack.

## Exploration branches

None yet. Format: `branch-name — question being explored — outcome`.

## Open questions (record answers in the design docs, log the change here)

1. Per-state layout fallback if union-graph layout is chronically poor for
   sparse early states (risk table; re-evaluate at the 3P exit gate —
   pass D13b's layout work may moot it).

Answered questions (answers live in the design docs; details in
log-archive.md): bundle location/build wiring (report.md "Shape");
`arch.convert` umbrella naming (as-shipped by D5); legend dim-not-hide
with tags driver (Q4, 2026-08-24); drill + 4-level C4 zoom over
in-place expand/collapse (Q5, 2026-08-24); interactions.md superseded
and mined (Q6, 2026-08-24); D9b projection-vector conversion to
inclusive `end_in` (Q7, 2026-08-24).

## Progress log (append-only, newest first)

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

- **(older entries)** — see [log-archive.md](log-archive.md).
