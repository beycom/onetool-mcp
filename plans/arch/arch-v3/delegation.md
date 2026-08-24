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
| D1 | Phase 0: skeleton + fixture source dump | READY | now |
| D2 | Phase 1a: models + YAML I/O | READY | D1 |
| D3 | Phase 1b: resolver (filter/clip/diff/advance) | READY (spec committed) | D2 |
| D4 | Phase 1c: validation + pack tools | READY | D3 |
| D5 | Phase 2: Excel adapter | READY | phase-1 gate |
| D6 | Phase 3a: report bundle scaffold + POC port | READY (payload spec committed) | phase-2 gate |
| D7 | Phase 3b: report features | READY (projection spec committed) | D6 |
| D8 | Phase 4: SQLite adapter, SVG export | GATED on phase-3 re-gate | phase 3R |
| D9a | Phase 3R wave 1a: model/resolver/validation rework + fixture | READY (schema.md updated 2026-08-24) | now |
| D9b | Phase 3R wave 1b: Excel + payload + projection rework | READY | D9a |
| D10a | Phase 3R wave 2a: chrome, panels, tables | READY (report.md "Wave-2 UI contract" committed 2026-08-24) | wave-1 (D9) gate |
| D10b | Phase 3R wave 2b: canvas semantics + visuals | READY | D10a |
| D11 | Phase 3R wave 3: view-mode capabilities | GATED on phase-3 re-gate + designs | phase-3 re-gate |

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
2. The v2 worktree at
   '/Users/gavin/01-work-thor/projects/group-hobby/onetool-mcp-worktrees/[STUCK]arch-v2'
   is a READ-ONLY donor. You may copy and adapt code from it into v3 files;
   never import from it and never modify it.
3. Do not touch src/otdev/tools/_arch/ (the v1 modules) or src/otdev/tools/arch.py
   unless your task explicitly says so. Do not add dependencies.
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

## D1 — Phase 0: skeleton + fixture source dump (READY)

```text
[standard rules]

Task A — package skeleton:
Create src/otdev/tools/_arch/v3/__init__.py (empty package). Nothing else in
it yet.

Task B — dump the fixture source workbook:
Read plans/arch/wip/acme-arch-v2.xlsx (openpyxl, read-only). For every sheet,
write plans/arch/arch-v3/fixture-src/<sheet-name>.csv containing exactly the
cell values (no formatting, empty trailing rows/columns trimmed). Add
plans/arch/arch-v3/fixture-src/README.md with one line: source file, dump
date, sheet list with row counts. This dump is input for a human-designed v3
fixture; do NOT attempt any v2→v3 conversion or interpretation.

Definition of done: package imports; every sheet dumped; README present;
rules 5–8.
```

## D2 — Phase 1a: models + YAML I/O (READY)

