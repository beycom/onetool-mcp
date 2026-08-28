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
| Confirmed UI direction (3P/3S decision source) | `plans/arch/arch-v3/ui-polish-direction.md` — confirmed 2026-08-27; authoritative for all UI/interaction decisions, supersedes conflicting guidance in ui-polish.md and the report.md wave-2 contract. The `designs/` artboard directory was removed the same day (decisions captured in the direction; files in git history) |
| UI polish issue list (3P input) | `plans/arch/arch-v3/ui-polish.md` — 24 itemized issues from the 2026-08-25 Playwright walkthrough, tagged D13a–D13d, plus #25–#27 from 2026-08-28 user screenshot feedback (all D13d); the 3P pass specs must close or waive every tagged item (expectations superseded where they conflict with ui-polish-direction.md) |
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
normative spec plus the prompt, with budgets agreed per pass.

**Direction update (2026-08-27):** `ui-polish-direction.md` is confirmed
and is the decision source for every pass spec; report.md and sequence.md
are reconciled to it (Option E docked shell — View/Info/Data docks,
compact header, lower-left Map/Fit/Zoom, Stage/Relationship dropdowns,
splines, one-hop selection, light theme, 1024 × 720 floor). The
previously authored D13a spec and prompt were written against the wave-2
chrome and were **superseded pre-run**; each pass spec is re-authored from
the direction before its prompt is issued (D13a re-authored the same day
— READY below) — contract reconciliation precedes all frontend work. Secondary design references: the measured
Archify/IcePanel values in `research/ui/ui-research-findings.md` + the
evidence captures, and the reference screenshots in `issues/`.

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

**Itemized issue list (2026-08-25, second evidence source):**
`ui-polish.md` — 24 issues from a full Playwright walkthrough,
plus #25–#27 (2026-08-28 user screenshot feedback → D13d)
(per `wip/notes/test-ui.md`), each with observed → expected and a
D13a–D13d tag. It confirms the baseline above and adds measured
values (all 17 edges 1px `#B1B1B7`, `marker-end: null`, zero edge
labels) plus six interaction/behavior defects the original pass
bullets did not cover; those are now folded into passes 2 and 4
below. Each pass spec must close or explicitly waive every issue
tagged to it; the exit gate checks the list is empty.

