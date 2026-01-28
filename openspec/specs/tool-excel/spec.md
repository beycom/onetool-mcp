# tool-excel Specification

## Purpose

Excel file manipulation tools using openpyxl. Internal tool with pack `excel`.

Provides functions to create, read, write Excel workbooks and apply formulas.

## Requirements

### Requirement: Workbook creation

The system MUST provide functions to create Excel workbooks and worksheets.

#### Scenario: Create new workbook

- **GIVEN** no file exists at the target path
- **WHEN** `excel.create(filepath="output/report.xlsx")` is called
- **THEN** a new Excel file is created with default sheet "Sheet1"
- **AND** parent directories are created if needed
- **AND** the function returns "Created workbook: output/report.xlsx"

#### Scenario: Create workbook with custom sheet name

- **GIVEN** no file exists at the target path
- **WHEN** `excel.create(filepath="output/data.xlsx", sheet_name="Sales")` is called
- **THEN** a new Excel file is created with sheet "Sales"

#### Scenario: Add worksheet to existing workbook

- **GIVEN** workbook exists at "output/data.xlsx"
- **WHEN** `excel.add_sheet(filepath="output/data.xlsx", sheet_name="Summary")` is called
- **THEN** sheet "Summary" is added to the workbook
- **AND** the function returns "Created sheet: Summary"

#### Scenario: Add sheet that already exists

- **GIVEN** workbook exists with sheet "Data"
- **WHEN** `excel.add_sheet(filepath="test.xlsx", sheet_name="Data")` is called
- **THEN** it SHALL return "Error: Sheet 'Data' already exists"

### Requirement: Data read/write

The system MUST provide functions to read and write cell data.

#### Scenario: Write data to worksheet

- **GIVEN** workbook exists at "test.xlsx"
- **WHEN** `excel.write(filepath="test.xlsx", data=[["Name", "Value"], ["A", 1], ["B", 2]])` is called
- **THEN** data is written starting at A1
- **AND** the function returns "Wrote 3 rows to Sheet1"

#### Scenario: Write with custom start cell

- **GIVEN** workbook exists with sheet "Data"
- **WHEN** `excel.write(filepath="test.xlsx", sheet_name="Data", data=[["X", "Y"]], start_cell="C5")` is called
- **THEN** data is written starting at C5

#### Scenario: Read entire sheet

- **GIVEN** worksheet has data in A1:B3
- **WHEN** `excel.read(filepath="test.xlsx")` is called
- **THEN** returns list of lists formatted as YAML: `[[Name, Value], [A, 1], [B, 2]]`

#### Scenario: Read specific range

- **GIVEN** worksheet has data
- **WHEN** `excel.read(filepath="test.xlsx", start_cell="B2", end_cell="C4")` is called
- **THEN** returns only data in range B2:C4

#### Scenario: Read from specific sheet

- **GIVEN** workbook has sheets "Data" and "Summary"
- **WHEN** `excel.read(filepath="test.xlsx", sheet_name="Summary")` is called
- **THEN** returns data from "Summary" sheet

#### Scenario: Read non-existent file

- **GIVEN** file does not exist
- **WHEN** `excel.read(filepath="missing.xlsx")` is called
- **THEN** it SHALL return "Error: File not found: missing.xlsx"

### Requirement: Workbook metadata

The system MUST provide a function to inspect workbook structure.

#### Scenario: Get workbook info

- **GIVEN** workbook exists with sheets "Data" and "Summary"
- **WHEN** `excel.info(filepath="test.xlsx")` is called
- **THEN** returns formatted info with filename, sheets list, and file size

#### Scenario: Get workbook info with used ranges

- **GIVEN** workbook has data in sheets
- **WHEN** `excel.info(filepath="test.xlsx", include_ranges=True)` is called
- **THEN** returns info including used range for each sheet (e.g., "A1:D10")

### Requirement: Excel formulas

The system MUST provide a function to apply Excel formulas.

#### Scenario: Apply SUM formula

- **GIVEN** worksheet has numbers in B2:B10
- **WHEN** `excel.formula(filepath="test.xlsx", cell="B11", formula="=SUM(B2:B10)")` is called
- **THEN** cell B11 contains the formula
- **AND** the function returns "Applied formula to B11: =SUM(B2:B10)"

#### Scenario: Formula without equals sign

- **GIVEN** worksheet exists
- **WHEN** `excel.formula(filepath="test.xlsx", cell="A1", formula="SUM(A2:A5)")` is called
- **THEN** the "=" is automatically prepended
- **AND** cell A1 contains "=SUM(A2:A5)"

#### Scenario: Apply formula to specific sheet

- **GIVEN** workbook has sheet "Totals"
- **WHEN** `excel.formula(filepath="test.xlsx", sheet_name="Totals", cell="C1", formula="=AVERAGE(A1:B1)")` is called
- **THEN** formula is applied to cell C1 in "Totals" sheet

### Requirement: Cell search

The system MUST provide a function to search for cell values by pattern.

#### Scenario: Search with wildcard pattern