```text
[standard rules]

Implement the v3 data model and YAML layer per plans/arch/arch-v3/schema.md.
Entity semantics and ID/text rules are inherited from
plans/arch/arch-v2/schema.md (read it). Budget: 700 source lines total.

Files to create:
- src/otdev/tools/_arch/v3/model.py — Pydantic models: Architecture root
  (schema_version=3, milestones, optional timelines, six entity collections:
  systems, subsystems, components, users, interfaces, relationships),
  Milestone, Timeline, and the six row kinds, each with optional from_/until
  milestone-reference fields (YAML keys "from"/"until").
- src/otdev/tools/_arch/v3/yamlio.py — load_architecture(path) and
  dump_architecture(arch, path) with deterministic output.
- src/otdev/tools/_arch/v3/__main__.py — minimal argparse CLI with one
  subcommand for now: `check <file.yaml>` = load, report errors with
  locations, exit 0/1; `--write-back` flag re-dumps deterministically.
  (~40 lines; later tasks add subcommands. Run as
  `uv run python -m otdev.tools._arch.v3 check …`.)
- tests/unit/tools/test_arch_v3_model.py, test_arch_v3_yamlio.py.

Model-layer rules to enforce (field-level only — collection-level validation
such as id uniqueness, reference resolution, and interval ordering is a LATER
task; do not implement it here):
- IDs: ASCII [A-Za-z0-9._-], nonblank. All strings trimmed, nonblank; no
  YAML null anywhere; unknown fields are errors (extra="forbid").
- properties: flat mapping, values string or list-of-strings only.
- tags: list of strings. Common fields per arch-v2/schema.md: id, name
  ("action" for Relationship), description, tags, properties. Interface adds
  provider, consumer, call_direction, data_flow; Subsystem adds system;
  Component adds subsystem; Relationship adds source, target.
- Rows sharing an id within a collection are ALLOWED at this layer (they are
  revisions; grouping logic comes later).
- YAML loading: reject anchors, aliases, and merge keys; carry line/column
  positions through to error messages (harvest the technique from the v2
  donor's load.py if useful).

Deterministic dump contract:
- Root key order: schema_version, milestones, timelines (omit if none),
  systems, subsystems, components, users, interfaces, relationships (empty
  collections dump as []).
- Row key order: id, name/action, kind-specific reference fields (system /
  subsystem / provider / consumer / source / target), call_direction,
  data_flow, from, until, description, tags, properties. Absent optional
  fields are omitted entirely.
- Block style, 2-space indent, no anchors/aliases. Adapt the deterministic-
  writer patterns from the v2 donor's write.py.

Tests (one file, tests/unit/tools/test_arch_v3_yamlio.py, minimal): the full
canonical example in schema.md loads; semantic round-trip holds
(load(dump(load(x))) == load(x)) and dump is idempotent; ONE parametrized
rejection test covering: unknown field, bad ID, null value, anchor/merge-key
(assert rejection only — no location/message assertions; breadth is
backfilled later).

Definition of done: all above tests green; rules 5–8.
```

## D3 — Phase 1b: resolver (GATED)

Architect must first commit:
- `src/otdev/tools/_arch/v3/resolver.py` containing dataclass/function
  **signatures + docstrings only** (state selector, revision grouping,
  liveness filter, clipping with `clipped_by` consequences, diff, advance);
- `tests/unit/tools/test_arch_v3_resolver.py` — the authoritative semantics
  suite (interval edge cases, gaps, off-timeline milestones, clipping chains,
  revision diffs, advance rewrites).

Prompt template:

```text
[standard rules]

Implement the function bodies in src/otdev/tools/_arch/v3/resolver.py until
tests/unit/tools/test_arch_v3_resolver.py passes in full. The test file is
the specification and is READ-ONLY — if you believe a test is wrong or two
tests conflict, STOP and report per rule 1; never edit a test. Semantics
reference: the Intervals, Revisions, Resolution, Diff, and "Advancing the
baseline" sections of plans/arch/arch-v3/schema.md. Do not change any
signature. Budget: 600 source lines in resolver.py.
```

## D4 — Phase 1c: validation + pack tools (READY once D3 lands)

```text
[standard rules]

Prereq: model.py, yamlio.py, resolver.py exist and their tests pass.
Budget: 500 source lines total for the two new files + facade.

Task A — src/otdev/tools/_arch/v3/validate.py:
Implement validate(arch) -> list of findings per the "Validation" section of
plans/arch/arch-v3/schema.md. Errors: unique ids per collection (revision
rows sharing an id excepted per the Revisions rules), resolvable parents /
endpoints / milestone references (identity-level: any revision counts),
required fields, interval ordering (from != until; from before until when
both on one timeline), timeline rules (>=1 milestone, resolvable, no repeats).
Warnings: identical adjacent revisions, authored intervals exceeding what
clipping allows, milestones referenced by no row, entities live on no
timeline. Every finding carries file/line/path location (positions from
yamlio) and a stable code string.

Task B — dev CLI (the primary iteration surface):
Extend src/otdev/tools/_arch/v3/__main__.py with subcommands validate,
resolve (timeline/at selector per schema.md "State selection boundary":
current|<milestone>|end), diff (two selectors), advance (--through
<milestone>, rewrites the file via yamlio), and init (minimal valid starter
YAML). Human-readable output to stdout, --json flag for machine output,
exit 0/1. All logic lives in the core modules — the CLI only parses args
and prints.

Task C — pack tools (thin facade):
Rewrite src/otdev/tools/arch.py as the v3 facade (this task MAY touch it):
tools arch.init, arch.validate, arch.resolve, arch.diff, arch.advance —
each a thin wrapper over the SAME core functions the CLI calls (argument
passing and return shaping only; zero logic in the facade). Follow the v1
arch.py ONLY for pack/tool declaration conventions (pack name, docstring
style, return shapes) — not for behavior. Do NOT delete the v1 _arch
modules yet; that is a separate reviewed step.

Tests (minimal — breadth backfilled later): one parametrized test that each
finding code fires on a minimal bad input (assert the code only, NOT
locations or messages), and a facade smoke test driving init -> validate ->
resolve -> diff -> advance on a temp file. Implement locations fully in the
code regardless — only their tests are deferred.

Definition of done: rules 5–8, plus line counts reported per file.
```

