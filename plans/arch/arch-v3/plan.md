# Arch v3 — Execution Plan

Tracking document for implementing v3. The **design** lives in the six sibling
docs (index, schema, report, sequence, adapters, delivery) — this file never
restates it, only tracks execution. Update the checkboxes and the progress log as work
lands; a fresh session should be able to resume from this file alone.

## How to use this file

- **Resuming:** read this file, then index.md, then the doc owning the
  chunk you are in (report.md for report/UI chunks, sequence.md for
  sequence chunks). Check the progress log for the last entry; older
  entries are in log-archive.md.
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
| Open issues (Phase 2 wave 2) | `plans/arch/arch-v3/issues/` — p3-* files + index (feed P22/P43); resolved p1/p2 files in `issues/resolved/`; Archify/IcePanel reference screenshots stay in `issues/` (cited by the polish pass specs) |
| UI research (IcePanel/Archify) | `plans/arch/arch-v3/research/ui/ui-research-findings.md` + evidence captures |
| Confirmed UI direction (decision source for all UI work) | `plans/arch/arch-v3/ui-polish-direction.md` — confirmed 2026-08-27; authoritative for all UI/interaction decisions, supersedes conflicting guidance in ui-polish.md and the report.md wave-2 contract. The `designs/` artboard directory was removed the same day (decisions captured in the direction; files in git history) |
| UI polish issue list (CLOSED 2026-08-29) | `plans/arch/arch-v3/ui-polish.md` — 27 itemized issues (2026-08-25 Playwright walkthrough + 2026-08-28 user screenshots), tagged D13a–D13d; every issue now carries a CLOSED/WAIVED/superseded annotation — the Phase 1 exit gate re-checks the walkthrough, not the list |
| Progress-log archive | `plans/arch/arch-v3/log-archive.md` |
| Archived history (reference only) | `plans/arch/archive/` — `arch-v2/` design history incl. `grill/`; `v2-wip/` (v2-era design/ideas/requirements/mocks + superseded interactions.md, mined into report.md "Wave-2 UI contract") |
| v2 donor code | HARVEST COMPLETE — branch `feature/arch-v2` on origin (head `e242fbb5`); worktree removed 2026-08-25. The dead patch/replay list ("must NOT return") lives in delivery.md |
| react-flow-poc | DELETED 2026-08-25 (superseded by the implemented app; in git history if ever needed) |

**Tooling hints (interactive/architect work):** use the OneTool `excel` pack
(`__ot excel`) to read/inspect workbooks and the `convert` pack (`__ot
convert`) for format conversions — don't hand-roll openpyxl scripts for
inspection. (In-pack _arch/v3 code still uses openpyxl directly, per the
design docs.) For UI verification (report app gates), follow
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
- **Rule:** no delegated chunk feeds the next wave until the architect has
  reviewed it at the gate. Remaining sequence (waves 0–1 build done —
  see Phase 1): P11 → P12 → Phase 1 exit gate → wave 2 (P21 ∥ P22 ∥
  P23 as their architect artifacts land) → wave 3 (P31 → sequence
  gate) → waves 4–5. Historical sequencing detail: log-archive.md.
- **Rolling prompt pipeline (user-directed 2026-08-29):** prompts are
  generated ahead — as many as make sense for the piece of work, no
  strict limit — and every queued prompt is REVIEWED AND UPDATED
  against the landed tree as part of each gate review before it runs
  (e.g. P11 and P12 generated together; P11 runs; at the P11 gate the
  architect re-checks P12's prompt against the post-P11 tree, updates
  it, and generates the next prompt in sequence).

## Speed mode (agreed 2026-08-23)

To move fast, formal ceremony is deferred until the design stabilises
(post Phase 1 exit gate). Backfill items are tracked in Phase 3 wave 5.

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

## Chunk numbering (reorg 2026-08-29)

Executor chunks are numbered `Pxy`: `x` = wave (execution order), `y` =
priority inside the wave (lower first; same-wave chunks may run in
parallel once their architect inputs exist). Waves 0–1 are the completed
build — their chunks keep their historical ids (D1–D14, D13a–D13d) in
the progress log, the design docs, and delegation.md, because renaming
finished work would break those references. Outstanding chunks carry the
new ids, with the old id noted as `(was Dn)`; delegation.md headings
carry both.

| New id | Was | Chunk |
| --- | --- | --- |
| P11 | — | Canvas presentation: radial layout, edge labels/ports, color economy, theme (added 2026-08-29) |
| P12 | — | Map model: in-place C4 expansion, endpoint resolution, presets (added 2026-08-29) |
| P21 | D12a | Sequence parser + payload (prompt ON HOLD, needs re-scope) |
| P22 | D11 | Report definitions + guided views |
| P23 | D8 | Client-side SVG / draw.io export + SQLite adapter |
| P31 | D12b | Sequence renderer frontend |
| P41 | — | SharePoint transport |
| P42 | — | v2 YAML migration converter (conditional) |
| P43 | — | Edit mode (save-back + manual positions) |
| P51 | Dn (backfill) | Test-breadth backfill |

