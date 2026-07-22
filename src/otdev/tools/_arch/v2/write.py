"""Deterministic schema-v2 YAML and compact Excel writers."""

from __future__ import annotations

import hashlib
import json
import zipfile
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import TYPE_CHECKING, Any, cast

import yaml

if TYPE_CHECKING:
    from openpyxl import Workbook

    from .models import ArchitectureWorkspace, Change, CompleteState

_FIXED_ZIP_TIME = (2000, 1, 1, 0, 0, 0)


class WorkspaceWriteError(ValueError):
    """Raised when a requested schema-v2 output cannot be represented."""


def strip_sources(value: Any) -> Any:
    """Remove format-local source traces before portable serialization."""
    if isinstance(value, dict):
        return {
            key: strip_sources(item)
            for key, item in value.items()
            if key != "source_location"
            and not (
                key == "source"
                and isinstance(item, dict)
                and "kind" in item
                and "path" in item
            )
        }
    if isinstance(value, list):
        return [strip_sources(item) for item in value]
    return value


def workspace_payload(workspace: ArchitectureWorkspace) -> dict[str, Any]:
    """Return a portable source-free workspace payload."""
    payload = workspace.model_dump(
        mode="json",
        exclude={"title", "presentation"},
        exclude_none=True,
    )
    return cast(
        "dict[str, Any]",
        strip_sources(payload),
    )


def complete_state_workspace(state: CompleteState) -> dict[str, Any]:
    """Return one complete state in the portable schema-v2 workspace envelope."""
    return {
        "schema_version": 2,
        "states": [strip_sources(state.model_dump(mode="json", exclude_none=True))],
        "changes": [],
        "roadmaps": [],
        "views": [],
        "diagrams": [],
    }


def _atomic_text_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False, prefix=f".{path.name}."
    ) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.replace(path)


def _write_yaml_payload(path: Path, payload: dict[str, Any]) -> None:
    _atomic_text_write(
        path,
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
    )


def _format_excel_value(*, header: str, value: Any) -> Any:
    if header in {
        "default_selection",
        "expected",
        "presentation",
        "properties",
        "state_extensions",
        "state_properties",
        "style",
        "themes",
        "tables",
        "variants",
    } or isinstance(value, dict):
        return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    if isinstance(value, list):
        if any(isinstance(item, (dict, list)) for item in value):
            return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
        return "[" + ";".join(str(item) for item in value) + "]"
    return value


def _add_sheet(
    *,
    workbook: Workbook,
    name: str,
    rows: list[dict[str, Any]],
    fallback_headers: list[str],
) -> None:
    worksheet = workbook.create_sheet(name)
    headers = list(fallback_headers)
    for row in rows:
        for key in row:
            if key not in headers:
                headers.append(key)
    worksheet.append(headers)
    for row in rows:
        worksheet.append(
            [
                _format_excel_value(header=header, value=row.get(header))
                if row.get(header) is not None
                else None
                for header in headers
            ]
        )


