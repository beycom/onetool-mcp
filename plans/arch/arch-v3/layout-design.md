# Layout engines — design (2026-08-30, decisions CONFIRMED)

Layout is the report's biggest open quality problem (p13, p17, p18 and the
2026-08-30 walkthrough all trace back to it). Direction agreed so far:
separate the layout methods into testable engines, give the report config
authority over method and spacing, and optionally let the viewer choose.

## 1. Engine abstraction

`layout.ts` already contains three methods entangled in `unionLayout`:
ELK `layered` (the general path), `radialLayout` (hub landscapes), and
`gridPack` (fallback). Extract them behind one interface:

```ts
type LayoutSettings = {
  method: 'layered' | 'radial' | 'grid' | 'tree' | 'force' | 'swimlane'
  direction: 'right' | 'down'            // layered/swimlane only
  spacing: { node: number; layer: number; boundary: number }
  ranking: 'auto' | `property:${string}` // FE→BE lane source, layered only
}

interface LayoutEngine {
  layout(graph: RolledGraph, sizes: NodeSizes, settings: LayoutSettings,
         context: { aspectRatio: number; hub: string | null }): Promise<Positions>
}
```

Rules:

- Engines are pure modules (`src/layout/<method>.ts`): graph + sizes +
  settings in, `Positions` out. No React, no view state. A registry maps
  method → engine; `unionLayout` becomes dispatch + cache.
- Child packing inside an expanded boundary is engine-owned — p13's
  narrow-column defect is fixed inside the engines, once, behind the
  shared interface.
- `stableExpansionLayout` (anchor stability) and `applyPositions` stay
  engine-independent post-processing.

Initial engines: **layered** (ELK, direction RIGHT or DOWN), **radial**
(existing, kept as the ego/hub view), **grid** (existing rectpack,
becomes an explicit choice instead of a silent fallback). Later, behind
the same interface: **swimlane** (ELK partitioning from `ranking`),
**tree** (ELK mrtree, containment-first), **force** (ELK stress).

## 2. Report config (follows the `theme` precedent exactly)

Authored block, presentation-only — never affects resolution, diffing, or
validation semantics; payload carries it verbatim; Excel round-trips it
via the settings sheet (`layout.method`, `layout.spacing.node`, …):

```yaml
layout:
  method: layered          # default engine for this report
  direction: right
  spacing:
    node: 60               # sibling gap
    layer: 120             # rank gap (layered)
    boundary: 40           # padding inside expanded boundaries
  ranking: property:layer  # optional FE→BE lane source, e.g. a `layer`
                           # property (frontend|service|data|external)
  user_choice: true        # expose the Layout control in the viewer
```

Validation: `unknown_layout_key`, `invalid_layout_value` (warn, fall back
to defaults — a bad knob must never kill the report). Absent block =
today's behaviour.

## 3. Viewer control

- A **Layout** dropdown in the View dock (the slot p27 frees by removing
  Detail), listing the registered methods; shown only when
  `user_choice: true`. Config's `method` is the default.
- The chosen method rides the view hash (`&layout=radial`) so shared
  links reproduce the picture, and localStorage remembers the viewer's
  preference per report.
- Spacing/direction/ranking stay config-only — the viewer picks a method,
  the author tunes it. Keeps the control simple and the config
  authoritative.

## 4. Testing — how we compare and decide

1. **Shared invariant suite**, parameterized over every registered
   engine × fixture graphs (star hub, chain, dense mesh, nested
   boundaries, 11-child expansion): no node overlaps, children inside
   their boundary with padding, canvas aspect within bounds,
   deterministic output (fixed seed), expansion keeps the anchor within a
   drift budget. New engines get the whole safety net for free.
2. **Per-engine specifics**: layered rank ordering (users leftmost,
   externals rightmost under `ranking`), radial hub centrality, swimlane
   partition integrity.
3. **Visual A/B harness**: dev-only query param (`?layout=<method>` on
   the Vite app) renders acme under each engine; a small script captures
   the screenshot set into `plans/arch/wip/layout-ab/` for side-by-side
   review. This is the mechanism for "test them and choose defaults" —
   and later for regression-checking spacing changes.

## 5. Delivery

Sequence: land the correctness fixes first (p17 dropped edges, p15
dimming — layout judgments are meaningless on half a graph), then extract
engines + config (absorbing p13), then the A/B pass to pick the default.
Propose this as a new plan.md chunk (engine extraction + config + harness
in one executor prompt; the A/B comparison and default decision stay with
the architect).

## Decisions (user-confirmed 2026-08-30)

1. **Ranking source for FE→BE**: an explicit `layer` property on entities
   (round-trips through Excel), with call-direction inference as fallback
   when absent.
2. **Sequencing**: correctness fixes land first (p17 dropped edges, p15
   dimming — chunk P13) before any layout work (chunk P14). Default
   method is then chosen from the A/B harness screenshots.
3. **Viewer control scope**: method-only in the viewer; spacing,
   direction, and ranking stay config-only. Flagged as revisitable — the
   `LayoutSettings` object is the single source viewers would extend, so
   widening the control later is additive.

## Open question

- Does the viewer's Layout choice belong in **saved report definitions**
  (p3-report-definitions) as well? Proposal: yes, it's view state.