## D5 — Phase 2: Excel adapter (READY once phase-1 gate passes)

```text
[standard rules]

Implement the v3 Excel adapter per plans/arch/arch-v3/adapters.md (read it in
full; inherited conventions are in plans/arch/arch-v2/file-formats.md).
Budget: 900 source lines.

Files: src/otdev/tools/_arch/v3/excel.py (read_workbook(path) -> Architecture,
write_workbook(arch, path), generate_template(path)), CLI subcommands
import-excel / export / template in __main__.py, plus thin tool wiring in
arch.py: arch.import_excel and arch.export, with import_excel also reachable
as arch.convert per delivery.md. As everywhere: logic in the core, CLI and
facade both call the same functions.

Contract highlights (adapters.md is authoritative):
- 9 sheets as listed; header matching is case/space/hyphen/underscore-
  insensitive; reserved columns always written; ANY extra column becomes a
  property; [a;b] list cells; scalar coercion per v2 rules.
- Timelines sheet: (timeline, milestone) rows, contiguous blocks, order =
  milestone order; empty sheet = implicit timeline.
- Revision rows are ordinary rows sharing an id.
- Generated template: dropdown validation for enums and milestone-reference
  columns; revision rows visually banded.
- Errors: sheet/row/column/field locations, all locations for duplicates and
  broken refs, all independent errors collected in one run; failed import
  changes nothing (atomic replace of the YAML only on success).
- Harvest cell parsing / header normalization from the v2 donor's
  normalize.py and load.py, and workbook writing from exporter.py.

Tests (tests/unit/tools/test_arch_v3_excel.py — these two only, breadth
backfilled later): round-trip MODEL equality (not presentation) on the acme
fixture at tests/**/fixtures/acme.yaml, and atomicity (import of a broken
workbook leaves the YAML byte-identical). Implement header normalization,
extra-column properties, list cells, and error locations fully in the code —
only their tests are deferred.

Definition of done: rules 5–8. Then STOP — the phase-2 gate (a human editing
the workbook and inspecting the diff) is run by the architect.
```

## D6 — Phase 3a: report scaffold + payload pipeline (READY)

