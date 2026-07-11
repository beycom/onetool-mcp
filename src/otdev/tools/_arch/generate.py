"""Solution-generation orchestration for the arch pack.

Owns the full `arch.generate` pipeline behind the facade: workbook diagram
collection, per-system/per-project page generation (one parameterized loop,
see `_PageKind`), render-engine execution, draw.io embedding, incremental
output reuse, and the stale-file sweep.
"""

from __future__ import annotations

import contextlib
import re
import shlex
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

from jinja2 import Environment, FileSystemLoader, StrictUndefined, TemplateError

from .config import (
    ArchProfileConfig,
    ConfigResolutionError,
    RenderTargetConfig,
    resolve_project_diagram_template_path_for_profile,
    resolve_render_target_for_profile,
    resolve_report_template_paths_for_profile,
    resolve_system_diagram_template_path_for_profile,
)
from .drawio import build_mxfile, extract_geometry, inject_content
from .exporters import serializable_entities
from .models import MODEL_VERSION, error_payload, first_value
from .system_model import (
    _SVG_CONTENT_ATTR_RE,
    LEVEL_APP,
    LEVEL_CMP,
    LEVEL_SYS,
    build_entity_graph,
    build_project_d2,
    build_project_view,
    build_solution_index_context,
    build_solution_project_context,
    build_solution_system_context,
    build_system_d2,
    build_system_view,
    first_tag_value,
    is_external_system,
    project_page_name,
    project_stage_ids,
    render_markdown,
    safe_output_fragment,
    svg_markup,
    system_page_name,
)

_SAFE_ID_FRAGMENT_RE = re.compile(r"^[A-Za-z0-9._-]+$")
_UNSAFE_PATH_CHARS_RE = re.compile(r"[;\|&`$<>\r\n]")
_MAX_RENDER_WORKERS = 6
# Per-render subprocess timeout: a hung engine must not block the tool call
# (or the render ThreadPool) indefinitely.
_RENDER_TIMEOUT_SECONDS = 60


@dataclass(slots=True)
class WorkbookDiagramSpec:
    system_id: str
    name: str
    description: str
    source_value: str
    source_path: Path
    row_number: int


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


