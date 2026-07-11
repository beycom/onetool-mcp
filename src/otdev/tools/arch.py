"""Architecture workflow tools for Excel ingestion, validation, generation, and bundling."""

from __future__ import annotations

pack = "arch"

__ot_requires__ = {
    "cli": [("d2", "brew install d2")],
}

__all__ = ["bundle_solution", "export_yaml", "generate", "import_yaml", "validate"]

import re
import shlex
import shutil
import subprocess
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined, TemplateError

from otdev.tools._arch.bundle import BundleError, bundle_solution_directory
from otdev.tools._arch.config import (
    ArchProfileConfig,
    ConfigResolutionError,
    RenderTargetConfig,
    get_active_profile,
    get_arch_config,
    resolve_output_dir,
    resolve_project_diagram_template_path_for_profile,
    resolve_render_target_for_profile,
    resolve_report_template_paths_for_profile,
    resolve_system_diagram_template_path_for_profile,
)
from otdev.tools._arch.drawio import (
    build_mxfile as _build_mxfile,
)
from otdev.tools._arch.drawio import (
    extract_geometry as _extract_geometry,
)
from otdev.tools._arch.drawio import (
    inject_content as _inject_content,
)
from otdev.tools._arch.exporters import (
    apply_tag_filters,
    serializable_entities,
)
from otdev.tools._arch.ingest import IngestError, ingest_input
from otdev.tools._arch.models import (
    DEFAULT_LIST_CELL_SEPARATOR,
    MODEL_VERSION,
    MissingDependencyError,
    first_value,
)
from otdev.tools._arch.roundtrip import (
    RoundtripError,
    export_entities_to_yaml,
    import_yaml_into_template,
    load_yaml_entities,
)
from otdev.tools._arch.system_model import (
    LEVEL_APP as _LEVEL_APP,
)
from otdev.tools._arch.system_model import (
    LEVEL_CMP as _LEVEL_CMP,
)
from otdev.tools._arch.system_model import (
    LEVEL_SYS as _LEVEL_SYS,
)
from otdev.tools._arch.system_model import (
    build_entity_graph as _build_entity_graph,
)
from otdev.tools._arch.system_model import (
    build_project_d2 as _build_project_d2,
)
from otdev.tools._arch.system_model import (
    build_project_view as _build_project_view,
)
from otdev.tools._arch.system_model import (
    build_solution_index_context as _build_solution_index_context,
)
from otdev.tools._arch.system_model import (
    build_solution_project_context as _build_solution_project_context,
)
from otdev.tools._arch.system_model import (
    build_solution_system_context as _build_solution_system_context,
)
from otdev.tools._arch.system_model import (
    build_system_d2 as _build_system_d2,
)
from otdev.tools._arch.system_model import (
    build_system_view as _build_system_view,
)
from otdev.tools._arch.system_model import (
    first_tag_value as _first_tag_value,
)
from otdev.tools._arch.system_model import (
    is_external_system as _is_external_system,
)
from otdev.tools._arch.system_model import (
    project_page_name as _project_page_name,
)
from otdev.tools._arch.system_model import (
    project_stage_ids as _project_stage_ids,
)
from otdev.tools._arch.system_model import (
    render_markdown as _render_markdown,
)
from otdev.tools._arch.system_model import (
    safe_output_fragment as _safe_output_fragment,
)
from otdev.tools._arch.system_model import (
    svg_markup as _svg_markup,
)
from otdev.tools._arch.system_model import (
    system_page_name as _system_page_name,
)
from otdev.tools._arch.validate import validate_entities
from otpack import LogSpan, resolve_cwd_path

_SAFE_ID_FRAGMENT_RE = re.compile(r"^[A-Za-z0-9._-]+$")
_UNSAFE_PATH_CHARS_RE = re.compile(r"[;\|&`$<>\r\n]")
_MAX_RENDER_WORKERS = 6
# Per-render subprocess timeout: a hung engine must not block the tool call
# (or the render ThreadPool) indefinitely.
_RENDER_TIMEOUT_SECONDS = 60


@dataclass(slots=True)
class _WorkbookDiagramSpec:
    system_id: str
    name: str
    description: str
    source_value: str
    source_path: Path
    row_number: int


def _error_payload(
    *, operation: str, code: str, message: str, details: dict[str, Any] | None = None
) -> dict[str, Any]:
    return {
        "ok": False,
        "operation": operation,
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
        },
    }


def _resolve_drawio_export_toggle(profile_data: dict[str, Any]) -> bool:
    """Read the `drawio_export` profile `data` toggle (design D10): `data`
    is a free-form mapping (`ArchProfileConfig.data`, `extra="forbid"` does
    not apply to its contents), so the flag is read with an explicit type
    check here rather than a typed config field. Defaults to enabled; a
    non-boolean value fails generation fast with `ConfigResolutionError`
    rather than being silently coerced (spec 'Invalid value rejected')."""
    value = profile_data.get("drawio_export", True)
    if not isinstance(value, bool):
        raise ConfigResolutionError(
            f"tools.arch.profiles.<name>.data.drawio_export must be a boolean, got {value!r}"
        )
    return value