```text
[standard rules]

Prereq: phases 1–2 are committed. The payload shape is defined in
plans/arch/arch-v3/report.md, section "Payload contract (v1)" — READ IT IN
FULL; it is the authoritative contract for every task below. Second donor:
plans/arch/react-flow-poc/ is READ-ONLY like the v2 worktree — copy and
adapt its source; never import from it or modify it.

Budget: 400 Python source lines; 2,500 TS/TSX source lines (phase 3 has
5,000 TS/TSX total and D7 needs the remainder). npm dependencies inside
frontend/arch-report/ are allowed and expected (React, React Flow v12,
elkjs, AG Grid Community, vite + a single-file plugin); the PYTHON
dependency rule from the standard rules is unchanged.

Task A — payload compiler (src/otdev/tools/_arch/v3/payload.py):
build_payload(arch, source_name) -> dict exactly per the contract. Use the
resolver (resolve, timeline_view, group_revisions, governing_row) in a
per-position sweep as the contract's normative algorithm describes; do NOT
reimplement interval or clipping semantics.

Task B — report generation (src/otdev/tools/_arch/v3/report.py):
generate_report(yaml_path, html_path): load, refuse on validation errors
(mirror export_workbook), build the payload, inject into the template at
src/otdev/tools/_arch/v3/_bundle/report-template.html per the contract's
injection rules (token replacement, </ escaping, atomic temp+replace —
mirror write_workbook). CLI subcommands in __main__.py: `generate <yaml>
<html>` and `payload <yaml> [out.json]` (pretty JSON, stdout when no
output operand). Facade: arch.generate with input_path/output_path in
arch.py (this task MAY touch arch.py). Logic in the core; CLI and facade
call the same functions.

Task C — report bundle scaffold (frontend/arch-report/):
Vite + React + TypeScript app building to ONE self-contained HTML file at
the template path above, with the payload placeholder <script> element
passing through the build untouched. The elkjs worker must be inlined —
verify the built output is a single file with zero external requests.
Port from the POC: Archify styling (grid, tokens, node/edge styles),
custom nodes/edges, passport panel shell, minimap, light/dark. Behavior
for THIS chunk: parse the payload, render the current state (position 0,
first timeline) at systems level with union-graph elkjs layout, node
selection opening the passport panel. Time slider, diff overlay, scoping,
level roll-up, and tables are D7 — leave a single clean seam (one
projectState(payload, view) call site), do not implement them. Dev loop:
`npm run dev` against a checked-in fixture payload generated from the acme
fixture via the `payload` CLI; document dev/build commands in
frontend/arch-report/README.md. Add a `just build-arch-report` recipe;
the built template gets committed (by the architect) so wheel builds
never need Node.

Tests (these only — tests/unit/tools/test_arch_v3_payload.py):
1. Acme payload invariants: fixed top-level key order; every row's live and
   clip segments sorted, disjoint, within the timeline domain; segment
   union disjoint across each revision group; at least one clip segment
   exists and every `by` names a known entity id; build twice -> equal.
2. Generate smoke: output contains no placeholder token; the arch-payload
   script element's content parses back to the payload; a second generate
   run is byte-identical.
Frontend has no test harness this chunk: report `npm run build` output and
a manual file:// open of the generated acme report (nodes render, panel
opens) instead.

Definition of done: rules 5–8, both tests green, the manual file:// check
reported. STOP after that — D7 is a separate prompt.
```

## D7 — Phase 3b: report features (READY, run after D6)

```text
[standard rules + UI rule 9]

Prereq: D6 is committed (frontend/arch-report/ scaffold renders the current
state). Authoritative inputs, both READ-ONLY beyond what this prompt says:
plans/arch/arch-v3/report.md sections "Payload contract (v1)" and "Client
projection contract (v1)", and the vector fixtures in
tests/unit/tools/fixtures/arch/projection/ (model.yaml, payload.json,
vectors.json — NEVER edit these; a vector that looks wrong is a
stop-and-ask per rule 1).

Budget: 2,500 TS/TSX source lines (the remainder of phase 3's 5,000).
Python changes: none expected; propose per rule 1 if you believe one is
needed. npm devDependencies for testing (vitest) are allowed.

Task A — projection layer (pure TS, no React imports):
Implement the contract's functions (liveAt/clipAt, stateAt, diffStates,
scopeAt, rollUp, unionGraph) behind the projectState seam D6 left. Wire a
vitest suite that loads payload.json + vectors.json and drives every vector
case through the real functions (`npm test`). Also regenerate payload.json
from model.yaml with the CLI `payload` subcommand and compare: identical
ids and interval segments are REQUIRED (serialization cosmetics may
differ); on any semantic difference STOP and report — do not regenerate
the committed fixture.

Task B — time + diff UI:
Milestone stepper/slider over the selected timeline (stops: Current then
each milestone; slider index == payload position), timeline picker when
several timelines exist, diff overlay toggle (compare off / vs current /
vs position) marking added (accent + badge), removed (ghosted from the
compared state), and changed (badge + field-level popover from
diffStates), colors always paired with icon/line-style. Progressive
disclosure: zero milestones on the selected timeline -> no time or compare
controls at all. Layout: elkjs once on unionGraph, positions fixed while
scrubbing; "re-fit this state" is an explicit button.

Task C — scope, level, tables, views:
Scope control (system multi-select + hops) and level control
(systems/subsystems/components) driving scopeAt/rollUp; boundary stubs
rendered collapsed. AG Grid tables (entities, interfaces, milestones,
diff) reading the SAME projected arrays as the canvas. URL-fragment
view encoding + copy-link (scope, level, time, compare, aspect, mode,
theme — per the Views table in report.md); no coordinates ever persisted.
Verify the built report works offline from file:// (no network requests).

Tests (these only): the vitest vector suite from Task A, plus ONE
interaction smoke test (any DOM-level harness D6 established or plain
vitest + jsdom): scrubbing the acme report's slider changes the rendered
node set. No extra coverage.

After the TS work: run `just build-arch-report`, regenerate the acme report
via the CLI, and verify from file:// per rule 9 (Playwright through __ot,
wip/notes/test-ui.md): scrub the timeline, toggle the diff overlay, switch
level and scope, open a copy-link URL, and confirm a clean console and zero
external network requests. Report what you saw. Definition of done: rules 5–8 (rule 5's pytest run is unchanged by
this chunk — also report `npm test` output), then STOP — the phase-3 gate
(architect + user reading the acme story) follows.
```