def clean_diagram_rows(*, entities: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    cleaned: list[dict[str, Any]] = []
    for row in entities.get("diagram", []):
        cleaned.append({k: v for k, v in row.items() if not str(k).startswith("_")})
    return cleaned


def collect_workbook_diagram_specs(
    *,
    entities: dict[str, list[dict[str, Any]]],
) -> tuple[list[WorkbookDiagramSpec], dict[str, list[dict[str, Any]]]]:
    errors: list[dict[str, Any]] = []
    specs: list[WorkbookDiagramSpec] = []

    allowed_system_ids = {
        str(row.get("id", "")).strip()
        for row in entities.get("sys", [])
        if str(row.get("id", "")).strip() and not is_external_system(row)
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
            WorkbookDiagramSpec(
                system_id=sys_id,
                name=name,
                description=description,
                source_value=source_value,
                source_path=source_path,
                row_number=row_number,
            )
        )

    return specs, {"errors": errors, "warnings": []}


def build_model_payload(
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
        **error_payload(
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


def _write_if_changed(path: Path, text: str) -> bool:
    """Write `text` to `path` only when the current content differs.

    Returns whether a write happened. Parent directories are created on demand.
    """
    if path.is_file() and path.read_text(encoding="utf-8") == text:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return True


def _svg_has_drawio_content(svg_text: str) -> bool:
    """Whether the SVG's root tag carries an embedded draw.io `content` attribute."""
    idx = svg_text.find("<svg")
    if idx == -1:
        return False
    tag_close = svg_text.find(">", idx)
    if tag_close == -1:
        return False
    return _SVG_CONTENT_ATTR_RE.search(svg_text[idx : tag_close + 1]) is not None


def _sweep_stale_files(*, solution_dir: Path, expected_files: list[str]) -> None:
    """Delete files under `solution_dir` not in the expected set; prune empty dirs.

    Only called after a fully successful generation run.
    """
    expected = {str(Path(item).resolve()) for item in expected_files}
    entries = sorted(solution_dir.rglob("*"), key=lambda p: len(p.parts), reverse=True)
    for path in entries:
        if path.is_file():
            if str(path.resolve()) not in expected:
                path.unlink()
        elif path.is_dir():
            with contextlib.suppress(OSError):
                path.rmdir()


def _render_view_diagrams(
    *,
    outputs: list[tuple[str, Path, Path, dict[str, Any], bool]],
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
    project (per-stage) loops. Outputs flagged as skipped reuse their existing
    `.svg` (unchanged `.d2` implies an unchanged embedded model) and are not
    re-injected. Returns (svg_by_key, None) on success or (None, error_payload)
    on failure."""
    ok, render_result = _execute_render_jobs(jobs=jobs, max_workers=_MAX_RENDER_WORKERS)
    if not ok:
        return None, error_payload(
            operation="generate",
            code=render_result["code"],
            message=render_result["message"],
            details=render_result["details"],
        )

    svg_by_key: dict[str, str] = {}
    for key, d2_path, svg_path, view, skipped in outputs:
        generated_files.append(str(d2_path))
        generated_files.append(str(svg_path))
        svg_text = svg_path.read_text(encoding="utf-8")
        if drawio_export and not skipped:
            geometry = extract_geometry(svg_text)
            mxfile_xml = build_mxfile(
                user_nodes=view["user_nodes"],
                external_nodes=view["external_nodes"],
                system_blocks=view["system_blocks"],
                interface_edges=view["interface_edges"],
                geometry=geometry,
            )
            svg_text = inject_content(svg_text, mxfile_xml)
            svg_path.write_text(svg_text, encoding="utf-8")
        svg_by_key[key] = svg_markup(svg_text)
        if not svg_by_key[key]:
            return None, error_payload(
                operation="generate",
                code="render_output_error",
                message=f"Rendered SVG for {kind_label} '{key}' is empty.",
                details={owner_key: owner_id, kind_key: key},
            )
    return svg_by_key, None


@dataclass(frozen=True)
class _PageKind:
    """One page family (systems or projects) for `_generate_pages` (design D2).

    The callables close over the run's entities/graph/profile/templates so the
    loop body stays generic: row source + skip predicate, per-page key list,
    view/d2 builders, output stem, page-context builder, page name, and the
    index card shape."""

    sheet: str
    unsafe_id_message: str
    kind_label: str
    kind_key: str
    owner_key: str
    rows: Callable[[], list[dict[str, Any]]]
    skip_row: Callable[[dict[str, Any]], bool]
    make_card: Callable[[dict[str, Any], str], dict[str, str]]
    page_keys: Callable[[str], list[str]]
    output_stem: Callable[[str, str], str]
    build_view: Callable[[str, str], dict[str, Any]]
    build_d2: Callable[[str, str, dict[str, Any]], str]
    build_page_context: Callable[[str, dict[str, str]], dict[str, Any]]
    page_name: Callable[[str], str]
    template_name: str


def _generate_pages(
    *,
    kind: _PageKind,
    entities: dict[str, list[dict[str, Any]]],
    images_dir: Path,
    solution_dir: Path,
    output_root: Path,
    render_target: RenderTargetConfig,
    env: Environment,
    styles_css: str,
    scripts_js: str,
    model_payload: dict[str, Any],
    profile_data: dict[str, Any],
    drawio_export: bool,
    force: bool,
    generated_files: list[str],
    render_stats: dict[str, int],
) -> tuple[list[dict[str, str]] | None, dict[str, Any] | None]:
    """Generate all pages of one kind: per-row card + per-key diagram renders
    (with the incremental skip rule, design D4) + the report HTML page.
    Returns (sorted cards, None) on success or (None, error_payload) on failure."""
    cards: list[dict[str, str]] = []
    for row in kind.rows():
        owner_id = str(row.get("id", "")).strip()
        if not owner_id:
            continue
        if kind.skip_row(row):
            continue
        id_issue = _validate_system_id_fragment(
            value=owner_id,
            field="id",
            sheet=kind.sheet,
            row=int(row.get("_sheet_row", 0)),
        )
        if id_issue:
            return None, _unsafe_id_error(
                entities=entities,
                issue=id_issue,
                message=kind.unsafe_id_message,
            )

        cards.append(kind.make_card(row, owner_id))

        jobs: list[tuple[int, RenderTargetConfig, dict[str, Any]]] = []
        outputs: list[tuple[str, Path, Path, dict[str, Any], bool]] = []
        for idx, key in enumerate(kind.page_keys(owner_id)):
            # Built once and reused for both the D2 source (below) and the
            # draw.io embedded model (after rendering, D1/D2): same render
            # context, so the two representations never drift apart.
            view = kind.build_view(owner_id, key)
            d2_text = kind.build_d2(owner_id, key, view)
            stem = kind.output_stem(owner_id, key)
            d2_path = images_dir / f"{stem}.d2"
            svg_path = images_dir / f"{stem}.svg"
            # Skip the engine when the d2 source is unchanged, the svg exists,
            # and its draw.io-embed state matches this run's toggle (D4).
            d2_unchanged = d2_path.is_file() and d2_path.read_text(encoding="utf-8") == d2_text
            skip = (
                not force
                and d2_unchanged
                and svg_path.is_file()
                and _svg_has_drawio_content(svg_path.read_text(encoding="utf-8")) == drawio_export
            )
            if not d2_unchanged:
                d2_path.parent.mkdir(parents=True, exist_ok=True)
                d2_path.write_text(d2_text, encoding="utf-8")
            if skip:
                render_stats["skipped"] += 1
                outputs.append((key, d2_path, svg_path, view, True))
                continue
            render_context = _build_render_context(
                target_config=render_target,
                input_path=str(d2_path),
                output_path=str(svg_path),
                work_dir=str(output_root),
            )
            outputs.append((key, d2_path, svg_path, view, False))
            jobs.append((idx, render_target, render_context))
            render_stats["executed"] += 1

        svg_by_key, render_error = _render_view_diagrams(
            outputs=outputs,
            jobs=jobs,
            drawio_export=drawio_export,
            kind_label=kind.kind_label,
            kind_key=kind.kind_key,
            owner_key=kind.owner_key,
            owner_id=owner_id,
            generated_files=generated_files,
        )
        if render_error is not None or svg_by_key is None:
            return None, render_error or error_payload(
                operation="generate",
                code="render_output_error",
                message="Rendering produced no output.",
            )

        base_context = kind.build_page_context(owner_id, svg_by_key)
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
            profile_data=profile_data,
        )
        template = env.get_template(kind.template_name)
        html = template.render(**context)
        html_path = solution_dir / kind.page_name(owner_id)
        _write_if_changed(html_path, html)
        generated_files.append(str(html_path))

    cards.sort(key=lambda item: item["name"].lower())
    return cards, None


def generate_solution(
    *,
    output_root: Path,
    entities: dict[str, list[dict[str, Any]]],
    diagram_specs: list[WorkbookDiagramSpec],
    profile_name: str,
    profile: Any,
    model_payload: dict[str, Any],
    title: str | None,
    drawio_export: bool = True,
    force: bool = False,
) -> dict[str, Any]:
    try:
        report_templates = resolve_report_template_paths_for_profile(profile=profile)
        system_diagram_template = resolve_system_diagram_template_path_for_profile(profile=profile)
        project_diagram_template = resolve_project_diagram_template_path_for_profile(profile=profile)
    except ConfigResolutionError as exc:
        return error_payload(
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
        return error_payload(
            operation="generate",
            code="template_not_found",
            message=f"Solution template path must be a directory: {template_dir}",
        )

    env = Environment(loader=FileSystemLoader(template_dirs), autoescape=True)

    # The solution directory is updated incrementally: unchanged outputs are
    # reused, and stale files are swept only after a fully successful run.
    solution_dir = output_root / "solution"
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
        return error_payload(
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

    graph = build_entity_graph(entities=entities)
    render_stats = {"executed": 0, "skipped": 0}
    diagram_result = _render_workbook_diagrams(
        output_root=output_root,
        profile_name=profile_name,
        profile=profile,
        diagram_specs=diagram_specs,
        force=force,
        render_stats=render_stats,
    )
    if not diagram_result["ok"]:
        return diagram_result
    extra_diagrams_by_system = diagram_result["by_system"]

    generated_files: list[str] = [*diagram_result["files"]]

    system_kind = _PageKind(
        sheet="sys",
        unsafe_id_message="System id contains unsafe output-path characters",
        kind_label="level",
        kind_key="level",
        owner_key="system_id",
        rows=lambda: entities["sys"],
        skip_row=is_external_system,
        make_card=lambda row, owner_id: {
            "id": owner_id,
            "name": str(row.get("name") or owner_id),
            "description": str(first_value(row, ("description",)) or ""),
            "tag": first_tag_value(row),
        },
        page_keys=lambda _owner_id: [LEVEL_SYS, LEVEL_APP, LEVEL_CMP],
        output_stem=lambda owner_id, key: f"{owner_id}-{key}",
        build_view=lambda owner_id, key: build_system_view(
            system_id=owner_id,
            level=key,
            entities=entities,
            graph=graph,
            profile_data=profile.data,
        ),
        build_d2=lambda owner_id, key, view: build_system_d2(
            system_id=owner_id,
            level=key,
            entities=entities,
            graph=graph,
            template_path=system_diagram_template,
            profile_data=profile.data,
            system_view=view,
        ),
        build_page_context=lambda owner_id, svg_by_key: build_solution_system_context(
            system_id=owner_id,
            entities=entities,
            graph=graph,
            svg_by_level=svg_by_key,
            workbook_diagrams=extra_diagrams_by_system.get(owner_id, []),
            drawio_export=drawio_export,
        ),
        page_name=system_page_name,
        template_name=report_templates.system_report_path.name,
    )
    project_kind = _PageKind(
        sheet="project",
        unsafe_id_message="Project id contains unsafe output-path characters",
        kind_label="project stage",
        kind_key="stage",
        owner_key="project_id",
        rows=lambda: entities.get("project", []),
        skip_row=lambda _row: False,
        make_card=lambda row, owner_id: {
            "id": owner_id,
            "name": str(row.get("name") or owner_id),
            "description": str(first_value(row, ("description",)) or ""),
            "tag": first_tag_value(row),
            "href": project_page_name(owner_id),
        },
        page_keys=lambda owner_id: project_stage_ids(project_id=owner_id, entities=entities),
        output_stem=lambda owner_id, key: f"project-{owner_id}-{safe_output_fragment(key)}",
        build_view=lambda owner_id, key: build_project_view(
            project_id=owner_id,
            stage=key,
            entities=entities,
            graph=graph,
            profile_data=profile.data,
        ),
        build_d2=lambda owner_id, key, view: build_project_d2(
            project_id=owner_id,
            stage=key,
            entities=entities,
            graph=graph,
            template_path=project_diagram_template,
            profile_data=profile.data,
            project_view=view,
        ),
        build_page_context=lambda owner_id, svg_by_key: build_solution_project_context(
            project_id=owner_id,
            entities=entities,
            graph=graph,
            svg_by_stage=svg_by_key,
            drawio_export=drawio_export,
        ),
        page_name=project_page_name,
        template_name=report_templates.project_report_path.name,
    )

    page_args = {
        "entities": entities,
        "images_dir": images_dir,
        "solution_dir": solution_dir,
        "output_root": output_root,
        "render_target": render_target,
        "env": env,
        "styles_css": styles_css,
        "scripts_js": scripts_js,
        "model_payload": model_payload,
        "profile_data": profile.data,
        "drawio_export": drawio_export,
        "force": force,
        "generated_files": generated_files,
        "render_stats": render_stats,
    }
    systems_list, page_error = _generate_pages(kind=system_kind, **page_args)
    if page_error is not None or systems_list is None:
        return page_error or error_payload(
            operation="generate",
            code="render_output_error",
            message="Rendering produced no output.",
        )
    projects_list, page_error = _generate_pages(kind=project_kind, **page_args)
    if page_error is not None or projects_list is None:
        return page_error or error_payload(
            operation="generate",
            code="render_output_error",
            message="Rendering produced no output.",
        )

    index_template = env.get_template(report_templates.solution_report_path.name)
    solution_title = title.strip() if title and title.strip() else "Architecture Solution"
    # Card-grid behavior (systems_list/projects_list above) is unchanged; the
    # index summary cards and global entity tables (D7) are additive.
    index_extra_context = build_solution_index_context(entities=entities, graph=graph)
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
    _write_if_changed(index_path, index_html)
    generated_files.insert(0, str(index_path))

    _sweep_stale_files(solution_dir=solution_dir, expected_files=generated_files)

    return {
        "ok": True,
        "files": generated_files,
        "renders": render_stats,
    }


def _render_workbook_diagrams(
    *,
    output_root: Path,
    profile_name: str,
    profile: ArchProfileConfig,
    diagram_specs: list[WorkbookDiagramSpec],
    force: bool = False,
    render_stats: dict[str, int] | None = None,
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
        return error_payload(
            operation="generate",
            code="invalid_config",
            message=str(exc),
        )

    diagram_dir = output_root / "solution" / "images"
    diagram_dir.mkdir(parents=True, exist_ok=True)
    generated_files: list[str] = []
    by_system: dict[str, list[dict[str, str]]] = {}

    # spec.system_id was already fragment-validated by
    # collect_workbook_diagram_specs; generation aborts before this point
    # when any diagram row carries an error.
    prepared: list[tuple[WorkbookDiagramSpec, int, str, Path]] = []
    for idx, spec in enumerate(diagram_specs, start=1):
        safe_name = re.sub(r"[^a-zA-Z0-9._-]+", "-", Path(spec.source_value).stem).strip("-")
        if not safe_name:
            safe_name = f"diagram-{idx}"
        svg_name = f"{spec.system_id}-{idx:02d}-{safe_name}.svg"
        output_path = diagram_dir / svg_name
        prepared.append((spec, idx, svg_name, output_path))

    jobs: list[tuple[int, RenderTargetConfig, dict[str, Any]]] = []
    for job_idx, (spec, _, _, output_path) in enumerate(prepared):
        # Source files live outside the output tree, so content-compare is
        # impossible; skip on mtime instead (design D4).
        if (
            not force
            and output_path.is_file()
            and output_path.stat().st_mtime >= spec.source_path.stat().st_mtime
        ):
            if render_stats is not None:
                render_stats["skipped"] += 1
            continue
        render_context = _build_render_context(
            target_config=target_config,
            input_path=str(spec.source_path),
            output_path=str(output_path),
            work_dir=str(output_root),
        )
        jobs.append((job_idx, target_config, render_context))
        if render_stats is not None:
            render_stats["executed"] += 1

    ok, render_result = _execute_render_jobs(
        jobs=jobs,
        max_workers=_MAX_RENDER_WORKERS,
    )
    if not ok:
        return error_payload(
            operation="generate",
            code=render_result["code"],
            message=render_result["message"],
            details=render_result["details"],
        )

    for spec, _, svg_name, output_path in prepared:
        generated_files.append(str(output_path))
        diagram_markup = svg_markup(output_path.read_text(encoding="utf-8"))
        by_system.setdefault(spec.system_id, []).append(
            {
                "name": spec.name,
                "description": render_markdown(spec.description),
                "source": str(spec.source_path),
                "svg": diagram_markup,
                "svg_path": f"images/{svg_name}",
            }
        )

        if not diagram_markup:
            return error_payload(
                operation="generate",
                code="render_output_error",
                message="Rendered workbook diagram SVG is empty.",
                details={"system_id": spec.system_id, "source": str(spec.source_path)},
            )

    return {"ok": True, "files": generated_files, "by_system": by_system}
