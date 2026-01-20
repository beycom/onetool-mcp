"""Excel workbook to Markdown converter.

Converts XLSX spreadsheets to Markdown with:
- Streaming row processing via openpyxl read_only mode
- Sheet-based sections
- Optional formula extraction
- YAML frontmatter and TOC generation
"""

from __future__ import annotations

from pathlib import Path  # noqa: TC003 (used at runtime)
from typing import Any

from openpyxl import load_workbook  # type: ignore[import-untyped]

from ot_tools._convert.utils import (
    IncrementalWriter,
    compute_file_checksum,
    generate_frontmatter,
    generate_toc,
    get_mtime_iso,
    normalise_whitespace,
)


def convert_excel(
    input_path: Path,
    output_dir: Path,
    source_rel: str,
    *,
    include_formulas: bool = False,
) -> dict[str, Any]:
    """Convert Excel workbook to Markdown.

    Args:
        input_path: Path to XLSX file
        output_dir: Directory for output files
        source_rel: Relative path to source for frontmatter
        include_formulas: Include cell formulas as comments

    Returns:
        Dict with 'output', 'sheets', 'rows' keys
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load workbook in read-only mode for streaming
    wb = load_workbook(input_path, read_only=True, data_only=not include_formulas)

    # Get metadata for frontmatter
    checksum = compute_file_checksum(input_path)
    mtime = get_mtime_iso(input_path)
    total_sheets = len(wb.sheetnames)

    writer = IncrementalWriter()
    total_rows = 0

    # If we need formulas, load a second workbook with formulas
    wb_formulas = None
    if include_formulas:
        wb_formulas = load_workbook(input_path, read_only=True, data_only=False)

    # Process each sheet
    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        ws_formulas = wb_formulas[sheet_name] if wb_formulas else None

        rows = _process_sheet(writer, sheet_name, ws, ws_formulas, include_formulas)
        total_rows += rows

    wb.close()
    if wb_formulas:
        wb_formulas.close()

    # Generate TOC
    headings = writer.get_headings()
    toc = generate_toc(headings)

    # Generate frontmatter
    frontmatter = generate_frontmatter(
        source=source_rel,
        converted=mtime,
        pages=total_sheets,
        checksum=checksum,
    )

    # Combine all content
    content = frontmatter + "\n" + toc + writer.get_content()
    content = normalise_whitespace(content)

    # Write output
    output_path = output_dir / f"{input_path.stem}.md"
    output_path.write_text(content, encoding="utf-8")

    return {
        "output": str(output_path),
        "sheets": total_sheets,
        "rows": total_rows,
    }


def _process_sheet(
    writer: IncrementalWriter,
    sheet_name: str,
    ws: Any,
    ws_formulas: Any | None,
    include_formulas: bool,
) -> int:
    """Process a single worksheet.

    Returns:
        Number of rows processed
    """
    writer.write_heading(2, f"Sheet: {sheet_name}")

    # Stream rows
    rows_data: list[list[str]] = []
    formulas_data: list[list[str]] = []
    max_cols = 0
    row_count = 0

    for row in ws.iter_rows():
        row_values: list[str] = []
        for cell in row:
            value = cell.value
            if value is None:
                row_values.append("")
            else:
                row_values.append(str(value))

        # Track formulas if needed
        if include_formulas and ws_formulas:
            formula_row: list[str] = []
            for _i, cell in enumerate(row):
                try:
                    # Get corresponding formula cell
                    formula_cell = ws_formulas.cell(
                        row=cell.row, column=cell.column
                    )
                    formula_value = formula_cell.value
                    if isinstance(formula_value, str) and formula_value.startswith("="):
                        formula_row.append(formula_value)
                    else:
                        formula_row.append("")
                except Exception:
                    formula_row.append("")
            formulas_data.append(formula_row)

        rows_data.append(row_values)
        max_cols = max(max_cols, len(row_values))
        row_count += 1

    if not rows_data:
        writer.write("(empty sheet)\n\n")
        return 0

    # Pad rows to same length
    for row in rows_data:
        while len(row) < max_cols:
            row.append("")

    # Write as Markdown table
    # First row as header
    header = rows_data[0]
    writer.write("| " + " | ".join(_escape_pipe(c) for c in header) + " |\n")
    writer.write("| " + " | ".join("---" for _ in header) + " |\n")

    # Remaining rows
    for row in rows_data[1:]:
        writer.write("| " + " | ".join(_escape_pipe(c) for c in row[: len(header)]) + " |\n")

    writer.write("\n")

    # Add formulas section if requested and any formulas found
    if include_formulas and formulas_data:
        has_formulas = any(any(cell for cell in row) for row in formulas_data)
        if has_formulas:
            writer.write("**Formulas:**\n\n")
            writer.write("```\n")
            for i, row in enumerate(formulas_data):
                for j, formula in enumerate(row):
                    if formula:
                        # Convert column index to letter
                        col_letter = _col_letter(j + 1)
                        writer.write(f"{col_letter}{i + 1}: {formula}\n")
            writer.write("```\n\n")

    return row_count


def _escape_pipe(text: str) -> str:
    """Escape pipe characters for Markdown tables."""
    return text.replace("|", "\\|").replace("\n", " ")


def _col_letter(n: int) -> str:
    """Convert column number to letter (1=A, 2=B, ..., 27=AA)."""
    result = ""
    while n > 0:
        n, remainder = divmod(n - 1, 26)
        result = chr(65 + remainder) + result
    return result