## Phase 1 — Core build, gate rework, UI polish (waves 0–1) — DONE except the exit gate

All build work through UI polish is complete and committed; budgets were
respected throughout. One-line record (details: log-archive.md + design
docs):

- **Setup** (was Phase 0): `_arch/v3/` skeleton; canonical acme fixture
  (`tests/unit/tools/fixtures/arch/acme.yaml`). `→ D1`
- **Model/resolver/YAML** (was Phase 1; 1,800 py budget): Pydantic
  models, deterministic YAML I/O, architect-authored resolver semantics
  suite, resolver (state-at-position, clipping, diff, advance), located
  validation, dev CLI, pack facade; v1 modules deleted at cutover.
  `→ D2–D4`
- **Excel adapter** (was Phase 2; 900 py): ten-sheet round-trip with
  header normalization, in-place mode-aware write, atomic located
  errors, `arch.import_excel` / `arch.export`. `→ D5`
- **Report app** (was Phase 3; 5,000 TS/TSX + 400 py): payload + client
  projection contracts (report.md), single-file bundle (React Flow +
  elkjs + AG Grid), client projection + union layout, time slider +
  diff overlay, tables, fragment views. `→ D6, D7`
- **Gate rework** (was Phase 3R waves 1–2): wave 1 schema (C4 naming,
  auto ids, inclusive intervals, provider/consumer interface model,
  ten-sheet Excel) `→ D9a, D9b` — gate PASSED 2026-08-25 including the
  scripted Excel hand-edit exercise; wave 2 UI (chrome / panels /
  tables + canvas semantics) `→ D10a, D10b`, commit c37e3d05. Residual
  caveat: the `arch_end_milestones` VSTACK/FILTER dropdown is still
  unverified in real Excel — eyeball it next time a generated workbook
  is opened.
- **UI polish** (was Phase 3P; four passes, all gates PASSED; specs:
  report.md "Polish contract" 1–4): D13a app shell (2026-08-28,
  974/1,800 changed lines), D13b canvas composition (2026-08-28,
  407/1,400), D13c graph elements (2026-08-28, 797/1,600), D13d View /
  Info / Data content and states (2026-08-29, 630/1,500). Every
  ui-polish.md issue is CLOSED / WAIVED / superseded.
- **Subsystem level** (was the D14 interlude; gate PASSED 2026-08-29,
  293/1,100): System / Subsystem / Container / Component / Code chain,
  Subsystem entity kind, eleven-sheet Excel, acme fixture delta.
- [x] **P11 — canvas presentation** (added 2026-08-29 from the user's
  IcePanel comparison review; spec: report.md "Polish contract — pass 5:
  canvas presentation (P11)"; DONE, gate PASSED 2026-08-29 at
  736/2,400 changed source lines plus a small architect fix at the
  gate — see the progress log).
  Topology-aware layout (hub-centered radial for star-shaped flat
  graphs, layered kept elsewhere), uniform spacing, edge termination
  stubs + distributed visible ports, at-rest edge label pills, quiet
  neutral strokes, strict color economy (one accent, spent only on
  interaction), per-kind color identity with the user-definable YAML
  `theme` block (schema.md "Theme"; Excel Settings sheet — the small
  Python scope), compact user cards. Prechecks done 2026-08-29: elkjs
  0.12.0 bundles radial/stress/force/sporeOverlap; endpoint kinds
  already unrestricted; systems structurally root-only.
- [x] **P12 — map model: in-place C4 expansion** (added 2026-08-29,
  user-directed; spec: report.md "Map contract — in-place C4 expansion
  (P12)"; DONE, gate PASSED 2026-08-29 at 710/2,600 executor lines
  plus the architect's 120-line anchor perimeter-overflow fix — see
  the progress log). Expansion-set view state replacing
  level+drill, tree-based one-generation expand/collapse (mixed child
  kinds), persistent cumulative expansion, deepest-visible endpoint
  resolution (defined vs derived attachment), Detail dropdown as bulk
  presets, drill/breadcrumb retirement, local push-apart relayout with
  position stability, boundary identity with description, acme
  showcase-path delta (four-level zoom path + subsystem- and
  component-level interfaces). Reverses answered question Q5.
- [ ] **Phase 1 exit gate (architect + user)** — the held 3P exit gate:
  open acme's report cold and the story reads without explanation and
  *looks* deliberate. Run ui-polish-direction.md "Acceptance checks" at
  1440 × 900 and 1024 × 720 under `file://` (light theme) —
  console-clean, zero external requests — and rerun the test-ui.md
  walkthrough (fresh load, select card + spline, Stage switch, Data
  open, 1024 × 720) confirming no behavior defect reproduces
  (ui-polish.md is already fully annotated). Walkthrough note: at Base
  the Subsystem level is empty by design — subsystems arrive with the
  migration waves. Only after this gate does wave 2 start.

## Phase 2 — Sequence diagrams, saved views, exports (waves 2–3)