## D8 — GATED (template to be issued at phase start)

- **D8 (phase 4):** SQLite adapter per adapters.md and client-side SVG/
  draw.io download; prompts written when the phase-3 re-gate passes
  (rework waves D9/D10 come first).

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
  `p3-ui-guided-view` (resolves MAP/PATH/LENS). Gated on the phase-3
  re-gate plus architect designs for both. `p3-edit-save-back` and
  `p3-ui-manual-positions` are NOT delegated — edit mode is deferred and
  gets its own prompts when the local-server write path is designed.

## D9a — Phase 3R wave 1a: model/resolver/validation rework (READY)

Run D9a and D9b back to back; the wave-1 gate reviews both together.

```text
[standard rules]

Context: the phase-3 gate produced a schema rework. plans/arch/arch-v3/
schema.md has been rewritten (C4 entity kinds, id scheme, inclusive
start_in/end_in intervals over a base state, Provider/Consumer directions)
— RE-READ IT IN FULL first; it supersedes everything you remember about the
v3 schema. This chunk reworks the Python model layer to the new contract.
Budget: 700 changed source lines (excluding tests and fixtures). The sweep
is clean: NO back-compat aliases, no deprecation shims — the old names must
not survive anywhere in v3 code, tests, or fixtures.

Task A — renames (mechanical; semantics unchanged unless listed in Task B):
- Collections/kinds: subsystems -> containers (Subsystem -> Container);
  NEW collection code (kind Code). Collection order everywhere: systems,
  containers, components, code, users, interfaces, relationships.
- Parent fields: Container.parent (was Subsystem.system), Component.container
  (was Component.subsystem), NEW Code.component.
- Intervals: from/until -> start_in/end_in per schema.md "Intervals". This
  is a semantic flip, not a rename: both bounds are now INCLUSIVE, and the
  reserved reference `base` names position 0. Liveness becomes
  pos(start_in) <= p <= pos(end_in); the resolver's internal position
  convention is 0 = base (drop any -1/current convention).
- Interface.data_flow -> data_flow_direction.
- State selectors: current -> base (grammar: base | <milestone id> | end)
  across resolver, CLI, and facade.
- YAML dump row key order: id, name/action, parent/container/component/
  provider/consumer/source/target, call_direction, data_flow_direction,
  start_in, end_in, description, tags, properties.

Task B — behavior changes (schema.md section in parentheses):
- Direction enums ("Provider / Consumer interface model"): call_direction
  Literal[consumer_to_provider, provider_to_consumer] default
  consumer_to_provider; data_flow_direction Literal[provider_to_consumer,
  consumer_to_provider, bidirectional] default provider_to_consumer. The
  value "unspecified" is GONE. Deterministic dump omits a field equal to
  its default.
- Container.parent resolves to a System OR a Container ("Entity kinds"):
  new validation errors for ambiguous parent (id present in both
  collections) and containment cycles. Resolver parent-chain clipping
  generalizes to arbitrary container nesting and Code
  (code -> component -> container -> ... -> system).
- Intervals ("Intervals"): start_in == end_in is now LEGAL (single-position
  row); error only when start_in comes after end_in with both milestones on
  one timeline. start_in: base is legal and equivalent to absent. end_in:
  base means present only in the base state. Milestone id "base" is a new
  validation error (reserved). Revision rule: at most one row per id may
  start in the base (absent or base start_in).
- advance ("Advancing the baseline"): delete rows whose end_in is base or
  precedes `through`; rewrite end_in: through -> end_in: base; the rest as
  documented.
- New module src/otdev/tools/_arch/v3/ids.py ("Identifiers"): next_id(kind,
  existing_ids) and assign_missing_ids(arch) -> {collection: [(row_index,
  assigned_id)]} implementing the per-kind prefix scheme (s-, c-, cp-, cd-,
  u-, i-, r-; max+1 over ids matching <prefix>-<digits>; zero-pad 4, wider
  when exhausted; gaps never renumbered). Used by `init` (scheme-form ids)
  and by D9b's Excel import. Slug ids stay legal — no new id validation.

Task C — fixture and tests:
- Regenerate tests/unit/tools/fixtures/arch/acme.yaml mechanically:
  collection/field renames as above; every `until: m` becomes
  `end_in: <the milestone immediately before m in catalog order>`, or
  `end_in: base` when m is the first milestone; `from: m` becomes
  `start_in: m` (same milestone — the from side does not shift). No other
  content changes.
- Existing test files (model, yamlio, resolver, validate, facade): apply
  the same renames and boundary conversion to inputs and expectations.
  The resolver suite is the authoritative spec: renames and interval
  conversion ONLY — do not weaken, delete, or merge any assertion; report
  per-file test counts before and after (they must not drop).
- NEW tests, exactly these: (1) nested-container clip chain — a system
  end_in clips a container, a nested container, a component, and a code
  row plus an interface into the tree, with correct clipped_by; (2) code
  kind round-trips through YAML; (3) validation: containment cycle,
  ambiguous parent, reserved milestone id base — one case each; (4)
  start_in == end_in row live at exactly that position; (5) end_in: base
  row live at position 0 only; (6) ids.py: assignment into a gapped
  sequence yields max+1, padding, per-kind independence; (7) direction
  fields: defaults omitted on dump and applied on load; (8) advance:
  end_in == through rewrites to base, earlier end_in rows deleted.

Expected breakage: tests/unit/tools/test_arch_v3_payload.py and
test_arch_v3_excel.py will FAIL after this chunk (payload.py and excel.py
still speak the old schema) — that is D9b's job. Rule 5 applies to
everything else; still run the full `-k arch` suite and report which tests
fail and why. Definition of done: rules 5–8 with that exception, fixture
regenerated, per-file test counts reported.
```