def _resolve_generation_profile(
    *,
    config: Any,
    profile: str | None,
    profile_yaml: str | None,
) -> tuple[str, ArchProfileConfig]:
    if profile_yaml is not None and profile is not None:
        raise ConfigResolutionError("arch.generate accepts only one of profile or profile_yaml")

    if profile_yaml is not None:
        if not profile_yaml.strip():
            raise ConfigResolutionError("profile_yaml must be a non-empty YAML string")
        try:
            parsed = yaml.safe_load(profile_yaml)
        except yaml.YAMLError as exc:
            raise ConfigResolutionError(f"Invalid profile_yaml: {exc}") from exc
        if not isinstance(parsed, dict):
            raise ConfigResolutionError("profile_yaml must define a YAML mapping for ArchProfileConfig")
        try:
            resolved_profile = ArchProfileConfig.model_validate(parsed)
        except Exception as exc:
            raise ConfigResolutionError(f"Invalid profile_yaml profile config: {exc}") from exc
        return "profile_yaml", resolved_profile

    return get_active_profile(config=config, profile=profile)


def _now_timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _resolve_list_cell_separator() -> str:
    """Resolve the configured list-cell separator, falling back to the default.

    Kept resilient (never raises) so validate/round-trip do not fail on unrelated
    profile-config errors that generate() would otherwise surface.
    """
    try:
        return get_arch_config().list_cell_separator
    except ConfigResolutionError:
        return DEFAULT_LIST_CELL_SEPARATOR


def _validate_system_id_fragment(*, value: str, field: str, sheet: str, row: int) -> dict[str, Any] | None:
    if not value:
        return None
    if _SAFE_ID_FRAGMENT_RE.fullmatch(value):
        return None
    return {
        "code": "invalid_value",
        "message": f"{sheet} row has invalid {field} '{value}'. Allowed characters: letters, numbers, '.', '_', '-'.",
        "details": {
            "sheet": sheet,
            "row": row,
            "field": field,
            "value": value,
        },
    }


def _validate_path_fragment(*, value: str, field: str, sheet: str, row: int) -> dict[str, Any] | None:
    if not value:
        return None
    if _UNSAFE_PATH_CHARS_RE.search(value):
        return {
            "code": "invalid_value",
            "message": f"{sheet} row has unsafe characters in {field}.",
            "details": {
                "sheet": sheet,
                "row": row,
                "field": field,
                "value": value,
            },
        }
    return None