Unlocks at the Phase 1 exit gate. Owner docs: sequence.md (P21/P31),
report.md (P22/P23). Budgets are re-agreed when each prompt is issued
(provisional: ~500 py for P21, ~2,200 TS/TSX for P31). Write-path
decision (2026-08-24) still stands: the app has **view** mode
(standalone `file://`, read-only) and **edit** mode (local server owning
the YAML write path); edit-mode work stays in Phase 3.

Wave 2 — independent chunks, run in parallel once each chunk's architect
inputs exist:

- [ ] **Architect (before P21):** message-file attachments design (user
      request 2026-08-26): sequence messages AND model interfaces can
      link to sample request/response payload files (xml, json, csv)
      stored beside the model; the report renders them
      syntax-highlighted (highlighter ships in the offline bundle, no
      external requests). Lands as amendments to schema.md
      (interface-level field), sequence.md (DSL reference + `sequences`
      payload), and report.md (viewer contract) BEFORE P21 runs; the
      held P21 prompt is re-scoped to parse/emit the refs. The
      read-only Payload viewer deferred out of D13d (2026-08-29) ships
      with this design.
- [ ] **P21 (was D12a)** — sequence parser, validation findings,
      `sequences` payload, CLI + facade wiring. Control mechanism: the
      parser-vector fixture
      (`tests/unit/tools/fixtures/arch/sequence/`, committed
      2026-08-25). Prompt issued 2026-08-25, ON HOLD — re-scope for
      message-file refs before running.
- [ ] **P22 (was D11)** — saved report definitions + guided views:
      `p3-report-definitions` (named reports, view-mode flow — starting
      point: export the config as a ready-to-paste `views:` YAML entry;
      persist-to-model rides the deferred edit path) and
      `p3-ui-guided-view` (authored, playable guided views; resolves
      the MAP/PATH/LENS placeholders left by D7). Gated on architect
      designs for both. Issues: `issues/p3-*`.
- [ ] **P23 (was D8)** — client-side SVG / draw.io download from the
      report (serialize the laid-out scene client-side — the v2
      `ArchitectureScene`-not-DOM rule applies) + SQLite adapter (one
      table/kind + properties side table, per adapters.md).

Wave 3 — after the P21 gate:

- [ ] **Architect (P31 control):** layout vectors + 2–3 acme flow docs
      (multi-scenario, interval-carrying, ad-hoc participant).
- [ ] **P31 (was D12b)** — `seqlayout.ts`, SVG layer, entity-box header
      row, SEQ-* interactions, fragment keys.
- [ ] **Sequence gate (architect + user):** open an acme flow from
      View's Sequences group, play it through, switch scenario via the
      dropdown, focus a participant, hide one, open the Map vertical
      overview — the story reads without explanation; sticky headers
      hold; open a message's linked request/response file and it
      renders syntax-highlighted; console clean; zero external requests
      from `file://`.

## Phase 3 — Delivery, edit mode, backfill (waves 4–5)

Wave 4 — per-item budgets, ordered by demonstrated need:

- [ ] **P41** — SharePoint transport reusing the Excel mapping.
- [ ] **P42** — migration converter from v2 YAML — only if a real v2
      dataset exists to migrate; otherwise skip (throwaway tooling).
- [ ] **Architect:** edit-mode design — the local-server write path
      (deferred until Schema, Report, and File Import were complete;
      those are done, so this unblocks whenever edit mode is
      prioritised).
- [ ] **P43** — edit mode: `p3-edit-save-back` +
      `p3-ui-manual-positions` (after the edit-mode design).
- [ ] Revisit deferred items against demonstrated need only: Confluence
      embedding, PDF, dark theme (ui-polish.md #24 evidence binds any
      future dark pass).

Wave 5 — speed-mode debt, once v3 is stable:

- [ ] **Architect:** OpenSpec — author the v3 spec
      (`openspec/specs/.../tool-arch/`) from the shipped behavior;
      archive/replace v1 spec content.
- [ ] **P51** — test breadth: validation codes with location
      assertions, YAML/Excel error locations, header-normalization
      cases, model field-rule cases, template generation (mechanical;
      prompt written then).
- [ ] **Architect:** user-facing pack docs / docs-site page for the
      arch pack.

## Exploration branches

None yet. Format: `branch-name — question being explored — outcome`.

## Open questions (record answers in the design docs, log the change here)

