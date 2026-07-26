---
name: ot-excel
description: Use when inspecting, creating, reading, searching, writing, restructuring, or applying formulas and native tables in Excel workbooks through OneTool. Use verification-first mutation; use ot-convert for read-only Markdown extraction.
user-invocable: false
---

# OneTool Excel

Use `excel` for structured workbook operations.

## Availability

Check `__ot ot.packs(pattern='excel', info='min')`. If `[util]` or `openpyxl` is missing, stop and
offer installation guidance; do not install software without a separate request.

## Workflow

1. Inspect workbook info, sheets, used ranges, formulas, and tables.
2. Confirm target sheet, range, and intended structural effect.
3. Preserve the original or write to a new path for consequential edits.
4. Apply the smallest mutation.
5. Re-read affected cells, formulas, table metadata, and workbook info.

Never infer a safe row or column deletion from partial data. Formula writes are not recalculated
by `openpyxl`; disclose when an external spreadsheet application must recalculate results.