## D9b — Phase 3R wave 1b: Excel + payload + projection rework (READY, run after D9a)

```text
[standard rules + UI rule 9]

Prereq: D9a is complete (model/resolver/validation on the new schema; acme
fixture regenerated). Re-read plans/arch/arch-v3/schema.md, adapters.md,
and report.md sections "Payload contract (v1)" and "Client projection
contract (v1)" IN FULL — all three were reworked 2026-08-24 and supersede
the code. Budget: 600 changed source lines total (Python + TS/TSX,
excluding tests and generated fixtures).

Task A — Excel adapter (src/otdev/tools/_arch/v3/excel.py per adapters.md):
- Ten sheets: Architecture, Milestones, Timelines, Systems, Containers
  (+ parent), Components (+ container), Code (+ component), Users,
  Interfaces (+ provider, consumer, call_direction, data_flow_direction),
  Relationships. Interval columns are start_in/end_in everywhere.
- Blank id cells: auto-assign on import via ids.assign_missing_ids —
  deterministic in sheet row order; assignments appear in the import
  result/report. A blank-id row is always a new entity.
- Template dropdowns: direction enums per the new literals; end_in
  dropdowns include base.

Task B — payload compiler (src/otdev/tools/_arch/v3/payload.py per the
updated contract): seven collections in schema order; rows serialize
start_in/end_in as authored (milestone id or base); call_direction/
data_flow_direction omitted when equal to their defaults; live and clip
segments are END-INCLUSIVE ([s, e] with e = last live position, null =
unbounded). Positions are unchanged (0 = base). Keep driving the
authoritative resolver — no reimplemented interval semantics.

Task C — projection vector fixtures
(tests/unit/tools/fixtures/arch/projection/): convert mechanically, then
verify. model.yaml: same rename + interval conversion rules as D9a's acme
step. payload.json: regenerate with the CLI `payload` subcommand from the
converted model.yaml. vectors.json: kind names and node keys rename
(subsystems -> containers, new code kind appears in KINDS order); level
names systems/containers/components; positions and expected id sets are
UNCHANGED — if any expected state, diff, scope, or rollup result would
change beyond renaming, STOP and report per rule 1. Update the README
provenance note (one dated line: converted for the wave-1 schema rework).

Task D — frontend (frontend/arch-report/src/): types.ts, payload.ts,
projection.ts, view.ts, App.tsx, GridPanel.tsx: apply the renames; liveAt
becomes end-inclusive per the contract; KINDS and representative walk per
the updated contract (parent chain through nested containers; code -> its
component); level control and URL-fragment level tokens
systems/containers/components; every UI label "Current" for position 0
becomes "Base"; kind labels System/Container/Component/Code. Regenerate
src/fixture-payload.json via the CLI from the acme fixture.

Tests: existing suites updated by rename/conversion only. NEW tests,
exactly these: (1) Excel import assigns scheme ids to blank-id rows,
deterministically, and reports them; (2) Excel round-trip covers a Code row
and a nested container. Frontend: vitest vector suite green against the
converted fixtures; the D7 interaction smoke test still passes.

Finish: `just build-arch-report`, regenerate the acme report via the CLI,
verify per rule 9 from file:// (scrub the timeline — slider now starts at
"Base" — toggle diff overlay, switch level and scope, clean console, zero
external requests). Full `uv run pytest tests/unit/tools -k arch` must now
be green including payload and excel. Definition of done: rules 5–8, npm
test output reported, then STOP — the wave-1 gate (architect) reviews D9a +
D9b together.
```