1. Per-state layout fallback if union-graph layout is chronically poor for
   sparse early states (risk table; re-evaluate at the Phase 1 exit
   gate — D13b's layout work may moot it).

Answered questions (answers live in the design docs; details in
log-archive.md): P12 anchor-capacity overflow (Q2 of the P12 gate,
2026-08-29 — perimeter spill to adjacent sides, architect-implemented;
report.md "Perimeter overflow" under pass-5 edge termination is the
authority); bundle location/build wiring (report.md "Shape");
`arch.convert` umbrella naming (as-shipped by D5); legend dim-not-hide
with tags driver (Q4, 2026-08-24); drill + 4-level C4 zoom over
in-place expand/collapse (Q5, 2026-08-24 — **REVERSED 2026-08-29**,
user-directed: the map model wins; report.md "Map contract (P12)" is
the new authority); interactions.md superseded
and mined (Q6, 2026-08-24); D9b projection-vector conversion to
inclusive `end_in` (Q7, 2026-08-24).

## Progress log (append-only, newest first)

- **2026-08-29** — Phase 1 exit gate: architect half RUN (user half
  outstanding) + one gate fix landed. Walkthrough at 1440×900 and
  1024×720 under `file://` (light theme, state cleared for true cold
  load): console clean at every step, the only network request is the
  local HTML file, cold open reads (radial hub, at-rest pills, Read
  framing), card select opens Info with one-hop accent and keeps the
  selection visible, spline select shows connection Details with linked
  endpoints/direction/member, Stage 5 renders the cutover story (new
  hub + retired dashes), Data opens with four tabs and no empty
  columns, at 1024×720 View auto-collapses when Info opens and the app
  fills the viewport exactly (1024×720 doc size, zero scroll).
  Evidence: `plans/arch/wip/test-results/exit-gate/*.png`.
  GATE FIX (architect, mid-gate user finding): splines rendered dead
  straight — the executor's cubic controls sat ON the chord (45% along
  it), violating the pass-5 contract (report.md:1006 "control points
  perpendicular to the card border"; :1318 "curve runs between stub
  tips"). `splinePath.ts` now derives controls from the anchor-side
  normals (reach 0.35×span clamped 24–140 px, waypoint tangent 0.12)
  and places label pills by sampling the true curve; stubs, arrows,
  obstacle routing, and the returned polyline are unchanged (45
  frontend tests pass unmodified). Live re-check matches the IcePanel
  reference: sweeping S-curves, perpendicular arrivals, pills on the
  curve, one-hop accent intact, console clean. Bundle rebuilt, acme
  report regenerated. Tooling note: Playwright MCP's screenshot tool
  wedged mid-session (5 s timeouts with a quiescent page); fixed by
  `ot_servers.restart(name='playwright')`. Not re-run this pass
  (verified at the D13a–d gates, unaffected by the spline fix): dock
  drag-resize, forced reduced-motion. Payload-viewer and sequence
  acceptance checks are Phase 2 scope. Next action: user reviews the
  regenerated `plans/arch/wip/acme-report.html` + the exit-gate
  screenshots and confirms (or fails) the gate; on pass, wave 2 opens
  with the attachments design → P21.

- **2026-08-29** — P12 anchor-capacity blocker resolved (architect) and
  the P12 architect gate PASSED; tree committed. Design decision on open
  question 2: **perimeter overflow** — an over-full card side sheds its
  outermost endpoints around the nearest corner to the adjacent side,
  bearing-recomputed so perimeter order holds, cascading
  deterministically; cards never grow for edge count, aggregation
  unchanged, RangeError only when total demand exceeds the whole
  perimeter (report.md "Perimeter overflow" under the pass-5 edge
  termination rules is the authority; enlarging cards and cross-pair
  aggregation were rejected — the former couples geometry to edge
  count, the latter is semantically impossible for distinct visible
  pairs). Implemented in `edgeAnchors.ts` (+120 architect lines outside
  the executor budget) with a spill + true-impossible test added.
  Previously blocked walkthrough steps then verified live: the
  Container preset at stage 1 renders (20 cards / 13 boundaries, the
  monolith's edges distributed with zero converged ports), all four
  presets apply, browser Back walks preset history, link reload
  restores the full Component expansion (33 cards / 28 boundaries,
  dropdown "Custom"/preset detection correct), 1024×720 fills with no
  scroll — console clean at every step; `preset-container.png` replaced
  with passing evidence. Gate re-verification: frontend 45 passed
  (16 files incl. all six prescribed P12 cases — three in
  projectionWave2.test.ts, presets/stability/fragment in
  App/layout/view tests), arch py 79 passed, `just lint`, `tsc
  --noEmit`, `just build-arch-report`, acme regenerated; executor
  budget confirmed at 710/2,600 (686 TS/CSS + 24 acme). Code review
  conforms to the map contract: validated cumulative `expand` fragment
  with legacy level/drill mapping, authored-containment presets with
  Custom detection, one history entry per action, recursive mixed-kind
  boundary projection with deepest-visible endpoint resolution
  (boundary attachment for definitions on expanded entities),
  internal-edge suppression, drill/breadcrumb/Up retirement,
  `stableExpansionLayout` minimal push-apart with cached collapse
  restore, presets re-laying fresh under P11 star rules, boundary
  identity with description, and the two showcase interfaces exactly
  as authored. The executor's own live pass (center drift < 0.003 px,
  15/15 position restore, four-level reattachment) plus the
  map-four-levels screenshot confirm the showcase path. Next action:
  the Phase 1 exit gate (architect + user).

- **2026-08-29** — P12 rule-9 retry reached the prompt's explicit
  anchor-capacity stop condition. Before the stop, the 1440×900 file pass
  had a clean console and one local-file request; system expansion preserved
  Digital Commerce Platform's screen center within 0.003 px and kept the
  viewport transform unchanged, while only four overlapping neighbors moved.
  The live four-level path rendered System → Storefront and Edge → Commerce
  Edge → both components; the cutover edge reattached from subsystem to
  container to `components:strangler-route-config`; collapse restored all 15
  cold-layout node styles exactly; each tested expansion, collapse, and preset
  added one history entry. Captured `map-collapsed.png`,
  `map-sys-expanded.png`, `endpoint-slide.png`, and `map-four-levels.png`.
  Applying the Container preset then raised `RangeError`: 11 anchors cannot
  fit the 162 px right side of `containers:commerce-monolith` with 14 px
  separation and corner clearance. `preset-container.png` records the failed
  render, not passing evidence. Stopped without changing spacing. The
  remaining presets, link reload/Back checks, 1024×720 pass, and successful
  Container screenshot remain blocked on open question 2.

- **2026-08-29** — P12 in-place C4 map expansion implemented; left
  uncommitted for architect review. Fragment state now uses a validated,
  cumulative `expand` set with legacy link mapping, Detail bulk presets,
  Custom detection, one-entry history updates, subtree-pruning collapse,
  and selection restoration. The map projects recursive mixed-kind
  boundaries, resolves each connection endpoint to its deepest visible
  ancestor, aggregates shared pairs, suppresses internal splines while
  retaining connection facts, and attaches definitions on expanded
  entities to their boundary. Expansion uses nested ELK interiors, caches
  layouts by `(timeline, expansion set)`, grows locally with deterministic
  48 px push-apart, restores cached collapse positions, and leaves camera
  zoom unchanged. The Acme fixture adds `edge-bot-defense` and
  `strangler-route-cutover`; payload, bundle, and wip report regenerated.
  Source budget: **710 / 2,600 changed lines** (tests and generated files
  excluded). Tests: exactly six prescribed P12 cases added or recut;
  frontend **44 passed**, arch Python **79 passed / 540 deselected**, smoke
  **27 passed / 3,210 deselected**, `just lint`, TypeScript, bundle build,
  fixture validation (**0 errors / 25 warnings**), and `git diff --check`
  passed. Live UI gate remains outstanding: OneTool Playwright stayed
  locked by another browser profile after its proxy restart, and the
  isolated in-app browser had no available backend, so no P12 screenshots,
  console/network capture, or viewport walkthrough were claimed.
  Assumptions resolved from the strongest explicit contracts: (1) the
  user's final no-commit instruction and standard rule 8 override the
  request's earlier commit wording; (2) expansion ids use the existing
  canonical `kind:id` node keys; (3) fragment validation and presets use
  authored containment rather than one stage's live children so expansion
  survives stage changes, while affordances/counts use live children; (4)
  an explicit `expand` value wins over legacy `level` when both exist, and
  a legacy `drill` adds its expandable ancestor chain and selection; (5)
  applying a preset deliberately replaces any cached target layout with a
  fresh P11 radial-or-layered layout. Open questions: none. Next action:
  architect review, then rerun the rule-9 live gate when the browser profile
  is free.

- **2026-08-29** — P11 architect gate PASSED (with one gate fix); tree
  committed; P12 prompt re-reviewed and finalized per the pipeline rule.
  Independently re-verified: frontend 45 passed, arch py 79 passed,
  `just lint` clean, `just build-arch-report` (incl. `tsc --noEmit`)
  reproduced the pre-fix template byte-for-byte, budget confirmed at
  736/2,400 (697 tracked + 39 new theme.ts), CLI runs standalone
  (acme validate: 0 errors / 24 warnings). Code review conforms to the
  pass-5 contract: deterministic radial construction with 48 px
  clearance and grid-packed disconnected nodes, bearing-ordered
  distributed anchors (>= 14 px separation, centered groups respect
  corner clearance), straight 12 px stubs with flush 0.8x arrows,
  midpoint label pills with +/-20% alternating nudge and
  card/pill-collision avoidance, neutral `--edge` strokes with accent
  reserved for selection/one-hop, six `--kind-*` tokens shared across
  canvas/Info/Data, theme round-trip (YAML/Excel Settings/payload) with
  located `unknown_theme_key`/`invalid_color`, compact 220 px user
  cards. GATE FIX (architect, in-scope): the executor tied interface-
  port expansion to `showLabel`, which P11 widened to Read — so at Read
  every interface also rendered an expanded port pill at its attachment
  point; live Playwright check found all 14 clipping their cards and 9
  pill-pill overlaps (the executor's "no overlaps" claim had only
  checked midpoint labels; their own screenshots show the clutter).
  Fixed by a separate `expandPort` flag (Full depth or
  selected/hovered — D13c's original timing); at Read ports are now
  dots, and the live re-check shows zero pill-card and zero pill-pill
  overlaps at Read with a clean console. Bundle rebuilt, acme report
  regenerated, labels-at-rest.png recaptured (the other four executor
  screenshots predate the fix but their subjects are unaffected).
  Watch item for P12: `edgeAnchors` fails fast (RangeError) when a
  side cannot fit its batch — fine today, but expansion concentrates
  edges, noted in the P12 prompt. P12 prompt finalized: post-P11
  integration notes (expandPort split, `preferredHub` pass-through,
  anchor-capacity stop-and-ask) and the exact acme showcase rows
  (edge-bot-defense at subsystem level, strangler-route-cutover at
  component level; four-level path commerce-platform -> storefront-edge
  -> commerce-edge -> components verified live in the fixture). Next
  action: user confirms the P12 budget (2,600) and runs the P12 prompt;
  the Phase 1 exit gate follows the P12 gate.

- **2026-08-29** — P11 canvas presentation implemented; left uncommitted for
  the architect's gate review. Flat projected stars now seed a deterministic
  radial union layout (centered hub, top-biased users, outward deeper nodes,
  disconnected grid pack); non-stars retain the existing ELK input. Edges use
  batched distributed ports, 12 px normal stubs, flush smaller arrows, and
  collision-checked Read/Full label pills. Canvas colors are neutral at rest,
  share six kind tokens across canvas/Info/Data, reserve accent for interaction,
  and compact user cards. Optional `theme.kinds` now validates, round-trips in
  canonical YAML and Excel `Settings`, and passes through the payload. Source
  budget: **736 / 2,400 lines** (additions + deletions; tests/generated bundle
  excluded). Tests: exactly six prescribed cases added or updated; frontend
  **45 passed**, arch Python **79 passed / 540 deselected**, `just lint` and
  `just build-arch-report` clean. CLI payload fixtures and the acme report were
  regenerated. Rule-9 file verification passed at 1440×900 and 1024×720 with
  zero console warnings/errors, local-file requests only, no card/label
  overlaps, and the required five screenshots captured in `plans/arch/wip/`.
  Assumptions resolved from the strongest explicit contracts: (1) the user's
  final no-commit instruction and standard rule 8 override the prompt's generic
  commit wording; (2) “ELK unchanged” preserves its existing 40/72 px options,
  while radial layout alone guarantees the explicit 48 px clearance; (3) a
  fixed side has finite 14 px port capacity, so impossible batches fail with a
  clear `RangeError`; (4) equal hub candidates sort by incident count then node
  key, and disconnected means outside the chosen hub component; (5) absent
  payload theme serializes as `{}` because the payload schema explicitly names
  the key; (6) the numbered Settings-sheet contract supersedes the stale
  ten-sheet wording, with Settings optional on read and created when needed;
  (7) theme keys and valid hex values preserve authored spelling/case without
  normalization; (8) “rendered edges” means projected aggregated graph edges;
  (9) hub center means the one-hop ring's bounding-box center, with deeper and
  disconnected nodes allowed outside it; (10) the cold projected star chooses
  the hub for the cached union layout, preserving stage-stable positions without
  letting a future hidden node occupy the baseline center. Open questions: none.

- **2026-08-29** — P11/P12 designed and authored (user-directed, from the
  IcePanel comparison review of the current acme report); tree committed.
  The review found the landscape layout, edge presentation, color usage,
  and level navigation all short of the bar: corner-fan layered layout
  for a star graph, no at-rest edge labels, teal-everywhere, endpoint
  convergence at corners, and level-redraw navigation that loses the
  user's place. Thirty agreed changes captured as two new wave-1 chunks
  ahead of the Phase 1 exit gate: **P11 canvas presentation** (radial
  hub layout for star-shaped flat graphs, uniform spacing, termination
  stubs + distributed visible ports, at-rest white label pills, quiet
  neutral strokes, strict one-accent color economy, per-kind color
  identity user-definable via a new YAML `theme` block with Excel
  Settings sheet, compact user cards) and **P12 map model** (expansion-
  set view state replacing level+drill, tree-based one-generation
  expansion with mixed child kinds, persistent cumulative expansion,
  deepest-visible endpoint resolution with defined/derived attachment,
  Detail dropdown as bulk presets, drill retirement, local push-apart
  relayout, boundary identity, acme showcase-path delta) — P12
  REVERSES Q5 (2026-08-24). Design landed as: schema.md normative
  containment matrix + "Theme" section, adapters.md Settings sheet
  (twelve sheets), report.md "Polish contract — pass 5 (P11)" and "Map
  contract (P12)", ui-polish-direction.md Detail + canvas-language
  amendments. Prechecks passed: elkjs 0.12.0 bundles
  radial/stress/sporeOverlap; ENDPOINT_KINDS already spans all six
  entity kinds (no Python for any-level interfaces); System/User have
  no parent field (matrix structurally enforced). New process rule
  recorded: rolling prompt pipeline — prompts generated ahead, each
  reviewed/updated at the preceding gate. Prompts authored in
  delegation.md: P11 READY (budget 2,400 proposed), P12 GENERATED
  (budget 2,600 proposed; re-review at the P11 gate). Next action: user
  confirms the P11 budget and runs the P11 prompt; architect gates it,
  re-reviews P12, then P12 runs; the Phase 1 exit gate follows both.

- **2026-08-29** — Plan reorganised (user-directed); tree committed.
  Chunk ids move to `Pxy` wave numbering (x = wave, y = priority) and
  the phases are renamed Phase 1 / 2 / 3. Completed work (old Phases
  0–3, 3R waves 1–2, 3P passes, D14) is collapsed into the Phase 1 DONE
  record; finished chunks keep their historical ids (D1–D14, D13a–D13d)
  wherever already referenced. Outstanding chunks renumber: D12a→P21,
  D11→P22, D8→P23, D12b→P31; newly numbered P41 SharePoint, P42
  migration converter (conditional), P43 edit mode, P51 test-breadth
  backfill — mapping table in "Chunk numbering"; delegation.md headings
  carry both ids. Status at reorg: DONE — the whole Phase 1 build
  (D1–D10, polish passes D13a–D13d, D14 subsystem level, all gates
  PASSED), sequence.md v1, the sequence parser-vector fixture, and all
  27 ui-polish.md issues closed/waived. OUTSTANDING — the Phase 1 exit
  gate (architect + user, next action), then wave 2 (attachments
  design → P21; P22; P23), wave 3 (layout vectors → P31 → sequence
  gate), waves 4–5 (P41–P43; OpenSpec, P51, docs backfill). The nine
  2026-08-28 log entries moved to log-archive.md. Next action: run the
  Phase 1 exit gate with the user.

- **2026-08-29** — D13d architect gate PASSED; tree committed. Independently
  re-verified: 42 frontend tests (15 files) including exactly the six
  prescribed D13d cases, `just lint`, 78 arch py tests,
  `just build-arch-report` reproduces the tree's template byte-for-byte
  (shasum match), budget confirmed at 630/1,500 changed source lines
  (389 tracked + 241 new modules InfoPanel.tsx/display.ts). Code review
  conforms to the pass-4 contract: viewport-filling html/body/#root with
  the 1024 × 720 clamp; ResizablePanel title rows with icon-only chevrons
  and icon rails (all floating pills/gutters gone from styles.css); Tags
  capped at five control rows with internal scroll; InfoPanel humanized
  collision-free details grid, kind-coloured Contains chips (cap 8 +
  expand), "Changes at this stage" from the diff with the card
  change-popover deleted (Escape handler updated), connection Details
  with linked endpoints / aspect-aware direction / lifecycle from payload
  intervals, entity-only Connections tab, bounded Back history (20),
  persistent "View dependencies"; GridPanel at the four direction tabs
  with rawState Entities across all six kinds, first-render auto-size
  gated on no stored layout, all-empty columns hidden, humanized
  min-width headers, Show on Canvas banner, two-way selection sync with
  ensureNodeVisible keyed on rows; motion tokens + content-in animation
  with the reduced-motion animation override. AG Grid conditional mount
  verified safe (create effect depends on rows, early-returns without an
  element). Screenshots confirm the connection Details, entity Details
  chips, auto-sized headers, and collapsed rails. Acceptable deviations
  noted: clip status reads "Retired at this stage" (drops the clipped-by
  attribution — one-label-style simplification); a table-selected row not
  rendered at the current level now gets the Show on Canvas banner
  instead of silently highlighting an ancestor (that IS the direction's
  flow); connection rows selected in Data/Info now also highlight their
  containing spline (in-scope improvement). ui-polish.md annotated: #13,
  #20, #21, #22, #25, #26, #27 CLOSED and #16 closed in full — every
  issue in the file now carries a CLOSED/WAIVED/superseded note. Next
  action: the Phase 3P exit gate (architect + user): the cold-open story
  test, the direction's acceptance checks at 1440 × 900 and 1024 × 720
  under `file://`, and the test-ui.md walkthrough re-run; after it passes,
  D12a re-scope, D11, D12b, and D8 unlock.

- **2026-08-29**: D13d View / Info / Data content and states complete;
  worktree left dirty for architect review. The report now fills the viewport
  at and above the 1024 x 720 floor. Each dock has a title row with an
  icon-only collapse chevron and reopens from a reserved icon rail. View uses
  compact diagram and link rows, hides controls without a choice, and limits
  Tags to five internally scrolling rows. Info humanizes every field in a
  collision-free grid, links contained entities as kind-coloured chips, moves
  stage changes out of the removed card popover, gives interfaces and splines
  linked endpoint, direction, value, interval, and member details, provides
  internal Back, and keeps View dependencies in Details. Data now has the four
  prescribed tabs; raw-state Entities includes every live kind, including
  subsystems; empty columns hide by default, populated columns auto-size with
  full headers, Show on Canvas changes to the row's detail, and canvas/table
  selection stays synchronized after grid rebuilds. Empty states, diagnostics,
  shared dock/Info/search motion, and reduced-motion overrides completed the
  consistency sweep. Source budget: 630/1,500 changed TS/TSX/CSS lines,
  counted as additions plus deletions with tests and the generated bundle
  excluded.
  Tests: exactly the six prescribed D13d cases added; frontend 42 passed across
  15 files. `just lint`, smoke 27 passed / 3,209 deselected, arch Python 78
  passed / 540 deselected, `just build-arch-report`, CLI acme regeneration,
  and `git diff --check` passed. Rule-9 Playwright passed on the generated
  `file://` report in light theme at 1440 x 900, 1024 x 720, and 1920 x 1080:
  the app, document, and body matched each viewport exactly with zero scroll or
  dead band; every console check was clean; the only request was the local HTML
  file. The walkthrough covered entity Details and Contains chips, stage
  changes, connection Details and Back, four Data tabs, auto-sized headers,
  Show on Canvas, two-way selection, every dock's collapse/reopen path, and the
  final Escape order. Forced reduced motion measured 0.01 ms dock/search timing
  and no edge animation. Screenshots: `wip/test-results/d13d/info-entity-details.png`,
  `info-connection.png`, `data-autosized.png`, `collapsed-rails.png`, and
  `viewport-fill-1920.png`. Assumptions: the execution request confirms the
  1,500-line budget; the final no-commit instruction controls; rule 8 permits
  this progress entry as the sole design-doc write; Code rows use Component
  detail and User rows use System detail because those are their deepest
  renderable projections; Show on Canvas clears drill and scope so the chosen
  row appears; interface direction follows the active Calls or Data flow field,
  while relationship direction remains source to target; kind chips use
  distinct light-theme colours derived from the existing token palette. Open
  questions: none. Next action: architect gate review, then the Phase 3P exit
  gate.

- **2026-08-29** — D13d authored (architect); tree committed. Normative
  spec "Polish contract — pass 4: View / Info / Data content and states
  (D13d)" added to report.md, grounded in the post-D14 tree (SidePanel,
  ResizablePanel, GridPanel, ViewDock): viewport-filling shell with dock
  header rows / chevrons / icon rails replacing every floating pill and
  gutter (#25, #26); no-choice View controls hide and Tags caps at 5
  rows (#27); humanized non-overlapping Info kv with linked Contains
  chips (#20); stage changes as a Details section with the card
  change-popover removed (the D13c leftover); kind-appropriate
  connection Details rendering endpoints, direction, values, and
  lifecycle interval from the existing payload (#21, no Python);
  internal Back + "View dependencies" in Details (#16 rest); final
  Escape order (#13); Data at the direction's four tabs with the D14
  subsystems tab folded into a rawState-sourced Entities, auto-size /
  empty-collapse / untruncated headers (#22), Show on Canvas, two-way
  sync; designed empty states and the motion/reduced-motion sweep. Six
  prescribed tests. Architect decision: the read-only Payload viewer and
  Attachments tabs are DEFERRED out of 3P to the Phase 3S attachments
  chunk — no file refs exist in the payload until the schema.md/
  sequence.md attachments design lands, and the syntax highlighter
  should ship once, with real data (pass-4 bullet amended; the 3P exit
  gate does not check a Payload viewer). D13d prompt READY in
  delegation.md, proposed budget 1,500 changed source lines. Next
  action: user confirms the D13d budget and passes the delegation.md
  prompt to the executor; the architect gates the result, then runs the
  3P exit gate (with the user) — after which D12a re-scope, D11, D12b,
  and D8 unlock.

- **2026-08-29** — D14 architect gate PASSED; #21 payload precheck PASSED;
  tree committed. Independently re-verified: 78 arch py tests + `just lint`
  clean, 36 frontend tests (12 files) including the five prescribed D14
  cases, `just build-arch-report` reproduces the tree's template
  byte-for-byte (shasum match), budget confirmed at 293/1,100 changed
  source lines (203 py/TS + 90 acme fixture). Code review conforms to the
  D14 contract: Subsystem kind with `ss` prefix and the strict
  system→subsystem→container chain (model/ids/yamlio), resolver replaces
  the container-nesting recursion with flat subsystem/container passes,
  ambiguous-parent moves to systems×subsystems, the containment-cycle
  check is correctly deleted (no cycle is constructible in the new chain),
  eleven-sheet Excel with Subsystems as sheet 5; frontend Level rename
  with the Subsystem option hidden for empty datasets, the rewritten
  boundary-nesting table, and search/Info/Data wiring. Fixture verified:
  six subsystems under commerce-platform, exactly the 19 prescribed
  container rewires, zero clips at base. Because the executor's cold-load
  screenshot showed only 3–4 subsystems, a live Playwright spot-check was
  run: at the final stage the subsystem level renders all 6 Subsystem
  cards plus 10 ungrouped container leaves (3 in-viewport — correct under
  D13b's Read-capped cold framing); at Base the level shows none because
  the subsystems arrive with the migration waves (correct liveness — note
  for the exit-gate walkthrough); console clean. Minor, not gate-blocking:
  Data gained a dedicated `subsystems` tab reading rawState rows — pass 4
  owns Data-table shape and may fold or keep it. #21 precheck: interface
  rows already carry provider/consumer/call_direction/name/tags/
  properties/intervals and relationship rows source/target/action/
  description/intervals — connection details render from the existing
  payload, no plumbing, nothing escalates to the user. Log entries dated
  2026-08-27 and older moved to log-archive.md (inline log was at 15).
  Next action: author the D13d pass-4 spec + prompt.

- **(older entries)** — see [log-archive.md](log-archive.md).
