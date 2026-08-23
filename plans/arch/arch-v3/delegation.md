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
| D7 | Phase 3b: report features | GATED on projection spec + D6 | D6 |
| D8 | Phase 4: SQLite adapter, SVG export | GATED on phase-3 gate | phase 3 |

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

## D7 / D8 — GATED (templates to be issued at phase start)

- **D7 (report features):** after the architect commits the client projection
  spec (filter/diff/scope-BFS/level-roll-up function contracts + test
  vectors). Scope: time slider, diff overlay, timeline picker, progressive
  disclosure, tables, URL-fragment views, offline file:// check.
- **D8 (phase 4):** SQLite adapter per adapters.md and client-side SVG/
  draw.io download; prompts written when phase 3 gate passes.
