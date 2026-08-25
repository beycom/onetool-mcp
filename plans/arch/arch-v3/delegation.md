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

| Prompt | Chunk | Status | Run after |
| --- | --- | --- | --- |
| D1–D7 | Phases 0–3 build chunks | DONE (2026-08-23/24) | — |
| D9a, D9b | Phase 3R wave 1: schema/model + Excel/payload rework | DONE, gate PASSED 2026-08-25 | — |
| D10a, D10b | Phase 3R wave 2: report UI | DONE, commit c37e3d05 | — |
| D13a | Phase 3P pass 1: visual foundation | READY (spec in report.md; budget 700 proposed) | now |
| D13b–D13d | Phase 3P passes 2–4 | GATED on per-pass specs | previous pass gate |
| D12a | Phase 3S: sequence parser + payload | ISSUED, ON HOLD | Phase 3P exit gate |
| D12b | Phase 3S: sequence renderer + SEQ-* | GATED on layout vectors + acme flow docs | Phase 3P exit gate |
| D11 | wave 3: view-mode capabilities | GATED on designs | Phase 3P exit gate |
| D8 | Phase 4: SQLite adapter, SVG export | GATED | Phase 3P exit gate |

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

## D8 — GATED (template to be issued at phase start)

- **D8 (phase 4):** SQLite adapter per adapters.md and client-side SVG/
  draw.io download; prompts written after the Phase 3P exit gate.

## D9–D11 — Phase 3R gate rework (GATED; issued per wave)

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
- **D11 (wave 3 — view-mode capabilities):** `p3-report-definitions`
  (view-mode flow; `views:` YAML export starting point) and
  `p3-ui-guided-view` (resolves MAP/PATH/LENS). Gated on the Phase 3P
  exit gate plus architect designs for both. `p3-edit-save-back` and
  `p3-ui-manual-positions` are NOT delegated — edit mode is deferred and
  gets its own prompts when the local-server write path is designed.

## D12 — Phase 3S: sequence diagrams (GATED; issued per chunk)

Design doc: sequence.md (2026-08-25). Prompts are issued when the
architect artifacts exist; executors work from sequence.md + the prompt.

- **D12a (Python):** ISSUED 2026-08-25 (below) — flow-doc parser,
  validation findings, `sequences` payload section, CLI +
  `arch.validate`/`arch.generate` wiring. The parser-vector fixture
  (`tests/unit/tools/fixtures/arch/sequence/`) is committed and is the
  control mechanism. ON HOLD until the Phase 3P exit gate (user
  directive 2026-08-25); no frontend files.
- **D12b (frontend):** `seqlayout.ts` + SVG layer + entity-box header row
  + the SEQ-* interaction contract. Gated on the architect's layout
  vectors and the acme flow docs; runs after the Phase 3P exit gate,
  may run parallel with D11/D8.

## D9a — Phase 3R wave 1a: model/resolver/validation rework (DONE 2026-08-25, committed)

Wave-1a schema/model/resolver/validation rework (C4 naming, auto ids, inclusive intervals, provider/consumer). Full prompt in git history.

## D9b — Phase 3R wave 1b: Excel + payload + projection rework (DONE 2026-08-25, wave-1 gate PASSED)

Wave-1b ten-sheet Excel + payload/projection rework, blank-id import. Full prompt in git history.

## D10a — Phase 3R wave 2a: chrome, panels, tables (DONE 2026-08-25, commit c37e3d05)

Wave-2a chrome, panels, tables. Full prompt in git history.

## D10b — Phase 3R wave 2b: canvas semantics + visuals (DONE 2026-08-25, commit c37e3d05)

Wave-2b canvas semantics + visuals; architect gate fixes (drill root carve-out, cluster button styling, layout-key staleness guard) rode the same commit. Full prompt in git history.

## D13 — Phase 3P: UI polish passes (GATED; issued per pass)

Four presentation passes D13a–D13d over the wave-2 report UI (plan.md
"Phase 3P"). Each is GATED until its architect spec lands in report.md;
prompts are issued one pass at a time and each pass gates before the
next is issued. No new features ride along.

## D13a — Phase 3P pass 1: visual foundation (READY)

