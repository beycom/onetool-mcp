# Arch v3 — Execution Plan

Tracking document for implementing v3. The **design** lives in the five sibling
docs (index, schema, report, adapters, delivery) — this file never restates it,
only tracks execution. Update the checkboxes and the progress log as work
lands; a fresh session should be able to resume from this file alone.

## How to use this file

- **Resuming:** read this file, then index.md, then the doc owning the phase
  you are in (schema.md for phase 1, adapters.md for phase 2, report.md for
  phase 3). Check the progress log for the last entry.
- **Stopping:** append a progress-log entry saying what state the tree is in
  and the next action. Commit WIP rather than leaving dirty trees.
- **Exploring a different direction:** branch off `feature/arch-v3`, note the
  branch and question under "Exploration branches" below. Design changes go
  into the five docs (replacing text, not adding files — delivery.md rule 1),
  with a log entry here.

## Ground truth

| What | Where |
| --- | --- |
| Working tree / branch | this worktree, `feature/arch-v3` (worktree `arch-v3`) |
| Design docs | `plans/arch/arch-v3/` (index, schema, report, adapters, delivery) |
| v1 implementation (to be replaced) | `src/otdev/tools/arch.py` + `src/otdev/tools/_arch/` (models, ingest, validate, generate, exporters, roundtrip, …) |
| v2 donor code (do NOT build on; harvest only) | worktree `[STUCK]arch-v2`, branch `feature/arch-v2`, pushed to origin, clean. `src/otdev/tools/_arch/v2/` — 8,761 lines |
| Report interaction reference | `plans/arch/react-flow-poc/` (vite app: `ArchitectureCanvas.tsx`, styles, panels) |
| Real dataset for the phase-1 port | `plans/arch/wip/acme-arch-v2.xlsx` (dumped to `plans/arch/arch-v3/fixture-src/`) |
| Canonical v3 fixture | `tests/unit/tools/fixtures/arch/acme.yaml` |
| v2 design history (reference only) | `plans/arch/arch-v2/` incl. `grill/` |

**Tooling hints (interactive/architect work):** use the OneTool `excel` pack
(`__ot excel`) to read/inspect workbooks and the `convert` pack (`__ot
convert`) for format conversions — don't hand-roll openpyxl scripts for
inspection. (In-pack _arch/v3 code still uses openpyxl directly, per the
design docs.)

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
  → D8.

## Speed mode (agreed 2026-08-23)

To move fast, formal ceremony is deferred until the design stabilises
(post phase-3 gate). Backfill items are tracked in Phase 4.

- **OpenSpec: skipped entirely.** No change proposals, no spec deltas during
  the build. Backfilled once v3 ships.
- **Docs: skipped.** The five design docs remain the only design writing;
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

- [ ] Pydantic models: Architecture root, Milestone, Timeline, six entity
      kinds, `from`/`until` fields, flat properties. ID/text rules from v2.
      `→ D2`
- [ ] YAML read/write, deterministic output (harvest v2 `write.py` patterns).
      `→ D2`
- [ ] **Architect:** resolver signatures + authoritative semantics test
      suite (interval edge cases: gap reintroduction, milestone not on
      timeline, from==until rejection, clipping chains, revision diffs,
      advance rewrites). This is the phase's design core — not delegated.
- [ ] Resolver implementation: revision grouping, state-at-position filter
      (`current`/milestone/`end` selector), clipping with `clipped_by`
      consequences, diff (added/removed/changed field-by-field),
      `advance(through=…)` deterministic rewrite. `→ D3` (to architect's
      tests)
- [ ] Validation: structural errors + advisory warnings with locations
      (implemented in full; only its test breadth is deferred). `→ D4`
- [ ] Dev CLI (`__main__.py`): validate / resolve / diff / advance
      subcommands — the fast iteration loop, no MCP needed. `→ D4`
- [ ] Tools: `arch.init`, `arch.validate`, `arch.resolve`, `arch.diff`,
      `arch.advance` (thin facade over the same functions). `→ D4`
- [ ] **Gate (architect):** acme fixture validates; diffs between its
      milestones are correct by inspection. Record line count vs budget in
      the log.
- [ ] Cut over `arch.py` to v3; delete v1 modules; update any specs/docs
      referencing v1 behavior. (Architect-reviewed step.)

## Phase 2 — Excel adapter (budget: 900 py lines)

Owner doc: adapters.md. Entire build chunk is one delegation. `→ D5`

- [ ] Adapter interface: `read(source) -> Architecture`, `write(arch, target)`.
- [ ] Workbook read: 9 sheets, header normalization, `[a;b]` lists, extra
      columns → properties, Timelines block ordering (harvest v2 parsing).
- [ ] Workbook write + generated template: dropdown validation for enums and
      milestone refs, revision-row banding.
- [ ] Tabular error contract: sheet/row/column/field, all locations, atomic
      failed import.
- [ ] Tools: `arch.import_excel` (under `arch.convert`), `arch.export`.
- [ ] Round-trip model-equality tests on the acme fixture.
- [ ] **Gate (architect + user):** edit acme in Excel (add milestone, retire
      system, revise subsystem) → import → diff shows exactly those three
      edits.

## Phase 3 — Report app (budget: 5,000 TS/TSX + 400 py lines)

Owner doc: report.md. POC is the interaction donor.

- [ ] **Architect:** payload JSON spec (rows with pre-resolved integer
      positions + derived consequences) — unblocks D6.
- [ ] Bundle scaffolding: React Flow v12 + elkjs worker + AG Grid, vite
      single-file build at **pack build time**; wheel-packaged artifact;
      Archify styling + panels ported from POC; `arch.generate` template
      injection (~400 py). `→ D6` (parallel with D5)
- [ ] **Architect:** client projection spec (filter, diff set-arithmetic,
      scope BFS, level roll-up — contracts + test vectors) — unblocks D7.
- [ ] Client projection + union-graph layout (fixed positions across
      slider), passport panel, minimap, light/dark. `→ D7`
- [ ] Time slider + diff overlay + timeline picker, progressive disclosure
      (zero milestones → no time UI). `→ D7`
- [ ] Tables (entities, interfaces, milestones, diff) off the same filtered
      arrays; URL-fragment views + copy-link; offline `file://` check. `→ D7`
- [ ] **Gate (architect + user):** open acme's report, scrub the timeline;
      the story reads correctly without explanation.

## Phase 4 — Polish and second adapters (per-item budgets)

- [ ] Client-side SVG / draw.io download from the report. `→ D8`
- [ ] SQLite adapter (one table/kind + properties side table). `→ D8`
- [ ] SharePoint transport reusing the Excel mapping.
- [ ] Migration converter from v2 YAML — only if a real v2 dataset exists to
      migrate; otherwise skip (throwaway tooling).
- [ ] Revisit deferred items (sequence attachments, saved Report Definitions,
      Confluence) against demonstrated need only.

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

1. Report bundle location + build wiring into the wheel (phase 3 start).
2. Whether `arch.convert` is the umbrella tool name or `import_excel`/`export`
   stand alone (phase 2 start; delivery.md says aliased under convert).
3. Per-state layout fallback if union-graph layout is chronically poor for
   sparse early states (risk table; decide only with the acme report open).

## Progress log (append-only, newest first)

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
