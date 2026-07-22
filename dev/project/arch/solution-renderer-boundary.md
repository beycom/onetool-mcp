# Solution Renderer Boundary

## Decision

**Retain LikeC4.** OneTool owns solution selection, projection, canonical identity,
product state, and renderer-neutral geometry. LikeC4 remains a pinned layout and
canvas adapter; Wave 2 found no approved behavior that requires a fork,
undocumented hook, or renderer-specific product contract.

## Owned contracts

- Python and browser projection operate on canonical `ViewGraph` IDs and the
  normalized solution selector.
- `SolutionLayoutResult` contains request and graph identity, canonical node
  bounds and containment, canonical routed edges, aggregate interface members,
  overall bounds, and product diagnostics.
- Navigation, URL/history state, tables, inspectors, statuses, coloring, and
  Draw.io generation do not browse LikeC4 models.
- Browser and API Draw.io consume the projected graph plus plain geometry.
  Boundary interfaces remain metadata and do not create external nodes.

## Explicit LikeC4 inventory

The automated boundary check permits imports only in:

- `src/solution/renderer/` — dynamic/static renderer adapters and canvas node;
- `vite.config.ts`, `src/vite-env.d.ts`, and `src/styles.css` — pinned build and CSS integration;
- `scripts/compile-likec4.mjs` and `scripts/export-likec4.mjs` — pinned compile/layout boundary; and
- `compat/likec4.test.ts` and `compat/react.test.ts` — pinned dependency contract tests.

`ComputedView`, `DiagramView`, `_stage`, `_type`, `modelRef`, and compatibility
casts are limited to the renderer adapter, with one `_type` assertion in the
pinned LikeC4 compatibility test. `npm run verify:renderer-boundary` rejects new
imports or low-level fields elsewhere.

Static authored LikeC4 catalog views retain generated-ID mappings inside the
pinned compile/static-renderer path. Persisted selection, fragments, tables,
inspectors, runtime projection, and exports continue to use canonical OneTool
IDs.

External diagram payloads remain outside the renderer contract. The explorer
embeds content-addressed local attachments once, enforces 10 MiB per-file and
25 MiB aggregate limits, sanitizes SVG/HTML, and renders them without network
access. Solution navigation retains at most 100 entries. Python LikeC4 compile
and export caches use LRU eviction at 32 entries or 64 MiB and do not cache an
entry larger than the byte budget.

## Migration trigger review

| Trigger | Result | Evidence |
|---|---|---|
| Low-level fields or model objects spread outside the adapter | Absent | Boundary script and frontend import inventory |
| Canonical relationship, aggregate, or boundary identity required reconstruction | Absent | Projection, neutral adapter, and Draw.io XML tests |
| Draw.io required an export-only projection or renderer-local identity | Absent | Both export paths receive canonical `ViewGraph` plus `SolutionLayoutResult` |
| Cancellation or performance required patching renderer internals | Absent | Renderer-neutral request gate, deferred dispatch, and bounded caches |
| Approved interaction required a fork or undocumented hook | Absent | Browser behavior uses the supported diagram surface |
| Pinned upgrades repeatedly broke OneTool contracts | Absent | Exact-version compatibility tests remain green |
| Adapter duplicates a growing renderer model/geometry implementation | Absent | One computed-view conversion and one neutral geometry conversion are isolated |

No bounded React Flow comparison is warranted. Re-run this review if a trigger
becomes present; renderer replacement remains a separate approved change.

## Reproducible performance budgets

`tests/performance.test.ts` uses a deterministic fixture with 180 systems, 360
interfaces, 12 groups, 9 tags, 6 changes, and 3 snapshots. The CI budgets are:

| Operation | Budget |
|---|---:|
| Selector resolution plus two-hop projection | 150 ms |
| 1,000 cached projection retrievals | 40 ms |
| Deferred layout dispatch | 250 ms |
| Synchronous control update | 25 ms |
| Prepared browser payload | 3 MB |

Run `npm test -- --run tests/performance.test.ts` from the frontend directory.
