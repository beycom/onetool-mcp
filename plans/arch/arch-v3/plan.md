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
| Open issues | `plans/arch/arch-v3/issues/` + index (cleaned up 2026-08-30): p14/p16/p27 assigned to chunk-15 (p27 decided: remove the Detail dropdown); p24/p26/p28/p29/p32 open, unassigned (wave-2 polish chunk, authored at wave-2 start); p3-* files feed chunk-22/chunk-43; resolved files (incl. provider-consumer.md, absorbed into schema.md) in `issues/resolved/`; Archify/IcePanel reference screenshots stay in `issues/` (cited by the polish pass specs) |
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
  see Phase 1): P11 → P12 → Phase 1 exit gate → wave 2 (chunk-21 ∥ chunk-22 ∥
  chunk-23 as their architect artifacts land) → wave 3 (chunk-31 → sequence
  gate) → waves 4–5. Historical sequencing detail: log-archive.md.
- **Issues are fixed only through chunks (made explicit 2026-08-30):**
  the user never "fixes an issue" as a separate activity — an issue
  file in `issues/` waits until a chunk absorbs it. The chunk's
  delegation prompt names the exact issue files it resolves (with a
  READ-them instruction) and the plan's chunk table repeats the issue
  ids; at the gate the architect moves the resolved files to
  `issues/resolved/` and annotates them with the resolving chunk. So
  the user's whole job is: run the READY prompt in delegation.md,
  answer any user-decision issues the plan flags — nothing else.
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

Outstanding executor chunks are named `chunk-xy` (renamed 2026-08-30
from `Pxy`, which collided case-insensitively with the `pxy-*` issue
files — mapping is 1:1, `P21` → `chunk-21`): `x` = wave (execution
order), `y` = priority inside the wave (lower first; same-wave chunks
may run in parallel once their architect inputs exist). Completed
chunks keep their historical ids — `D1`–`D14`, `D13a`–`D13d`, and
`P11`–`P14` — in the progress log, the design docs, and delegation.md,
because renaming finished work would break those references. Chunk
evidence dirs under `plans/arch/wip/test-results/` follow the chunk id
(`chunk-15/`; the older `p13/`, `p14/` dirs are frozen history).

**Identifier registries (one line each, so no scheme is ever confused
with another):**

- `D1`–`D14` / `P11`–`P14` — completed executor chunks (frozen
  historical ids).
- `chunk-xy` — outstanding executor chunks (this table; prompts in
  delegation.md).
- `pxy-*.md` — issue files in `issues/` (x = wave; separate registry
  from chunks — issue p15 and chunk-15 are unrelated).
- `#1`–`#27` — ui-polish.md items (all closed 2026-08-29, frozen).
- Phases 1–3 and waves 0–5 — plan structure. NOT called "stages":
  **Stage** is reserved for the report UI's milestone positions
  (the Stage dropdown).
- Progress-log entries older than 2026-08-30 use the pre-rename `Pxy`
  chunk ids; the log is append-only and was not rewritten.

| New id | Was | Chunk |
| --- | --- | --- |
| P11 | — | Canvas presentation: radial layout, edge labels/ports, color economy, theme (added 2026-08-29) |
| P12 | — | Map model: in-place C4 expansion, endpoint resolution, presets (added 2026-08-29) |
| P13 | — | Report UI correctness fixes: issues p15, p17, p18, p19 (added 2026-08-30) |
| P14 | — | Layout engines + config + A/B harness — layout-design.md; absorbs issue p13 (added 2026-08-30) |
| chunk-15 | — | Edge-label collision + collapse affordance + Detail-dropdown removal — issues p14, p16, p27 (added 2026-08-30) |
| chunk-21 | D12a | Sequence parser + payload + attachments (re-scoped 2026-08-30) |
| chunk-22 | D11 | Report definitions + guided views |
| chunk-23 | D8 | Client-side SVG / draw.io export + SQLite adapter |
| chunk-31 | D12b | Sequence renderer frontend |
| chunk-41 | — | SharePoint transport |
| chunk-42 | — | v2 YAML migration converter (conditional) |
| chunk-43 | — | Edit mode (save-back + manual positions) |
| chunk-51 | Dn (backfill) | Test-breadth backfill |

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
- [x] **P13 — report UI correctness fixes** (added 2026-08-30 from the
  architect inspection pass; DONE, gate PASSED 2026-08-30 at 102/600
  changed source lines). Boundary-node hidden handles (p17), set-based
  selection emphasis with member scoping (p15/p19), whole-graph initial
  fit capped at 100% (p18 — report.md framing rule amended at the
  gate), member-level Info Connections grouping (p19).
