# Arch v3 — Delegation prompts

Ready-to-paste prompts for executor models (capable, obedient, YOLO access to
the project). Division of labour:

- **Architect (Fable session):** design decisions, resolver semantics and its
  authoritative test suite, the fixture's change story, payload/projection
  specs, gate reviews of all delegated output, budget enforcement, authoring
  the GATED prompts below when their inputs exist.
- **Executor models:** every prompt in this file. They implement to contract;
  they never make design decisions.

Status legend: **READY** — paste and run now (respect the "after" column).
**GATED** — the architect must produce an input artifact first; the prompt
below is the template it will be issued from.

**Numbering note (reorg 2026-08-29, renamed 2026-08-30):** outstanding
chunks are `chunk-xy` (x = wave, y = priority — registry legend and
mapping table in plan.md "Chunk numbering"; renamed from `Pxy`, which
collided case-insensitively with the `pxy-*` issue files). Completed
chunks keep their historical ids (D1–D14, P11–P14); outstanding
headings below carry the lineage (`chunk-21 (was D12a)` etc.). A chunk
that resolves issues NAMES the exact `issues/pxy-*.md` files in its
prompt — executors read them as part of the contract.

| Prompt | Chunk | Status | Run after |
| --- | --- | --- | --- |
| D1–D7 | Phases 0–3 build chunks | DONE (2026-08-23/24) | — |
| D9a, D9b | Phase 3R wave 1: schema/model + Excel/payload rework | DONE, gate PASSED 2026-08-25 | — |
| D10a, D10b | Phase 3R wave 2: report UI | DONE, commit c37e3d05 | — |
| D13a | Polish pass 1: app shell | DONE, gate PASSED 2026-08-28 (974/1,800 lines) | — |
| D13b | Polish pass 2: canvas composition | DONE (gate PASSED 2026-08-28) | — |
| D13c | Polish pass 3: graph elements | DONE, gate PASSED 2026-08-28 (797/1,600 lines) | — |
| D14 | Subsystem level rename (schema + report + acme) | DONE, gate PASSED 2026-08-29 (293/1,100 lines) | — |
| D13d | Polish pass 4: View / Info / Data | DONE, gate PASSED 2026-08-29 (630/1,500 lines) | — |
| P11 | Canvas presentation: radial layout, labels, ports, color economy, theme | DONE, gate PASSED 2026-08-29 (736/2,400 lines + a small architect fix at the gate) | — |
| P12 | Map model: in-place C4 expansion | DONE, gate PASSED 2026-08-29 (710/2,600 lines + the architect's anchor perimeter-overflow fix) | — |
| P13 | Report UI correctness fixes (issues p15, p17, p18, p19) | DONE — gate PASSED 2026-08-30 | — |
| P14 | Layout engines + config + A/B harness (layout-design.md) | DONE — gate PASSED 2026-08-30 (with an architect fix) | — |
| chunk-15 | Edge-label collision + collapse affordance + Detail-dropdown removal (issues p14, p16, p27) | DONE — gate PASSED 2026-08-31 (193/700 lines + the architect's port-label collision fix) | — |
| chunk-16 | Canvas performance: gesture freeze, CSS zoom scaling, referential stability (issue p33) | DONE — gate PASSED 2026-08-31 (252/500 lines, no architect fix needed) | — |
| chunk-17 | Gate-feedback polish sweep (issues p24, p26, p28, p29, p32 open bullets, p34, p35) | DONE — gate PASSED 2026-09-01 (242/1,500 lines + the architect's blank-value set-filter fix) | — |
| chunk-21 (was D12a) | Sequence parser + payload + attachments | DONE — gate PASSED 2026-08-31 (699/700 lines, no architect fix needed) | — |
| chunk-22 (was D11) | Report definitions + guided views | GATED on designs | Phase 1 exit gate |
| chunk-23 (was D8) | SQLite adapter, SVG/draw.io export | GATED | Phase 1 exit gate |
| chunk-31 (was D12b) | Sequence renderer + SEQ-* | GATED on layout vectors + acme flow docs | chunk-21 gate |

## Standard rules — prepend to EVERY prompt

```text
Work in /Users/gavin/01-work-thor/projects/group-hobby/onetool-mcp-worktrees/arch-v3
on branch feature/arch-v3. Rules:

1. The design docs in plans/arch/arch-v3/ (index, schema, report, adapters,
   delivery) are the single source of truth and are READ-ONLY. If anything in
   your task is ambiguous, or the docs seem to contradict each other or the
   code, STOP: write the question into the "Open questions" section of
   plans/arch/arch-v3/plan.md and end your run. Never improvise a design
   decision, field, tool name, or behavior that is not written down.
2. v2 donor harvesting is COMPLETE and its worktree is gone. If a task
   seems to need v2 code, STOP per rule 1 (branch feature/arch-v2 exists
   on origin for the architect to consult).
3. Do not touch src/otdev/tools/arch.py or files outside your task's
   named surface unless your task explicitly says so. Do not add
   dependencies.
   IMPORTS in src/otdev/tools/_arch/v3/: use whatever accelerates —
   stdlib, any dependency already in the project (pydantic, openpyxl, the
   repo's YAML lib), otpack utilities, and stable ot library helpers.
   Never re-implement something onetool/otpack already provides. One hard
   limit: no runtime modules (ot.executor, server/MCP plumbing, anything
   needing a running server) — `python -m otdev.tools._arch.v3` must work
   standalone. MODIFYING project code outside _arch/v3/, arch.py, and your
   listed test files is allowed only when your prompt names the file, or
   after proposing it (rule 1) and being told to proceed; if you touch a
   shared module, also run that module's own tests and report the result.
   Unsure whether an import is runtime-side? Rule 1: stop and ask.
4. Match surrounding code style. Mark all tests @pytest.mark.unit and
   @pytest.mark.tools.
5. Before finishing: `just lint` is clean and
   `uv run pytest tests/unit/tools -k arch` is green. Report actual output.
6. Stay under the line budget in the task (source lines, excluding tests).
   If you cannot, STOP and report what is forcing the overrun — do not
   compress style to squeeze under.
7. Tests: write ONLY the tests your task explicitly lists — no extra
   coverage, no docstring/doc polish, no OpenSpec changes. Breadth is
   deliberately deferred (see "Speed mode" in plan.md).
8. When done: append a dated entry to the progress log in
   plans/arch/arch-v3/plan.md (what landed, source line count vs budget, test
   count, open questions). Do NOT commit and do NOT push — leave the worktree
   dirty; the architect commits after the gate review. Never run
   git add/commit/stash/restore/checkout on files you did not create.
```

**UI chunks only (D7, D8, anything touching `frontend/arch-report/`) — append
this to the prompt:**

```text
9. UI verification follows wip/notes/test-ui.md: drive the browser with
   Playwright through OneTool (`__ot playwright.browser_navigate(...)`,
   snapshots, CSS-targeted clicks, browser_console_messages,
   browser_network_requests, screenshots; no `ot.` prefix on proxied
   calls). Check the console for errors in EVERY verification pass, even
   when the page looks correct. Use per-page injection for annotations
   (`play_util.inject_annotations()`); enable_auto_inject is known broken.
   Close the browser when done.
```

## D1 — Phase 0: skeleton + fixture source dump (DONE 2026-08-23 (run inline by the architect))

Skeleton `_arch/v3/` package + acme workbook sheet dump to fixture-src. Full prompt in git history.

## D2 — Phase 1a: models + YAML I/O (DONE 2026-08-23, gate PASSED)

Schema-v3 Pydantic models + strict deterministic YAML I/O. Full prompt in git history.

## D3 — Phase 1b: resolver (DONE 2026-08-23, gate PASSED)

Resolver implemented to the architect's semantics suite (intervals, clipping, diff, advance). Full prompt in git history.

## D4 — Phase 1c: validation + pack tools (DONE 2026-08-23, phase-1 gate PASSED)

Located validation, dev CLI subcommands, pack facade tools; v1 cutover followed inline. Full prompt in git history.

## D5 — Phase 2: Excel adapter (DONE 2026-08-23, phase-2 gate PASSED)

Excel adapter: ten-sheet read/write, in-place mode-aware write, atomic located errors, round-trip tests. Full prompt in git history.

## D6 — Phase 3a: report scaffold + payload pipeline (DONE 2026-08-23, gate PASSED)

Report scaffold: payload compiler, vite single-file bundle, template injection. Full prompt in git history.

## D7 — Phase 3b: report features (DONE 2026-08-24, gate PASSED)

Client projection + union layout, time slider + diff, tables, fragment views. (The first phase-3 gate on the result produced the issues/ set.) Full prompt in git history.

## chunk-23 (was D8) — GATED (template to be issued at wave-2 start)

- **chunk-23:** SQLite adapter per adapters.md and client-side SVG/
  draw.io download; prompts written after the Phase 1 exit gate.

## D9–D10 + chunk-22 — gate rework and view-mode capabilities (issued per wave)

Same delegation model as D1–D8. Requirements live in
`plans/arch/arch-v3/issues/` (index `issues.md`); the architect folds each
wave's decisions into the design docs first, then issues the prompt here —
executors work only from the design docs and the prompt, never directly
from issue files.

- **D9 (wave 1 — schema/model):** ISSUED 2026-08-24 as D9a + D9b below.
  schema.md, adapters.md, and report.md carry the reworked contracts (C4
  kinds, id scheme, `start_in`/`end_in` over a base state,
  Provider/Consumer directions).
- **D10 (wave 2 — report UI):** ISSUED 2026-08-24 as D10a + D10b below.
  The twelve `p2-*` issues, the Q4–6 decisions, the research binding
  lists, and the mined interactions.md clauses are all folded into
  report.md "Wave-2 UI contract (v1)" — the single authoritative input.
  Split per the scoping note: D10a chrome/panels/tables, D10b canvas
  semantics + visuals. UI rule 9 applies to both.
- **chunk-22 (was D11 — view-mode capabilities):** `p3-report-definitions`
  (view-mode flow; `views:` YAML export starting point) and
  `p3-ui-guided-view` (resolves MAP/PATH/LENS). Gated on the Phase 1
  exit gate plus architect designs for both. `p3-edit-save-back` and
  `p3-ui-manual-positions` are NOT delegated — edit mode (chunk-43) is
  deferred and gets its own prompts when the local-server write path is
  designed.

## chunk-21/chunk-31 (were D12a/D12b) — sequence diagrams (GATED; issued per chunk)

Design doc: sequence.md (2026-08-25). Prompts are issued when the
architect artifacts exist; executors work from sequence.md + the prompt.

- **chunk-21 (was D12a — Python):** ISSUED 2026-08-25 (below) — flow-doc
  parser, validation findings, `sequences` payload section, CLI +
  `arch.validate`/`arch.generate` wiring. The parser-vector fixture
  (`tests/unit/tools/fixtures/arch/sequence/`) is committed and is the
  control mechanism. ON HOLD until the Phase 1 exit gate (user
  directive 2026-08-25); re-scope for message-file refs before running;
  no frontend files.
- **chunk-31 (was D12b — frontend):** `seqlayout.ts` + SVG layer + entity-box
  header row + the SEQ-* interaction contract. Gated on the architect's
  layout vectors and the acme flow docs; runs after the chunk-21 gate, may
  run parallel with chunk-22/chunk-23.

## D9a — Phase 3R wave 1a: model/resolver/validation rework (DONE 2026-08-25, committed)

Wave-1a schema/model/resolver/validation rework (C4 naming, auto ids, inclusive intervals, provider/consumer). Full prompt in git history.

## D9b — Phase 3R wave 1b: Excel + payload + projection rework (DONE 2026-08-25, wave-1 gate PASSED)

Wave-1b ten-sheet Excel + payload/projection rework, blank-id import. Full prompt in git history.

## D10a — Phase 3R wave 2a: chrome, panels, tables (DONE 2026-08-25, commit c37e3d05)

Wave-2a chrome, panels, tables. Full prompt in git history.

## D10b — Phase 3R wave 2b: canvas semantics + visuals (DONE 2026-08-25, commit c37e3d05)

Wave-2b canvas semantics + visuals; architect gate fixes (drill root carve-out, cluster button styling, layout-key staleness guard) rode the same commit. Full prompt in git history.

## D13 — UI polish passes (DONE — all four passes gated PASSED by 2026-08-29)

Four passes D13a–D13d implementing the confirmed UI direction over the
wave-2 report UI (plan.md "Phase 3P" carries the re-scoped pass list,
2026-08-27). Each is GATED until its architect spec lands; prompts are
issued one pass at a time and each pass gates before the next is issued.
No new features ride along.

Spec-authoring input (architect only — executors read the design docs,
never issue files): `plans/arch/arch-v3/ui-polish-direction.md` is the
decision source for every pass spec; `ui-polish.md` tags its 24
walkthrough issues to a pass as evidence (its expectations are
superseded where they conflict with the direction). When authoring a
pass's contract, translate the direction plus that pass's tagged issues
into normative requirements (or record a waiver/supersession in
ui-polish.md), and give behavior changes tests — they are behavior, not
presentation. Pass-4 precheck before speccing D13d: confirm the payload
already carries edge endpoint/interface/relationship data for the
connection-details fix (ui-polish #21); if it needs plumbing, escalate
to the user instead of burying it in a polish pass.

## D13a — Phase 3P pass 1: app shell (DONE 2026-08-28, gate PASSED)

Docked View/Info/Data shell, compact header + global search, dropdown
controls, lower-left Map/Fit/Zoom row, light-only tokens, `select`
fragment; 974/1,800 changed source lines. Gate review 2026-08-28.
(Prompt text in git history; the 2026-08-25 "visual foundation"
predecessor was superseded pre-run.)

## D13b — Phase 3P pass 2: canvas composition (DONE 2026-08-28, gate PASSED)

Content-sized cards (per-level tier widths, injectable-measurer
cardSize), ELK tuning + edgeless grid packing, initialViewport framing
capped at Read, thresholds derived from the type scale (79% Read /
110% Full), shiftViewport minimal-pan camera replacing the D13a refit
effect; 407/1,400 changed source lines. Gate review 2026-08-28.
(Prompt text in git history.)

## D13d — Polish pass 4: View / Info / Data content and states (DONE 2026-08-29, gate PASSED)

```text
[standard rules + UI rule 9]

Prereq: the D14 subsystem-level commit (703ee691) is the baseline.
Authoritative contract — READ IN FULL, in this order:
1. plans/arch/arch-v3/report.md "Polish contract — pass 4: View / Info /
   Data content and states (D13d)" — the normative spec; implement it
   exactly.
2. plans/arch/arch-v3/ui-polish-direction.md "View dock", "Data dock",
   "Info dock" — the confirmed direction the spec encodes.
3. plans/arch/arch-v3/ui-polish.md #13, #16, #20, #21, #22, #25, #26,
   #27 — the observed→expected evidence this pass must close.

Scope — implement the pass contract exactly:
1. Shell: viewport fill at/above the 1024 × 720 floor (no dead band, no
   outer page scroll, verified in the generated file:// report); dock
   header rows with icon-only collapse chevrons; collapsed docks as
   slim icon rails; View-dock content as compact list rows.
2. View: controls with no meaningful choice hide; Tags capped at 5
   visible rows with internal scroll.
3. Info: humanized, non-overlapping kv grid with linked Contains chips;
   "Changes at this stage" Details section and removal of the card
   change-popover; kind-appropriate connection Details (linked
   endpoints, direction, values, lifecycle interval — the payload
   already carries everything, NO Python changes); internal Back;
   "View dependencies" entry in Details; final Escape order.
4. Data: the four direction tabs (the subsystems tab folds into a
   rawState-sourced Entities with a kind column), auto-sized populated
   columns, all-empty columns collapsed, headers never truncated,
   Show on Canvas, two-way selection sync.
5. Designed empty/failure states and the motion/consistency sweep with
   a reduced-motion audit.
Out of scope — do not touch: cardSize/camera/layout, edgeAnchors/
splinePath/edgePresentation, projection.ts, all Python, the Payload
viewer and Attachments tabs (deferred to Phase 3S), guided-story UI,
the deps-diagram layout, dark theme.

Budget: 1,500 changed source lines (additions plus deletions, TS/TSX/
CSS, tests and the generated bundle excluded). Stop and ask before
exceeding it.

Tests: exactly the six cases in the pass contract's "Prescribed
tests"; every existing frontend and arch python test stays green.

Finish: `just lint`, frontend suite, `just build-arch-report`,
regenerate the acme report via the CLI, then verify per rule 9 from
file:// in light theme at 1440x900, 1024x720, AND 1920x1080 (proving
viewport fill with no dead band): clean console, zero external
requests; walk cold load -> select an entity (Details kv, chips,
changes section) -> open a connection from Connections and Back
returns -> Data open (four tabs, auto-sized columns, Show on Canvas)
-> collapse and reopen every dock via the new chrome -> Escape order.
Capture screenshots: info-entity-details, info-connection,
data-autosized, collapsed-rails, viewport-fill-1920. Definition of
done: rules 5-8, then STOP.
```

## D14 — Subsystem level rename (DONE, gate PASSED 2026-08-29)

```text
[standard rules + UI rule 9]

Prereq: the D13c graph-elements commit is the baseline. Subsystem
cards, boundaries, and kind pills inherit D13c's anatomy rules
automatically — no new visual design in this chunk.
Authoritative contract — READ IN FULL, in this order:
1. plans/arch/arch-v3/schema.md, section "Entity kinds (C4-aligned)"
   (amended 2026-08-28: the new Subsystem kind and the strict
   System > Subsystem > Container > Component > Code layering);
2. plans/arch/arch-v3/report.md, section "C4 zoom and drill (D10b)"
   (amended 2026-08-28: the four level ids systems / subsystems /
   containers / components, their roll-up semantics, boundary chains,
   and the hidden-when-empty Subsystem option);
3. plans/arch/arch-v3/adapters.md, "Excel workbook" (eleven sheets —
   Subsystems is sheet 5).
Any ambiguity between this prompt and those sections is a rule-1 stop.

WHAT THIS IS: a schema + naming change, no visual redesign. The
detail-level model becomes System / Subsystem (optional) / Container /
Component: Subsystem is a new entity kind (a logical grouping of
related containers inside a system); containers no longer nest. The
former frontend levels 'top-containers' and 'containers' ("Container"
/ "Child Containers") are replaced by 'subsystems' ("Subsystem") and
'containers' ("Container"). Do NOT touch D13b's layout/camera behavior
or start pass-3 work (edge/card visuals).

Budget: 1,100 changed source lines (Python + TS/TSX + fixture; tests
excluded). No new dependencies.

Scope A — Python (src/otdev/tools/_arch/v3/):
1. model.py: Subsystem model (row shape as Container; `parent`
   required, must name a System). Architecture gains the `subsystems`
   collection; Container.parent now references a System or Subsystem.
2. yamlio.py: `subsystems` in the canonical key order, between
   `systems` and `containers`.
3. ids.py: generated-id prefix `ss` for subsystems.
4. resolver.py: add `subsystems` to the kind lists; clipping parent
   chain becomes system > subsystem > container > component > code
   (a container with a subsystem parent clips to the subsystem, which
   clips to its system). Subsystems are legal interface/relationship
   endpoints (schema.md: any entity kind).
5. validate.py: subsystem `parent` must resolve to a system; container
   `parent` resolves to a system OR subsystem; ambiguous parent = id
   present in both `systems` and `subsystems`; a container `parent`
   naming another container is now an error (nesting removed). Drop
   the container-cycle machinery only if it is exclusively about
   container nesting.
6. excel.py: `Subsystems` sheet (sheet 5, headers as Systems +
   `parent`), same dropdown/validation pattern as Containers;
   round-trip and in-place write include it.
7. payload.py: emit `rows.subsystems`.

Scope B — Frontend (frontend/arch-report/src/):
8. types.ts: Level = 'systems' | 'subsystems' | 'containers' |
   'components'; RowKind + payload rows gain 'subsystems'; row parent
   fields per schema.
9. projection.ts: representativeAtLevel/rollUp/boundaryAncestors per
   the amended C4 zoom table — at 'subsystems' a container with no
   subsystem stays itself; at 'containers' subsystem + system
   boundaries nest; at 'components' the full chain. Drill through a
   subsystem boundary works like any boundary.
10. view.ts: level fragment tokens updated ('top-containers' retired;
    unknown values keep falling back per existing diagnostics).
11. ViewDock.tsx: DETAILS = System / Subsystem / Container /
    Component; the Subsystem option renders only when the payload has
    at least one subsystem row.
12. cardSize.ts: CARD_WIDTH keys → systems 280, subsystems 260,
    containers 240, components 240.
13. App.tsx: KIND_LABEL, search kinds, child-count logic (a
    subsystem's children are containers whose parent is its id).
14. GridPanel: a Subsystems table with the standard columns.

Scope C — acme fixture (tests/unit/tools/fixtures/arch/acme.yaml):
15. Insert this `subsystems:` collection between `systems:` and
    `containers:` (hand-authored slug ids are legal):

subsystems:
- id: storefront-edge
  name: Storefront and Edge
  parent: commerce-platform
  start_in: acme-2027-edge-foundation
  description: Customer-facing entry points routing storefront traffic
    into the new platform.
  tags:
  - ecommerce
  - frontend
- id: platform-foundation
  name: Platform Foundation
  parent: commerce-platform
  start_in: acme-2027-edge-foundation
  description: Cross-cutting eventing, observability, and legacy
    integration capability underpinning every other subsystem.
  tags:
  - platform
  - integration
- id: catalog-search
  name: Catalog and Search
  parent: commerce-platform
  start_in: acme-2028-catalog-search
  description: Product catalog mastering, merchandising, and search
    capability.
  tags:
  - bounded-context-catalog
- id: customer-cart-pricing
  name: Customer, Cart and Pricing
  parent: commerce-platform
  start_in: acme-2029-customer-cart-pricing
  description: Customer-identity-linked shopping capability - profiles,
    carts, prices, and notifications.
  tags:
  - bounded-context-customer
- id: transaction-core
  name: Transaction Core
  parent: commerce-platform
  start_in: acme-2030-transaction-core
  description: Order capture and fulfilment initiation - checkout,
    orders, payments, and inventory.
  tags:
  - bounded-context-order
- id: back-office-insight
  name: Back Office and Insight
  parent: commerce-platform
  start_in: acme-2031-complete-cutover
  description: Administration and operational reporting over the
    completed platform.
  tags:
  - admin
  - analytics

16. Rewire exactly these container `parent` values (all other
    containers keep their system parent — that exercises the
    "subsystem is optional" path):
    storefront-edge: commerce-edge, storefront-bff
    platform-foundation: event-backbone, observability-platform,
      legacy-integration-adapter, analytics-event-adapter
    catalog-search: catalog-service, search-service,
      catalog-sync-adapter
    customer-cart-pricing: customer-service, cart-service,
      pricing-service, notification-service
    transaction-core: checkout-service, order-service,
      payment-service, inventory-service
    back-office-insight: admin-portal, reporting-service
17. Components stay untouched (the component level is already
    populated with 55 rows).

Tests — exactly five new cases plus mechanical updates (level-token
renames in existing suites and vectors; expected counts updated where
the subsystem level changes them):
(1) py round-trip: YAML and Excel round-trip a model with subsystems
    unchanged;
(2) py validation: ambiguous parent (id in systems AND subsystems) and
    a container parented to a container are both errors;
(3) TS projection: at 'subsystems', a grouped container rolls up to
    its subsystem and an ungrouped container stays itself;
(4) TS projection: at 'containers', subsystem boundaries nest inside
    system boundaries;
(5) TS ViewDock: the Subsystem option is absent when the payload has
    no subsystems and present when it does.

Finish: regenerate frontend/arch-report/src/fixture-payload.json (the
README command), `just build-arch-report`, regenerate the acme report
via the CLI, verify per rule 9 from file:// at 1440x900 (light): clean
console, zero external requests; the Detail dropdown reads System /
Subsystem / Container / Component; the Subsystem level shows the six
subsystems inside the Digital Commerce Platform boundary with
ungrouped containers as leaves; the Container level nests subsystem
boundaries inside system boundaries; Stage switches still move
nothing. Capture screenshots: subsystem level cold load, container
level showing nested boundaries. Definition of done: rules 5-8, then
STOP — D13c is a separate prompt.
```

## D13c — Phase 3P pass 3: graph elements (DONE, gate PASSED 2026-08-28)

```text
[standard rules + UI rule 9]

Prereq: the D13b canvas-composition commit is the baseline (content-
sized cards, tuned ELK, initialViewport framing, shiftViewport
camera). Authoritative contract — READ IN FULL, in this order:
1. plans/arch/arch-v3/ui-polish-direction.md (the product direction);
2. plans/arch/arch-v3/report.md, sections "Confirmed UI direction
   (2026-08-27)" and "Polish contract — pass 3: graph elements
   (D13c)" — the pass contract scopes exactly what this pass
   implements versus defers.
Do NOT read issue, research, or ui-polish files. The pass contract
wins on scope; the direction wins on behavior; any other ambiguity is
a rule-1 stop.

This pass owns what cards, boundaries, interface ports, and splines
LOOK like and how selection emphasizes them. It does NOT touch
layout, framing, camera, thresholds (pass 2 code stays), dock
content (pass 4), or projection semantics: projection.ts is
READ-ONLY (rendered per-direction spline splitting happens in the
App-side edge building, not in projection). Expected surface:
App.tsx (node/edge components + edge building), styles.css, the
cardSize module's content model, plus new modules for anchor/spline
math and edge presentation (suggested: edgeAnchors.ts,
edgePresentation.ts) and their test files.

Budget: 1,600 changed source lines (excluding tests). Python changes:
none. No new npm dependencies.

Scope — implement the pass contract exactly:
1. Card anatomy per depth (kind pill, two-line name, description,
   fact pills, counts); entityIcon DELETED everywhere; persistent
   >=24px drill control; boundary stubs as compact external cards;
   card diffs as pills + narrow border markers (the change-popover
   stays this pass).
2. Containment boundaries as subtle tints with readable headers.
3. Splines: bezier only, geometry-derived floating anchors via the
   edgeAnchors pure function with lane separation; per-direction
   spline split of aggregated edges (bidirectional members count on
   both); count chips; zoom-compensated stroke >= ~1.5 screen px and
   visible custom arrowheads; labels neutral-at-Full /
   always-when-selected-or-hovered; diff styling as an increment on
   a legible base.
4. Interface ports: dot at Far/Read, labeled chip at Full or on
   spline hover/selection, attached at the provider-side anchor;
   never a detached empty box.
5. Selection: the IcePanel one-hop model exactly (accent border,
   animated outgoing / static incoming in one accent, brightened
   neighbors, dimmed-but-readable rest, reduced-motion static
   fallback); emphasis priority selection > tag lens > neutral;
   Relationship switch re-resolves directions with zero node
   movement.

Tests: exactly the five cases listed in the pass contract's
Verification section, plus mechanical updates to existing cardSize/
emphasis/presentation tests. The projection/vector suites must pass
untouched.

Finish: `just build-arch-report`, regenerate the acme report via the
CLI, verify per rule 9 from file:// at 1440x900 AND 1024x720 (light):
clean console, zero external requests, no orthogonal detours or
interior crossings, arrowheads visible at cold-load zoom, one-hop
selection correct incl. forced prefers-reduced-motion, Stage diff
legible-base. Capture the five screenshots listed in the pass
contract. Definition of done: rules 5-8 (report npm test output;
pytest run unchanged by this chunk), then STOP — D13d is a separate
prompt.
```

## chunk-16 — canvas performance (DONE 2026-08-31, gate PASSED)

```text
[standard rules + UI rule 9]

Context: pan/zoom on large graphs is slow and labels flicker during
zoom. The root cause is confirmed and documented — READ IN FULL, in
this order:
1. plans/arch/arch-v3/issues/p33-ui-canvas-performance.md — the issue
   this chunk resolves, with the confirmed root cause (per-frame
   viewport state commits + the edge-presentation memo keyed on
   canvasViewport, defeating memo() on every edge).
2. plans/arch/arch-v3/report.md "Performance contract — canvas at
   scale (chunk-16)" — the normative spec; implement it exactly.

This chunk changes WHEN presentation is computed, never WHAT is
rendered at rest: at any settled viewport the scene must be pixel-
identical to today's. Frontend only (frontend/arch-report/); no Python,
no payload changes.

Scope:
1. Track the live viewport in a ref; commit React viewport state only
   on gesture end (onMoveEnd), programmatic camera moves, and
   readingDepth bucket transitions (spec rule 2). Extract the commit
   decision as a pure, tested helper.
2. Move zoom-scale compensation (stroke width, arrowhead scale) to a
   CSS custom property written to the canvas container via ref each
   frame; delete the per-edge React plumbing of zoom for pure scaling
   (spec rule 4). Depth-dependent LOGIC (label eligibility, port
   expansion) stays in React and keys off the committed depth bucket.
3. Make edge/node data referentially stable across recomputes with
   unchanged inputs; stabilize handler identities (spec rules 5–6).
   Restructure the big edges useMemo as needed, but do not change its
   at-rest output.
4. Do not touch: layout engines, projection.ts, view.ts, collision-
   pass semantics (only when it runs), any Python.

Budget: 500 changed source lines (additions + deletions; tests and the
generated bundle excluded). Stop and ask before exceeding it.

Tests: exactly the three cases in the performance contract's
"Prescribed tests"; every existing frontend test stays green.

Finish: `just lint` (touched paths), frontend suite, tsc,
`just build-arch-report`, regenerate the acme report via the CLI, then
verify per rule 9 from file:// at 1440x900: load the report with the
legacy #level=components link (bulk expansion), record a Performance
trace of a 2 s continuous pan and a scroll-zoom crossing a depth
boundary, and confirm (a) no multi-frame stalls from React commits,
(b) zero label/pill visibility changes mid-gesture, (c) the settled
scene matches a pre-change capture of the same viewport. Record
before/after trace numbers in the log entry. Console clean, zero
external requests. Definition of done: rules 5-8, then STOP.
```

## chunk-17 — gate-feedback polish sweep (DONE 2026-09-01, gate PASSED)

```text
[standard rules + UI rule 9]

Prereq: the chunk-16 gate commit is the baseline.
Context: the user's 2026-08-31 exit-gate walkthrough re-raised open
polish defects. This chunk resolves seven issue files — READ EVERY ONE
IN FULL, each carries Current/Expected and screenshots:
  plans/arch/arch-v3/issues/p24-ui-data-table-filters.md
  plans/arch/arch-v3/issues/p26-ui-chrome-polish.md
  plans/arch/arch-v3/issues/p28-ui-dependency-view.md
  plans/arch/arch-v3/issues/p29-ui-minimap.md
  plans/arch/arch-v3/issues/p32-ui-consistency-sweep.md (open bullets
    only — the dev-console bullet is already satisfied)
  plans/arch/arch-v3/issues/p34-ui-tag-filter.md
  plans/arch/arch-v3/issues/p35-ui-reset-view.md
Then READ plans/arch/arch-v3/report.md "Polish contract — pass 6:
gate-feedback sweep (chunk-17)" — it pins the cross-issue decisions
(reset-control placement and semantics, tag-halo treatment, single
popover controller, control-token scale) and the out-of-scope list.
Styling authority for anything the issues leave open:
ui-polish-direction.md.

Scope: implement every issue's Expected section plus the five pinned
decisions. Frontend only; no Python, no payload changes, no layout-
engine changes. Do not regress chunk-16's gesture freeze (no new
per-frame state).

Budget: 1,500 changed source lines (additions + deletions; TS/TSX/CSS;
tests and the generated bundle excluded). Stop and ask before
exceeding it.

Tests: exactly the five cases in the pass-6 contract's "Prescribed
tests"; every existing frontend test stays green (AG Grid filter-config
tests updated to set filters count as updates).

Finish: `just lint` (touched paths), frontend suite, tsc,
`just build-arch-report`, regenerate the acme report via the CLI, then
verify per rule 9 from file:// at 1440x900 and 1024x720: walk each
issue's Current scenario and confirm its Expected holds — table header
set-filters with one popup at a time; Data tabs / View dependencies /
map cluster / Connections rows at control scale; dependency view with
hidden canvas controls, styled fallback, named interfaces; readable
minimap; tag lens with halo + matched-count; reset control round-trip
via Back. Capture one screenshot per issue into the chunk evidence dir
(/tmp/arch-v3-evidence/test-results/chunk-17/). Console clean, zero
external requests. Definition of done: rules 5-8, then STOP.
```

## chunk-21 (was D12a) — sequence parser + payload + attachments (DONE 2026-08-31, gate PASSED)

```text
[standard rules]

Context: v3 gains sequence diagrams and file attachments. plans/arch/
arch-v3/sequence.md is the owner doc — READ IT IN FULL first (source-doc
format, DSL incl. the `attach` statement, compilation, payload shape,
finding codes) — plus schema.md "Attachments" (interface `attachments`
field, path rules, shared finding codes) and report.md "Payload contract"
(`files` key, interface-row serialization). This chunk is the Python half
only: parse and validate Markdown flow docs, compile the `sequences`
payload section, add the interface `attachments` field end to end (YAML,
Excel, payload), resolve + embed attachment files, and wire discovery
into validate/generate. NO frontend files, no bundle rebuild (the payload
of every existing fixture/report is unchanged — see "omit when empty"
below).

Control mechanism: tests/unit/tools/fixtures/arch/sequence/ — architect-
authored parser vectors. READ ITS README FIRST; it pins the driver
contract, finding codes, anchor rules, and every decision the vectors
encode (pairing rule, marker placement, drop-defaults, ordering, the
`attach` rules). Vectors are READ-ONLY: one that looks wrong is a rule-1
stop, never an edit. Budget: 700 changed source lines (excluding tests
and fixtures).

Task:
1. New module src/otdev/tools/_arch/v3/sequence.py: parse one flow doc
   (frontmatter, doc-level participant lines, `##` scenario headings with
   prose, ```seq fences, `attach` statements) and compile the doc set
   against an Architecture per sequence.md "DSL" + "Compilation".
   Findings use the existing Finding dataclass (file = the flow doc
   path, line/column per the README anchor rules; columns are your
   choice but must be >= 1).
2. Discovery: <model-dir>/sequences/*.md beside the model YAML, sorted
   filename order. arch.validate / CLI validate include flow-doc
   findings; any flow-doc error fails generate atomically, exactly like
   model errors.
3. Interface `attachments` (schema.md "Attachments"): optional path-list
   field on the Interface model, canonical YAML round-trip (authored
   order, omit empty), Excel Interfaces-sheet `attachments` list cell
   (`[a;b]`, adapters.md), located findings for both interface rows
   (anchored at the YAML list entry) and flow-doc `attach` lines:
   errors invalid_path / unresolved_file / invalid_file, warning
   large_attachment (> 256 KB; the file still embeds).
4. Payload: build_payload gains the top-level `sequences` key (after the
   entity collections), sorted by flow id, compiled per sequence.md —
   intervals reuse the existing segment machinery (clips always []) —
   and the `files` key after it (report.md): every path referenced by
   any interface row or message, embedded once, sorted by path, value
   {"lang", "text"} with lang from the extension (json/xml/csv/yaml,
   else text). Interface rows serialize `attachments` as authored;
   message items carry `attachments` per sequence.md. OMIT `sequences`
   when there are no flow docs and `files` when nothing carries
   attachments: existing checked-in payloads (projection fixture, acme
   dev payload) and the generated report must stay byte-identical —
   that is what keeps this chunk off D10's surface.
5. Facade/CLI: no new subcommands; validate/generate/payload pick the
   flows up via the shared load path in api.py.

Tests (exactly these):
1. tests/unit/tools/test_arch_v3_sequence.py — the vector driver per the
   fixture README: for each flows/*.md (attachments vectors included)
   compare (severity, code, line) triples sorted by (line, code) and
   deep-compare the compiled entry against expected.json
   ("sequence": null = doc must produce >= 1 error and no compiled
   entry); plus the crossdoc/ set producing exactly the listed
   duplicate_id finding.
2. large_scenario thresholds: synthetic docs with 31 participants (warn)
   / 30 (silent), and 301 items in one scenario (warn) / 300 (silent).
3. Discovery + atomicity: a temp model dir whose sequences/ holds one
   good and one erroring doc -> validate reports both docs' findings,
   generate fails atomically (no output file); with the erroring doc
   removed -> payload contains `sequences` sorted by flow id; and a
   model dir with no sequences/ -> payload has NO `sequences` key.
4. Interface attachments round-trip: a model with two attachments on one
   interface round-trips through canonical YAML and through Excel
   (list cell; blank cell = no attachments) with model equality; an
   interface path that is missing / escapes the model dir / has an
   invalid character produces the three located errors at the YAML
   entry.
5. Embedding: a model dir where an interface and a flow message
   reference the same file -> payload `files` has ONE entry for it,
   sorted paths, correct lang for .json/.xml/.csv/.yaml/other; a file
   at exactly 256 KB is silent and one byte over warns
   large_attachment; a model with no attachments anywhere has NO
   `files` key.

Definition of done: rules 5–8, plus: all existing arch tests stay green,
`uv run python -m otdev.tools._arch.v3 validate
tests/unit/tools/fixtures/arch/sequence/model.yaml` still reports 0
errors, and regenerating the checked-in projection-fixture payload and
acme dev payload via the CLI is byte-identical. STOP after the log entry
— the architect reviews at the gate.
```

## P11 — Canvas presentation: layout, edges, ports, color, theme (DONE 2026-08-29, gate PASSED)

```text
[standard rules + UI rule 9]

Prereq: the plan-reorg commit (99133320) or later is the baseline.
Authoritative contract — READ IN FULL, in this order:
1. plans/arch/arch-v3/report.md "Polish contract — pass 5: canvas
   presentation (P11)" — the normative spec; implement it exactly.
2. plans/arch/arch-v3/schema.md "Theme (presentation colors)" and
   "Entity kinds" (containment matrix) — the schema authority for the
   theme block.
3. plans/arch/arch-v3/adapters.md sheet list — the Settings sheet
   (sheet 12) you are adding.
4. plans/arch/arch-v3/ui-polish-direction.md "Canvas visual language"
   (2026-08-29 amendment) — the confirmed direction the spec encodes.

Scope — implement the pass-5 contract exactly:
1. Topology-aware layout: the star-detection pure function; the
   deterministic radial construction (hub center, users top arc,
   stable ring order, >= 48 px clearance, two-plus-hop outward
   placement, unconnected grid pack); ELK layered untouched for
   non-star graphs, boundary levels, and the deps view.
2. Edge termination: per-side distributed attachment (>= 14 px apart,
   >= 14 px off corners), perpendicular 12 px stubs both ends, visible
   port dots, accent-tinted ports on selection; rework edgeAnchors.ts
   accordingly (its existing tests are updated, not deleted).
3. At-rest labels: white label pills at Read and Full per the spec
   (content, max-width + ellipsis + title, midpoint placement with
   deterministic nudging); D13c selection/hover label behavior stays
   on top.
4. Color economy: neutral edge/border/pill tokens; per-kind CSS custom
   properties (--kind-system ... --kind-user) defaulting to the D13d
   Info-chip palette and consumed by canvas kind pills, card borders,
   boundary tints, Info Contains chips, and Data kind chips; the teal
   accent ONLY on selection/one-hop/focus/dock links; arrowheads
   scaled ~0.8x; compact user cards (width tier 220, description at
   Full only).
5. Theme plumbing (Python — this chunk MAY touch model.py, yamlio.py,
   validate.py, payload.py, excel.py in _arch/v3/): optional `theme`
   model block per schema.md, validation codes unknown_theme_key /
   invalid_color (located), canonical YAML position after timelines,
   payload pass-through, Excel Settings sheet with round-trip
   equality; regenerate checked-in payloads via the CLI (must be
   byte-identical except where a fixture gains a theme).
Out of scope — do not touch: projection.ts, view.ts, drill/expansion
behavior (P12), Info/Data content beyond the kind-token consumption
named above, camera.ts logic, sequence work.

Budget: 2,400 changed source lines (additions plus deletions; py +
TS/TSX/CSS; tests and the generated bundle excluded). Stop and ask
before exceeding it.

Tests: exactly the six cases in the pass-5 contract's "Prescribed
tests"; every existing frontend and arch python test stays green
(edgeAnchors tests updated to the new attachment contract count as
updates, not new tests).

Finish: `just lint`, arch py suite, frontend suite,
`just build-arch-report`, regenerate the acme report via the CLI, then
verify per rule 9 from file:// in light theme at 1440x900 and
1024x720: clean console, zero external requests; walk cold load (the
acme System landscape MUST lay out radially — hub centered, no
corner fan, no card overlap) -> confirm at-rest label pills at Read ->
zoom to confirm ports, stubs, and flush arrowheads -> select the hub
(accent appears ONLY on selection artifacts; everything else neutral)
-> switch Stage (diff colors intact over the neutral base) -> confirm
kind pill/border colors match the Info Contains chip colors. Capture
screenshots: landscape-radial-1440, labels-at-rest, ports-closeup,
selection-accent, theme-kinds. Definition of done: rules 5-8, then
STOP.
```

## P12 — Map model: in-place C4 expansion (DONE 2026-08-29, gate PASSED; the anchor-capacity stop was resolved by the architect's perimeter-overflow decision — report.md "Perimeter overflow")

```text
[standard rules + UI rule 9]

Prereq: the P11 gate commit is the baseline (prompt re-reviewed against
it per the pipeline rule).
Post-P11 integration notes (bind your work to the landed tree):
- Interface ports expand to labeled pills ONLY at Full depth or when
  selected/hovered (`expandPort` in App.tsx, separate from
  `showLabel`); at-rest Read labels are the midpoint pills. Keep that
  split — do not re-tie port expansion to showLabel.
- `unionLayout(graph, key, sizes, aspectRatio, preferredHub)` takes the
  projected star hub (App computes `projectedHub` via `starHub`);
  preset relayouts must keep passing it so radial-vs-layered stays
  stage-stable under your new `(timeline, expansion set)` layout key.
- `edgeAnchors` throws RangeError when a side cannot fit its batch
  (>= 14 px separation + corner clearance). Expansion concentrates
  edges on boundary borders (large, fine) but compact user cards are
  220 px wide with short sides — if a capacity error surfaces in the
  walkthrough, stop and ask; do not silently relax the spacing.
Authoritative contract — READ IN FULL, in this order:
1. plans/arch/arch-v3/report.md "Map contract — in-place C4 expansion
   (P12)" — the normative spec; implement it exactly.
2. plans/arch/arch-v3/schema.md "Entity kinds" — the containment
   matrix that defines what expands to what.
3. plans/arch/arch-v3/ui-polish-direction.md "Detail" (2026-08-29
   amendment) — the confirmed direction.

Scope — implement the map contract exactly:
1. View state: the `expand` fragment key (validated id list); level+
   drill retired with legacy-link mapping (drill= -> ancestor-chain
   expansion + select; level= -> the equivalent preset); Detail
   dropdown as bulk presets with "Custom" display; history semantics
   (each expand/collapse and each preset application = one entry).
2. Projection: tree-based rendering (collapsed card with roll-up
   members / expanded boundary with mixed-kind direct children,
   recursive); boundary identity (header + bottom description; never
   a card inside its own boundary); per-endpoint deepest-visible
   resolution with defined/derived attachment, aggregation on shared
   visible pairs, internal-edge suppression; direction/one-hop/lens/
   diff semantics unchanged.
3. Interaction: expand control = magnifier + live child count (only
   with live children), double-click expands, boundary-header collapse
   prunes the subtree; drill view, breadcrumb, and Up control removed;
   Escape order unchanged.
4. Layout: ELK layered inside expanded boundaries (INCLUDE_CHILDREN
   when nested); local push-apart on expand (only displaced neighbors
   move, minimum displacement to restore 48 px clearance,
   deterministic); collapse restores cached positions exactly; presets
   re-lay out fresh (P11 star rules decide radial vs layered); camera
   keeps the expanded entity's center fixed, zoom unchanged.
5. Acme showcase delta: the four-level path is commerce-platform ->
   storefront-edge -> commerce-edge -> its components (edge-waf-cdn,
   strangler-route-config); verify names/descriptions read well at
   every hop and enrich only where thin. Add EXACTLY these two
   interfaces (fixture rows in the interfaces list, matching the
   existing row shape):
   - id: edge-bot-defense, name: "Edge bot and abuse signals",
     provider: storefront-edge (subsystem-level definition), consumer:
     fraud-provider, call_direction: provider_to_consumer, start_in:
     acme-2027-edge-foundation, tags [security, synchronous],
     properties {technology: HTTPS, type: api}. Collapsed it renders
     commerce-platform -> Fraud Decision Provider (derived); expanding
     the system slides it to the Storefront and Edge boundary
     (defined).
   - id: strangler-route-cutover, name: "Strangler route cutover
     control", provider: strangler-route-config (component-level
     definition), consumer: commerce-monolith, call_direction:
     provider_to_consumer, start_in: acme-2027-edge-foundation, tags
     [strangler, internal], properties {technology: Config push, type:
     control}. It demonstrates the full derived ladder: each expansion
     hop (system -> subsystem -> container -> component) re-attaches
     one level deeper.
   Regenerate the wip acme report.
Out of scope — do not touch: P11's radial/edge/color modules beyond
consuming them, all Python except payload regeneration commands, Info/
Data content (selection sync must keep working), the deps view,
sequence work.

Budget: 2,600 changed source lines (additions plus deletions; TS/TSX/
CSS + acme fixture YAML; tests and the generated bundle excluded).
Stop and ask before exceeding it.

Tests: exactly the six cases in the map contract's "Prescribed tests";
every existing frontend and arch python test stays green (projection
vectors for the retired levels are re-cut per the spec, counted as
updates).

Finish: `just lint`, arch py suite, frontend suite,
`just build-arch-report`, regenerate the acme report via the CLI, then
verify per rule 9 from file:// in light theme at 1440x900 and
1024x720: clean console, zero external requests; walk cold load ->
expand Digital Commerce Platform (boundary grows in place, neighbors
displace minimally, everything else holds position) -> expand
storefront-edge -> a container -> components (four-level path, mixed
child kinds visible at the system level) -> confirm an external edge
slides from derived to defined attachment while expanding -> collapse
back up (positions restore) -> apply each Detail preset -> Copy view
link and reload it (expansion restored) -> browser Back walks the
expansion steps. Capture screenshots: map-collapsed, map-sys-expanded,
map-four-levels, endpoint-slide, preset-container. Definition of done:
rules 5-8, then STOP.
```

## P13 — Report UI correctness fixes (READY, added 2026-08-30)

Fixes issues p15, p17, p18, p19 (files in plans/arch/arch-v3/issues/ —
read all four before starting; they carry repro steps and expected
behavior). Prepend the Standard rules.

```text
Task: fix four correctness defects in the report app
(frontend/arch-report/src/). Issue files (READ FIRST):
plans/arch/arch-v3/issues/p17-ui-boundary-edges-dropped.md,
p15-ui-zoom-dimming.md, p18-ui-initial-framing.md,
p19-ui-connections-undercount.md.

Surface: frontend/arch-report/src/ only (App.tsx, edgePresentation.ts,
camera.ts, InfoPanel.tsx, styles.css and their test files). Do not touch
layout.ts beyond what a fix strictly needs — layout rework is chunk P14.

1. p17 (do this first — everything else is judged on its result):
   BoundaryNodeView renders no React Flow handles, so every edge whose
   endpoint resolves to an expanded boundary is dropped with RF error
   #008. Add hidden target/source Handles to BoundaryNodeView matching
   ArchitectureNodeView (Position.Left target, Position.Right source).
   Verify in the dev app: expanding systems:legacy-commerce then
   containers:commerce-monolith on the acme fixture renders every
   projected edge and logs zero React Flow warnings.

2. p15: emphasis classification dims everything when a boundary is
   selected, because classifyEmphasis compares spline endpoints against
   the single selected key while edges anchor to deepest-visible child
   keys. Change classifyEmphasis to take a Set of selected keys; in
   App.tsx build that set as the selected display key PLUS, when it is a
   boundary, all its descendant node keys (boundary.childKeys transitive,
   via projected.boundaries). Selected set members render emphasized,
   edges touching the set are outgoing/incoming, their far endpoints
   neighbor, the rest unrelated. The selected element must never dim.

3. p18: initial load must frame the whole graph (same result as Fit),
   capped at 100% zoom. Adjust initialViewport in camera.ts (and its
   call in App.tsx) — remove the reading-depth floor that currently
   opens at 79% showing ~3 of 11 systems. Applies to hash-restored views
   without an explicit camera too. (The orphan-label clause in p18 is
   NOT in scope — it lands with the label work.)

4. p19: the Info panel Connections tab must list interfaces by MEMBER
   involvement, not spline-endpoint equality: an interface belongs to
   the selection when its provider/consumer (or source/target) id is the
   selected row id or any of its rolled-up member ids (same roll-up
   App.tsx uses for connectionCount). Group incoming/outgoing per the
   current aspect. Also scope edge emphasis the same way: selecting a
   rolled-up member emphasizes only splines whose members involve it
   (reuse the Set from item 2).

Tests (vitest, existing patterns in *.test.tsx/ts — only these):
- boundary node exposes handles (p17),
- classifyEmphasis with a selected boundary set: children emphasized,
  touching edges directional, nothing dims the selected set (p15),
- initialViewport fits bounds and caps zoom at 1 (p18),
- connections grouping for a fixture entity matches member-level
  interface rows (p19).

Verify: cd frontend/arch-report && npm run build (tsc clean) && npm test
green. Then just build-arch-report and regenerate the acme report:
uv run python -m otdev.tools._arch.v3 generate <acme yaml>
plans/arch/wip/acme-report.html (find the acme YAML path used by the
previous regeneration; STOP per rule 1 if ambiguous). Report actual
command output. Budget: 600 source lines (expect far less).
```

## P14 — Layout engines + config + A/B harness (READY, authored 2026-08-30 at the P13 gate)

Design authority: plans/arch/arch-v3/layout-design.md (CONFIRMED).
Absorbs issue p13-ui-expansion-layout. Prepend the Standard rules.
Proposed budget: 2,000 changed source lines.

```text
Task: extract the report's layout methods into engines behind one
interface, add the authored `layout:` config block, expose a viewer
Layout control, and build the A/B comparison harness. Design (READ
FIRST, it is the contract): plans/arch/arch-v3/layout-design.md. Issue
plans/arch/arch-v3/issues/p13-ui-expansion-layout.md is absorbed here —
child packing inside expanded boundaries becomes engine-owned and its
narrow-column defect must be gone.

Surface: frontend/arch-report/src/ (layout work, viewer control, view
state) and src/otdev/tools/_arch/v3/ (config block only:
model/yamlio/excelio/validate/payload). Follow the `theme` block's
plumbing as the exact precedent at every Python step.

1. Engine extraction (refactor, no visual change yet). layout.ts holds
   three entangled methods: ELK layered (buildLayoutInput/unionLayout),
   radialLayout, gridPack. Extract each into a pure module under
   src/layout/ (layered.ts, radial.ts, grid.ts) implementing the
   LayoutEngine interface from layout-design.md section 1 (graph +
   sizes + settings + context in, Positions out; no React, no view
   state). Add a registry mapping method name -> engine; unionLayout
   becomes dispatch + cache. stableExpansionLayout and applyPositions
   stay engine-independent post-processing. With no `layout:` config
   present, method selection keeps today's behavior exactly (radial for
   star-shaped flat graphs per the P11 starHub rule, layered otherwise,
   grid for edgeless sets) and the P11 spacing/clearance contract
   (report.md pass 5) is unchanged. Existing layout tests must pass
   without weakening; mechanical import updates are fine.
2. Child packing (issue p13): expanded-boundary interiors are laid out
   by the parent graph's engine (layered interior for layered, the
   existing nested-ELK path refactored in). Fix the narrow-single-
   column packing so an 11-child expansion fills the boundary in rows/
   ranks with the `boundary` spacing padding; boundary edges still
   route to the P12 anchors.
3. `layout:` config block (Python, theme precedent): optional
   `Layout` model on Architecture per layout-design.md section 2 —
   method ('layered'|'radial'|'grid'), direction ('right'|'down'),
   spacing {node, layer, boundary} (positive ints), ranking ('auto' |
   'property:<name>'), user_choice (bool). Canonical YAML round-trip;
   Excel Settings-sheet keys (layout.method, layout.direction,
   layout.spacing.node, layout.spacing.layer, layout.spacing.boundary,
   layout.ranking, layout.user_choice) beside the theme.* keys; payload
   carries the block verbatim (absent -> {}); validation emits located
   WARN findings unknown_layout_key / invalid_layout_value and the
   report falls back to defaults — a bad knob must never kill the
   report. Absent block = today's behavior. Presentation-only: never
   touches resolution, diffing, or semantic validation.
4. Settings consumption (TS): config method/direction/spacing/ranking
   feed LayoutSettings; defaults when absent match today's constants.
   `ranking: property:<name>` applies to layered only: rank entities by
   that property's value on the entity row's properties (lane order
   frontend|service|data|external when the property is `layer`),
   falling back to call-direction inference (today's ELK ordering) for
   entities without the property or when ranking is 'auto'.
5. Viewer control: a Layout dropdown in the View dock listing the
   registered methods, rendered only when config `user_choice` is true;
   config method preselected. The choice rides the view hash
   (`layout=<method>`, view.ts precedent) so shared links reproduce the
   picture, and localStorage remembers the viewer's preference per
   report. Spacing/direction/ranking stay config-only.
6. A/B harness (dev only): the Vite dev app honors a `?layout=<method>`
   query override (never in the built bundle's persisted state), plus a
   small script (scripts/ or package.json task) that captures one
   screenshot per registered method of the acme fixture into
   plans/arch/wip/layout-ab/. Do NOT change the default method — the
   architect picks it from these captures afterwards.

Tests (only these):
- Shared invariant suite parameterized over every registered engine ×
  fixture graphs (star hub, chain, dense mesh, nested boundaries,
  11-child expansion): no node overlaps, children inside their boundary
  with padding, deterministic output across two runs, expansion keeps
  the anchor within the existing drift budget.
- Per-engine: layered honors `ranking` lane order with inference
  fallback; radial keeps hub centrality (existing assertions may move,
  not weaken).
- Python: `layout:` YAML round-trip, Excel Settings round-trip,
  payload passthrough, and the two located WARN findings (mirror the
  theme test shapes).
- Viewer: dropdown hidden when user_choice is false/absent; hash +
  localStorage restore honors the priority query > hash > stored >
  config.

Verify: cd frontend/arch-report && npm run build && npm test; uv run
pytest tests/unit/tools -k arch; just lint; just build-arch-report;
regenerate plans/arch/wip/acme-report.html (same command as P13).
Rule-9 dev-app pass at 1440x900: acme with no layout block renders
identically to today (spot-check the cold radial star + one expansion,
console clean); with user_choice on, switch each method live and
capture the layout-ab screenshot set. Report actual command output.
Budget: 2,000 source lines. STOP and ask per rule 1 if the layered
interior packing conflicts with the P12 anchor-stability contract
rather than improvising.
```

## chunk-15 — Edge-label collision + collapse affordance + Detail-dropdown removal (READY, authored 2026-08-30; p27 added same day)

```text
[standard rules incl. rule 9]

Context: two open canvas defects block the Phase 1 exit gate — issues
p14-ui-edge-labels-overlap and p16-ui-collapse-affordance — plus the
decided issue p27-ui-detail-dropdown (user decision 2026-08-30:
remove). READ ALL THREE issue files in plans/arch/arch-v3/issues/ plus
their v3-*.png evidence screenshots. The normative contracts are in
report.md: "At-rest edge labels" -> "Collision invariant (chunk-15)" +
"Orphan suppression", "Map contract — Interaction" ->
"Collapse-control placement (chunk-15)", and the Map contract's
"Detail dropdown: REMOVED" bullet. Frontend
only (frontend/arch-report/): no Python, no payload changes, no layout
engine changes (layout.ts engines are off-surface — this is
presentation-pass work over the rendered frame). Budget: 700 changed
source lines (additions + deletions; tests and the generated bundle
excluded).

Task:
1. Label collision pass per report.md: one pass over the current
   frame's rendered rects — cards at actual rendered size (including
   the selected/expanded card), boundary headers, and other pills —
   covering at-rest AND selection-/hover-revealed pills together.
   Resolution: nudge along the spline (±20% arc length), then hide;
   never stack or clip. A single direct hover/selection reveal is
   exempt and renders above everything. Re-run the pass on zoom-band,
   selection, and expansion changes. Orphan suppression: a pill renders
   only when at least one endpoint of its spline is in or near the
   viewport.
2. Collapse control per report.md: rendered inline with the boundary's
   own title (immediately after the name + kind pill group, inside the
   header chrome), collapse glyph (chevron/minus — never ×), no
   floating/repositioning toward child cards at any zoom, `aria-label`
   "Collapse <name>". Keep the existing collapse semantics and Escape
   order untouched.
3. Remove the Detail dropdown per the Map contract bullet: delete the
   View-dock control, its "Custom" preset-detection display, and any
   code reachable only from them. KEEP the preset expansion sets as
   the internal mapping for legacy `level=` fragment links (a legacy
   link still restores the equivalent bulk expansion in one history
   push) and keep the `expand` fragment machinery untouched. The freed
   slot hosts the chunk-14 Layout method control when configured;
   update or remove ONLY the existing tests that exercise the dropdown
   UI itself (preset-mapping tests stay, recut against the legacy-link
   path if they went through the control).

Tests (exactly these five, plus keeping every existing test green):
1. Collision: a synthetic scene where selecting a hub reveals pills
   whose midpoints collide with the hub card -> every rendered pill
   rect is disjoint from all card rects and all other pill rects, and
   the overflow pills are hidden (not stacked).
2. Hover reveal: hovering a spline whose pill is hidden renders exactly
   that one pill.
3. Orphan suppression: a spline with both endpoints far outside the
   viewport renders no pill; moving one endpoint into the viewport
   restores it.
4. Boundary header: the collapse control renders inside the header row
   adjacent to the title (DOM order + geometry assertion) with the
   prescribed aria-label, and its glyph is not "×".
5. Detail removal: the View dock renders no Detail control; a legacy
   `level=` fragment link still restores the equivalent bulk expansion
   set in one history entry.

Rule-9 verification at 1440x900 (dev app AND regenerated file://
report): reproduce both issue screenshots' setups — restore the
Container-level expansion via a legacy `level=` link (the dropdown is
gone) or manual card expansion, select the hub card, zoom close — and
confirm zero pill-card and zero pill-pill overlaps at every step;
confirm the outer System boundary's collapse control sits beside its
own title and nothing collapse-like renders adjacent to the focused
child card; confirm View shows no Detail control and the dock layout
has no gap; console clean throughout. Capture replacement evidence to
/tmp/arch-v3-evidence/test-results/chunk-15/. Rebuild the bundle and regenerate
plans/arch/wip/acme-report.html via the CLI.

Definition of done: rules 5–8 (lint, arch pytest, budget, log entry) +
rule 9 above; frontend vitest suite green; `just build-arch-report`
clean. STOP after the log entry — the architect reviews at the gate.
```
