"""Excel <-> YAML round-trip helpers for arch pack."""

from __future__ import annotations

import re
from copy import copy
from typing import TYPE_CHECKING, Any

import yaml

from .models import (
    DEFAULT_LIST_CELL_SEPARATOR,
    FIELD_ALIASES,
    FIELD_CANONICAL_BY_ALIAS,
    PASSTHROUGH_KEY,
    SHEETS,
    canonical_sheet_name,
    ensure_openpyxl,
    first_value,
    format_cell_list,
    normalize_key,
    resolve_sheet_name,
)

if TYPE_CHECKING:
    from pathlib import Path

_CELL_REF_RE = re.compile(r"([A-Za-z]+)(\d+)")


class RoundtripError(ValueError):
    """Raised for round-trip conversion errors."""


def export_entities_to_yaml(
    *,
    entities: dict[str, list[dict[str, Any]]],
    output_path: Path,
    passthrough: dict[str, dict[str, Any]] | None = None,
) -> str:
    """Write entities (and any passthrough sheets) to a YAML file.

    List-valued fields are emitted as native YAML sequences. Non-canonical sheets are
    preserved verbatim under the reserved ``_passthrough`` key.
    """
    cleaned: dict[str, Any] = {}
    for sheet in SHEETS:
        cleaned[sheet] = []
        for row in entities.get(sheet, []):
            cleaned[sheet].append({k: v for k, v in row.items() if not k.startswith("_")})

    if passthrough:
        cleaned[PASSTHROUGH_KEY] = {
            name: {"headers": list(sheet["headers"]), "rows": [list(r) for r in sheet["rows"]]}
            for name, sheet in passthrough.items()
        }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        yaml.safe_dump(cleaned, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return str(output_path)


def load_yaml_entities(
    *, input_path: Path
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, dict[str, Any]]]:
    """Load YAML entity sections and any passthrough sheets.

    Returns ``(entities, passthrough)``. Canonical sheet names/aliases populate entities;
    the reserved ``_passthrough`` key carries opaque non-canonical sheets. Any other
    unknown top-level section is rejected.
    """
    if not input_path.exists():
        raise RoundtripError(f"YAML input not found: {input_path}")
    loaded = yaml.safe_load(input_path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise RoundtripError("YAML root must be a mapping of sheet -> rows")

    passthrough = _parse_passthrough(loaded.get(PASSTHROUGH_KEY))

    sections_by_canonical: dict[str, list[tuple[str, Any]]] = {sheet: [] for sheet in SHEETS}
    for raw_key, raw_rows in loaded.items():
        if raw_key == PASSTHROUGH_KEY:
            continue
        canonical = canonical_sheet_name(raw_key)
        if canonical is None:
            raise RoundtripError(
                f"YAML contains unknown section '{raw_key}'. Known sections: {sorted(SHEETS)} "
                f"(non-canonical sheets belong under '{PASSTHROUGH_KEY}')"
            )
        sections_by_canonical[canonical].append((str(raw_key), raw_rows))

    entities: dict[str, list[dict[str, Any]]] = {}
    for sheet in SHEETS:
        matches = sections_by_canonical[sheet]
        if len(matches) > 1:
            names = [name for name, _ in matches]
            raise RoundtripError(f"YAML defines multiple sections for '{sheet}': {names}")
        rows = matches[0][1] if matches else []
        if not isinstance(rows, list):
            raise RoundtripError(f"YAML section '{sheet}' must be a list")
        parsed: list[dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                raise RoundtripError(f"YAML section '{sheet}' contains non-mapping row")
            parsed.append(dict(row))
        entities[sheet] = parsed
    return entities, passthrough


def _parse_passthrough(raw: Any) -> dict[str, dict[str, Any]]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise RoundtripError(f"YAML '{PASSTHROUGH_KEY}' must be a mapping of sheet name -> {{headers, rows}}")
    passthrough: dict[str, dict[str, Any]] = {}
    for name, sheet in raw.items():
        if not isinstance(sheet, dict) or "headers" not in sheet or "rows" not in sheet:
            raise RoundtripError(
                f"YAML '{PASSTHROUGH_KEY}.{name}' must have 'headers' and 'rows'"
            )
        headers = sheet["headers"]
        rows = sheet["rows"]
        if not isinstance(headers, list) or not isinstance(rows, list):
            raise RoundtripError(
                f"YAML '{PASSTHROUGH_KEY}.{name}' headers and rows must be lists"
            )
        passthrough[str(name)] = {"headers": list(headers), "rows": [list(r) for r in rows]}
    return passthrough


def _row_value_for_header(*, row: dict[str, Any], header: str) -> Any:
    if header in row:
        return row.get(header)
    canonical = FIELD_CANONICAL_BY_ALIAS.get(header)
    if canonical is None:
        return None
    return first_value(row, FIELD_ALIASES[canonical])


def _copy_row_style(*, worksheet: Any, source_row: int, target_row: int, max_col: int) -> None:
    for col in range(1, max_col + 1):
        source = worksheet.cell(row=source_row, column=col)
        target = worksheet.cell(row=target_row, column=col)
        if source.has_style:
            target.number_format = source.number_format
            target.font = copy(source.font)
            target.fill = copy(source.fill)
            target.border = copy(source.border)
            target.alignment = copy(source.alignment)
            target.protection = copy(source.protection)


def import_yaml_into_template(
    *,
    entities: dict[str, list[dict[str, Any]]],
    template_path: Path,
    output_path: Path,
    list_cell_separator: str = DEFAULT_LIST_CELL_SEPARATOR,
    passthrough: dict[str, dict[str, Any]] | None = None,
) -> str:
    """Import YAML entities (and passthrough sheets) into a workbook template and save it."""
    openpyxl = ensure_openpyxl()
    if not template_path.exists():
        raise RoundtripError(f"Template workbook not found: {template_path}")

    wb = openpyxl.load_workbook(template_path)
    try:
        for sheet in SHEETS:
            sheet_name = resolve_sheet_name(
                workbook=wb,
                canonical_sheet=sheet,
                workbook_path=template_path,
                error_cls=RoundtripError,
                label="Template workbook",
            )
            rows = entities.get(sheet, [])
            if sheet_name is None:
                # Refuse to silently drop the model's rows when the template
                # has no sheet to receive them.
                if rows:
                    raise RoundtripError(
                        f"Template workbook '{template_path}' has no sheet for '{sheet}' "
                        f"but the model defines {len(rows)} row(s); add the sheet to the template"
                    )
                continue
            ws = wb[sheet_name]
            first_row = next(ws.iter_rows(min_row=1, max_row=1, values_only=False), None)
            header_cells = list(first_row) if first_row is not None else []
            headers = [normalize_key(cell.value) for cell in header_cells]
            max_col = len(headers)
            # Refuse to silently drop row fields the template has no column for.
            covered_keys: set[str] = set()
            for header in headers:
                if not header:
                    continue
                covered_keys.add(header)
                canonical_field = FIELD_CANONICAL_BY_ALIAS.get(header)
                if canonical_field:
                    covered_keys.update(FIELD_ALIASES[canonical_field])
            unmapped = sorted(
                {
                    key
                    for row in rows
                    for key in row
                    if not key.startswith("_") and key not in covered_keys
                }
            )
            if unmapped:
                raise RoundtripError(
                    f"Template sheet '{ws.title}' has no columns for fields {unmapped}; "
                    "add the columns to the template or remove the fields"
                )

            # Clear existing row values while preserving style/layout.
            for row_idx in range(2, ws.max_row + 1):
                for col_idx in range(1, max_col + 1):
                    ws.cell(row=row_idx, column=col_idx).value = None

            style_source_row = 2 if ws.max_row >= 2 else 1
            for offset, row in enumerate(rows, start=2):
                if offset > ws.max_row:
                    ws.insert_rows(offset)
                    _copy_row_style(
                        worksheet=ws,
                        source_row=style_source_row,
                        target_row=offset,
                        max_col=max_col,
                    )
                for col_idx, header in enumerate(headers, start=1):
                    if not header:
                        continue
                    value = _row_value_for_header(row=row, header=header)
                    ws.cell(row=offset, column=col_idx).value = format_cell_list(
                        value, separator=list_cell_separator
                    )

            # Adjust table range to cover written rows (tables must keep at
            # least one data row below their header row).
            non_empty_header_cells = [
                cell for cell, header in zip(header_cells, headers, strict=True) if header
            ]
            col_end = (
                non_empty_header_cells[-1].column_letter if non_empty_header_cells else "A"
            )
            for table in ws.tables.values():
                start_cell = table.ref.split(":", maxsplit=1)[0]
                ref_match = _CELL_REF_RE.match(start_cell)
                start_row = int(ref_match.group(2)) if ref_match else 1
                last_row = start_row + max(1, len(rows))
                table.ref = f"{start_cell}:{col_end}{last_row}"

        _write_passthrough_sheets(workbook=wb, passthrough=passthrough or {})

        output_path.parent.mkdir(parents=True, exist_ok=True)
        wb.save(output_path)
    finally:
        wb.close()

    return str(output_path)


def _write_passthrough_sheets(*, workbook: Any, passthrough: dict[str, dict[str, Any]]) -> None:
    """Write opaque passthrough sheets back to the workbook, creating sheets as needed."""
    for name, sheet in passthrough.items():
        headers = list(sheet.get("headers", []))
        rows = [list(r) for r in sheet.get("rows", [])]
        if name in workbook.sheetnames:
            ws = workbook[name]
            if ws.max_row >= 1:
                ws.delete_rows(1, ws.max_row)
        else:
            ws = workbook.create_sheet(title=name)
        ws.append(headers)
        for row in rows:
            ws.append(row)


__all__ = [
    "RoundtripError",
    "export_entities_to_yaml",
    "import_yaml_into_template",
    "load_yaml_entities",
]