- [x] **P14 — layout engines + config + A/B harness** (added
  2026-08-30; design: layout-design.md; DONE, gate PASSED 2026-08-30 at
  1,479/2,000 changed source lines including the architect's layered-
  interior fix — see the progress log; absorbs issue p13, resolved).
  Engine extraction (layered/radial/grid behind LayoutEngine), `layout:`
  config block on the theme precedent, method-only viewer control with
  hash + localStorage, shared invariant suite, dev-only ?layout= A/B
  harness. Default-method decision (architect, from the captures): the
  topology-aware default is retained (layout-design.md Decisions 0).
- [ ] **chunk-15 — edge-label collision + collapse affordance +
  Detail-dropdown removal** (added 2026-08-30 when the user flagged
  that issues p14 and p16 were owned by no chunk; p27 added same day
  by user decision: remove. Specs: report.md "Collision invariant
  (chunk-15)" under At-rest edge labels — absorbs p18's deferred
  orphan-label clause — "Collapse-control placement (chunk-15)" and
  "Detail dropdown: REMOVED" under the Map contract; prompt READY in
  delegation.md, proposed budget 700). Runs before the exit-gate user
  half: p14 reproduces in the gate's own select-card walkthrough step.
- [ ] **Phase 1 exit gate (architect + user)** — runs after the chunk-15
  gate (label collision changes the rendered frame). The held 3P exit gate:
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

Unlocks at the Phase 1 exit gate. Owner docs: sequence.md (chunk-21/chunk-31),
report.md (chunk-22/chunk-23). Budgets are re-agreed when each prompt is issued
(provisional: ~500 py for chunk-21, ~2,200 TS/TSX for chunk-31). Write-path
decision (2026-08-24) still stands: the app has **view** mode
(standalone `file://`, read-only) and **edit** mode (local server owning
the YAML write path); edit-mode work stays in Phase 3.

Wave 2 — independent chunks, run in parallel once each chunk's architect
inputs exist:

- [x] **Architect (before chunk-21):** message-file attachments design —
      DONE 2026-08-30 (user request 2026-08-26). Landed as: schema.md
      "Attachments" (interface `attachments` path list, path grammar,
      shared finding codes invalid_path / unresolved_file /
      invalid_file / large_attachment), sequence.md `attach` statement
      + compilation additions, report.md payload `files` key +
      interface-row serialization + "Attachments and the Payload
      viewer" (viewer ships with chunk-31 — one bundled highlighter, real
      data; covers interface attachments too), adapters.md Interfaces
      `attachments` column, and two new architect-authored parser
      vectors (`flows/attachments*.md` + `files/` samples) in the chunk-21
      control fixture. The held chunk-21 prompt was re-scoped the same day.
- [ ] **chunk-21 (was D12a)** — sequence parser, validation findings,
      `sequences` payload, interface + message attachments (fields,
      resolution, `files` embedding, Excel column), CLI + facade
      wiring. Control mechanism: the parser-vector fixture
      (`tests/unit/tools/fixtures/arch/sequence/`, committed
      2026-08-25; attachments vectors added 2026-08-30). Prompt
      re-scoped 2026-08-30, READY (proposed budget 700) — runs at the
      Phase 1 exit gate.
- [ ] **chunk-22 (was D11)** — saved report definitions + guided views:
      `p3-report-definitions` (named reports, view-mode flow — starting
      point: export the config as a ready-to-paste `views:` YAML entry;
      persist-to-model rides the deferred edit path) and
      `p3-ui-guided-view` (authored, playable guided views; resolves
      the MAP/PATH/LENS placeholders left by D7). Gated on architect
      designs for both. Issues: `issues/p3-*`.
