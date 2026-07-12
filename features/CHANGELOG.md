# features-v3.xlsx changelog

Update history for `features/features-v3.xlsx`. Each entry records the git
hash the workbook is current through (**coverage**), so the next update only
needs `git log <coverage>..HEAD`.

Newest first. See `features/approach.md` for the update procedure.

## 2026-07-12 14:20 — coverage: d866c497

- v3.0.0 is not yet released, so everything landing on main ships in 3.0.0:
  relabelled all 20 `post-3.0.0` rows (the 15 added below plus the 5 earlier
  rows from `a9f5f68e`/3.0.0-era follow-ups) to `release-version=3.0.0`.
  No project version bump.
- Analysis: merged the post-3.0.0 bucket into 3.0.0 (now 55 features /
  406 value); Grand Total unchanged (138 / 1048). Notes scope updated.

## 2026-07-12 14:05 — coverage: d866c497

- Reviewed commits `6df04d4f..d866c497`: the 2026-07-11 pack-review wave
  (~35 `fix:` commits plus small `feat:` commits) and the 2026-07-12
  six-change OpenSpec wave (arch, knowledge, mem, ot_image, otpack,
  whiteboard).
- Added 15 rows, all `release-version=post-3.0.0`:
  - 2026-07-12: **Whiteboard named boards everywhere** (7), **Whiteboard
    offline ELK layout** (6), **Shared embedding infrastructure** (otpack, 6),
    **Multi-image vision ask** (7), **Format-true image storage and batched
    answers** (6), **Memory indexed search** (9), **Memory history and
    rollback** (7), **Knowledge AI enrichment** (8), **Architecture
    incremental generation** (8), **Architecture validation warnings** (6).
  - 2026-07-11: **Web fetch guardrails** (6, covers block_private_urls +
    max_download_bytes + final_url reporting), **Local history pruning** (6),
    **Ground vertical model overrides** (5), **Secrets unset tool** (4),
    **Timer stop tool** (3).
- The rest of the 2026-07-11 wave is correctness/robustness hardening
  (ripgrep flag injection, excel handle leaks, db read-only guard, ctx purge
  semantics, image atomic meta writes, etc.) — recorded here, not as rows.
  Likewise the arch facade decomposition, mem/knowledge embedding delegation
  to otpack, and whiteboard layout() extraction are refactors behind the
  feature rows above.
- Refreshed `loc` (cloc 2.10 over the pack module paths) on 30 existing rows:
  arch 4937→5107, mem 2767→3258, knowledge 2956→3086 (scope:
  knowledge.py + _knowledge + onetool/kb.py), ot_image 771→828, whiteboard
  2475→2945 (excludes the vendored elk.bundled.js), localhist 1442→1505,
  webfetch 259→291, ground 382→394, ot_secrets 606→481 (rescoped to
  ot_secrets.py), ot_timer 89→72 (rescoped to ot_timer.py).
- Extended Features `Table1` to A1:H139; updated Analysis values
  (post-3.0.0: 20 features / 132 value; Grand Total: 138 / 1048).

## 2026-07-09 08:48 — coverage: 6df04d4f

- Reviewed commits since generation: `a9f5f68e` (feature-bearing) and
  `6df04d4f` (docs-only reorganisation, no feature rows).
- Added 2 rows for `a9f5f68e` (feat(tool:arch): add solution reports and
  drawio export), both `pack=arch`, `release-version=post-3.0.0`,
  `build-date=2026-07-09`:
  - **Architecture project reports** (value 8) — per-project pages with stage
    diagrams, change-type styling and badges, shared style legend, index
    summary cards and global entity tables.
  - **Architecture draw.io editable SVG export** (value 7) — embedded mxfile
    model in every generated diagram SVG with real rendered geometry,
    `data.drawio_export` toggle, per-diagram "Export to draw.io" controls.
- Refreshed `loc` on the two existing arch rows 2770 → 4937 (cloc over
  `src/otdev/tools/arch.py` + `src/otdev/tools/_arch`; the arch templates add
  ~713 more, not counted).
- `a9f5f68e` also carries a code-review hardening pass (workbook-value HTML
  escaping, case-insensitive enum handling, diagram path containment,
  pinned/offline-guarded report assets) — recorded here rather than as a
  feature row.
- Extended Features `Table1` to A1:H124; updated Analysis pivot values
  (post-3.0.0: 5 features / 38 value; Grand Total: 123 / 954) and set the
  pivot cache to refresh on load.

## 2026-07-05 11:34 — coverage: 6c3aa8b9 (v3 generated)

- v3 revision of the inventory: merged 6 near-duplicate rows, removed a
  boilerplate sentence from descriptions, fixed ctx rows to the canonical
  pack name `ot_context`.
- Added 5 rows: ot-ref agent skill distribution, HTTP root MCP transport,
  anonymous telemetry with opt-out, configurable server prompts, MCP resource
  discovery.
- Scope: current surviving features and significant changes from v1.0.0
  through post-3.0.0 commits; 121 rows, total value 939.
