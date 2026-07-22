# Production Grid Spike

This spike exercises the production dependency graph with one React tree, one
Mantine provider, LikeC4 React, and AG Grid Community against 5,000 architecture
rows. Run `npm run benchmark:grid` to build the deterministic fixture in a
temporary directory and refresh measured results.

## Decision

AG Grid Community passes the representative fixture and remains selected.

| Candidate | Representative fit | Outcome |
| --- | --- | --- |
| AG Grid Community | Built-in virtualisation, typed filters, multi-sort, column resize/reorder/pinning, selection, keyboard navigation, and filtered/sorted CSV; wrapper supplies searchable column choice and copy actions | Selected |
| Mantine DataTable | Mantine-native presentation, but application-owned filtering/sorting, no equivalent multi-sort baseline, and weaker large-grid virtualisation contract | Rejected |
| TanStack Table | Strong headless state, but OneTool would own virtualisation, drag/reorder, keyboard interaction, copy, and export behaviour | Rejected |

## Measured Result

The committed `grid-spike.json` records the current machine result. Acceptance
requires zero runtime network requests, keyboard focus movement, and interactive
filter/sort response on the 5,000-row fixture. Bundle size is recorded from the
self-contained production HTML rather than an unrepresentative library chunk.

| Measurement | Result on 2026-07-20 |
| --- | ---: |
| Cold local-file startup to rendered grid | 903.8 ms |
| Quick-filter response | 73.7 ms |
| Stable-ID descending sort | 52.5 ms |
| Self-contained 5,000-row benchmark HTML | 6,748,047 bytes |
| Runtime network requests | 0 |
| Keyboard focus moved | Yes |
| Grid/header/search screen-reader roles present | Yes |
| Shell-owned overlay rendered above integration tree | Yes |

## Dynamic Solution Budgets

`tests/performance.test.ts` uses the deterministic multi-snapshot projection
fixture in `tests/fixtures/projection-benchmark.ts`. It fails the frontend test
suite when any of these machine-independent guardrails regress:

| Operation | Budget |
| --- | ---: |
| System-set resolution plus two-hop projection | < 150 ms |
| 1,000 cached projection retrievals | < 40 ms |
| Deferred layout-request dispatch | < 250 ms |
| Synchronous control-state update | < 25 ms |
| Prepared snapshot payload | < 3,000,000 bytes |

These budgets cover projection and dispatch rather than Graphviz completion,
whose wall time varies by browser and host. Runtime tests prove stale-result
protection; the generated-report browser test proves topology changes and
offline layout.

## Accessibility and Theme Findings

- The shared root Mantine provider owns grid menus while LikeC4 uses the same
  deduplicated Mantine instance.
- AG Grid uses typed Quartz parameters derived from OneTool CSS variables for
  light/dark surfaces, focus, separators, typography, and selection.
- Search uses a labelled native input; grid headers and rows remain keyboard
  reachable; selection has a non-colour checkbox affordance.
- Current-view CSV preserves filtered/sorted rows and visible column order. The
  all-data action exports every row and column through the Community API.
- Wrapper-owned copy and searchable column controls are exercised through the
  production grid wrapper.
