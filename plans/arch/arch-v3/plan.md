# Arch v3 — Execution Plan

Tracking document for implementing v3. The **design** lives in the five sibling
docs (index, schema, report, adapters, delivery) — this file never restates it,
only tracks execution. Update the checkboxes and the progress log as work
lands; a fresh session should be able to resume from this file alone.

## How to use this file

- **Resuming:** read this file, then index.md, then the doc owning the phase
  you are in (schema.md for phase 1, adapters.md for phase 2, report.md for
  phase 3, sequence.md for phase 3S). Check the progress log for the last entry.
- **Stopping:** append a progress-log entry saying what state the tree is in
  and the next action. Commit WIP rather than leaving dirty trees.
- **Exploring a different direction:** branch off `feature/arch-v3`, note the
  branch and question under "Exploration branches" below. Design changes go
  into the six docs (replacing text, not adding files — delivery.md rule 1),
  with a log entry here.

## Ground truth

| What | Where |
| --- | --- |
| Working tree / branch | this worktree, `feature/arch-v3` (worktree `arch-v3`) |
| Design docs | `plans/arch/arch-v3/` (index, schema, report, sequence, adapters, delivery) |
| v1 implementation (to be replaced) | `src/otdev/tools/arch.py` + `src/otdev/tools/_arch/` (models, ingest, validate, generate, exporters, roundtrip, …) |
| v2 donor code (do NOT build on; harvest only) | worktree `[STUCK]arch-v2`, branch `feature/arch-v2`, pushed to origin, clean. `src/otdev/tools/_arch/v2/` — 8,761 lines |
| Report interaction reference | `plans/arch/react-flow-poc/` (vite app: `ArchitectureCanvas.tsx`, styles, panels) |
| Real dataset for the phase-1 port | `plans/arch/wip/acme-arch-v2.xlsx` (dumped to `plans/arch/arch-v3/fixture-src/`) |
| Canonical v3 fixture | `tests/unit/tools/fixtures/arch/acme.yaml` |
| v2 design history (reference only) | `plans/arch/arch-v2/` incl. `grill/` |
| Phase-3 gate feedback issues | `plans/arch/arch-v3/issues/` — 20 issues, index `issues.md`, waves p1/p2/p3 + reference screenshots |
| UI research (IcePanel/Archify) | `plans/arch/arch-v3/research/ui/ui-research-findings.md` + evidence captures |
| Interaction contract (v2-era) | `plans/arch/wip/interactions.md` — SUPERSEDED 2026-08-24; mined into report.md "Wave-2 UI contract" |

**Tooling hints (interactive/architect work):** use the OneTool `excel` pack
(`__ot excel`) to read/inspect workbooks and the `convert` pack (`__ot
convert`) for format conversions — don't hand-roll openpyxl scripts for
inspection. (In-pack _arch/v3 code still uses openpyxl directly, per the
design docs.) For UI verification (report app, phase 3+ gates), follow
`wip/notes/test-ui.md` — Playwright driven through `__ot playwright.*` for
snapshots, clicks, console/network inspection, and screenshots; console
inspection belongs in every pass.

