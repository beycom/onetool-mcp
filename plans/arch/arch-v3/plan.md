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
| UI polish issue list (3P input) | `plans/arch/arch-v3/ui-polish.md` — 24 itemized issues from the 2026-08-25 Playwright walkthrough, tagged D13a–D13d; the 3P pass specs must close or waive every tagged item (expectations superseded where they conflict with ui-polish-direction.md) |
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
`ui-polish.md` — 24 issues from a full Playwright walkthrough
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
- [ ] **Pass 2 — canvas composition: layout, fit, camera.** `→ D13b`
      (spec: report.md "Polish contract — pass 2: canvas composition",
      authored 2026-08-28; prompt READY in delegation.md; budget 1,400
      changed source lines proposed — confirm before running.)
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
- [ ] **Pass 3 — graph elements: cards, splines, selection.** `→ D13c`
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
      user at the gate rather than riding a polish pass; Data tables
      auto-size populated columns, collapse all-empty columns, never
      truncate headers (#22), sync selection with the canvas both
      ways, offer Show on Canvas; the read-only Payload viewer;
      Escape order per the direction (#13); designed empty and
      failure states; final motion/consistency sweep with a
      reduced-motion audit.
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

- **(older entries)** — see [log-archive.md](log-archive.md).