## D10a — Phase 3R wave 2a: chrome, panels, tables (READY, run after the wave-1 gate)

```text
[standard rules + UI rule 9]

Prereq: the wave-1 gate (D9a + D9b) has passed and is committed. The
authoritative contract is plans/arch/arch-v3/report.md — READ IN FULL the
sections "Wave-2 UI contract (v1)" (your subsections are the ones marked
D10a, plus "Interaction baseline"), "Views", and "Canvas and look". Do NOT
read issue or research files; the contract supersedes them. The v2 donor
worktree remains a READ-ONLY harvest source (its
src/otdev/tools/_arch/v2/frontend grid/ArchitectureGrid.tsx and table
config models are named donors for the tables task).

Budget: 1,400 changed TS/TSX source lines (excluding tests). Python
changes: none expected (propose per rule 1). No new npm runtime
dependencies without a rule-1 proposal; vitest/jsdom devDependencies are
fine.

Scope — implement the D10a subsections of the contract exactly:
1. Chrome and layout: one compact header line; grouped control clusters
   (time strip, projection cluster, bottom-right zoom rail); remove the
   MAP/PATH/LENS mode buttons and the `mode` fragment key (keep `view`
   reserved); no horizontal page overflow down to 500 px, clusters
   collapse into menus.
2. Zoom rail with reading depth: fit / zoom out / percentage + MAP-READ-
   FULL depth label / zoom in / fullscreen toggle. Thresholds (<100 MAP,
   100-174 READ, >=175 FULL) as centralized constants; expose the current
   depth as a CSS class/data attribute on the canvas root (D10b consumes
   it — do not implement node content gating yourself).
3. Plain background per the contract.
4. Docked side panel (Details + Connections tabs, edge member list,
   "Open dependency view" action stub that is present but disabled with
   an accessible reason until D10b lands).
5. Resizable panels: bottom tables panel + side panel drag handles,
   collapse toggles, double-click reset, localStorage persistence
   validated on load. Build the panel behavior as a reusable piece — the
   D10b legend panel will use it.
6. Fullscreen per the contract.
7. Tables at v2 parity per the contract (harvest the v2 donor patterns).
8. Interaction baseline items that touch this scope: Escape dismissal
   order, keyboard zoom, fragment restoration diagnostics, history
   replace-vs-push (the contract lists them).

Tests (exactly these, plus keeping existing suites green):
1. Panel/table layout persistence round-trip (vitest + jsdom
   localStorage): save, reload, restored; a stored layout naming an
   unknown column is rejected and defaults apply.
2. View fragment encode/decode: no `mode` key emitted; no pixel-size or
   coordinate keys ever appear; unknown fragment ids produce the
   diagnostic path, not a crash.
The existing vitest vector suite and the slider interaction smoke test
must stay green (update DOM selectors in the smoke test if the chrome
rework moved elements — do not weaken its assertion).

Finish: `just build-arch-report`, regenerate the acme report via the CLI,
verify per rule 9 from file://: compact header, side panel docks and the
canvas resizes, panel drag-resize + collapse + double-click reset survive
a reload, fullscreen enter/exit (keyboard f / Escape), table quick
filter + multi-sort + column hide/pin persisting across reload, plain
background in both themes, clean console, zero external requests.
Definition of done: rules 5-8 (pytest run unchanged by this chunk — also
report `npm test` output), then STOP — D10b is a separate prompt.
```