def _clean_diagram_rows(*, entities: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    cleaned: list[dict[str, Any]] = []
    for row in entities.get("diagram", []):
        cleaned.append({k: v for k, v in row.items() if not str(k).startswith("_")})
    return cleaned


def _collect_workbook_diagram_specs(
    *,
    entities: dict[str, list[dict[str, Any]]],
) -> tuple[list[_WorkbookDiagramSpec], dict[str, list[dict[str, Any]]]]:
    errors: list[dict[str, Any]] = []
    specs: list[_WorkbookDiagramSpec] = []

    allowed_system_ids = {
        str(row.get("id", "")).strip()
        for row in entities.get("sys", [])
        if str(row.get("id", "")).strip() and not _is_external_system(row)
    }

    for idx, row in enumerate(entities.get("diagram", []), start=1):
        row_errors_before = len(errors)
        row_number = int(row.get("_sheet_row", idx + 1))
        sys_id = str(first_value(row, ("sys", "system", "system_id", "sys_id")) or "").strip()
        source_value = str(first_value(row, ("file", "source", "path")) or "").strip()
        workbook_value = str(row.get("_source_file") or "").strip()

        if not sys_id:
            errors.append(
                {
                    "code": "missing_required_field",
                    "message": "Diagram row is missing system reference",
                    "details": {"sheet": "diagram", "row": row_number, "field": "sys"},
                }
            )
        elif sys_id not in allowed_system_ids:
            errors.append(
                {
                    "code": "invalid_reference",
                    "message": f"Diagram row references unknown or external system '{sys_id}'",
                    "details": {"sheet": "diagram", "row": row_number, "field": "sys", "value": sys_id},
                }
            )
        else:
            system_id_issue = _validate_system_id_fragment(
                value=sys_id,
                field="sys",
                sheet="diagram",
                row=row_number,
            )
            if system_id_issue:
                errors.append(system_id_issue)

        if not source_value:
            errors.append(
                {
                    "code": "missing_required_field",
                    "message": "Diagram row is missing file path",
                    "details": {"sheet": "diagram", "row": row_number, "field": "file"},
                }
            )
            continue
        path_issue = _validate_path_fragment(
            value=source_value,
            field="file",
            sheet="diagram",
            row=row_number,
        )
        if path_issue:
            errors.append(path_issue)
            continue

        if not workbook_value:
            errors.append(
                {
                    "code": "invalid_reference",
                    "message": "Diagram row is missing workbook source metadata",
                    "details": {"sheet": "diagram", "row": row_number, "field": "_source_file"},
                }
            )
            continue

        workbook_path = Path(workbook_value).resolve()
        workbook_dir = workbook_path.parent
        source_path = (workbook_dir / source_value).resolve()
        if not source_path.is_relative_to(workbook_dir):
            errors.append(
                {
                    "code": "invalid_reference",
                    "message": f"Diagram file must be inside the workbook directory: {source_value}",
                    "details": {
                        "sheet": "diagram",
                        "row": row_number,
                        "field": "file",
                        "value": source_value,
                        "resolved_path": str(source_path),
                    },
                }
            )
            continue
        if not source_path.is_file():
            errors.append(
                {
                    "code": "invalid_reference",
                    "message": f"Diagram source file not found: {source_value}",
                    "details": {
                        "sheet": "diagram",
                        "row": row_number,
                        "field": "file",
                        "value": source_value,
                        "resolved_path": str(source_path),
                    },
                }
            )
            continue

        # A row with any recorded error (e.g. an invalid system reference
        # above) must not produce a spec.
        if len(errors) > row_errors_before:
            continue

        name = str(first_value(row, ("name", "title")) or source_path.stem).strip() or source_path.stem
        description = str(first_value(row, ("description", "desc", "summary")) or "").strip()
        specs.append(
            _WorkbookDiagramSpec(
                system_id=sys_id,
                name=name,
                description=description,
                source_value=source_value,
                source_path=source_path,
                row_number=row_number,
            )
        )

    return specs, {"errors": errors, "warnings": []}


def _build_model_payload(
    *,
    entities: dict[str, list[dict[str, Any]]],
    diagrams: list[dict[str, Any]],
    include_tags: list[str] | None,
    exclude_tags: list[str] | None,
) -> dict[str, Any]:
    return {
        "model": {
            "version": MODEL_VERSION,
            "generated_at": _now_timestamp(),
        },
        "entities": serializable_entities(entities=entities),
        "diagrams": diagrams,
        "filters": {
            "include_tags": include_tags or [],
            "exclude_tags": exclude_tags or [],
        },
    }


def _build_render_context(
    *,
    target_config: RenderTargetConfig,
    input_path: str,
    output_path: str,
    work_dir: str,
) -> dict[str, Any]:
    """Build the context `_execute_render_engine` consumes: the render paths
    plus `profile_data` for the command template."""
    return {
        "profile_data": dict(target_config.profile.data),
        "paths": {
            "input": input_path,
            "output": output_path,
            "work_dir": work_dir,
        },
    }


def _template_context(
    *,
    base_context: dict[str, Any],
    model_payload: dict[str, Any],
    profile_data: dict[str, Any],
) -> dict[str, Any]:
    """Build strict template context with explicit page fields + model + profile_data."""
    merged = dict(base_context)
    merged["model"] = model_payload
    merged["profile_data"] = dict(profile_data)
    return merged


def _execute_render_engine(
    *,
    target_config: RenderTargetConfig,
    render_context: dict[str, Any],
) -> tuple[bool, dict[str, Any]]:
    input_path = str(render_context["paths"]["input"])
    output_path = str(render_context["paths"]["output"])
    for field_name, field_value in (("input", input_path), ("output", output_path)):
        if _UNSAFE_PATH_CHARS_RE.search(field_value):
            return False, {
                "code": "invalid_path_fragment",
                "message": f"Render {field_name} path contains unsafe characters.",
                "details": {
                    "target": target_config.target,
                    "field": field_name,
                    "value": field_value,
                },
            }

    try:
        env = Environment(undefined=StrictUndefined, autoescape=False)
        # shlex-quote the paths so spaces (and quotes) survive the
        # shlex.split below; the default `d2 {{ input }} {{ output }}`
        # template interpolates them bare.
        render_vars: dict[str, Any] = {
            "input": shlex.quote(input_path),
            "output": shlex.quote(output_path),
            "profile_data": dict(render_context.get("profile_data", {})),
        }
        cmd = env.from_string(target_config.cmd_template).render(
            **render_vars,
        )
    except TemplateError as exc:
        return False, {
            "code": "template_variable_error",
            "message": f"Invalid command template for target '{target_config.target}': {exc}",
            "details": {
                "target": target_config.target,
                "engine": target_config.engine_name,
                "template": target_config.cmd_template,
            },
        }
    try:
        argv = shlex.split(cmd)
    except ValueError as exc:
        return False, {
            "code": "invalid_engine_command",
            "message": f"Invalid rendered command for target '{target_config.target}': {exc}",
            "details": {
                "target": target_config.target,
                "engine": target_config.engine_name,
                "command": cmd,
            },
        }
    if not argv:
        return False, {
            "code": "invalid_engine_command",
            "message": f"Rendered command for target '{target_config.target}' is empty.",
            "details": {
                "target": target_config.target,
                "engine": target_config.engine_name,
                "template": target_config.cmd_template,
            },
        }

    try:
        process = subprocess.run(
            argv,
            shell=False,
            check=False,
            capture_output=True,
            text=True,
            cwd=render_context["paths"]["work_dir"],
            timeout=_RENDER_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return False, {
            "code": "engine_command_timeout",
            "message": (
                f"Render engine command timed out after {_RENDER_TIMEOUT_SECONDS}s "
                f"for target '{target_config.target}'."
            ),
            "details": {
                "target": target_config.target,
                "engine": target_config.engine_name,
                "command": " ".join(shlex.quote(part) for part in argv),
                "timeout_seconds": _RENDER_TIMEOUT_SECONDS,
            },
        }
    except FileNotFoundError as exc:
        command_name = argv[0]
        if command_name == "d2":
            message = (
                f"Render engine command '{command_name}' is not installed for target "
                f"'{target_config.target}'. Install D2 CLI: https://github.com/terrastruct/d2"
            )
        else:
            message = (
                f"Render engine command '{command_name}' is not installed for target "
                f"'{target_config.target}'."
            )
        return False, {
            "code": "engine_command_not_found",
            "message": message,
            "details": {
                "target": target_config.target,
                "engine": target_config.engine_name,
                "command": " ".join(shlex.quote(part) for part in argv),
                "error": str(exc),
            },
        }
    if process.returncode != 0:
        return False, {
            "code": "engine_command_failed",
            "message": f"Render engine command failed for target '{target_config.target}'.",
            "details": {
                "target": target_config.target,
                "engine": target_config.engine_name,
                "command": " ".join(shlex.quote(part) for part in argv),
                "exit_code": process.returncode,
                "stdout": process.stdout,
                "stderr": process.stderr,
            },
        }
    return True, {
        "target": target_config.target,
        "engine": target_config.engine_name,
        "command": " ".join(shlex.quote(part) for part in argv),
    }


def _execute_render_jobs(
    *,
    jobs: list[tuple[int, RenderTargetConfig, dict[str, Any]]],
    max_workers: int,
) -> tuple[bool, Any]:
    """Run render jobs concurrently and return results indexed by input order."""
    if not jobs:
        return True, {}

    worker_count = max(1, min(max_workers, len(jobs)))
    results: dict[int, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        future_map = {
            executor.submit(
                _execute_render_engine,
                target_config=target_config,
                render_context=render_context,
            ): idx
            for idx, target_config, render_context in jobs
        }

        for future in as_completed(future_map):
            idx = future_map[future]
            ok, render_result = future.result()
            if not ok:
                for pending in future_map:
                    if not pending.done():
                        pending.cancel()
                return False, render_result
            results[idx] = render_result

    return True, results


def _unsafe_id_error(
    *,
    entities: dict[str, list[dict[str, Any]]],
    issue: dict[str, Any],
    message: str,
) -> dict[str, Any]:
    """Full validation-failed payload for an id that is unsafe as an output-path fragment."""
    return {
        **_error_payload(
            operation="generate",
            code="validation_failed",
            message=message,
            details={"error_count": 1},
        ),
        "valid": False,
        "issues": {"errors": [issue], "warnings": []},
        "summary": {
            "counts": {sheet: len(rows) for sheet, rows in entities.items()},
            "errors": 1,
            "warnings": 0,
        },
    }


def _render_view_diagrams(
    *,
    outputs: list[tuple[str, Path, Path, dict[str, Any]]],
    jobs: list[tuple[int, RenderTargetConfig, dict[str, Any]]],
    drawio_export: bool,
    kind_label: str,
    kind_key: str,
    owner_key: str,
    owner_id: str,
    generated_files: list[str],
) -> tuple[dict[str, str] | None, dict[str, Any] | None]:
    """Render one page's diagram jobs, embed the draw.io model (D1/D2), and
    collect SVG markup per output key. Shared by the system (per-level) and
    project (per-stage) loops. Returns (svg_by_key, None) on success or
    (None, error_payload) on failure."""
    ok, render_result = _execute_render_jobs(jobs=jobs, max_workers=_MAX_RENDER_WORKERS)
    if not ok:
        return None, _error_payload(
            operation="generate",
            code=render_result["code"],
            message=render_result["message"],
            details=render_result["details"],
        )

    svg_by_key: dict[str, str] = {}
    for key, d2_path, svg_path, view in outputs:
        generated_files.append(str(d2_path))
        generated_files.append(str(svg_path))
        svg_text = svg_path.read_text(encoding="utf-8")
        if drawio_export:
            geometry = _extract_geometry(svg_text)
            mxfile_xml = _build_mxfile(
                user_nodes=view["user_nodes"],
                external_nodes=view["external_nodes"],
                system_blocks=view["system_blocks"],
                interface_edges=view["interface_edges"],
                geometry=geometry,
            )
            svg_text = _inject_content(svg_text, mxfile_xml)
            svg_path.write_text(svg_text, encoding="utf-8")
        svg_by_key[key] = _svg_markup(svg_text)
        if not svg_by_key[key]:
            return None, _error_payload(
                operation="generate",
                code="render_output_error",
                message=f"Rendered SVG for {kind_label} '{key}' is empty.",
                details={owner_key: owner_id, kind_key: key},
            )
    return svg_by_key, None


def _generate_solution(
    *,
    output_root: Path,
    entities: dict[str, list[dict[str, Any]]],
    diagram_specs: list[_WorkbookDiagramSpec],
    profile_name: str,
    profile: Any,
    model_payload: dict[str, Any],
    title: str | None,
    drawio_export: bool = True,
) -> dict[str, Any]:
    try:
        report_templates = resolve_report_template_paths_for_profile(profile=profile)
        system_diagram_template = resolve_system_diagram_template_path_for_profile(profile=profile)
        project_diagram_template = resolve_project_diagram_template_path_for_profile(profile=profile)
    except ConfigResolutionError as exc:
        return _error_payload(
            operation="generate",
            code="template_not_found",
            message=str(exc),
        )

    template_dirs = [
        str(report_templates.solution_report_path.parent),
        str(report_templates.system_report_path.parent),
        str(report_templates.project_report_path.parent),
    ]
    template_dirs = list(dict.fromkeys(template_dirs))
    template_dir = report_templates.solution_report_path.parent
    if not template_dir.is_dir():
        return _error_payload(
            operation="generate",
            code="template_not_found",
            message=f"Solution template path must be a directory: {template_dir}",
        )

    env = Environment(loader=FileSystemLoader(template_dirs), autoescape=True)

    solution_dir = output_root / "solution"
    # The solution directory is fully regenerated; clear stale outputs from prior runs.
    if solution_dir.is_dir():
        shutil.rmtree(solution_dir)
    solution_dir.mkdir(parents=True, exist_ok=True)
    images_dir = solution_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    try:
        render_target = resolve_render_target_for_profile(
            target="solution",
            profile_name=profile_name,
            profile=profile,
        )
    except ConfigResolutionError as exc:
        return _error_payload(
            operation="generate",
            code="invalid_config",
            message=str(exc),
        )

    styles_css = ""
    scripts_js = ""
    styles_path = template_dir / "styles.css"
    scripts_path = template_dir / "scripts.js"
    if styles_path.exists():
        styles_css = styles_path.read_text(encoding="utf-8")
    if scripts_path.exists():
        scripts_js = scripts_path.read_text(encoding="utf-8")

    graph = _build_entity_graph(entities=entities)
    diagram_result = _render_workbook_diagrams(
        output_root=output_root,
        profile_name=profile_name,
        profile=profile,
        diagram_specs=diagram_specs,
    )
    if not diagram_result["ok"]:
        return diagram_result
    extra_diagrams_by_system = diagram_result["by_system"]

    systems_list: list[dict[str, str]] = []
    projects_list: list[dict[str, str]] = []
    generated_files: list[str] = [*diagram_result["files"]]

    for sys_row in entities["sys"]:
        system_id = str(sys_row.get("id", "")).strip()
        if not system_id:
            continue
        if _is_external_system(sys_row):
            continue
        system_id_issue = _validate_system_id_fragment(
            value=system_id,
            field="id",
            sheet="sys",
            row=int(sys_row.get("_sheet_row", 0)),
        )
        if system_id_issue:
            return _unsafe_id_error(
                entities=entities,
                issue=system_id_issue,
                message="System id contains unsafe output-path characters",
            )

        systems_list.append(
            {
                "id": system_id,
                "name": str(sys_row.get("name") or system_id),
                "description": str(first_value(sys_row, ("description",)) or ""),
                "tag": _first_tag_value(sys_row),
            }
        )

        level_jobs: list[tuple[int, RenderTargetConfig, dict[str, Any]]] = []
        level_outputs: list[tuple[str, Path, Path, dict[str, Any]]] = []
        for idx, level in enumerate((_LEVEL_SYS, _LEVEL_APP, _LEVEL_CMP)):
            # Built once and reused for both the D2 source (below) and the
            # draw.io embedded model (after rendering, D1/D2): same render
            # context, so the two representations never drift apart.
            system_view = _build_system_view(
                system_id=system_id,
                level=level,
                entities=entities,
                graph=graph,
                profile_data=profile.data,
            )
            d2_text = _build_system_d2(
                system_id=system_id,
                level=level,
                entities=entities,
                graph=graph,
                template_path=system_diagram_template,
                profile_data=profile.data,
                system_view=system_view,
            )
            d2_path = images_dir / f"{system_id}-{level}.d2"
            svg_path = images_dir / f"{system_id}-{level}.svg"
            d2_path.write_text(d2_text, encoding="utf-8")
            render_context = _build_render_context(
                target_config=render_target,
                input_path=str(d2_path),
                output_path=str(svg_path),
                work_dir=str(output_root),
            )
            level_outputs.append((level, d2_path, svg_path, system_view))
            level_jobs.append((idx, render_target, render_context))

        rendered_svgs, render_error = _render_view_diagrams(
            outputs=level_outputs,
            jobs=level_jobs,
            drawio_export=drawio_export,
            kind_label="level",
            kind_key="level",
            owner_key="system_id",
            owner_id=system_id,
            generated_files=generated_files,
        )
        if render_error is not None or rendered_svgs is None:
            return render_error or _error_payload(
                operation="generate",
                code="render_output_error",
                message="Rendering produced no output.",
            )
        svg_by_level = rendered_svgs

        base_context = _build_solution_system_context(
            system_id=system_id,
            entities=entities,
            graph=graph,
            svg_by_level=svg_by_level,
            workbook_diagrams=extra_diagrams_by_system.get(system_id, []),
            drawio_export=drawio_export,
        )
        base_context.update(
            {
                "styles": styles_css,
                "scripts": scripts_js,
                "generated_at": _now_timestamp(),
            }
        )
        context = _template_context(
            base_context=base_context,
            model_payload=model_payload,
            profile_data=profile.data,
        )

        system_template = env.get_template(report_templates.system_report_path.name)
        system_html = system_template.render(**context)
        system_html_path = solution_dir / _system_page_name(system_id)
        system_html_path.write_text(system_html, encoding="utf-8")
        generated_files.append(str(system_html_path))

    systems_list.sort(key=lambda item: item["name"].lower())

    for project_row in entities.get("project", []):
        project_id = str(project_row.get("id", "")).strip()
        if not project_id:
            continue
        project_id_issue = _validate_system_id_fragment(
            value=project_id,
            field="id",
            sheet="project",
            row=int(project_row.get("_sheet_row", 0)),
        )
        if project_id_issue:
            return _unsafe_id_error(
                entities=entities,
                issue=project_id_issue,
                message="Project id contains unsafe output-path characters",
            )

        project_name = str(project_row.get("name") or project_id)
        projects_list.append(
            {
                "id": project_id,
                "name": project_name,
                "description": str(first_value(project_row, ("description",)) or ""),
                "tag": _first_tag_value(project_row),
                "href": _project_page_name(project_id),
            }
        )

        stage_jobs: list[tuple[int, RenderTargetConfig, dict[str, Any]]] = []
        stage_outputs: list[tuple[str, Path, Path, dict[str, Any]]] = []
        for idx, stage in enumerate(_project_stage_ids(project_id=project_id, entities=entities)):
            safe_stage = _safe_output_fragment(stage)
            # Built once and reused for both the D2 source (below) and the
            # draw.io embedded model (after rendering, D1/D2): same render
            # context, so the two representations never drift apart.
            project_view = _build_project_view(
                project_id=project_id,
                stage=stage,
                entities=entities,
                graph=graph,
                profile_data=profile.data,
            )
            d2_text = _build_project_d2(
                project_id=project_id,
                stage=stage,
                entities=entities,
                graph=graph,
                template_path=project_diagram_template,
                profile_data=profile.data,
                project_view=project_view,
            )
            d2_path = images_dir / f"project-{project_id}-{safe_stage}.d2"
            svg_path = images_dir / f"project-{project_id}-{safe_stage}.svg"
            d2_path.write_text(d2_text, encoding="utf-8")
            render_context = _build_render_context(
                target_config=render_target,
                input_path=str(d2_path),
                output_path=str(svg_path),
                work_dir=str(output_root),
            )
            stage_outputs.append((stage, d2_path, svg_path, project_view))
            stage_jobs.append((idx, render_target, render_context))

        rendered_svgs, render_error = _render_view_diagrams(
            outputs=stage_outputs,
            jobs=stage_jobs,
            drawio_export=drawio_export,
            kind_label="project stage",
            kind_key="stage",
            owner_key="project_id",
            owner_id=project_id,
            generated_files=generated_files,
        )
        if render_error is not None or rendered_svgs is None:
            return render_error or _error_payload(
                operation="generate",
                code="render_output_error",
                message="Rendering produced no output.",
            )
        svg_by_stage = rendered_svgs

        base_context = _build_solution_project_context(
            project_id=project_id,
            entities=entities,
            graph=graph,
            svg_by_stage=svg_by_stage,
            drawio_export=drawio_export,
        )
        base_context.update(
            {
                "styles": styles_css,
                "scripts": scripts_js,
                "generated_at": _now_timestamp(),
            }
        )
        context = _template_context(
            base_context=base_context,
            model_payload=model_payload,
            profile_data=profile.data,
        )

        project_template = env.get_template(report_templates.project_report_path.name)
        project_html = project_template.render(**context)
        project_html_path = solution_dir / _project_page_name(project_id)
        project_html_path.write_text(project_html, encoding="utf-8")
        generated_files.append(str(project_html_path))

    projects_list.sort(key=lambda item: item["name"].lower())

    index_template = env.get_template(report_templates.solution_report_path.name)
    solution_title = title.strip() if title and title.strip() else "Architecture Solution"
    # Card-grid behavior (systems_list/projects_list above) is unchanged; the
    # index summary cards and global entity tables (D7) are additive.
    index_extra_context = _build_solution_index_context(entities=entities, graph=graph)
    index_base_context: dict[str, Any] = {
        "title": solution_title,
        "systems": systems_list,
        "projects": projects_list,
        "styles": styles_css,
        "scripts": scripts_js,
        "generated_at": _now_timestamp(),
        "is_index": True,
        **index_extra_context,
    }
    index_context = _template_context(
        base_context=index_base_context,
        model_payload=model_payload,
        profile_data=profile.data,
    )
    index_html = index_template.render(**index_context)
    index_path = solution_dir / "index.html"
    index_path.write_text(index_html, encoding="utf-8")
    generated_files.insert(0, str(index_path))

    return {
        "ok": True,
        "files": generated_files,
    }


def _render_workbook_diagrams(
    *,
    output_root: Path,
    profile_name: str,
    profile: ArchProfileConfig,
    diagram_specs: list[_WorkbookDiagramSpec],
) -> dict[str, Any]:
    if not diagram_specs:
        return {"ok": True, "files": [], "by_system": {}}

    try:
        target_config = resolve_render_target_for_profile(
            target="diagram",
            profile_name=profile_name,
            profile=profile,
        )
    except ConfigResolutionError as exc:
        return _error_payload(
            operation="generate",
            code="invalid_config",
            message=str(exc),
        )

    diagram_dir = output_root / "solution" / "images"
    diagram_dir.mkdir(parents=True, exist_ok=True)
    generated_files: list[str] = []
    by_system: dict[str, list[dict[str, str]]] = {}

    # spec.system_id was already fragment-validated by
    # _collect_workbook_diagram_specs; generation aborts before this point
    # when any diagram row carries an error.
    prepared: list[tuple[_WorkbookDiagramSpec, int, str, Path]] = []
    for idx, spec in enumerate(diagram_specs, start=1):
        safe_name = re.sub(r"[^a-zA-Z0-9._-]+", "-", Path(spec.source_value).stem).strip("-")
        if not safe_name:
            safe_name = f"diagram-{idx}"
        svg_name = f"{spec.system_id}-{idx:02d}-{safe_name}.svg"
        output_path = diagram_dir / svg_name
        prepared.append((spec, idx, svg_name, output_path))

    jobs: list[tuple[int, RenderTargetConfig, dict[str, Any]]] = []
    for job_idx, (spec, _, _, output_path) in enumerate(prepared):
        render_context = _build_render_context(
            target_config=target_config,
            input_path=str(spec.source_path),
            output_path=str(output_path),
            work_dir=str(output_root),
        )
        jobs.append((job_idx, target_config, render_context))

    ok, render_result = _execute_render_jobs(
        jobs=jobs,
        max_workers=_MAX_RENDER_WORKERS,
    )
    if not ok:
        return _error_payload(
            operation="generate",
            code=render_result["code"],
            message=render_result["message"],
            details=render_result["details"],
        )

    for spec, _, svg_name, output_path in prepared:
        generated_files.append(str(output_path))
        diagram_markup = _svg_markup(output_path.read_text(encoding="utf-8"))
        by_system.setdefault(spec.system_id, []).append(
            {
                "name": spec.name,
                "description": _render_markdown(spec.description),
                "source": str(spec.source_path),
                "svg": diagram_markup,
                "svg_path": f"images/{svg_name}",
            }
        )

        if not diagram_markup:
            return _error_payload(
                operation="generate",
                code="render_output_error",
                message="Rendered workbook diagram SVG is empty.",
                details={"system_id": spec.system_id, "source": str(spec.source_path)},
            )

    return {"ok": True, "files": generated_files, "by_system": by_system}


def validate(*, input_path: str) -> dict[str, Any]:
    """Validate architecture workbook input.

    Args:
        input_path: Workbook file, directory, or glob path.

    Returns:
        Structured validation payload with summary and issues.
    """
    with LogSpan(span="arch.validate", inputPath=input_path) as span:
        try:
            workbooks, entities, _passthrough = ingest_input(
                input_path=input_path,
                list_cell_separator=_resolve_list_cell_separator(),
            )
            validation = validate_entities(entities=entities)
            payload: dict[str, Any] = {
                "ok": validation["valid"],
                "operation": "validate",
                "input": {
                    "path": str(resolve_cwd_path(input_path)),
                    "workbooks": [str(path) for path in workbooks],
                },
                "valid": validation["valid"],
                "issues": validation["issues"],
                "summary": validation["summary"],
            }
            if not validation["valid"]:
                payload["error"] = {
                    "code": "validation_failed",
                    "message": "Validation found blocking issues",
                    "details": {
                        "error_count": validation["summary"]["errors"],
                    },
                }
            span.add(valid=validation["valid"], errorCount=validation["summary"]["errors"])
            return payload
        except (IngestError, MissingDependencyError, RoundtripError) as exc:
            span.add(error=str(exc))
            return _error_payload(
                operation="validate",
                code="ingest_error",
                message=str(exc),
                details={"input_path": input_path},
            )
        except Exception as exc:  # pragma: no cover - defensive
            span.add(error=str(exc))
            return _error_payload(
                operation="validate",
                code="unexpected_error",
                message=str(exc),
                details={"traceback": traceback.format_exc(limit=5)},
            )


def generate(
    *,
    input_path: str,
    output_dir: str | None = None,
    profile: str | None = None,
    profile_yaml: str | None = None,
    title: str | None = None,
    include_tags: list[str] | None = None,
    exclude_tags: list[str] | None = None,
) -> dict[str, Any]:
    """Generate architecture outputs from workbook input.

    Args:
        input_path: Workbook file, directory, or glob path.
        output_dir: Output directory for generated files.
        profile: Profile override. Defaults to tools.arch.default_profile.
        profile_yaml: Inline YAML profile block for this run. Mutually exclusive with profile.
        title: Optional title for the generated solution index page.
        include_tags: Include-only tag filter.
        exclude_tags: Exclude tag filter.

    Returns:
        Structured generation payload with solution output files.
    """
    with LogSpan(
        span="arch.generate",
        inputPath=input_path,
        profile=profile or "<default>",
        profileYaml=bool(profile_yaml and profile_yaml.strip()),
    ) as span:
        try:
            config = get_arch_config()
        except ConfigResolutionError as exc:
            span.add(error=str(exc))
            return _error_payload(
                operation="generate",
                code="invalid_config",
                message=str(exc),
            )

        try:
            output_root = resolve_output_dir(output_dir=output_dir, config=config)
            workbooks, entities, _passthrough = ingest_input(
                input_path=input_path,
                list_cell_separator=config.list_cell_separator,
            )
            profile_name, active_profile = _resolve_generation_profile(
                config=config,
                profile=profile,
                profile_yaml=profile_yaml,
            )
            # Fail-fast (design D10): validate the drawio_export toggle at
            # generation start, before any output is written.
            drawio_export_enabled = _resolve_drawio_export_toggle(active_profile.data)
            filtered = apply_tag_filters(
                entities=entities,
                include_tags=include_tags,
                exclude_tags=exclude_tags,
            )
            validation = validate_entities(entities=filtered)
            if not validation["valid"]:
                span.add(valid=False, errorCount=validation["summary"]["errors"])
                return {
                    **_error_payload(
                        operation="generate",
                        code="validation_failed",
                        message="Validation failed; generation did not run",
                        details={"error_count": validation["summary"]["errors"]},
                    ),
                    "valid": False,
                    "issues": validation["issues"],
                    "summary": validation["summary"],
                }

            diagram_specs, diagram_issues = _collect_workbook_diagram_specs(entities=filtered)
            if diagram_issues["errors"]:
                return {
                    **_error_payload(
                        operation="generate",
                        code="validation_failed",
                        message="Diagram validation failed; generation did not run",
                        details={"error_count": len(diagram_issues["errors"])},
                    ),
                    "valid": False,
                    "issues": {
                        **validation["issues"],
                        "diagram": diagram_issues,
                    },
                    "summary": {
                        **validation["summary"],
                        "diagram_rows": len(filtered.get("diagram", [])),
                    },
                }

            model_payload = _build_model_payload(
                entities=filtered,
                diagrams=_clean_diagram_rows(entities=filtered),
                include_tags=include_tags,
                exclude_tags=exclude_tags,
            )
            solution_result = _generate_solution(
                output_root=output_root,
                entities=filtered,
                diagram_specs=diagram_specs,
                profile_name=profile_name,
                profile=active_profile,
                model_payload=model_payload,
                title=title,
                drawio_export=drawio_export_enabled,
            )
            if not solution_result["ok"]:
                return solution_result
            solution_files: list[str] = solution_result["files"]

            summary = {
                "formats": ["solution"],
                "generated_files": len(solution_files),
                "counts": validation["summary"]["counts"],
                "diagram_rows": len(filtered.get("diagram", [])),
                "model_version": MODEL_VERSION,
            }
            span.add(valid=True, profile=profile_name, generatedFiles=summary["generated_files"])
            return {
                "ok": True,
                "operation": "generate",
                "input": {
                    "path": str(resolve_cwd_path(input_path)),
                    "workbooks": [str(path) for path in workbooks],
                },
                "output_dir": str(output_root),
                "profile": profile_name,
                "filters": {
                    "include_tags": include_tags or [],
                    "exclude_tags": exclude_tags or [],
                },
                "files": {"solution": solution_files},
                "model": {"version": MODEL_VERSION},
                "summary": summary,
            }
        except (IngestError, MissingDependencyError, RoundtripError) as exc:
            span.add(error=str(exc))
            return _error_payload(
                operation="generate",
                code="ingest_error",
                message=str(exc),
                details={"input_path": input_path},
            )
        # Error-code scheme: "invalid_config" = tools.arch config itself is
        # invalid (get_arch_config, render-target resolution);
        # "template_not_found" = a report/diagram template is missing;
        # "config_error" = profile resolution/validation at generate() level
        # (profile/profile_yaml args, profile data toggles).
        except ConfigResolutionError as exc:
            span.add(error=str(exc))
            return _error_payload(
                operation="generate",
                code="config_error",
                message=str(exc),
            )
        except Exception as exc:  # pragma: no cover - defensive
            span.add(error=str(exc))
            return _error_payload(
                operation="generate",
                code="unexpected_error",
                message=str(exc),
                details={"traceback": traceback.format_exc(limit=5)},
            )


def export_yaml(*, input_path: str, output_path: str) -> dict[str, Any]:
    """Export Excel entity sheets to YAML.

    Args:
        input_path: Workbook file, directory, or glob path.
        output_path: YAML output path.

    Returns:
        Structured export result.
    """
    with LogSpan(span="arch.export_yaml", inputPath=input_path, outputPath=output_path) as span:
        try:
            _, entities, passthrough = ingest_input(
                input_path=input_path,
                list_cell_separator=_resolve_list_cell_separator(),
            )
            destination = resolve_cwd_path(output_path)
            exported = export_entities_to_yaml(
                entities=entities,
                output_path=destination,
                passthrough=passthrough,
            )
            span.add(ok=True)
            return {
                "ok": True,
                "operation": "export_yaml",
                "output_path": exported,
                "summary": {"counts": {sheet: len(rows) for sheet, rows in entities.items()}},
            }
        except (IngestError, MissingDependencyError, RoundtripError) as exc:
            span.add(error=str(exc))
            return _error_payload(
                operation="export_yaml",
                code="roundtrip_error",
                message=str(exc),
                details={"input_path": input_path, "output_path": output_path},
            )
        except Exception as exc:  # pragma: no cover - defensive
            span.add(error=str(exc))
            return _error_payload(
                operation="export_yaml",
                code="unexpected_error",
                message=str(exc),
                details={"traceback": traceback.format_exc(limit=5)},
            )


def import_yaml(*, input_path: str, template_path: str, output_path: str) -> dict[str, Any]:
    """Import YAML entities into a template workbook.

    Args:
        input_path: YAML input path.
        template_path: Workbook template path.
        output_path: Output workbook path.

    Returns:
        Structured import result including validation.
    """
    with LogSpan(
        span="arch.import_yaml",
        inputPath=input_path,
        templatePath=template_path,
        outputPath=output_path,
    ) as span:
        try:
            entities, passthrough = load_yaml_entities(input_path=resolve_cwd_path(input_path))
            imported_path = import_yaml_into_template(
                entities=entities,
                template_path=resolve_cwd_path(template_path),
                output_path=resolve_cwd_path(output_path),
                list_cell_separator=_resolve_list_cell_separator(),
                passthrough=passthrough,
            )
            validation_result = validate(input_path=imported_path)
            response: dict[str, Any] = {
                "ok": validation_result.get("valid", False),
                "operation": "import_yaml",
                "output_path": imported_path,
                "validation": validation_result,
            }
            if not response["ok"]:
                response["error"] = {
                    "code": "validation_failed",
                    "message": "Imported workbook failed validation",
                    "details": {
                        "error_count": validation_result.get("summary", {}).get("errors", 0)
                    },
                }
            span.add(ok=response["ok"])
            return response
        except (RoundtripError, MissingDependencyError, IngestError) as exc:
            span.add(error=str(exc))
            return _error_payload(
                operation="import_yaml",
                code="roundtrip_error",
                message=str(exc),
                details={
                    "input_path": input_path,
                    "template_path": template_path,
                    "output_path": output_path,
                },
            )
        except Exception as exc:  # pragma: no cover - defensive
            span.add(error=str(exc))
            return _error_payload(
                operation="import_yaml",
                code="unexpected_error",
                message=str(exc),
                details={"traceback": traceback.format_exc(limit=5)},
            )


def bundle_solution(
    *,
    directory: str,
    output_path: str | None = None,
    include: str | None = None,
) -> dict[str, Any]:
    """Bundle generated solution outputs by inlining SVG and zipping directory.

    Args:
        directory: Solution directory.
        output_path: Optional explicit zip path.
        include: Optional file, directory, or glob pattern for extra bundle files.

    Returns:
        Structured bundle result.
    """
    with LogSpan(span="arch.bundle_solution", directory=directory) as span:
        try:
            result = bundle_solution_directory(
                directory=resolve_cwd_path(directory),
                output_path=resolve_cwd_path(output_path) if output_path else None,
                include=include,
            )
            span.add(ok=True, archivedFiles=len(result["archived_files"]))
            return {
                "ok": True,
                "operation": "bundle_solution",
                **result,
            }
        except (BundleError, MissingDependencyError) as exc:
            span.add(error=str(exc))
            return _error_payload(
                operation="bundle_solution",
                code="bundle_error",
                message=str(exc),
                details={"directory": directory, "output_path": output_path, "include": include},
            )
        except Exception as exc:  # pragma: no cover - defensive
            span.add(error=str(exc))
            return _error_payload(
                operation="bundle_solution",
                code="unexpected_error",
                message=str(exc),
                details={"traceback": traceback.format_exc(limit=5)},
            )