**Donor shortlist from v2** (delivery.md rule 5 — harvest, don't refactor):
Excel cell parsing / header normalization (`normalize.py`, `load.py`),
deterministic YAML/workbook writers (`write.py`, `exporter.py`), ID/text rules
(`models.py` validators). Everything patch/replay/projection-shaped
(`replay.py`, `compare.py`, `viewgraph.py`, `projection.py`, `frontend.py`,
`likec4.py`) is explicitly dead — see "must NOT return" in delivery.md.

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
  reviewed it at the gate. Sequence: D1 → (fixture, architect) → D2 →
  (resolver spec, architect) → D3 → D4 → phase-1 gate → D5 ∥ D6 → D7 → gate
  → D8. Rework sequence (Phase 3R): (schema.md rework, architect) → D9 →
  gate → (report.md reconciliation, architect) → D10 → phase-3 re-gate →
  D11 ∥ D8. Sequence aspect (Phase 3S): (sequence.md + vectors + acme
  flows, architect) → D12a after the wave-1 gate → D12b after the phase-3
  re-gate (∥ D11/D8).

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

## Phase 0 — Setup (small)

- [x] Confirm layout decision above (or record the alternative here).
- [x] Skeleton `_arch/v3/` package + dump acme workbook sheets to CSV for
      fixture design. `→ D1` (done inline by architect — trivial)
- [x] **Architect:** design the canonical v3 acme fixture
      (`tests/unit/tools/fixtures/arch/acme.yaml`) from the dump — at least
      one milestone, one revision row, one `until` retirement — the living
      fixture for every gate.

## Phase 1 — Model, resolver, YAML (budget: 1,800 py lines)

Owner doc: schema.md.

- [x] Pydantic models: Architecture root, Milestone, Timeline, six entity
      kinds, `from`/`until` fields, flat properties. ID/text rules from v2.
      `→ D2`
- [x] YAML read/write, deterministic output (harvest v2 `write.py` patterns).
      `→ D2`
- [x] **Architect:** resolver signatures + authoritative semantics test
      suite (interval edge cases: gap reintroduction, milestone not on
      timeline, from==until rejection, clipping chains, revision diffs,
      advance rewrites). This is the phase's design core — not delegated.
- [x] Resolver implementation: revision grouping, state-at-position filter
      (`current`/milestone/`end` selector), clipping with `clipped_by`
      consequences, diff (added/removed/changed field-by-field),
      `advance(through=…)` deterministic rewrite. `→ D3` (to architect's
      tests)
- [x] Validation: structural errors + advisory warnings with locations
      (implemented in full; only its test breadth is deferred). `→ D4`
- [x] Dev CLI (`__main__.py`): validate / resolve / diff / advance
      subcommands — the fast iteration loop, no MCP needed. `→ D4`
- [x] Tools: `arch.init`, `arch.validate`, `arch.resolve`, `arch.diff`,
      `arch.advance` (thin facade over the same functions). `→ D4`
- [x] **Gate (architect):** acme fixture validates; diffs between its
      milestones are correct by inspection. Record line count vs budget in
      the log.
- [x] Cut over `arch.py` to v3; delete v1 modules; update any specs/docs
      referencing v1 behavior. (Architect-reviewed step.)

## Phase 2 — Excel adapter (budget: 900 py lines)

Owner doc: adapters.md. Entire build chunk is one delegation. `→ D5`

- [x] Adapter interface: `read(source) -> Architecture`, `write(arch, target)`.
- [x] Workbook read: 9 sheets, header normalization, `[a;b]` lists, extra
      columns → properties, Timelines block ordering (harvest v2 parsing).
- [x] Workbook write + generated template: dropdown validation for enums and
      milestone refs, revision-row banding. Write is mode-aware: existing
      target → in-place data-row update preserving formatting/tables
      (refuse if the workbook holds charts/images — openpyxl drops them);
      see adapters.md "Write modes".
- [x] Tabular error contract: sheet/row/column/field, all locations, atomic
      failed import.
- [x] Tools: `arch.import_excel` (under `arch.convert`), `arch.export`.
- [x] Round-trip model-equality tests on the acme fixture.
- [x] **Gate (architect + user):** edit acme in Excel (add milestone, retire
      system, revise subsystem) → import → diff shows exactly those three
      edits. (Architect ran the scripted equivalent — see log; the user
      hand-run is folded into the Phase 3R wave-1 gate against the new
      schema — agreed 2026-08-24.)

## Phase 3 — Report app (budget: 5,000 TS/TSX + 400 py lines)

Owner doc: report.md. POC is the interaction donor.

- [x] **Architect:** payload JSON spec (rows with pre-resolved integer
      positions + derived consequences) — unblocks D6. (report.md "Payload
      contract (v1)"; D6 prompt issued in delegation.md.)
- [x] Bundle scaffolding: React Flow v12 + elkjs worker + AG Grid, vite
      single-file build at **pack build time**; wheel-packaged artifact;
      Archify styling + panels ported from POC; `arch.generate` template
      injection (~400 py). `→ D6` (parallel with D5)
- [x] **Architect:** client projection spec (filter, diff set-arithmetic,
      scope BFS, level roll-up — contracts + test vectors) — unblocks D7.
      (report.md "Client projection contract (v1)"; vectors in
      tests/unit/tools/fixtures/arch/projection/; D7 prompt issued.)
- [x] Client projection + union-graph layout (fixed positions across
      slider), passport panel, minimap, light/dark. `→ D7`
- [x] Time slider + diff overlay + timeline picker, progressive disclosure
      (zero milestones → no time UI). `→ D7`
- [x] Tables (entities, interfaces, milestones, diff) off the same filtered
      arrays; URL-fragment views + copy-link; offline `file://` check. `→ D7`
- [ ] **Gate (architect + user):** open acme's report, scrub the timeline;
      the story reads correctly without explanation.
      *First run 2026-08-24: NOT passed — feedback captured as the 20 issues
      in `issues/`. Re-gate after Phase 3R waves 1–2.*

## Phase 3R — gate rework (waves from `issues/issues.md`)

The phase-3 gate produced 20 issues, grouped into three waves (provisional
fix order, not priorities — schema changes ripple into everything). Issue
files carry the requirements; this section only tracks execution. The
delegation model continues unchanged: architect updates the design docs
and authors the prompt, executors implement to contract. Chunks are
registered as **D9–D11** in delegation.md (GATED until their architect
artifacts exist); budgets are agreed with the user per wave when each
prompt is authored.

### Wave 1 — schema/model (contract changes; do first)

Issues: `p1-schema-c4-naming` (System/Container/Component/Code),
`p1-schema-auto-ids` (`s-0001`-style ids), `p1-schema-from-until-inclusive`
(inclusive interval naming), `p1-schema-provider-consumer` (interface model;
backed by `issues/provider-consumer.md`).

- [x] **Architect (2026-08-24):** schema.md rewritten for the four issues;
      ripple folded into adapters.md (ten sheets, blank-id import) and
      report.md (payload + projection contracts). Decisions recorded in the
      progress log below. Budgets agreed with the user: D9a 700 / D9b 600
      changed source lines.
- [x] Executor chunks: implement to the updated contracts. `→ D9a, D9b`
- [ ] **Gate (architect + user):** resolver suite, round-trips, and
      projection vectors green under the new schema; acme re-fixture
      validates. User hand-edits the exported acme workbook in Excel
      against the new ten-sheet schema (this replaces the outstanding
      phase-2 hand-run — agreed 2026-08-24).

### Wave 2 — report UI

Issues: the 12 `p2-*` files (nested groupings, side panel, resizable
panels, layout density, plain background, legend, flow animation,
dependency focus, entity boxes, edge rendering, fullscreen, v2-parity
tables).

Design inputs: `research/ui/ui-research-findings.md` — its "Top 10
behaviors worth copying" and "Do not copy" lists are binding input for the
prompts (semantic URL fragments only, graduated dimming over hiding, wide
edge hit rails, explicit semantic-zoom levels, no remote assets — offline
`file://` stays a gate check); measured Archify edge/node/opacity values
are the styling reference.

- [x] **Architect (2026-08-24):** report.md reconciliation done — new
      normative section "Wave-2 UI contract (v1)" folds in the Q4–6
      decisions, translates the research binding lists into constraints,
      and carries the mined INT-* baseline with an overrides table;
      interactions.md marked superseded. D10 issued as D10a (chrome,
      panels, tables — 1,400 changed TS/TSX lines) + D10b (canvas
      semantics + visuals — 1,900), budgets agreed with the user
      2026-08-24.
- [ ] Executor chunks: implement the wave. `→ D10a, D10b`
- [ ] **Re-run phase-3 gate** (architect + user).

### Wave 3 — new capabilities (after the re-gate)

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
- [ ] **Architect:** parser-vector fixture
      (`tests/unit/tools/fixtures/arch/sequence/`) — the D12a control
      mechanism.
- [ ] Python: parser, validation findings, `sequences` payload, CLI +
      facade wiring. `→ D12a` (runnable after the wave-1 gate)
- [ ] **Architect:** layout vectors + 2–3 acme flow docs (multi-scenario,
      interval-carrying, ad-hoc participant) — the D12b control mechanism.
- [ ] Frontend: `seqlayout.ts`, SVG layer, entity-box header row, SEQ-*
      interactions, fragment keys. `→ D12b` (after the phase-3 re-gate;
      ∥ D11/D8)
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

1. ~~Report bundle location + build wiring into the wheel~~ — ANSWERED
   2026-08-23 in report.md "Shape": source in `frontend/arch-report/`,
   `just build-arch-report` builds to `_arch/v3/_bundle/report-template.html`,
   built template committed (no Node at wheel-build or generate time).
2. ~~Whether `arch.convert` is the umbrella tool name~~ — ANSWERED
   2026-08-24 as-shipped by D5: `import_excel` aliased under `arch.convert`,
   `export` standalone. No further work.
3. Per-state layout fallback if union-graph layout is chronically poor for
   sparse early states (risk table; re-evaluate at the phase-3 re-gate —
   wave-2 layout changes may moot it).
4. ~~Legend semantics: hide vs dim~~ — ANSWERED 2026-08-24 (user): dim
   only, graduated Archify-style tiers; no hide/solo mode. Legend driver:
   **tags** as the first pass (property/kind switch deferred). Decision
   noted in the issue file; folded into report.md at the D10 architect step.
5. ~~Nested groupings: in-place expand/collapse vs drill~~ — ANSWERED
   2026-08-24 (user): no in-place expand/collapse. Keep drill navigation,
   and add a **"C4 zoom"** level control with 4 levels — System, Container,
   Child Containers, Component. Decision noted in the issue file; spec
   detail (boundary-box rendering per level, drill semantics) lands in
   report.md at the D10 architect step.
6. ~~Status of `plans/arch/wip/interactions.md`~~ — ANSWERED 2026-08-24
   (user): mine what's useful into report.md during the D10 reconciliation,
   leave the rest and mark the doc superseded. Issue text wins where they
   conflict; each override recorded in the reconciliation.
7. ~~D9b projection vector conversion~~ — ANSWERED 2026-08-24 (user): the
   new inclusive `start_in`/`end_in` schema wins, so update the authoritative
   alternate-timeline expectations. `sysL` has old `until: m2` while the
   alternate timeline is `[m1, m3]`. The required conversion to inclusive
   `end_in: m1` removes `sysL` after `m1` on that timeline. No single v3
   interval preserves the old behavior on both timelines.

## Progress log (append-only, newest first)

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