## D10b — Phase 3R wave 2b: canvas semantics + visuals (READY, run after D10a)

```text
[standard rules + UI rule 9]

Prereq: D10a is committed. The authoritative contract is
plans/arch/arch-v3/report.md — READ IN FULL "Wave-2 UI contract (v1)"
(your subsections are the ones marked D10b, plus "Interaction baseline"),
"Client projection contract (v1)", and "Views". The wave-2 contract
extends contract v1; where it names a change it wins. The projection
vector fixtures in tests/unit/tools/fixtures/arch/projection/ remain
READ-ONLY and authoritative — their level names are unchanged; a vector
that looks wrong is a stop-and-ask per rule 1. Do NOT read issue or
research files.

Budget: 1,900 changed TS/TSX source lines (excluding tests). Python
changes: none expected (propose per rule 1). No new npm runtime
dependencies without a rule-1 proposal.

Scope — implement the D10b subsections of the contract exactly:
1. C4 zoom: add the `top-containers` rollUp level (pure projection code;
   representative = nearest ancestor container whose parent is a system);
   four-level control with the contract's UI labels; fragment `level`
   tokens per the Views table.
2. Boundary boxes + hierarchical union layout (ELK INCLUDE_CHILDREN),
   per-level ancestor boundaries, selectable, never edge endpoints,
   child-count badges on roll-up nodes. Positions stay fixed while
   scrubbing.
3. Drill: distinct affordance, direct-children projection with
   system-representative boundary stubs, `drill` fragment pushing
   history, breadcrumb + Up, Back returns, scope disabled while drilled.
4. Entity boxes: the five-part anatomy, uniform size per level, reading-
   depth content gating driven by D10a's depth class.
5. Edges and emphasis: default/emphasis strokes per the styling
   reference, 24 px hit rail + 6 px focus rail, anchor distribution,
   member-count chips; selection emphasis with animated outgoing /
   static incoming edges, graduated dimming tiers (selection, hover,
   lens), reduced-motion fallback.
6. Legend + tag lens: floating collapsible panel (reuse D10a's panel
   behavior), tag entries with projected counts, OR-semantics lens with
   dim-only tiers, Clear, keyboard operability, `lens` fragment.
7. Dependency focus view per the contract, `deps` fragment, entered from
   the side panel action D10a stubbed (enable it) and a canvas control.

Tests (exactly these, plus keeping existing suites green):
1. top-containers structural invariants on the projection fixture
   payload: every non-user node is a system or a container whose parent
   is a system; no nested container appears; every component/code/nested-
   container id is a member of exactly one displayed representative's
   roll-up; edge keys remain unordered pairs with no self-pairs.
2. Drill node set on the acme payload: drilling a system with containers
   yields exactly its live direct children plus boundary stubs only for
   entities outside the subtree with retained connections.
3. Legend counts: for one acme state, each legend entry count equals the
   number of projected nodes carrying that tag.
The existing vitest vector suite (all cases) and the D10a tests must stay
green.

Finish: `just build-arch-report`, regenerate the acme report via the CLI,
verify per rule 9 from file://: all four C4 levels render (boundaries at
the three deeper levels), drill in + breadcrumb + browser Back, selecting
a node animates outgoing and highlights incoming edges with unrelated
content dimmed (and reduced-motion shows the static fallback), legend
dims and never hides with counts matching the canvas, dependency view
shows centered focus + in/out columns + count chips, node facts appear at
FULL zoom (>=175%), clean console, zero external requests. Definition of
done: rules 5-8 (also report `npm test` output), then STOP — the phase-3
re-gate (architect + user) follows.
```
