# Adapters v3: Excel now, everything tabular later

Status: proposed. Inherits the v2 file-format decisions (YAML canonical,
atomic replacement import, new-workbook export, cell conventions, header
normalization, error location contracts) — see
[arch-v2/file-formats.md](../arch-v2/file-formats.md). This document owns
what the interval model changes and the adapter architecture.

## Why intervals make adapters simple

The v2 Excel design had to interleave Current State rows and patch rows in
one sheet, guarded by `change`/`change_type` columns, with blank meaning
*absent* in one row context and *unchanged* in another, plus `unset` cell
markers. That is the part of v2 a spreadsheet user would get wrong.

In v3 every row is a complete, self-describing record. A domain sheet is a
plain table; blank always means blank. The whole adapter contract collapses
to: **each collection is a table; each row is a record; `from`/`until` are
two ordinary reference columns.** That contract maps identically onto Excel
sheets, SharePoint lists, SQLite tables, and CSV files — one mental model,
N transports.

## Adapter architecture

```text
            ┌── excel  (xlsx file)          v3.0
canonical ──┼── sharepoint (Graph API)      later — same mapping as excel
YAML  <──>  ┼── sqlite  (one table/kind)    later
 (model) ───┴── csv-dir (one file/kind)     later
```

- Every adapter implements two functions against the in-memory model:
  `read(source) -> Architecture` and `write(Architecture, target)`.
- Import path is always `read -> validate -> atomically replace YAML`.
  Runtime and reports consume YAML only. No adapter is a source of truth.
- Round-trip guarantee is model equality, not presentation equality
  (unchanged from v2).
- SharePoint is the Excel mapping over a different transport: same sheets as
  a workbook in a document library first (zero new mapping), native Lists as
  a refinement. Auth/transport is deferred exactly as v2 deferred it.

## Excel workbook (v3.0)

`.xlsx` only, no formulas. Sheets:

1. `Architecture` — one row: `schema_version` = 3.
2. `Milestones` — `id`, `name`, `description` (+ property columns).
3. `Timelines` — `timeline`, `milestone`; row order is milestone order, one
   contiguous block per timeline. Empty sheet = implicit timeline.
4. `Systems` — `id`, `name`, `from`, `until`, `description`, `tags`.
5. `Subsystems` — + `system`.
6. `Components` — + `subsystem`.
7. `Users` — as Systems.
8. `Interfaces` — + `provider`, `consumer`, `call_direction`, `data_flow`.
9. `Relationships` — `id`, `source`, `action`, `target`, `from`, `until`,
   `description`, `tags`.

Reserved columns always present; any additional column is a property
(v2 rule, including its accepted typo risk, mitigated by the generated
template). List cells use `[a;b]`. Enum and milestone-reference columns get
dropdown validation in generated workbooks.

Revision rows are just two rows with the same `id` and different `from` —
sortable and filterable like everything else. No row ordering constraints
beyond the `Timelines` blocks.

What a maintainer can now do natively in Excel, with zero tooling:

- filter `until` blank → the end-state architecture;
- filter `from` blank → the current architecture;
- filter any column by milestone id → that phase's full impact;
- sort by system → review a subsystem inventory row by row.

## SQLite (later, small)

One table per collection with the reserved columns typed, properties in a
side table (`entity_id`, `name`, `value`, `ord`). Because rows are complete
records, the mapping is mechanical; the adapter is mostly DDL plus the same
validation. This also becomes the natural query surface for large estates
(`SELECT … WHERE until IS NULL`).

## Errors

Unchanged from v2: YAML errors carry file/line/column/path; tabular errors
carry workbook-or-table/sheet/row/column/field; duplicates and broken
references cite every location; import collects independent errors in one
run; a failed import changes nothing.
