# Excel

**25 functions. Tables, formulas, structure. Full spreadsheet control.**

Excel file manipulation using openpyxl. Create, read, write workbooks, apply formulas, manage tables, and inspect spreadsheet structure.

## Highlights

- 25 functions covering all spreadsheet operations
- Table operations with dictionary-based data access
- Pure cell range functions (no file I/O required)
- JSON-formatted output for LLM consumption
- Auto-creates parent directories on workbook creation
- Auto-prepends `=` to formulas if missing

## Core Operations

| Function | Description |
|----------|-------------|
| `excel.create(filepath, sheet_name)` | Create new Excel workbook |
| `excel.add_sheet(filepath, sheet_name)` | Add worksheet to existing workbook |
| `excel.read(filepath, sheet_name, start_cell, end_cell)` | Read data from worksheet |
| `excel.write(filepath, data, sheet_name, start_cell)` | Write data to worksheet |
| `excel.info(filepath, include_ranges)` | Get workbook metadata |
| `excel.formula(filepath, cell, formula, sheet_name)` | Apply Excel formula to cell |

## Range Manipulation (Pure Functions)

| Function | Description |
|----------|-------------|
| `excel.cell_range(cell, right, down, left, up)` | Expand a cell into a range |
| `excel.cell_shift(cell, rows, cols)` | Shift a cell reference by offset |

## Search

| Function | Description |
|----------|-------------|
| `excel.search(filepath, pattern, sheet_name, regex, first_only)` | Search for values matching pattern |

## Table Operations

| Function | Description |
|----------|-------------|
| `excel.tables(filepath, sheet_name)` | List all defined tables |
| `excel.table_info(filepath, table_name, sheet_name)` | Get detailed table information |
| `excel.table_data(filepath, table_name, row_index, sheet_name)` | Get table data as dicts |
| `excel.create_table(filepath, data_range, table_name, sheet_name)` | Create native Excel table |

## Structure Manipulation

| Function | Description |
|----------|-------------|
| `excel.insert_rows(filepath, row, count, sheet_name)` | Insert rows at position |
| `excel.delete_rows(filepath, row, count, sheet_name)` | Delete rows at position |
| `excel.insert_cols(filepath, col, count, sheet_name)` | Insert columns at position |
| `excel.delete_cols(filepath, col, count, sheet_name)` | Delete columns at position |
| `excel.copy_range(filepath, source, target, sheet_name, target_sheet)` | Copy range to location |

## Extended Inspection

| Function | Description |
|----------|-------------|
| `excel.sheets(filepath)` | List all sheets with visibility |
| `excel.used_range(filepath, sheet_name)` | Get used range of worksheet |
| `excel.formulas(filepath, sheet_name)` | List all formula cells |
| `excel.hyperlinks(filepath, sheet_name)` | List all hyperlinks |
| `excel.merged_cells(filepath, sheet_name)` | List merged cell ranges |
| `excel.named_ranges(filepath)` | List all named ranges |

## Key Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `filepath` | str | Path to Excel file (required) |
| `sheet_name` | str | Target sheet (default: active sheet) |
| `data` | list[list] | Rows for writing (list of lists) |
| `start_cell` | str | Starting cell reference (default: "A1") |
| `pattern` | str | Search pattern (wildcards or regex) |
| `table_name` | str | Name for table operations |

## Examples

### Basic Operations

```python
# Create workbook with custom sheet
excel.create(filepath="output/report.xlsx", sheet_name="Sales")

# Write data
excel.write(
    filepath="output/report.xlsx",
    data=[["Product", "Revenue"], ["Widget", 1000], ["Gadget", 2500]],
    sheet_name="Sales"
)

# Read data back
excel.read(filepath="output/report.xlsx", sheet_name="Sales")

# Apply formula
excel.formula(filepath="output/report.xlsx", cell="B4", formula="=SUM(B2:B3)")
```

### Range Manipulation

```python
# Expand A1 into a 6x11 range (no file needed)
excel.cell_range(cell="A1", right=5, down=10)  # -> "A1:F11"

# Shift B3 down 5 rows and right 3 columns
excel.cell_shift(cell="B3", rows=5, cols=3)  # -> "E8"
```

### Tables

```python
# Create a table from data range
excel.create_table(filepath="data.xlsx", data_range="A1:D10", table_name="SalesData")

# Get table info
excel.table_info(filepath="data.xlsx", table_name="SalesData")

# Read table data as dictionaries
excel.table_data(filepath="data.xlsx", table_name="SalesData")

# Get single row by index
excel.table_data(filepath="data.xlsx", table_name="SalesData", row_index=0)
```

### Search

```python
# Wildcard search
excel.search(filepath="data.xlsx", pattern="Widget*")

# Regex search
excel.search(filepath="data.xlsx", pattern="^ID-\\d+$", regex=True)

# First match only
excel.search(filepath="data.xlsx", pattern="Error*", first_only=True)
```

### Structure Manipulation

```python
# Insert 3 rows at row 5
excel.insert_rows(filepath="data.xlsx", row=5, count=3)

# Delete column B and C
excel.delete_cols(filepath="data.xlsx", col="B", count=2)

# Copy range to another location
excel.copy_range(filepath="data.xlsx", source="A1:C10", target="E1")

# Copy to different sheet
excel.copy_range(filepath="data.xlsx", source="A1:C10", target="A1", target_sheet="Backup")
```

### Inspection

```python
# List all sheets
excel.sheets(filepath="report.xlsx")

# Get used range
excel.used_range(filepath="report.xlsx", sheet_name="Data")

# Find all formulas
excel.formulas(filepath="calc.xlsx")

# List merged cells
excel.merged_cells(filepath="report.xlsx")
```

## Demo Data

A sample spreadsheet is available at `demo/data/sample_sales.xlsx` with:
- **Sales** sheet: Product data with formulas and a table
- **Inventory** sheet: Stock levels with conditional formulas
- **Summary** sheet: Cross-sheet formulas and merged cells

## Source

[openpyxl Documentation](https://openpyxl.readthedocs.io/)

## Based on

[excel-mcp-server](https://github.com/haris-musa/excel-mcp-server) by Haris Musa (MIT)
