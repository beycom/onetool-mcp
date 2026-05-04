"""Architecture workflow tools for Excel ingestion, validation, generation, and bundling."""

from __future__ import annotations

pack = "arch"

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
from otpack import LogSpan, resolve_cwd_path

from otdev.tools._arch.bundle import BundleError, bundle_solution_directory
from otdev.tools._arch.config import (
    ArchProfileConfig,
    ConfigResolutionError,
    RenderTargetConfig,
    get_active_profile,
    get_arch_config,
    resolve_output_dir,
    resolve_render_target_for_profile,
    resolve_report_template_paths_for_profile,
    resolve_system_diagram_template_path_for_profile,
)
from otdev.tools._arch.exporters import (
    apply_tag_filters,
    serializable_entities,
)
from otdev.tools._arch.ingest import IngestError, ingest_input
from otdev.tools._arch.models import MODEL_VERSION, first_value
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
    build_solution_system_context as _build_solution_system_context,
)
from otdev.tools._arch.system_model import (
    build_system_d2 as _build_system_d2,
)
from otdev.tools._arch.system_model import (
    first_tag_value as _first_tag_value,
)
from otdev.tools._arch.system_model import (
    is_external_system as _is_external_system,
)
from otdev.tools._arch.system_model import (
    render_markdown as _render_markdown,
)
from otdev.tools._arch.system_model import (
    svg_markup as _svg_markup,
)
from otdev.tools._arch.system_model import (
    system_page_name as _system_page_name,
)
from otdev.tools._arch.validate import validate_entities