- [x] **Pass 1 — app shell.** `→ D13a` (DONE, gate PASSED 2026-08-28;
      spec: report.md "Polish contract — pass 1: app shell"; 974/1,800
      changed source lines.)
      The Option E docked shell per the direction: compact
      header (identity + `Cmd/Ctrl+K` global search only), View dock
      left (grouped diagram list + Detail / Stage / Relationship /
      Tags controls + Copy view link), adaptive Info dock right,
      full-width Data dock bottom, dock resize / collapse / rail /
      restore behavior, fixed lower-left `Map | Fit | Zoom` cluster;
      removal of the status bar, floating legend, theme toggle,
      fullscreen, and Share. Light-only design tokens, sans-for-UI /
      mono-for-data typography, inline-SVG icons, contrast audit.
      1024 × 720 floor with View auto-collapse when Info opens at
      1024 px. Closes the shell-superseded issues (#14, #16 chrome,
      #18, #19, #23; #24 deferred with dark theme).
- [x] **Pass 2 — canvas composition: layout, fit, camera.** `→ D13b`
      (DONE, gate PASSED 2026-08-28; spec: report.md "Polish contract —
      pass 2: canvas composition"; 407/1,400 changed source lines.)
      Per-level content-sized cards (names never truncate before the
      box does — #10); ELK tuning — tighter spacing, aspect-ratio
      hint, proportional boundary padding; fit against the *visible*
      canvas between the docks (#8, #9); initial framing per the
      direction (whole graph only when it stays at Read, else cap at
      Read and center); semantic-zoom thresholds (Far / Read / Full)
      re-derived from real node scale (#11); dock open/close/resize
      preserves zoom and shifts the camera only enough to keep the
      focus visible — never a full Fit; layout stays fixed across
      Stage, Relationship, and tag changes; selection stays visible
      when Info opens (#12, #15 by construction — the vanishing
      chrome no longer exists); grid packing for sparse/edgeless
      drill sets; Map minimap attaches above the lower-left row.
      Behavior changes get tests; existing projection vectors and
      tests must stay green. Highest-risk pass.
- [x] **Interlude — subsystem level rename (user-directed 2026-08-28;
      exception to the no-new-features rule; runs after the pass-3
      gate — D13c was already in flight when this was designed).**
      `→ D14` (DONE, gate PASSED 2026-08-29; 293/1,100 changed
      source lines.)
      The detail-level model becomes System / Subsystem (optional) /
      Container / Component / Code: Subsystem is a new entity kind (a
      logical grouping of related containers inside a system);
      containers no longer nest; the former `top-containers` /
      "Child Containers" frontend levels are replaced by `subsystems`
      / `containers` with the Subsystem option hidden when a model
      defines none. Normative design landed 2026-08-28 in schema.md
      ("Entity kinds"), report.md ("C4 zoom and drill"), adapters.md
      (eleven-sheet workbook), ui-polish-direction.md (Detail
      dropdown). The acme fixture delta (six subsystems inside
      Digital Commerce Platform mapping the migration waves; 19
      container rewires; components already populated) is authored
      in the D14 prompt.
- [x] **Pass 3 — graph elements: cards, splines, selection.** `→ D13c`
      (DONE, gate PASSED 2026-08-28; spec: report.md "Polish contract —
      pass 3: graph elements"; 797/1,600 changed source lines.)
      Larger text-led cards per the direction's card anatomy — one
      rounded shape for every kind, no entity icons or logos, kind
      and fact pills, two-line name wrap; persistent drill affordance
      with a real hit target; **splines** replace orthogonal routing
      (kills #4/#5's rectangular detours and interior crossings) with
      distributed anchors, aggregation count chips, visible arrowheads
      and real contrast (#1, #2), label pills at Full and on
      selection/hover (#3); one-hop IcePanel selection emphasis
      (animated outgoing / static incoming in one accent, brightened
      neighbors, dimmed-but-readable unrelated, reduced-motion static
      fallback); containment boundaries as subtle tints with clear
      headers; interfaces as attached labeled ports (#6); stage-diff
      styling as an increment on legible base splines (#7);
      Relationship switch visibly changes the picture without moving
      boxes.
- [ ] **Pass 4 — View / Info / Data content and states.** `→ D13d`
      (spec: report.md "Polish contract — pass 4"; prompt READY in
      delegation.md; budget 1,500 changed source lines proposed —
      confirm before running.)
      View control stack per the direction (controls with no
      meaningful choice hide; guided-story controls at the top of
      View); adaptive Info — Details / Connections tabs, stage changes
      as a concise Details section, Attachments only when files
      exist, internal Back, kv grid that never overlaps with one
      label style (#20), "View dependencies" entry (resolves #16
      without a floating toolbar); connection details show endpoints
      (linked), direction, interface, relationship values, and
      lifecycle interval (#21) — **architect precheck before
      authoring this spec:** confirm the payload already carries that
      edge data; if it needs plumbing, that part escalates to the
      user at the gate rather than riding a polish pass (precheck
      PASSED 2026-08-29 — no plumbing needed); Data tables
      auto-size populated columns, collapse all-empty columns, never
      truncate headers (#22), sync selection with the canvas both
      ways, offer Show on Canvas; the read-only Payload viewer
      (DEFERRED 2026-08-29 to the Phase 3S attachments chunk — no
      file refs exist in the payload until that design lands);
      Escape order per the direction (#13); designed empty and
      failure states; final motion/consistency sweep with a
      reduced-motion audit.
      **Added scope (user feedback 2026-08-28, ui-polish.md §7):**
      the shell fills the browser viewport at any size at or above
      the 1024 × 720 floor — no fixed-size render, no outer page
      scroll or dead band (#25); dock chrome redesigned to standard
      clean panel patterns — slim dock header rows with icon-only
      collapse chevrons, collapsed docks as icon rails, no floating
      labeled pills ("Collapse View dock" / "Open Info dock" gutter /
      "Open Data dock" strip all replaced), View-dock diagram card
      and Copy view link restyled as compact list rows (#26); the
      Tags list caps at 5 visible rows then scrolls internally (#27).
- [ ] **Exit gate (architect + user):** the phase-3 gate question —
      open acme's report cold and the story reads without
      explanation, but now also *looks* deliberate: no dead-space
      fit, no phantom rectangles, readable cards at initial framing,
      coherent docked chrome. Run the direction's "Acceptance checks"
      at 1440 × 900 and 1024 × 720 under `file://` (light theme) —
      console-clean, zero external requests. Additionally: every
      ui-polish.md issue is closed, superseded, or carries an
      explicit waiver note in that file — rerun the test-ui.md
      walkthrough (fresh load, select card + spline, Stage switch,
      Data open, 1024 × 720) and confirm none of the behavior defects
      reproduce. Only after this gate do D11/D12b/D8 resume (and the
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
      + payload shape, renderer decision, SEQ-* interaction contract,
      verification plan. (2026-08-25; interaction contract revised
      2026-08-27 to the confirmed direction — controls in View, Scenario
      dropdown, Map overview; C4 group collapse and the floating
      navigator removed)
- [x] **Architect:** parser-vector fixture
      (`tests/unit/tools/fixtures/arch/sequence/`) — the D12a control
      mechanism. (2026-08-25; D12a prompt issued the same day)
- [ ] **Architect:** message-file attachments design (user request
      2026-08-26): sequence messages AND model interfaces can link to
      message files — sample request/response payloads (xml, json, csv)
      stored beside the model — and the report renders them
      syntax-highlighted (highlighter ships in the offline bundle; no
      external requests). Design lands as amendments to schema.md
      (interface-level field), sequence.md (DSL reference + `sequences`
      payload), and report.md (viewer contract: side panel for
      interfaces, message click-through in the seq view) BEFORE D12a
      runs; the held D12a prompt is re-scoped to parse/emit the refs.
- [ ] Python: parser, validation findings, `sequences` payload, CLI +
      facade wiring. `→ D12a` (prompt issued but ON HOLD until the
      Phase 3P exit gate — user directive 2026-08-25; re-scope for
      message-file refs before running — see architect item above)
- [ ] **Architect:** layout vectors + 2–3 acme flow docs (multi-scenario,
      interval-carrying, ad-hoc participant) — the D12b control mechanism.
- [ ] Frontend: `seqlayout.ts`, SVG layer, entity-box header row, SEQ-*
      interactions, fragment keys. `→ D12b` (after the phase-3 re-gate
      AND the Phase 3P exit gate; ∥ D11/D8)
- [ ] **Gate (architect + user):** open an acme flow from View's
      Sequences group, play it through, switch scenario via the
      dropdown, focus a participant, hide one, open the Map vertical
      overview — the story reads without explanation; sticky headers
      hold; open a message's linked request/response file in Data's
      Payload tab and it renders syntax-highlighted; console clean;
      zero external requests from `file://`.

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

- **(older entries)** — see [log-archive.md](log-archive.md).