def _entity_row(
    *,
    entity: Any,
    change_id: str | None = None,
    state_id: str | None = None,
    state_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row = cast(
        "dict[str, Any]",
        strip_sources(entity.model_dump(mode="json", exclude_none=True)),
    )
    if change_id is not None:
        row = {"change": change_id, **row}
    elif state_id is not None:
        row = {"state": state_id, **(state_metadata or {}), **row}
    return row


def _excel_rows(workspace: ArchitectureWorkspace) -> dict[str, list[dict[str, Any]]]:
    if len(workspace.states) != 1:
        raise WorkspaceWriteError(
            "Compact Excel workspaces require exactly one complete base state"
        )
    state = workspace.states[0]
    state_extensions = dict(state.model_extra or {})
    base_entity_count = sum(
        len(items)
        for items in (
            state.systems,
            state.applications,
            state.components,
            state.interfaces,
            state.users,
            state.relationships,
        )
    )
    if base_entity_count == 0 and (
        state.name or state.description or state.properties or state_extensions
    ):
        raise WorkspaceWriteError(
            "An empty Excel state cannot store state metadata in domain sheets"
        )
    state_metadata = {
        key: value
        for key, value in {
            "state_name": state.name,
            "state_description": state.description,
            "state_properties": state.properties or None,
            "state_extensions": state_extensions or None,
        }.items()
        if value is not None
    }

    rows: dict[str, list[dict[str, Any]]] = {
        "change": [],
        "roadmap": [],
        "view": [],
        "diagram": [],
        "sys": [
            _entity_row(entity=item, state_id=state.id, state_metadata=state_metadata)
            for item in state.systems
        ],
        "app": [
            _entity_row(entity=item, state_id=state.id, state_metadata=state_metadata)
            for item in state.applications
        ],
        "cmp": [
            _entity_row(entity=item, state_id=state.id, state_metadata=state_metadata)
            for item in state.components
        ],
        "interface": [
            _entity_row(entity=item, state_id=state.id, state_metadata=state_metadata)
            for item in state.interfaces
        ],
        "usr": [
            _entity_row(entity=item, state_id=state.id, state_metadata=state_metadata)
            for item in state.users
        ],
    }
    rows["interface"].extend(
        {
            "entity_kind": "relationship",
            **_entity_row(entity=item, state_id=state.id, state_metadata=state_metadata),
        }
        for item in state.relationships
    )
    patch_mapping = {
        "systems": "sys",
        "applications": "app",
        "components": "cmp",
        "interfaces": "interface",
        "users": "usr",
        "relationships": "interface",
    }
    for change in workspace.changes:
        change_row = cast(
            "dict[str, Any]",
            strip_sources(
                change.model_dump(
                    mode="json",
                    exclude={"patches", "source"},
                    exclude_none=True,
                )
            ),
        )
        rows["change"].append(change_row)
        for field, sheet in patch_mapping.items():
            for patch in cast("list[Any]", getattr(change.patches, field)):
                patch_row = _entity_row(entity=patch, change_id=change.id)
                if field == "relationships":
                    patch_row = {"entity_kind": "relationship", **patch_row}
                rows[sheet].append(patch_row)
    for roadmap in workspace.roadmaps:
        roadmap_extra = dict(roadmap.model_extra or {})
        for item in roadmap.items:
            rows["roadmap"].append(
                {
                    "roadmap": roadmap.id,
                    "roadmap_name": roadmap.name,
                    "base": roadmap.base,
                    "change": item.change,
                    "order": item.order,
                    **roadmap_extra,
                }
            )
    rows["view"] = [
        cast(
            "dict[str, Any]",
            strip_sources(item.model_dump(mode="json", exclude_none=True)),
        )
        for item in workspace.views
    ]
    rows["diagram"] = [
        cast(
            "dict[str, Any]",
            strip_sources(item.model_dump(mode="json", exclude_none=True)),
        )
        for item in workspace.diagrams
    ]
    return rows


def _normalize_xlsx(path: Path) -> None:
    with NamedTemporaryFile(dir=path.parent, delete=False, suffix=path.suffix) as handle:
        normalized = Path(handle.name)
    try:
        with (
            zipfile.ZipFile(path, "r") as source,
            zipfile.ZipFile(
                normalized,
                "w",
                compression=zipfile.ZIP_DEFLATED,
                compresslevel=9,
            ) as destination,
        ):
            for original in sorted(source.infolist(), key=lambda item: item.filename):
                info = zipfile.ZipInfo(original.filename, _FIXED_ZIP_TIME)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = original.external_attr
                info.create_system = original.create_system
                with source.open(original) as source_entry, destination.open(info, "w") as target:
                    while chunk := source_entry.read(1024 * 1024):
                        target.write(chunk)
        normalized.replace(path)
    finally:
        normalized.unlink(missing_ok=True)


def _write_excel_workspace(path: Path, workspace: ArchitectureWorkspace) -> None:
    try:
        from openpyxl import Workbook
    except ImportError as exc:  # pragma: no cover - optional dependency guard
        raise WorkspaceWriteError("openpyxl is required for Excel architecture output") from exc

    rows = _excel_rows(workspace)
    workbook = Workbook()
    active = workbook.active
    if active is not None:
        workbook.remove(active)
    fixed = datetime(2000, 1, 1)
    workbook.properties.created = fixed
    workbook.properties.modified = fixed
    headers = {
        "change": ["id", "name"],
        "roadmap": ["roadmap", "base", "change", "order"],
        "view": ["id", "name"],
        "diagram": ["id", "name", "kind"],
        "sys": ["state", "change", "id", "name"],
        "app": ["state", "change", "id", "name", "system"],
        "cmp": ["state", "change", "id", "name", "application"],
        "interface": ["state", "change", "entity_kind", "id", "name"],
        "usr": ["state", "change", "id", "name"],
    }
    for sheet in (
        "change",
        "roadmap",
        "view",
        "diagram",
        "sys",
        "app",
        "cmp",
        "interface",
        "usr",
    ):
        _add_sheet(
            workbook=workbook,
            name=sheet,
            rows=rows[sheet],
            fallback_headers=headers[sheet],
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=path.parent, delete=False, suffix=path.suffix) as handle:
        temporary = Path(handle.name)
    try:
        workbook.save(temporary)
        temporary.replace(path)
        _normalize_xlsx(path)
    finally:
        workbook.close()
        temporary.unlink(missing_ok=True)


def write_workspace(*, path: Path, workspace: ArchitectureWorkspace) -> str:
    """Write a complete workspace and return its SHA-256 content hash."""
    suffix = path.suffix.lower()
    if suffix in {".yaml", ".yml"}:
        _write_yaml_payload(path, workspace_payload(workspace))
    elif suffix in {".xlsx", ".xlsm"}:
        _write_excel_workspace(path, workspace)
    else:
        raise WorkspaceWriteError(f"Unsupported workspace output format: {path}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_complete_state(*, path: Path, state: CompleteState) -> str:
    """Write one complete YAML/Excel state and return its SHA-256 hash."""
    from .models import ArchitectureWorkspace

    workspace = ArchitectureWorkspace.model_validate(complete_state_workspace(state))
    return write_workspace(path=path, workspace=workspace)


def write_derived_change(*, path: Path, change: Change) -> str:
    """Write one derived sparse change as deterministic YAML."""
    if path.suffix.lower() not in {".yaml", ".yml"}:
        raise WorkspaceWriteError("Derived changes currently require a YAML destination")
    payload = {
        "schema_version": 2,
        "states": [],
        "changes": [strip_sources(change.model_dump(mode="json", exclude_none=True))],
        "roadmaps": [],
        "views": [],
        "diagrams": [],
    }
    _write_yaml_payload(path, payload)
    return hashlib.sha256(path.read_bytes()).hexdigest()
