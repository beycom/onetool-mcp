"""Configuration and path resolution for arch pack."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ot.paths import get_config_dir, get_global_templates_dir
from otpack import get_effective_cwd, get_tool_config, resolve_cwd_path


class _ArchBaseModel(BaseModel):
    """Base model that forbids unknown config keys."""

    model_config = ConfigDict(extra="forbid")


class ArchProfileConfig(_ArchBaseModel):
    """Profile-specific settings."""

    solution_report: str = Field(
        default="templates/arch/solution/default/index.html.j2",
        description="Solution report page template file",
    )
    system_report: str = Field(
        default="templates/arch/solution/default/system.html.j2",
        description="System report page template file",
    )
    project_report: str = Field(
        default="templates/arch/solution/default/project.html.j2",
        description="Project report page template file",
    )
    system_diagram: str = Field(
        default="templates/arch/d2/system.d2.j2",
        description="System D2 template file path",
    )
    project_diagram: str = Field(
        default="templates/arch/d2/project.d2.j2",
        description="Project D2 template file path",
    )
    system_engine: str = Field(
        default="d2 {{ input }} {{ output }} --layout elk",
        description="Command template used to render system diagrams",
    )
    diagram_engine: str = Field(
        default="d2 {{ input }} {{ output }} --layout elk",
        description="Command template used to render workbook-defined diagrams",
    )
    data: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional template variables injected into Jinja contexts",
    )


class ArchConfig(_ArchBaseModel):
    """Strict tools.arch configuration model."""

    output_dir: str = Field(
        default="arch",
        description="Default output directory for generated architecture files",
    )
    default_profile: str = Field(
        default="simple",
        description="Profile name used when generate() omits profile",
    )
    list_cell_separator: str = Field(
        default=";",
        description=(
            "Separator between items when a list-valued field is encoded into a single "
            "Excel cell as bracketed text (e.g. [core;internal]). Applies only to the Excel "
            "cell encoding; YAML uses native lists. List items must not contain this character."
        ),
    )
    profiles: dict[str, ArchProfileConfig] = Field(
        default_factory=lambda: {"simple": ArchProfileConfig()},
        description="Named profiles containing templates and engine commands",
    )


class ConfigResolutionError(ValueError):
    """Raised for invalid arch config/template path values."""


class RenderTargetConfig(_ArchBaseModel):
    """Resolved render target configuration."""

    target: Literal["solution", "diagram"]
    profile_name: str
    profile: ArchProfileConfig
    engine_name: str
    cmd_template: str


@dataclass(frozen=True)
class ReportTemplateConfig:
    """Resolved report template files."""

    solution_report_path: Path
    system_report_path: Path
    project_report_path: Path


def get_arch_config() -> ArchConfig:
    """Load typed arch config."""
    try:
        return get_tool_config("arch", ArchConfig)
    except Exception as exc:
        raise ConfigResolutionError(f"Invalid tools.arch configuration: {exc}") from exc


def get_active_profile(
    *,
    config: ArchConfig,
    profile: str | None = None,
) -> tuple[str, ArchProfileConfig]:
    """Resolve active profile from config with optional override."""
    profile_name = profile or config.default_profile
    active_profile = config.profiles.get(profile_name)
    if active_profile is None:
        key = "profile" if profile_name != config.default_profile else "default_profile"
        raise ConfigResolutionError(
            f"Unknown tools.arch.{key} '{profile_name}'. "
            f"Available: {sorted(config.profiles)}"
        )
    return profile_name, active_profile


def resolve_output_dir(*, output_dir: str | None, config: ArchConfig) -> Path:
    """Resolve output directory relative to project cwd."""
    target = output_dir or config.output_dir
    return resolve_cwd_path(target)


def resolve_render_target_for_profile(
    *,
    target: Literal["solution", "diagram"],
    profile_name: str,
    profile: ArchProfileConfig,
) -> RenderTargetConfig:
    """Resolve render target command from an explicit profile object."""

    engine_template = (
        profile.system_engine if target == "solution" else profile.diagram_engine
    ).strip()
    target_key = "system" if target == "solution" else "diagram"
    if not engine_template:
        raise ConfigResolutionError(
            f"tools.arch.profiles.{profile_name}.{target_key}_engine must not be empty"
        )

    engine_name = engine_template.split(maxsplit=1)[0]

    return RenderTargetConfig(
        target=target,
        profile_name=profile_name,
        profile=profile,
        engine_name=engine_name,
        cmd_template=engine_template,
    )


def _resolve_config_relative(path_str: str) -> Path:
    try:
        config_dir = get_config_dir()
    except RuntimeError:
        config_dir = get_effective_cwd()
    return (config_dir / path_str).resolve()


def resolve_path_with_fallback(*, configured_path: str, fallback_relative: str) -> Path:
    """Resolve a template path with editable override then bundled default behavior."""
    raw = Path(configured_path).expanduser()

    if raw.is_absolute():
        resolved = raw.resolve()
        if not resolved.exists():
            raise ConfigResolutionError(
                f"Configured absolute path not found: {resolved}"
            )
        return resolved

    config_candidate = _resolve_config_relative(configured_path)
    if config_candidate.exists():
        return config_candidate

    if not Path(configured_path).as_posix().startswith("templates/arch/"):
        raise ConfigResolutionError(
            f"Configured relative path not found: {configured_path}"
        )

    fallback = (get_global_templates_dir() / fallback_relative).resolve()
    if fallback.exists():
        return fallback

    raise ConfigResolutionError(
        f"Editable template override and bundled fallback missing: {configured_path}"
    )


def _resolve_required_file(
    *, configured_path: str, fallback_relative: str, label: str
) -> Path:
    """Resolve a required template file path."""
    path = resolve_path_with_fallback(
        configured_path=configured_path,
        fallback_relative=fallback_relative,
    )
    if not path.is_file():
        raise ConfigResolutionError(f"{label} must be a file: {path}")
    return path


def resolve_report_template_paths_for_profile(
    *, profile: ArchProfileConfig
) -> ReportTemplateConfig:
    """Resolve report template files for an explicit profile object."""
    solution_report = _resolve_required_file(
        configured_path=profile.solution_report,
        fallback_relative="arch-templates/solution/default/index.html.j2",
        label="solution_report",
    )
    system_report = _resolve_required_file(
        configured_path=profile.system_report,
        fallback_relative="arch-templates/solution/default/system.html.j2",
        label="system_report",
    )
    project_report = _resolve_required_file(
        configured_path=profile.project_report,
        fallback_relative="arch-templates/solution/default/project.html.j2",
        label="project_report",
    )
    return ReportTemplateConfig(
        solution_report_path=solution_report,
        system_report_path=system_report,
        project_report_path=project_report,
    )


def _resolve_diagram_template(
    *, configured_path: str, fallback_relative: str, label: str
) -> Path:
    """Resolve a D2 diagram template path (requires a sibling styles.d2)."""
    template_path = resolve_path_with_fallback(
        configured_path=configured_path,
        fallback_relative=fallback_relative,
    )
    if not template_path.is_file():
        raise ConfigResolutionError(f"{label} must be a file: {template_path}")

    style_path = template_path.parent / "styles.d2"
    if not style_path.exists():
        raise ConfigResolutionError(f"{label} missing required file: {style_path}")
    return template_path


def resolve_system_diagram_template_path_for_profile(
    *, profile: ArchProfileConfig
) -> Path:
    """Resolve system diagram template path for an explicit profile object."""
    return _resolve_diagram_template(
        configured_path=profile.system_diagram,
        fallback_relative="arch-templates/d2/system.d2.j2",
        label="system_diagram",
    )


def resolve_project_diagram_template_path_for_profile(
    *, profile: ArchProfileConfig
) -> Path:
    """Resolve project diagram template path for an explicit profile object."""
    return _resolve_diagram_template(
        configured_path=profile.project_diagram,
        fallback_relative="arch-templates/d2/project.d2.j2",
        label="project_diagram",
    )


__all__ = [
    "ArchConfig",
    "ArchProfileConfig",
    "ConfigResolutionError",
    "RenderTargetConfig",
    "ReportTemplateConfig",
    "get_active_profile",
    "get_arch_config",
    "resolve_output_dir",
    "resolve_path_with_fallback",
    "resolve_project_diagram_template_path_for_profile",
    "resolve_render_target_for_profile",
    "resolve_report_template_paths_for_profile",
    "resolve_system_diagram_template_path_for_profile",
]