_SAFE_ID_FRAGMENT_RE = re.compile(r"^[A-Za-z0-9._-]+$")
_UNSAFE_PATH_CHARS_RE = re.compile(r"[;\|&`$<>\r\n]")
_MAX_RENDER_WORKERS = 6


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
    warnings: list[dict[str, Any]] = []
    specs: list[_WorkbookDiagramSpec] = []

    allowed_system_ids = {
        str(row.get("id", "")).strip()
        for row in entities.get("sys", [])
        if str(row.get("id", "")).strip() and not _is_external_system(row)
    }

    for idx, row in enumerate(entities.get("diagram", []), start=1):
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
        source_path = (workbook_path.parent / source_value).resolve()
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

    return specs, {"errors": errors, "warnings": warnings}


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
    model_payload: dict[str, Any],
    target_config: RenderTargetConfig,
    input_path: str,
    output_path: str,
    work_dir: str,
    template_dir: str,
) -> dict[str, Any]:
    profile_data = dict(target_config.profile.data)
    return {
        "model": model_payload,
        "target": target_config.target,
        "profile": target_config.profile_name,
        "view": {"profile": target_config.profile_name},
        "profile_data": profile_data,
        "paths": {
            "input": input_path,
            "output": output_path,
            "work_dir": work_dir,
            "template_dir": template_dir,
        },
        "engine": {
            "name": target_config.engine_name,
        },
        "report": {
            "id": f"{target_config.target}-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "timestamp": _now_timestamp(),
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
        render_vars: dict[str, Any] = {
            "input": input_path,
            "output": output_path,
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
        )
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
) -> tuple[bool, dict[int, dict[str, Any]]]:
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


def _generate_solution(
    *,
    output_root: Path,
    entities: dict[str, list[dict[str, Any]]],
    diagram_specs: list[_WorkbookDiagramSpec],
    profile_name: str,
    profile: Any,
    model_payload: dict[str, Any],
    title: str | None,
) -> dict[str, Any]:
    try:
        report_templates = resolve_report_template_paths_for_profile(profile=profile)
        system_diagram_template = resolve_system_diagram_template_path_for_profile(profile=profile)
    except ConfigResolutionError as exc:
        return _error_payload(
            operation="generate",
            code="template_not_found",
            message=str(exc),
        )

    template_dirs = [
        str(report_templates.solution_report_path.parent),
        str(report_templates.system_report_path.parent),
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
    solution_dir.mkdir(parents=True, exist_ok=True)
    images_dir = solution_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    legacy_d2_assets_dir = images_dir / "d2"
    if legacy_d2_assets_dir.is_dir():
        shutil.rmtree(legacy_d2_assets_dir)

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
        model_payload=model_payload,
        diagram_specs=diagram_specs,
    )
    if not diagram_result["ok"]:
        return diagram_result
    extra_diagrams_by_system = diagram_result["by_system"]

    systems_list: list[dict[str, str]] = []
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
            return {
                **_error_payload(
                    operation="generate",
                    code="validation_failed",
                    message="System id contains unsafe output-path characters",
                    details={"error_count": 1},
                ),
                "valid": False,
                "issues": {"errors": [system_id_issue], "warnings": []},
                "summary": {
                    "counts": {sheet: len(rows) for sheet, rows in entities.items()},
                    "errors": 1,
                    "warnings": 0,
                },
            }

        systems_list.append(
            {
                "id": system_id,
                "name": str(sys_row.get("name") or system_id),
                "description": str(first_value(sys_row, ("description",)) or ""),
                "tag": _first_tag_value(sys_row),
            }
        )

        svg_by_level: dict[str, str] = {}
        level_jobs: list[tuple[int, RenderTargetConfig, dict[str, Any]]] = []
        level_outputs: list[tuple[str, Path, Path]] = []
        for idx, level in enumerate((_LEVEL_SYS, _LEVEL_APP, _LEVEL_CMP)):
            d2_text = _build_system_d2(
                system_id=system_id,
                level=level,
                entities=entities,
                graph=graph,
                template_path=system_diagram_template,
                profile_data=profile.data,
            )
            d2_path = images_dir / f"{system_id}-{level}.d2"
            svg_path = images_dir / f"{system_id}-{level}.svg"
            d2_path.write_text(d2_text, encoding="utf-8")
            render_context = _build_render_context(
                model_payload=model_payload,
                target_config=render_target,
                input_path=str(d2_path),
                output_path=str(svg_path),
                work_dir=str(output_root),
                template_dir=str(template_dir),
            )
            level_outputs.append((level, d2_path, svg_path))
            level_jobs.append((idx, render_target, render_context))

        ok, render_result = _execute_render_jobs(
            jobs=level_jobs,
            max_workers=3,
        )
        if not ok:
            return _error_payload(
                operation="generate",
                code=render_result["code"],
                message=render_result["message"],
                details=render_result["details"],
            )

        for level, d2_path, svg_path in level_outputs:
            generated_files.append(str(d2_path))
            generated_files.append(str(svg_path))
            svg_by_level[level] = _svg_markup(svg_path.read_text(encoding="utf-8"))

            if not svg_by_level[level]:
                return _error_payload(
                    operation="generate",
                    code="render_output_error",
                    message=f"Rendered SVG for level '{level}' is empty.",
                    details={"system_id": system_id, "level": level},
                )

        base_context = _build_solution_system_context(
            system_id=system_id,
            entities=entities,
            graph=graph,
            svg_by_level=svg_by_level,
            workbook_diagrams=extra_diagrams_by_system.get(system_id, []),
        )
        base_context.update(
            {
                "styles": styles_css,
                "scripts": scripts_js,
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
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

    index_template = env.get_template(report_templates.solution_report_path.name)
    solution_title = title.strip() if title and title.strip() else "Architecture Solution"
    index_base_context: dict[str, Any] = {
        "title": solution_title,
        "systems": systems_list,
        "styles": styles_css,
        "scripts": scripts_js,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
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
    model_payload: dict[str, Any],
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

    prepared: list[tuple[_WorkbookDiagramSpec, int, str, Path]] = []
    for idx, spec in enumerate(diagram_specs, start=1):
        system_id_issue = _validate_system_id_fragment(
            value=spec.system_id,
            field="sys",
            sheet="diagram",
            row=spec.row_number,
        )
        if system_id_issue:
            return {
                "ok": False,
                "operation": "generate",
                "error": {
                    "code": "validation_failed",
                    "message": "Diagram row has invalid system id for output-path generation",
                    "details": {"error_count": 1},
                },
                "valid": False,
                "issues": {"errors": [system_id_issue], "warnings": []},
            }
        safe_name = re.sub(r"[^a-zA-Z0-9._-]+", "-", Path(spec.source_value).stem).strip("-")
        if not safe_name:
            safe_name = f"diagram-{idx}"
        svg_name = f"{spec.system_id}-{idx:02d}-{safe_name}.svg"
        output_path = diagram_dir / svg_name
        prepared.append((spec, idx, svg_name, output_path))

    jobs: list[tuple[int, RenderTargetConfig, dict[str, Any]]] = []
    for job_idx, (spec, _, _, output_path) in enumerate(prepared):
        render_context = _build_render_context(
            model_payload=model_payload,
            target_config=target_config,
            input_path=str(spec.source_path),
            output_path=str(output_path),
            work_dir=str(output_root),
            template_dir=str(spec.source_path.parent),
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
            workbooks, entities = ingest_input(input_path=input_path)
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
        except (IngestError, ImportError) as exc:
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
            workbooks, entities = ingest_input(input_path=input_path)
            profile_name, active_profile = _resolve_generation_profile(
                config=config,
                profile=profile,
                profile_yaml=profile_yaml,
            )
            effective_include_tags = include_tags
            filtered = apply_tag_filters(
                entities=entities,
                include_tags=effective_include_tags,
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
                include_tags=effective_include_tags,
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
            )
            if not solution_result["ok"]:
                return solution_result
            files: dict[str, list[str]] = {"solution": solution_result["files"]}

            summary = {
                "formats": ["solution"],
                "generated_files": sum(len(paths) for paths in files.values()),
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
                    "include_tags": effective_include_tags or [],
                    "exclude_tags": exclude_tags or [],
                },
                "files": files,
                "model": {"version": MODEL_VERSION},
                "summary": summary,
            }
        except (IngestError, ImportError) as exc:
            span.add(error=str(exc))
            return _error_payload(
                operation="generate",
                code="ingest_error",
                message=str(exc),
                details={"input_path": input_path},
            )
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
            _, entities = ingest_input(input_path=input_path)
            destination = resolve_cwd_path(output_path)
            exported = export_entities_to_yaml(entities=entities, output_path=destination)
            span.add(ok=True)
            return {
                "ok": True,
                "operation": "export_yaml",
                "output_path": exported,
                "summary": {"counts": {sheet: len(rows) for sheet, rows in entities.items()}},
            }
        except (IngestError, ImportError, RoundtripError) as exc:
            span.add(error=str(exc))
            return _error_payload(
                operation="export_yaml",
                code="roundtrip_error",
                message=str(exc),
                details={"input_path": input_path, "output_path": output_path},
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
            entities = load_yaml_entities(input_path=resolve_cwd_path(input_path))
            imported_path = import_yaml_into_template(
                entities=entities,
                template_path=resolve_cwd_path(template_path),
                output_path=resolve_cwd_path(output_path),
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
        except (RoundtripError, ImportError, IngestError) as exc:
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
        except BundleError as exc:
            span.add(error=str(exc))
            return _error_payload(
                operation="bundle_solution",
                code="bundle_error",
                message=str(exc),
                details={"directory": directory, "output_path": output_path, "include": include},
            )