```text
[standard rules + UI rule 9]

Prereq: commit c37e3d05 (wave-2 UI + gate fixes) is the baseline. The
authoritative contract is plans/arch/arch-v3/report.md — READ IN FULL
the section "Polish contract — pass 1: visual foundation (D13a)". Do
NOT read issue or research files. This is a PURE PRESENTATION pass:
projection.ts, layout.ts, view.ts, types.ts, zoom.ts and all behavior,
DOM semantics, aria labels, data-testids, and fragment keys are
untouched. Expected surface: styles.css (dominant), a new icons
component file, and minimal App.tsx/GridPanel.tsx edits where markup
must host the icons, footer wording, and the tables-bar affordance.

Budget: 700 changed source lines (excluding tests). Python changes:
none. No new npm dependencies (icons are local inline-SVG components).

Scope — implement the contract section exactly:
1. Design tokens on :root (fonts, type scale, spacing, radius,
   elevation, control height); dark theme redefines colors only.
2. Mono-for-data / sans-for-UI typography split; eliminate sub-11px
   chrome text and the uppercase mono micro-labels.
3. One shared card recipe for clusters, zoom rail, legend, minimap,
   scope menu, and panel chrome.
4. Inline-SVG icon set for the chrome controls listed in the contract
   (node drill magnifier and kind icons are OUT — pass 3).
5. Dark and light contrast audit per the contract targets.
6. Footer humanised per the contract; rendered-node-ids visually
   hidden but kept in the DOM with its testid.
7. Collapsed tables panel as a docked bar.

Tests: none new. `npm test` must pass UNCHANGED — if a test needs
editing, you have changed behavior; stop and report instead.

Finish: `just build-arch-report`, regenerate the acme report via the
CLI, verify per rule 9 from file://: both themes, full width and
500px, clean console, zero external requests; capture before/after
screenshots of the default systems view (light + dark) for the gate.
Definition of done: rules 5-8 (report `npm test` output; pytest run
unchanged by this chunk), then STOP — D13b is a separate prompt.
```

## D12a — Phase 3S: sequence parser + payload (issued 2026-08-25, ON HOLD until the Phase 3P exit gate)

```text
[standard rules]

Context: v3 gains sequence diagrams. plans/arch/arch-v3/sequence.md is the
owner doc — READ IT IN FULL first (source-doc format, DSL, compilation,
payload shape, finding codes). This chunk is the Python half only: parse
and validate Markdown flow docs, compile the `sequences` payload section,
and wire discovery into validate/generate. NO frontend files, no bundle
rebuild (the payload of every existing fixture/report is unchanged — see
"omit when empty" below).

Control mechanism: tests/unit/tools/fixtures/arch/sequence/ — architect-
authored parser vectors. READ ITS README FIRST; it pins the driver
contract, finding codes, anchor rules, and every decision the vectors
encode (pairing rule, marker placement, drop-defaults, ordering).
Vectors are READ-ONLY: one that looks wrong is a rule-1 stop, never an
edit. Budget: 500 changed source lines (excluding tests and fixtures).

Task:
1. New module src/otdev/tools/_arch/v3/sequence.py: parse one flow doc
   (frontmatter, doc-level participant lines, `##` scenario headings with
   prose, ```seq fences) and compile the doc set against an Architecture
   per sequence.md "DSL" + "Compilation". Findings use the existing
   Finding dataclass (file = the flow doc path, line/column per the
   README anchor rules; columns are your choice but must be >= 1).
2. Discovery: <model-dir>/sequences/*.md beside the model YAML, sorted
   filename order. arch.validate / CLI validate include flow-doc
   findings; any flow-doc error fails generate atomically, exactly like
   model errors.
3. Payload: build_payload gains the top-level `sequences` key (after the
   entity collections), sorted by flow id, compiled per sequence.md —
   intervals reuse the existing segment machinery (clips always []).
   OMIT the key when there are no flow docs: existing checked-in
   payloads (projection fixture, acme dev payload) and the generated
   report must stay byte-identical — that is what keeps this chunk off
   D10's surface.
4. Facade/CLI: no new subcommands; validate/generate/payload pick the
   flows up via the shared load path in api.py.

Tests (exactly these):
1. tests/unit/tools/test_arch_v3_sequence.py — the vector driver per the
   fixture README: for each flows/*.md compare (severity, code, line)
   triples sorted by (line, code) and deep-compare the compiled entry
   against expected.json ("sequence": null = doc must produce >= 1 error
   and no compiled entry); plus the crossdoc/ set producing exactly the
   listed duplicate_id finding.
2. large_scenario thresholds: synthetic docs with 31 participants (warn)
   / 30 (silent), and 301 items in one scenario (warn) / 300 (silent).
3. Discovery + atomicity: a temp model dir whose sequences/ holds one
   good and one erroring doc -> validate reports both docs' findings,
   generate fails atomically (no output file); with the erroring doc
   removed -> payload contains `sequences` sorted by flow id; and a
   model dir with no sequences/ -> payload has NO `sequences` key.

Definition of done: rules 5–8, plus: all existing arch tests stay green,
`uv run python -m otdev.tools._arch.v3 validate
tests/unit/tools/fixtures/arch/sequence/model.yaml` still reports 0
errors, and regenerating the checked-in projection-fixture payload and
acme dev payload via the CLI is byte-identical. STOP after the log entry
— the architect reviews at the gate.
```