- [ ] **chunk-23 (was D8)** — client-side SVG / draw.io download from the
      report (serialize the laid-out scene client-side — the v2
      `ArchitectureScene`-not-DOM rule applies) + SQLite adapter (one
      table/kind + properties side table, per adapters.md).

Wave 3 — after the chunk-21 gate:

- [ ] **Architect (chunk-31 control):** layout vectors + 2–3 acme flow docs
      (multi-scenario, interval-carrying, ad-hoc participant).
- [ ] **chunk-31 (was D12b)** — `seqlayout.ts`, SVG layer, entity-box header
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

- [ ] **chunk-41** — SharePoint transport reusing the Excel mapping.
- [ ] **chunk-42** — migration converter from v2 YAML — only if a real v2
      dataset exists to migrate; otherwise skip (throwaway tooling).
- [ ] **Architect:** edit-mode design — the local-server write path
      (deferred until Schema, Report, and File Import were complete;
      those are done, so this unblocks whenever edit mode is
      prioritised).
- [ ] **chunk-43** — edit mode: `p3-edit-save-back` +
      `p3-ui-manual-positions` (after the edit-mode design).
- [ ] Revisit deferred items against demonstrated need only: Confluence
      embedding, PDF, dark theme (ui-polish.md #24 evidence binds any
      future dark pass).

Wave 5 — speed-mode debt, once v3 is stable:

- [ ] **Architect:** OpenSpec — author the v3 spec
      (`openspec/specs/.../tool-arch/`) from the shipped behavior;
      archive/replace v1 spec content.
- [ ] **chunk-51** — test breadth: validation codes with location
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

