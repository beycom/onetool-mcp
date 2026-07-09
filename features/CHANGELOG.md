# features-v3.xlsx changelog

Update history for `features/features-v3.xlsx`. Each entry records the git
hash the workbook is current through (**coverage**), so the next update only
needs `git log <coverage>..HEAD`.

Newest first. See `features/approach.md` for the update procedure.

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
