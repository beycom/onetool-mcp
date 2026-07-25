"""Architecture workflow tools for Excel ingestion, validation, generation, and bundling."""

from __future__ import annotations

pack = "arch"

__ot_requires__ = {
    "cli": [("d2", "brew install d2")],
}

__all__ = ["bundle_solution", "export_yaml", "generate", "import_yaml", "validate"]

import traceback
from typing import Any

import yaml

from otdev.tools._arch.bundle import BundleError, bundle_solution_directory
from otdev.tools._arch.config import (
    ArchProfileConfig,
    ConfigResolutionError,
    get_active_profile,
    get_arch_config,
    resolve_output_dir,
)
from otdev.tools._arch.exporters import apply_tag_filters
from otdev.tools._arch.generate import (
    build_model_payload,
    clean_diagram_rows,
    collect_workbook_diagram_specs,
    generate_solution,
)
from otdev.tools._arch.ingest import IngestError, ingest_input
from otdev.tools._arch.models import (
    DEFAULT_LIST_CELL_SEPARATOR,
    MODEL_VERSION,
    MissingDependencyError,
    error_payload,
)
from otdev.tools._arch.roundtrip import (
    RoundtripError,
    export_entities_to_yaml,
    import_yaml_into_template,
    load_yaml_entities,
)
from otdev.tools._arch.validate import validate_entities
from otpack import LogSpan, resolve_cwd_path


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
        raise ConfigResolutionError(
            "arch.generate accepts only one of profile or profile_yaml"
        )

    if profile_yaml is not None:
        if not profile_yaml.strip():
            raise ConfigResolutionError("profile_yaml must be a non-empty YAML string")
        try:
            parsed = yaml.safe_load(profile_yaml)
        except yaml.YAMLError as exc:
            raise ConfigResolutionError(f"Invalid profile_yaml: {exc}") from exc
        if not isinstance(parsed, dict):
            raise ConfigResolutionError(
                "profile_yaml must define a YAML mapping for ArchProfileConfig"
            )
        try:
            resolved_profile = ArchProfileConfig.model_validate(parsed)
        except Exception as exc:
            raise ConfigResolutionError(
                f"Invalid profile_yaml profile config: {exc}"
            ) from exc
        return "profile_yaml", resolved_profile

    return get_active_profile(config=config, profile=profile)


def _resolve_list_cell_separator() -> str:
    """Resolve the configured list-cell separator, falling back to the default.

    Kept resilient (never raises) so validate/round-trip do not fail on unrelated
    profile-config errors that generate() would otherwise surface.
    """
    try:
        return get_arch_config().list_cell_separator
    except ConfigResolutionError:
        return DEFAULT_LIST_CELL_SEPARATOR


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
            span.add(
                valid=validation["valid"], errorCount=validation["summary"]["errors"]
            )
            return payload
        except (IngestError, MissingDependencyError, RoundtripError) as exc:
            span.add(error=str(exc))
            return error_payload(
                operation="validate",
                code="ingest_error",
                message=str(exc),
                details={"input_path": input_path},
            )
        except Exception as exc:  # pragma: no cover - defensive
            span.add(error=str(exc))
            return error_payload(
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
    force: bool = False,
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
        force: Re-render every diagram and rewrite every output file, bypassing
            the incremental unchanged-output reuse.

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
            return error_payload(
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
                    **error_payload(
                        operation="generate",
                        code="validation_failed",
                        message="Validation failed; generation did not run",
                        details={"error_count": validation["summary"]["errors"]},
                    ),
                    "valid": False,
                    "issues": validation["issues"],
                    "summary": validation["summary"],
                }

            diagram_specs, diagram_issues = collect_workbook_diagram_specs(
                entities=filtered
            )
            if diagram_issues["errors"]:
                return {
                    **error_payload(
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

            model_payload = build_model_payload(
                entities=filtered,
                diagrams=clean_diagram_rows(entities=filtered),
                include_tags=include_tags,
                exclude_tags=exclude_tags,
            )
            solution_result = generate_solution(
                output_root=output_root,
                entities=filtered,
                diagram_specs=diagram_specs,
                profile_name=profile_name,
                profile=active_profile,
                model_payload=model_payload,
                title=title,
                drawio_export=drawio_export_enabled,
                force=force,
            )
            if not solution_result["ok"]:
                return solution_result
            solution_files: list[str] = solution_result["files"]

            summary = {
                "formats": ["solution"],
                "generated_files": len(solution_files),
                "counts": validation["summary"]["counts"],
                "warnings": validation["summary"]["warnings"],
                "diagram_rows": len(filtered.get("diagram", [])),
                "model_version": MODEL_VERSION,
                "renders": solution_result["renders"],
            }
            span.add(
                valid=True,
                profile=profile_name,
                generatedFiles=summary["generated_files"],
            )
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
                "issues": validation["issues"],
                "model": {"version": MODEL_VERSION},
                "summary": summary,
            }
        except (IngestError, MissingDependencyError, RoundtripError) as exc:
            span.add(error=str(exc))
            return error_payload(
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
            return error_payload(
                operation="generate",
                code="config_error",
                message=str(exc),
            )
        except Exception as exc:  # pragma: no cover - defensive
            span.add(error=str(exc))
            return error_payload(
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
    with LogSpan(
        span="arch.export_yaml", inputPath=input_path, outputPath=output_path
    ) as span:
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
                "summary": {
                    "counts": {sheet: len(rows) for sheet, rows in entities.items()}
                },
            }
        except (IngestError, MissingDependencyError, RoundtripError) as exc:
            span.add(error=str(exc))
            return error_payload(
                operation="export_yaml",
                code="roundtrip_error",
                message=str(exc),
                details={"input_path": input_path, "output_path": output_path},
            )
        except Exception as exc:  # pragma: no cover - defensive
            span.add(error=str(exc))
            return error_payload(
                operation="export_yaml",
                code="unexpected_error",
                message=str(exc),
                details={"traceback": traceback.format_exc(limit=5)},
            )


def import_yaml(
    *, input_path: str, template_path: str, output_path: str
) -> dict[str, Any]:
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
            entities, passthrough = load_yaml_entities(
                input_path=resolve_cwd_path(input_path)
            )
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
                        "error_count": validation_result.get("summary", {}).get(
                            "errors", 0
                        )
                    },
                }
            span.add(ok=response["ok"])
            return response
        except (RoundtripError, MissingDependencyError, IngestError) as exc:
            span.add(error=str(exc))
            return error_payload(
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
            return error_payload(
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
            return error_payload(
                operation="bundle_solution",
                code="bundle_error",
                message=str(exc),
                details={
                    "directory": directory,
                    "output_path": output_path,
                    "include": include,
                },
            )
        except Exception as exc:  # pragma: no cover - defensive
            span.add(error=str(exc))
            return error_payload(
                operation="bundle_solution",
                code="unexpected_error",
                message=str(exc),
                details={"traceback": traceback.format_exc(limit=5)},
            )