- **GIVEN** worksheet has cells containing "Error: timeout" and "Error: connection"
- **WHEN** `excel.search(filepath="log.xlsx", pattern="Error*")` is called
- **THEN** it SHALL return a YAML list of matches: `[{cell: A5, value: "Error: timeout"}, ...]`

#### Scenario: Search with regex pattern

- **GIVEN** worksheet has cells with values "ID-001", "ID-002", "Total"
- **WHEN** `excel.search(filepath="data.xlsx", pattern="^ID-\\d+$", regex=True)` is called
- **THEN** it SHALL return only cells matching the regex pattern

#### Scenario: Search first match only

- **GIVEN** worksheet has multiple cells containing "Total"
- **WHEN** `excel.search(filepath="data.xlsx", pattern="Total", first_only=True)` is called
- **THEN** it SHALL return only the first match as a single dict

#### Scenario: Search specific sheet

- **GIVEN** workbook has sheets "Data" and "Summary"
- **WHEN** `excel.search(filepath="data.xlsx", pattern="*Total*", sheet_name="Summary")` is called
- **THEN** it SHALL search only the "Summary" sheet

#### Scenario: Search with no matches

- **GIVEN** worksheet has no cells matching "XYZ123"
- **WHEN** `excel.search(filepath="data.xlsx", pattern="XYZ123")` is called
- **THEN** it SHALL return an empty list: `[]`

### Requirement: Range manipulation

The system MUST provide functions to expand and shift cell references using openpyxl's CellRange.

#### Scenario: Expand cell to range

- **GIVEN** starting cell "A1"
- **WHEN** `excel.cell_range(cell="A1", right=5, down=5)` is called
- **THEN** it SHALL return "A1:F6"

#### Scenario: Expand with left and up

- **GIVEN** starting cell "C3"
- **WHEN** `excel.cell_range(cell="C3", left=2, up=2)` is called
- **THEN** it SHALL return "A1:C3"

#### Scenario: Shift cell down

- **GIVEN** starting cell "A1"
- **WHEN** `excel.cell_shift(cell="A1", rows=5)` is called
- **THEN** it SHALL return "A6"

#### Scenario: Shift cell right

- **GIVEN** starting cell "A1"
- **WHEN** `excel.cell_shift(cell="A1", cols=5)` is called
- **THEN** it SHALL return "F1"

#### Scenario: Shift cell diagonally

- **GIVEN** starting cell "B3"
- **WHEN** `excel.cell_shift(cell="B3", rows=2, cols=3)` is called
- **THEN** it SHALL return "E5"

### Requirement: Table listing

The system MUST provide a function to list defined tables in a worksheet.

#### Scenario: List tables

- **GIVEN** worksheet has tables "SalesData" and "Inventory"
- **WHEN** `excel.tables(filepath="report.xlsx")` is called
- **THEN** it SHALL return YAML list: `[{name: SalesData, ref: A1:E10}, {name: Inventory, ref: G1:J5}]`

#### Scenario: List tables in specific sheet

- **GIVEN** workbook has tables in different sheets
- **WHEN** `excel.tables(filepath="report.xlsx", sheet_name="Sales")` is called
- **THEN** it SHALL return only tables in the "Sales" sheet

#### Scenario: Worksheet with no tables

- **GIVEN** worksheet has no defined tables
- **WHEN** `excel.tables(filepath="data.xlsx")` is called
- **THEN** it SHALL return an empty list: `[]`

### Requirement: Table metadata

The system MUST provide a function to get detailed table information.

#### Scenario: Get table info

- **GIVEN** table "SalesData" exists with columns ID, Name, Amount
- **WHEN** `excel.table_info(filepath="sales.xlsx", table_name="SalesData")` is called
- **THEN** it SHALL return YAML with: name, ref, headers list, row_count, has_totals

#### Scenario: Table not found

- **GIVEN** no table named "Missing" exists
- **WHEN** `excel.table_info(filepath="sales.xlsx", table_name="Missing")` is called
- **THEN** it SHALL return "Error: Table 'Missing' not found"

### Requirement: Table data access

The system MUST provide a function to read table data as dictionaries.

#### Scenario: Read all table rows

- **GIVEN** table "Sales" has 3 data rows with columns ID, Name, Amount
- **WHEN** `excel.table_data(filepath="sales.xlsx", table_name="Sales")` is called
- **THEN** it SHALL return YAML list of dicts: `[{ID: 1, Name: Alice, Amount: 100}, ...]`

#### Scenario: Read specific table row

- **GIVEN** table "Sales" has multiple rows
- **WHEN** `excel.table_data(filepath="sales.xlsx", table_name="Sales", row_index=0)` is called
- **THEN** it SHALL return the first data row (excluding header) as a single dict

### Requirement: Row operations

The system MUST provide functions to insert and delete rows.

#### Scenario: Insert rows

- **GIVEN** worksheet has data in rows 1-10
- **WHEN** `excel.insert_rows(filepath="data.xlsx", row=5, count=3)` is called
- **THEN** 3 empty rows are inserted at row 5
- **AND** existing rows 5-10 shift down to 8-13
- **AND** it SHALL return "Inserted 3 rows at row 5"

#### Scenario: Delete rows

