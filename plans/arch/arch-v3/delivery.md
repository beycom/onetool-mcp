# Delivery v3

Status: proposed. The plan is shaped by why v1 and v2 circled: scope grew
faster than foundations proved themselves, and specs grew faster than code
(5,600+ lines of planning docs, ~230 interaction requirements, an 18–28K LOC
estimate for the v2 report). v3 inverts that: small phases, each shippable,
each with a line budget and a demo gate.

## Ground rules

1. **Docs stay this size.** These six documents are the design. New design
   writing replaces text here; it does not accumulate in new files. The v2
   wip docs are historical reference only.
2. **Budgets are contracts** (source lines, excluding tests). Exceeding a
   budget means the design is wrong — simplify the design, don't raise the
   number.
3. **No schema field without a behavior.** A field enters the schema only
   when validation, resolution, or the report uses it in the same phase.
4. **Each phase ends with a demo against a real dataset** (port one genuine
   architecture — e.g. the acme workbook in `plans/arch/wip/` — in phase 1
   and keep it as the living fixture).
5. **Clean break.** v3 replaces the v2 implementation wholesale; the v2
   branch is the donor for code that fits (Excel cell parsing, ID
   normalization, deterministic writers), not a base to refactor in place.

## Phases

### Phase 1 — Model, resolver, YAML (budget: 1,800 Python lines)

- Pydantic models for milestones, timelines, six entity kinds, intervals,
  revisions.
- Interval resolution: state filter, clipping with derived consequences,
  diff, `advance`.
- Validation (structural errors + advisory warnings) with file/line/path
  locations.
- YAML read/write, deterministic output.
- Tools: `arch.init`, `arch.validate`, `arch.resolve`, `arch.diff`,
  `arch.advance`.
- Gate: the ported real dataset validates; diffs between its milestones are
  correct by inspection.

### Phase 2 — Excel adapter (budget: 900 Python lines)

- Workbook read/write per adapters.md, generated template with dropdowns,
  round-trip model-equality tests.
- Tools: `arch.import_excel` (aliased under `arch.convert`), `arch.export`.
- Gate: edit the real dataset in Excel (add a milestone, retire a system,
  revise a container), import, diff shows exactly those edits.

### Phase 3 — Report app (budget: 5,000 TS/TSX lines + 400 Python)

- Prebuilt single-file bundle (React Flow + elkjs worker + AG Grid), built
  at *pack build time*, committed or wheel-packaged — never at generate
  time.
- Payload compiler + injection in Python (`arch.generate`).
- 3.0 surface: canvas, union-graph layout, stage-aware filtering with
  inherent per-stage diff, Detail / Stage / Relationship / Tags controls,
  inspector, tables, copy-link, offline from `file://`. UI shell and
  interaction are governed by
  `plans/arch/arch-v3/ui-polish-direction.md` (2026-08-27): the Option E
  docked shell (View / Info / Data), lower-left Map/Fit/Zoom, splines,
  one-hop selection, light theme only, 1024 × 720 first-pass floor.
- Gate: open the real dataset's report, step through the stages, and the
  story of the architecture reads correctly without explanation — at
  1440 × 900 and 1024 × 720, console-clean, zero external requests.

### Phase 3S — Sequence diagrams (budget: ~500 Python + ~2,200 TS/TSX)

Owner doc: sequence.md. Added 2026-08-25 (user-directed), replacing the
"sequence attachments" deferral.

- Flow-doc parser, validation findings, `sequences` payload section, CLI.
- Custom deterministic sequence layout + React rendering; participant
  headers reuse the canvas entity-box component.
- Interaction contract (controls live in the View dock — direction
  2026-08-27): Scenario dropdown, compact playback, local search, sticky
  headers, participant focus and explicit hiding, Map vertical overview,
  sync/async kinds; message details in Info, payload files in Data. No
  C4 group bands, group collapse, merged lifelines, or floating
  participant navigation.
- Gate: open an acme flow from View, play it through, switch scenario,
  focus a participant, hide one — the story reads without explanation;
  zero external requests from `file://`.

### Phase 4 — Polish and second adapters (budget: per-item)

- Client-side SVG / draw.io download; timeline picker for multi-scenario
  data; saved Report Definition files if URL fragments prove insufficient.
- SQLite adapter, then SharePoint transport reusing the Excel mapping.
- Only then: revisit deferred items against demonstrated need —
  Confluence, layout hints, and the 2026-08-27 direction's first-pass
  cuts (dark theme, application fullscreen, Share, a Changes diagram
  view, saved report creation, manual positions, viewer scope controls,
  Technology/Status lenses).

## What must NOT return without a fight

Each of these died for cause; reintroducing one requires updating index.md
with the concrete requirement that revived it:

- authored patches, `change_type`, `unset`, preconditions, tombstones;
- a second projection implementation anywhere;
- Node/npm/LikeC4 invocation at generate time;
- persisted coordinates or manual placement;
- per-entity `icon`/`style`/`group`/`notes` fields;
- alias tables or backward-compatible field names;
- a spec/interaction catalog that grows without a shipped phase between
  additions.

## Risks

| Risk | Mitigation |
| --- | --- |
| Union-graph layout looks poor for sparse early states | "Re-fit this state" action; if chronic, per-state layout with position seeding — a report change, not a schema change |
| Revision rows confuse Excel users (duplicate ids) | Generated template groups and color-bands revision rows; validation warnings name both rows |
| Real datasets need field-level change more often than assumed | Revisions already cover it; if restating rows proves genuinely painful at scale, that is the trigger to revisit — with data in hand |
| elkjs worker performance on big graphs in-browser | v2's size guidance stands (warn >160 nodes); level roll-up keeps default views small |
| Single YAML file grows unwieldy over years | `advance` compacts delivered milestones; splitting files stays rejected (v2 decision) until a real dataset breaks this |
