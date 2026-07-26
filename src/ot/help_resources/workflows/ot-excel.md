<!-- Generated from skills/ot-excel/SKILL.md; do not edit. -->
# OneTool Excel

Use `excel` for structured workbook operations.

## Capability boundary

Check `__ot ot.packs(pattern='excel', info='min')`. If `[util]` or `openpyxl` is missing, stop and
offer installation guidance; do not install software without a separate request.

The pack covers workbook/sheet metadata, used/merged/named ranges, formulas, hyperlinks, native
tables, reads/searches, cell-range calculations, writes/copies, and row/column insertion/deletion.
It does not provide a pivot operation. Use `convert.excel` only for read-oriented Markdown output.

## Workflow

1. Inspect workbook info, sheets, used ranges, formulas, and tables.
2. Confirm target sheet, range, and intended structural effect.
3. Preserve the original or write to a new path for consequential edits.
4. Apply the smallest write, copy, formula, table, sheet, row, or column mutation.
5. Re-read affected cells and inspect formulas, table metadata, used range, and workbook info.

## Safety and side effects

Workbook operations write files and structural edits can invalidate formulas, named ranges, or
external references. Preserve the original or choose a new output path for consequential work.
Never infer a deletion target from a partial read. `openpyxl` stores formulas but does not calculate
them; cached values may remain stale until a spreadsheet application recalculates.

## Verification and recovery

Re-open the saved workbook, inspect target sheets/ranges, verify formulas/table boundaries, and
report the recalculation caveat. If a write fails, inspect the exact path/sheet/range and setup help
once; do not repeat a partially applied structural mutation blindly.