- **GIVEN** worksheet has data in rows 1-10
- **WHEN** `excel.delete_rows(filepath="data.xlsx", row=3, count=2)` is called
- **THEN** rows 3-4 are deleted
- **AND** rows 5-10 shift up to 3-8
- **AND** it SHALL return "Deleted 2 rows starting at row 3"

### Requirement: Column operations

The system MUST provide functions to insert and delete columns.

#### Scenario: Insert columns by letter

- **GIVEN** worksheet has data in columns A-E
- **WHEN** `excel.insert_cols(filepath="data.xlsx", col="C", count=2)` is called
- **THEN** 2 empty columns are inserted at column C
- **AND** existing columns C-E shift right to E-G
- **AND** it SHALL return "Inserted 2 columns at column C"

#### Scenario: Insert columns by number

- **GIVEN** worksheet has data
- **WHEN** `excel.insert_cols(filepath="data.xlsx", col=3, count=2)` is called
- **THEN** it SHALL behave the same as using col="C"

#### Scenario: Delete columns

- **GIVEN** worksheet has data in columns A-F
- **WHEN** `excel.delete_cols(filepath="data.xlsx", col="B", count=2)` is called
- **THEN** columns B-C are deleted
- **AND** columns D-F shift left to B-D
- **AND** it SHALL return "Deleted 2 columns starting at column B"

### Requirement: Range copying

The system MUST provide a function to copy cell ranges.

#### Scenario: Copy range within sheet

- **GIVEN** worksheet has data in A1:C10
- **WHEN** `excel.copy_range(filepath="data.xlsx", source="A1:C10", target="E1")` is called
- **THEN** data from A1:C10 is copied to E1:G10
- **AND** original data remains unchanged
- **AND** it SHALL return "Copied A1:C10 to E1:G10"

#### Scenario: Copy range to another sheet

- **GIVEN** workbook has sheets "Source" and "Backup"
- **WHEN** `excel.copy_range(filepath="data.xlsx", source="A1:D5", target="A1", sheet_name="Source", target_sheet="Backup")` is called
- **THEN** data is copied from Source sheet to Backup sheet

### Requirement: Table creation

The system MUST provide a function to create native Excel tables.

#### Scenario: Create table from range

- **GIVEN** worksheet has data in A1:E10 with headers in row 1
- **WHEN** `excel.create_table(filepath="sales.xlsx", data_range="A1:E10", table_name="SalesData")` is called
- **THEN** a native Excel table is created from the range
- **AND** first row is used as headers
- **AND** it SHALL return "Created table 'SalesData' from A1:E10"

#### Scenario: Create table with auto-generated name

- **GIVEN** worksheet has data
- **WHEN** `excel.create_table(filepath="data.xlsx", data_range="A1:C5")` is called
- **THEN** a table is created with auto-generated name (e.g., "Table1")

### Requirement: Sheet inspection

The system MUST provide a function to list sheets with details.

#### Scenario: List sheets with visibility

- **GIVEN** workbook has visible sheet "Data" and hidden sheet "Raw"
- **WHEN** `excel.sheets(filepath="report.xlsx")` is called
- **THEN** it SHALL return YAML list: `[{name: Data, state: visible}, {name: Raw, state: hidden}]`

### Requirement: Used range inspection

The system MUST provide a function to get data bounds.

#### Scenario: Get used range

- **GIVEN** worksheet has data from A1 to Z100
- **WHEN** `excel.used_range(filepath="data.xlsx")` is called
- **THEN** it SHALL return "A1:Z100"

#### Scenario: Empty worksheet

- **GIVEN** worksheet has no data
- **WHEN** `excel.used_range(filepath="empty.xlsx")` is called
- **THEN** it SHALL return "empty"

### Requirement: Formula inspection

The system MUST provide a function to list formula cells.

#### Scenario: List formulas

- **GIVEN** worksheet has formulas in B10 and C10
- **WHEN** `excel.formulas(filepath="calc.xlsx")` is called
- **THEN** it SHALL return YAML list: `[{cell: B10, formula: "=SUM(B2:B9)"}, {cell: C10, formula: "=AVERAGE(C2:C9)"}]`

### Requirement: Hyperlink inspection

The system MUST provide a function to list hyperlinks.

#### Scenario: List hyperlinks

- **GIVEN** worksheet has hyperlinks in A5 and B10
- **WHEN** `excel.hyperlinks(filepath="links.xlsx")` is called
- **THEN** it SHALL return YAML list with cell, target URL, and display text

### Requirement: Merged cell inspection

The system MUST provide a function to list merged ranges.

#### Scenario: List merged cells

- **GIVEN** worksheet has merged cells B2:F4 and A10:C10
- **WHEN** `excel.merged_cells(filepath="report.xlsx")` is called
- **THEN** it SHALL return YAML list: `[B2:F4, A10:C10]`

### Requirement: Named range inspection

The system MUST provide a function to list named ranges.

#### Scenario: List named ranges

- **GIVEN** workbook has named ranges "SalesTotal" and "TaxRate"
- **WHEN** `excel.named_ranges(filepath="report.xlsx")` is called
- **THEN** it SHALL return YAML list with name and destination for each
