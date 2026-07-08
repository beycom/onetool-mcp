"""Workbook discovery and ingestion for arch pack."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from otpack import resolve_cwd_path

from .models import (
    DEFAULT_LIST_CELL_SEPARATOR,
    SHEETS,
    canonical_sheet_name,
    ensure_openpyxl,
    normalize_cell,
    normalize_key,
    parse_cell_list,
    resolve_sheet_name,
)

_YAML_SUFFIXES = {".yaml", ".yml"}


class IngestError(ValueError):
    """Raised when workbook ingestion fails."""


def discover_workbooks(*, input_path: str) -> list[Path]:
    """Discover workbook files from file, directory, or glob path."""
    resolved = resolve_cwd_path(input_path)
    if resolved.is_file():
        if resolved.suffix.lower() not in {".xlsx", ".xlsm"}:
            raise IngestError(f"input_path must point to .xlsx/.xlsm file: {resolved}")
        return [resolved]

    candidates: list[Path]
    raw = Path(input_path)
    if any(token in input_path for token in ("*", "?", "[")):
        if raw.is_absolute():
            root = Path(raw.anchor)
            pattern = str(raw.relative_to(raw.anchor))
            candidates = sorted(
                path.resolve() for path in root.glob(pattern) if path.is_file()
            )
        else:
            root = resolve_cwd_path(".")
            pattern = input_path
            candidates = sorted(path.resolve() for path in root.glob(pattern) if path.is_file())
    elif resolved.is_dir():
        candidates = sorted(path.resolve() for path in resolved.glob("*.xls*") if path.is_file())
    else:
        raise IngestError(f"No workbook(s) found for input_path: {input_path}")

    # Skip Excel owner lock files (`~$name.xlsx`) left while a workbook is open.
    workbooks = [
        path
        for path in candidates
        if path.suffix.lower() in {".xlsx", ".xlsm"} and not path.name.startswith("~$")
    ]
    if not workbooks:
        raise IngestError(f"No workbook(s) found for input_path: {input_path}")
    return workbooks


def _sheet_rows_from_workbook(
    *,
    workbook: Any,
    workbook_path: Path,
    sheet_name: str,
    list_cell_separator: str = DEFAULT_LIST_CELL_SEPARATOR,
) -> list[dict[str, Any]]:
    if sheet_name not in workbook.sheetnames:
        return []
    ws = workbook[sheet_name]
    first_row = next(ws.iter_rows(min_row=1, max_row=1, values_only=True), None)
    if first_row is None:
        return []
    header_values = [normalize_key(cell) for cell in first_row]
    if not any(header_values):
        return []
    header_counts = Counter(header for header in header_values if header)
    duplicate_headers = sorted(header for header, count in header_counts.items() if count > 1)
    if duplicate_headers:
        raise IngestError(
            f"Workbook '{workbook_path}' sheet '{sheet_name}' has columns that collide "
            f"after normalization: {duplicate_headers}"
        )
    rows: list[dict[str, Any]] = []
    for row_index, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        parsed: dict[str, Any] = {}
        for idx, header in enumerate(header_values):
            if not header:
                continue
            value = normalize_cell(row[idx] if idx < len(row) else None)
            if value is None:
                continue
            if isinstance(value, str) and not value:
                continue
            parsed[header] = parse_cell_list(value, separator=list_cell_separator)
        if parsed:
            parsed["_sheet_row"] = row_index
            parsed["_source_file"] = str(workbook_path)
            rows.append(parsed)
    return rows


def ingest_workbooks(
    *,
    workbook_paths: list[Path],
    list_cell_separator: str = DEFAULT_LIST_CELL_SEPARATOR,
) -> dict[str, list[dict[str, Any]]]:
    """Read canonical entity rows from workbook list."""
    openpyxl = ensure_openpyxl()
    merged: dict[str, list[dict[str, Any]]] = {sheet: [] for sheet in SHEETS}
    for workbook_path in workbook_paths:
        workbook = openpyxl.load_workbook(workbook_path, data_only=True)
        try:
            for sheet in SHEETS:
                worksheet_name = resolve_sheet_name(
                    workbook=workbook,
                    canonical_sheet=sheet,
                    workbook_path=workbook_path,
                    error_cls=IngestError,
                )
                if worksheet_name is None:
                    continue
                merged[sheet].extend(
                    _sheet_rows_from_workbook(
                        workbook=workbook,
                        workbook_path=workbook_path,
                        sheet_name=worksheet_name,
                        list_cell_separator=list_cell_separator,
                    )
                )
        finally:
            workbook.close()
    return merged


def read_passthrough_workbooks(*, workbook_paths: list[Path]) -> dict[str, dict[str, Any]]:
    """Capture non-canonical worksheets verbatim for lossless round-trip.

    Returns a mapping of original sheet name -> {"headers": [...], "rows": [[...], ...]},
    preserving header text and cell values exactly. Sheets whose name resolves to a
    canonical entity are ignored (handled by ``ingest_workbooks``).
    """
    openpyxl = ensure_openpyxl()
    passthrough: dict[str, dict[str, Any]] = {}
    for workbook_path in workbook_paths:
        workbook = openpyxl.load_workbook(workbook_path, data_only=True)
        try:
            for sheet_name in workbook.sheetnames:
                if canonical_sheet_name(sheet_name) is not None:
                    continue
                ws = workbook[sheet_name]
                first_row = next(ws.iter_rows(min_row=1, max_row=1, values_only=True), None)
                if first_row is None or not any(cell is not None for cell in first_row):
                    continue
                headers = list(first_row)
                rows: list[list[Any]] = []
                for row in ws.iter_rows(min_row=2, values_only=True):
                    cells = [row[idx] if idx < len(row) else None for idx in range(len(headers))]
                    if any(cell is not None for cell in cells):
                        rows.append(list(cells))
                if sheet_name in passthrough:
                    raise IngestError(
                        f"Passthrough sheet '{sheet_name}' appears in more than one workbook; "
                        "rename one to avoid an ambiguous merge"
                    )
                passthrough[sheet_name] = {"headers": headers, "rows": rows}
        finally:
            workbook.close()
    return passthrough


def _load_yaml_input(input_path: Path) -> tuple[dict[str, list[dict[str, Any]]], dict[str, dict[str, Any]]]:
    # Imported lazily to avoid an import cycle (roundtrip imports models only).
    from .roundtrip import load_yaml_entities

    entities, passthrough = load_yaml_entities(input_path=input_path)
    for rows in entities.values():
        for offset, row in enumerate(rows, start=2):
            row.setdefault("_sheet_row", offset)
            row.setdefault("_source_file", str(input_path))
    return entities, passthrough


def ingest_input(
    *,
    input_path: str,
    list_cell_separator: str = DEFAULT_LIST_CELL_SEPARATOR,
) -> tuple[list[Path], dict[str, list[dict[str, Any]]], dict[str, dict[str, Any]]]:
    """Resolve input and return (source files, canonical entities, passthrough sheets).

    Accepts an Excel workbook (file/dir/glob) or a single ``.yaml``/``.yml`` model file.
    """
    resolved = resolve_cwd_path(input_path)
    if resolved.is_file() and resolved.suffix.lower() in _YAML_SUFFIXES:
        entities, passthrough = _load_yaml_input(resolved)
        return [resolved], entities, passthrough

    workbooks = discover_workbooks(input_path=input_path)
    entities = ingest_workbooks(workbook_paths=workbooks, list_cell_separator=list_cell_separator)
    passthrough = read_passthrough_workbooks(workbook_paths=workbooks)
    return workbooks, entities, passthrough


__all__ = [
    "IngestError",
    "discover_workbooks",
    "ingest_input",
    "ingest_workbooks",
    "read_passthrough_workbooks",
]
