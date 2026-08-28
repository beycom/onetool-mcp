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
| Open issues (Phase 2 wave 2) | `plans/arch/arch-v3/issues/` — p3-* files + index (feed D22/D43); resolved p1/p2 files in `issues/resolved/`; Archify/IcePanel reference screenshots stay in `issues/` (cited by the polish pass specs) |
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
  reviewed it at the gate. Remaining sequence (waves 0–1 done — see
  Phase 1): Phase 1 exit gate → wave 2 (D21 ∥ D22 ∥ D23 as their
  architect artifacts land) → wave 3 (D31 → sequence gate) → waves 4–5.
  Historical sequencing detail: log-archive.md.

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

Executor chunks are numbered `Dxy`: `x` = wave (execution order), `y` =
priority inside the wave (lower first; same-wave chunks may run in
parallel once their architect inputs exist). Waves 0–1 are the completed
build — their chunks keep their historical ids (D1–D14, D13a–D13d) in
the progress log, the design docs, and delegation.md, because renaming
finished work would break those references. Outstanding chunks carry the
new ids, with the old id noted as `(was Dn)`; delegation.md headings
carry both.

| New id | Was | Chunk |
| --- | --- | --- |
| D21 | D12a | Sequence parser + payload (prompt ON HOLD, needs re-scope) |
| D22 | D11 | Report definitions + guided views |
| D23 | D8 | Client-side SVG / draw.io export + SQLite adapter |
| D31 | D12b | Sequence renderer frontend |
| D41 | — | SharePoint transport |
| D42 | — | v2 YAML migration converter (conditional) |
| D43 | — | Edit mode (save-back + manual positions) |
| D51 | Dn (backfill) | Test-breadth backfill |

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

Unlocks at the Phase 1 exit gate. Owner docs: sequence.md (D21/D31),
report.md (D22/D23). Budgets are re-agreed when each prompt is issued
(provisional: ~500 py for D21, ~2,200 TS/TSX for D31). Write-path
decision (2026-08-24) still stands: the app has **view** mode
(standalone `file://`, read-only) and **edit** mode (local server owning
the YAML write path); edit-mode work stays in Phase 3.

Wave 2 — independent chunks, run in parallel once each chunk's architect
inputs exist:

- [ ] **Architect (before D21):** message-file attachments design (user
      request 2026-08-26): sequence messages AND model interfaces can
      link to sample request/response payload files (xml, json, csv)
      stored beside the model; the report renders them
      syntax-highlighted (highlighter ships in the offline bundle, no
      external requests). Lands as amendments to schema.md
      (interface-level field), sequence.md (DSL reference + `sequences`
      payload), and report.md (viewer contract) BEFORE D21 runs; the
      held D21 prompt is re-scoped to parse/emit the refs. The
      read-only Payload viewer deferred out of D13d (2026-08-29) ships
      with this design.
- [ ] **D21 (was D12a)** — sequence parser, validation findings,
      `sequences` payload, CLI + facade wiring. Control mechanism: the
      parser-vector fixture
      (`tests/unit/tools/fixtures/arch/sequence/`, committed
      2026-08-25). Prompt issued 2026-08-25, ON HOLD — re-scope for
      message-file refs before running.
- [ ] **D22 (was D11)** — saved report definitions + guided views:
      `p3-report-definitions` (named reports, view-mode flow — starting
      point: export the config as a ready-to-paste `views:` YAML entry;
      persist-to-model rides the deferred edit path) and
      `p3-ui-guided-view` (authored, playable guided views; resolves
      the MAP/PATH/LENS placeholders left by D7). Gated on architect
      designs for both. Issues: `issues/p3-*`.
- [ ] **D23 (was D8)** — client-side SVG / draw.io download from the
      report (serialize the laid-out scene client-side — the v2
      `ArchitectureScene`-not-DOM rule applies) + SQLite adapter (one
      table/kind + properties side table, per adapters.md).

Wave 3 — after the D21 gate:

- [ ] **Architect (D31 control):** layout vectors + 2–3 acme flow docs
      (multi-scenario, interval-carrying, ad-hoc participant).
- [ ] **D31 (was D12b)** — `seqlayout.ts`, SVG layer, entity-box header
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

- [ ] **D41** — SharePoint transport reusing the Excel mapping.
- [ ] **D42** — migration converter from v2 YAML — only if a real v2
      dataset exists to migrate; otherwise skip (throwaway tooling).
- [ ] **Architect:** edit-mode design — the local-server write path
      (deferred until Schema, Report, and File Import were complete;
      those are done, so this unblocks whenever edit mode is
      prioritised).
- [ ] **D43** — edit mode: `p3-edit-save-back` +
      `p3-ui-manual-positions` (after the edit-mode design).
- [ ] Revisit deferred items against demonstrated need only: Confluence
      embedding, PDF, dark theme (ui-polish.md #24 evidence binds any
      future dark pass).

Wave 5 — speed-mode debt, once v3 is stable:

- [ ] **Architect:** OpenSpec — author the v3 spec
      (`openspec/specs/.../tool-arch/`) from the shipped behavior;
      archive/replace v1 spec content.
- [ ] **D51** — test breadth: validation codes with location
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
log-archive.md): bundle location/build wiring (report.md "Shape");
`arch.convert` umbrella naming (as-shipped by D5); legend dim-not-hide
with tags driver (Q4, 2026-08-24); drill + 4-level C4 zoom over
in-place expand/collapse (Q5, 2026-08-24); interactions.md superseded
and mined (Q6, 2026-08-24); D9b projection-vector conversion to
inclusive `end_in` (Q7, 2026-08-24).

## Progress log (append-only, newest first)

- **2026-08-29** — Plan reorganised (user-directed); tree committed.
  Chunk ids move to `Dxy` wave numbering (x = wave, y = priority) and
  the phases are renamed Phase 1 / 2 / 3. Completed work (old Phases
  0–3, 3R waves 1–2, 3P passes, D14) is collapsed into the Phase 1 DONE
  record; finished chunks keep their historical ids (D1–D14, D13a–D13d)
  wherever already referenced. Outstanding chunks renumber: D12a→D21,
  D11→D22, D8→D23, D12b→D31; newly numbered D41 SharePoint, D42
  migration converter (conditional), D43 edit mode, D51 test-breadth
  backfill — mapping table in "Chunk numbering"; delegation.md headings
  carry both ids. Status at reorg: DONE — the whole Phase 1 build
  (D1–D10, polish passes D13a–D13d, D14 subsystem level, all gates
  PASSED), sequence.md v1, the sequence parser-vector fixture, and all
  27 ui-polish.md issues closed/waived. OUTSTANDING — the Phase 1 exit
  gate (architect + user, next action), then wave 2 (attachments
  design → D21; D22; D23), wave 3 (layout vectors → D31 → sequence
  gate), waves 4–5 (D41–D43; OpenSpec, D51, docs backfill). The nine
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