- **2026-08-30** — p27 DECIDED (user): the Detail dropdown is
  **removed**, riding chunk-15; tree committed. Design landed as:
  report.md Map contract "Detail dropdown: REMOVED" (supersedes the
  P12 "becomes presets" rule — preset expansion sets survive only as
  the internal mapping for legacy `level=` fragment links, one history
  push, no "Custom" display; the freed View slot hosts the chunk-14
  Layout control when configured), a REMOVED annotation on the D13a
  Controls-conversion bullet, and the amended ui-polish-direction.md
  "Detail" section. chunk-15 prompt updated: task 3 (remove the
  control, keep legacy-link mapping, recut only dropdown-UI tests),
  prescribed test 5 (no Detail control; legacy `level=` link restores
  the bulk expansion in one history entry), rule-9 repro now uses a
  legacy link or manual expansion instead of the dropdown; budget
  raised 500 → 700. Issue p27 annotated DECIDED/ASSIGNED (index
  updated). Side effect noted for the exit gate: the P14 watch item
  ("LIVE preset switch leaves content outside the frame until Fit")
  is mooted by the removal — bulk expansion now arrives only via
  legacy-link loads, which frame correctly as fresh loads. The
  test-ui.md walkthrough's preset step (untracked wip note) needs the
  same substitution when the gate re-runs. Next action: user runs the
  chunk-15 prompt (budget 700 confirmed by this decision's scope);
  architect gates it; then the Phase 1 exit gate.

- **2026-08-30** — Identifier collision resolved (user decision):
  outstanding executor chunks renamed `Pxy` → `chunk-xy` (chunk-15,
  chunk-21, chunk-22, chunk-23, chunk-31, chunk-41/42/43, chunk-51);
  issue files KEEP their `pxy-*` names (an interim `ixy` rename from
  earlier today was reverted before commit). Completed chunks keep
  historical ids (D1–D14, P11–P14) per the 2026-08-29 reorg precedent;
  log entries below this one keep pre-rename ids (append-only — the
  mapping is 1:1). "stage-x" was considered for plan waves and
  REJECTED: **Stage** is reserved for the report UI's milestone
  positions. The full registry legend now lives in plan.md "Chunk
  numbering"; chunk evidence dirs follow the chunk id going forward
  (`test-results/chunk-15/`). Also made explicit in the Delegation
  model (user request): issues are fixed ONLY through chunks — each
  chunk prompt names the exact `issues/pxy-*.md` files it resolves and
  instructs the executor to read them; the architect moves them to
  resolved/ at the gate; the user's whole job is running the READY
  prompt and answering flagged user-decision issues (currently: p27,
  Detail dropdown, default remove). Live-text updates across plan.md,
  delegation.md, report.md, schema.md, adapters.md, issues/ index +
  files. Next action unchanged: user confirms the chunk-15 budget
  (500) and runs the chunk-15 prompt; architect gates it; then the
  Phase 1 exit gate.

- **2026-08-30** — Attachments design landed, chunk P15 authored (user
  flagged unowned issues p14/p16), issues/ cleaned up; tree committed.
  ATTACHMENTS (the wave-2 architect artifact, done ahead of the gate —
  it doesn't depend on the gate outcome): interfaces gain an optional
  `attachments` path list (schema.md "Attachments": relative POSIX
  paths under the model dir, grammar-checked, UTF-8 text only, format
  by extension json/xml/csv/yaml/text; errors invalid_path /
  unresolved_file / invalid_file, warning large_attachment > 256 KB;
  generate embeds atomically); sequence messages link the same files
  via the new `attach <path>` DSL statement binding to the most recent
  message (sequence.md); the payload gains a top-level `files` map
  (path → {lang, text}, deduplicated, after `sequences`, omitted when
  empty so existing payloads stay byte-identical — report.md payload
  contract) and interface rows serialize `attachments` as authored;
  Excel Interfaces sheet gains an `attachments` list cell
  (adapters.md); the viewer contract (report.md "Attachments and the
  Payload viewer") un-defers D13d's Payload tab — Info Attachments
  rows + Data Payload tab, bundled Prism working choice, csv via the
  existing AG Grid, ships with P31. Control fixture extended
  (architect-authored): vectors flows/attachments.md (clean compile
  with per-message attachment lists) and flows/attachments-bad.md (all
  five attach findings), files/ samples incl. a deliberate non-UTF-8
  binary, expected.json +101 lines, README rules pinned. P21 prompt
  re-scoped in delegation.md (attachments end to end; budget 500→700;
  READY, runs at the Phase 1 exit gate). P15 (user-flagged gap: p14
  edge-label pileup — which reproduces in the exit gate's select-card
  step — and p16 collapse-× ambiguity were owned by no chunk):
  contracts added to report.md ("Collision invariant (P15)" — one
  screen-space pass over rendered rects covering at-rest AND revealed
  pills, nudge-then-hide, single-reveal exemption, orphan suppression
  riding from p18; "Collapse-control placement (P15)" — inline with
  the boundary title, collapse glyph never ×, no repositioning toward
  children); prompt READY in delegation.md (frontend only, proposed
  budget 500, four prescribed tests); the exit-gate user half now
  follows the P15 gate. ISSUES CLEANUP (user-directed): p14/p16
  annotated with their P15 assignment; p32's dev-console bullet marked
  satisfied (p17 landed; gates verify console-clean); p25 already
  closed; provider-consumer.md moved to resolved/ (absorbed into
  schema.md) with links fixed; index updated — wave-2 items
  p24/p26–p29/p32 remain open and unassigned pending a wave-2 polish
  chunk, and p27 (Detail dropdown, default remove) awaits a user
  decision, cheap enough to ride P15 if confirmed before it runs.
  Next action: user confirms the P15 budget (500) and runs the P15
  prompt (and answers p27 if they want it folded in); architect gates
  P15; then the Phase 1 exit gate (architect re-run + user half); on
  pass, wave 2 opens with P21 ∥ P22/P23 design work.

- **2026-08-30** — Phase 1 exit gate: architect half RE-RUN on the
  post-P14 tree and PASSED, with one gate fix landed and committed; the
  user half is now the only outstanding Phase 1 item. Walkthrough at
  1440×900 and 1024×720 under `file://`, storage cleared for a true cold
  load: console clean at every step (0 warnings/errors), the only
  network request is the local HTML file; cold open reads (radial hub,
  whole-graph fit at 37%, doc exactly 1440×900, zero scroll, no
  layout-method control — correct, acme authors no `layout:` block);
  card select opens Info with one-hop accent and keeps the hub visible;
  spline select shows Connection details with linked endpoints,
  direction, and member; Stage 5 renders the cutover story with the
  selection surviving the switch; Data opens with four tabs and no
  stale-layout toast; at 1024×720 View auto-collapses to the 36 px rail
  when Info opens and the app fills the viewport exactly. Evidence:
  plans/arch/wip/test-results/exit-gate/p14-*.png and
  ghost-boundaries-stage5-component.png.
  GATE FIX (architect, in-scope): probing the P14 watch item (Component
  preset at Stage 5) found removed EXPANDED containers vanishing while
  their removed children rendered — three legacy components stacked at
  the boundary-relative origin (identical translate(20px,50px)); root
  cause: App.tsx merged removed entities from the compared projection as
  ghost NODES only, never ghost BOUNDARIES, so applyPositions dropped
  the missing parentId and applied the relative position as absolute.
  Fix: `mergeRemovedBoundaries` in projection.ts (pure, tested) merges
  removed non-stub boundaries from the compared projection as ghosts;
  boundary nodes build from the merged list (ghost = dashed, dimmed, no
  collapse control); report.md layout-stability rule amended. Live
  re-check: 4 ghost boundaries render the full legacy retirement story
  at Component/Stage 5, the three components sit inside their ghost
  parents, 0 leaf overlaps, 56 edges (11 retired ghost edges restored),
  console clean. ~40 changed source lines (tests + generated template
  excluded); frontend 73 passed (+2 merge cases), tsc clean, bundle
  rebuilt, acme regenerated. Pre-existing watch item unchanged: a LIVE
  preset switch still leaves content outside the frame until Fit
  (fresh-load framing is correct). Not re-run (verified at earlier
  gates, unaffected): dock drag-resize, reduced motion; payload-viewer
  and sequence checks are Phase 2 scope. Next action: user reviews the
  regenerated plans/arch/wip/acme-report.html + exit-gate screenshots
  and confirms or fails the gate; on pass, wave 2 opens with the
  attachments design → P21.

- **2026-08-30** — P14 architect gate PASSED (with one gate fix); tree
  committed; default-method decision recorded. Independently re-verified:
  frontend tests, arch py 83 (+4 prescribed), `just lint`,
  `just build-arch-report` reproduced the executor's template
  byte-for-byte pre-fix, CLI standalone validate (0 errors / 25
  warnings), budget confirmed at the executor's 1,450 (694 tracked + 756
  new). Code review conforms to layout-design.md: pure engines behind
  the registry, theme-precedent Python plumbing (raw-retaining Layout
  model, located warn-only findings, canonical YAML/Excel Settings/
  payload round-trip), DEV-only ?layout= override, query > hash >
  stored > config restore priority, settings-aware layout cache keys,
  and null-method fallback preserving today's topology default exactly.
  GATE FIX (architect, in-scope): the executor's
  `compactBoundaryInteriors` regridded ≥5-child boundary interiors
  AFTER ELK placement, so a grown boundary overflowed its parent and
  collided with siblings — the live Component preset on acme rendered
  10 node overlaps (the invariant fixtures never nested a packed
  boundary inside a small parent with siblings, so the suite passed).
  Rewrote the layered engine: grid interiors are pre-planned bottom-up
  (all-leaf-or-planned boundaries, ≥5 children), handed to ELK as
  fixed-size leaves with hidden-endpoint edges reattached to the
  planned ancestor, and children injected after ranking — parent growth
  and sibling spacing are correct by construction; the defective
  post-pass is deleted. Added the 'packed interior beside siblings'
  fixture to the shared invariant suite (69 frontend tests pass, +3
  engine cases). Live re-check: Component preset 43 nodes / 15 edges /
  0 overlaps, Container preset 24 / 15 / 0, console clean, fresh hash
  load frames 24/24 in view; evidence
  plans/arch/wip/test-results/p14/component-preset-fixed.png. Budget
  after fix: 1,479/2,000. All seven executor assumptions ACCEPTED.
  Default-method decision from the A/B captures: topology-aware default
  retained (radial for flat stars, layered with boundaries, grid for
  edgeless) — layout-design.md Decisions 0; no authored method in acme.
  Issue p13 RESOLVED → issues/resolved/. Watch item for the exit-gate
  walkthrough (pre-existing, not P14): the initial-framing effect
  excludes boundary nodes from its bounds, so a live preset switch can
  leave a tall bottom boundary partially cut until a Fit; fresh loads
  frame correctly. Ranking note: `property:` ranking currently
  re-sequences a sibling group along the flow axis (rank ordering, not
  true swimlanes — those stay a later engine per the design). Pipeline:
  no executor prompt is queued next — the exit gate is architect+user,
  and P21 stays ON HOLD behind the wave-2 attachments design
  (architect). Next action: Phase 1 exit gate on this tree (rerun the
  walkthrough — framing and layout both changed since the 2026-08-29
  architect half).

- **2026-08-30** — P14 layout engines, authored config, viewer control,
  and A/B harness implemented; left uncommitted for architect review.
  Layered, radial, and grid now implement one pure `LayoutEngine`
  contract behind a registry; `unionLayout` owns dispatch/cache while
  stable expansion and React Flow application remain shared
  post-processing. Layered expansion wraps large child sets into compact
  ranks, and radial expansion composes compact nested interiors with a
  radial root graph. Optional `layout:` settings round-trip through
  canonical YAML, Excel Settings, and payload; invalid/unknown knobs emit
  located `invalid_layout_value` / `unknown_layout_key` warnings and the
  viewer applies defaults. The View dock method control is gated by
  `user_choice`, with query > hash > per-report localStorage > config
  restore priority. The dev capture task wrote `layered.png`, `radial.png`,
  and `grid.png` to `plans/arch/wip/layout-ab/`. Source budget:
  **1,450 / 2,000 changed lines** (additions + deletions; tests and generated
  bundle excluded). Tests: exactly 23 prescribed P14 cases (19 frontend,
  4 Python); frontend **66 passed**, arch Python **83 passed / 540
  deselected**, smoke **27 passed / 3,214 deselected**, `just lint`,
  `just build-arch-report`, TypeScript, `git diff --check`, and acme CLI
  regeneration all passed. Rule-9 verification at 1440x900: cold acme
  rendered 14 nodes / 14 edges; the two-level expansion rendered 26 nodes
  and all 14 projected edges; the configured viewer switched all three
  methods live and persisted the method in hash + file-scoped storage. The
  generated `file://` report had zero console warnings/errors and one local
  request. The Vite check routed its pre-existing `/favicon.ico` 404 to a
  local 204 so app-console errors remained visible; the final capture run
  completed without console failures. Assumptions resolved from the ordered
  sources: (1) P13's four issue files are the exact files now under
  `issues/resolved/`, moved there by the P13 gate; (2) invalid layout values
  must survive model loading so advisory validation can warn and the report
  can fall back, matching the theme precedent's raw-value retention; (3) an
  absent block keeps the current topology choice and 40/72/20 spacing,
  while a present incomplete/invalid block falls back to
  layered/right/40/72/20/auto with `user_choice` false; (4) `boundary` is a
  minimum interior padding while the existing 50 px header and 48 px
  description clearances remain floors, preserving the absent-block layout;
  (5) per-report storage identity is pathname + payload source; (6) radial
  layouts with expansions use compact grid-packed interiors and a radial
  top-level composition, satisfying p13 without moving P12's shared anchor
  post-processing; (7) P14's `excelio` surface name maps to the existing
  `excel.py` adapter, the file that owns the theme Settings precedent.
  Open questions: none. Next action: architect gate review
  and default-method decision from the A/B captures.

- **2026-08-30** — P13 architect gate PASSED; tree committed; P14 prompt
  authored per the pipeline rule. Independently re-verified: frontend 47
  passed, `just build-arch-report` reproduces the tree's template
  byte-for-byte (shasum match), budget confirmed at 102/600 changed
  source lines (add+del; executor's 73 counted additions only); arch
  pytest and lint not re-run — no Python source changed (template only,
  regenerated). Code review conforms to the P13 prompt: BoundaryNodeView
  handles match ArchitectureNodeView exactly and are hidden by the
  existing `.react-flow__handle { opacity: 0 }` rule; classifyEmphasis
  takes a ReadonlySet with transitive boundary children built in App.tsx
  and member-row scoping for a hidden rolled-up selection;
  initialViewport is now fit-capped-at-1 (ZoomThresholds deleted);
  Connections iterates rawState interfaces by member-id fixpoint under
  the current aspect. Screenshots verified: cold load fits all systems
  at 26%, expanded Payment Service Provider lists the member-level
  incoming interface. All four executor assumptions ACCEPTED (canonical
  acme input; member vs boundary emphasis scoping; P13 framing rule
  supersedes report.md — amendment landed at lines 868–875 and
  verification vector 2; internal-interface omission matches the canvas
  roll-up). The stored-table-layout toast in both screenshots is a
  stale-localStorage diagnostic, not a defect. Issues p15/p17/p18/p19
  RESOLVED and moved to issues/resolved/ (p18's orphan-label clause
  explicitly rides the label work, issue p14). Pipeline: P14 prompt
  authored in delegation.md (engine extraction, `layout:` block, viewer
  control, invariant suite, A/B harness; proposed budget 2,000);
  layout-design.md committed. Next action: user confirms the P14 budget
  and runs the P14 prompt; the Phase 1 exit gate re-runs after the P14
  gate (initial framing changed, so the walkthrough must be redone on
  the post-layout tree).

- **2026-08-30**: P13 report UI correctness fixes landed for issues p15,
  p17, p18, and p19. Boundary nodes now expose hidden React Flow handles;
  selection emphasis covers transitive boundary children and scopes a hidden
  rolled-up member to its own interface rows; initial framing fits the whole
  graph with a 1.0 zoom cap; Info Connections groups live interfaces by the
  selected entity and its descendants under the current aspect. Source: 73 / 600
  added lines across `App.tsx`, `edgePresentation.ts`, `camera.ts`, and
  `InfoPanel.tsx`; no `layout.ts` or CSS changes. Tests: four prescribed
  regression cases added or updated; targeted Vitest 12 passed, full Vitest 47
  passed, frontend and embedded-bundle builds clean, acme regeneration `OK`,
  `just lint` clean, and arch pytest 79 passed / 540 deselected. Rule-9 dev-app
  verification at 1440x900: the required two expansions render 14 / 14 edges
  with four boundary handles and zero React Flow warnings; selecting the outer
  boundary keeps all 11 component cards emphasized; cold load fits all 14 nodes
  at 0.262 zoom; expanded Payment Service Provider lists `payment-to-provider`
  as incoming. Screenshots:
  `plans/arch/wip/test-results/p13/{initial-fit-1440,connections-member-rollup-1440}.png`.
  The console check found only two duplicate Vite `favicon.ico` 404s. Assumptions:
  (1) `tests/unit/tools/fixtures/arch/acme.yaml` is the regeneration input because
  plan.md and fixture-src/README.md name it as canonical; (2) when a hidden
  rolled-up member is selected, the non-visible canonical key in the selected-key
  set scopes splines by member-row endpoint, while a boundary's transitive visible
  child keys intentionally select the whole expanded boundary; (3) P13's explicit
  whole-graph initial-fit rule supersedes report.md's older Read-floor rule; (4)
  interfaces wholly internal to the selected descendant set are omitted to match
  the canvas roll-up, and a bidirectional interface belongs to both groups. Open
  questions: none. Next action: architect gate review; no commit or push made.

- **2026-08-30** — Architect inspection pass (Playwright, file:// + dev
  server, 1440×900 and 1024×720). Filed issues p13–p19, p24, p26–p29,
  p32 (see issues/issues.md); p25 closed as correct behavior; p15 updated
  with confirmed root cause. Critical find: p17 — edges to an expanded
  boundary are silently dropped (React Flow #008, BoundaryNodeView has no
  handles). Layout design confirmed with user (layout-design.md): engine
  abstraction, `layout:` config block (theme precedent), method-only
  viewer control, explicit `layer` ranking property with inference
  fallback. New chunks P13 (correctness fixes, READY) and P14 (layout
  engines, gated on P13 gate); prompts in delegation.md. Note: issue
  files `pxy-*.md` and chunk ids `Pxy` are separate registries — chunk
  P13 fixes issue p17 et al., and chunk P14 absorbs issue p13.

- **(older entries)** — see [log-archive.md](log-archive.md).
