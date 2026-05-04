"""Configuration and path resolution for arch pack."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from otpack import get_effective_cwd, get_tool_config, resolve_cwd_path
from pydantic import BaseModel, ConfigDict, Field

from ot.paths import get_config_dir, get_global_templates_dir


class _ArchBaseModel(BaseModel):
    """Base model that forbids unknown config keys."""

    model_config = ConfigDict(extra="forbid")


class ArchProfileConfig(_ArchBaseModel):
    """Profile-specific settings."""

    solution_report: str = Field(
        default="arch-templates/solution/default/index.html.j2",
        description="Solution report page template file",
    )
    system_report: str = Field(
        default="arch-templates/solution/default/system.html.j2",
        description="System report page template file",
    )
    system_diagram: str = Field(
        default="arch-templates/d2/system.d2.j2",
        description="System D2 template file path",
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
        default="architecture-output",
        description="Default output directory for generated architecture files",
    )
    default_profile: str = Field(
        default="simple",
        description="Profile name used when generate() omits profile",
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


def get_arch_config() -> ArchConfig:
    """Load typed arch config."""
    try:
        return get_tool_config("arch", ArchConfig)
    except Exception as exc:
        raise ConfigResolutionError(
            f"Invalid tools.arch configuration: {exc}"
        ) from exc


def get_active_profile(
    *,
    config: ArchConfig,
    profile: str | None = None,
) -> tuple[str, ArchProfileConfig]:
    """Resolve active profile from config with optional override."""
    profile_name = profile or config.default_profile
    profile = config.profiles.get(profile_name)
    if profile is None:
        key = "profile" if profile_name != config.default_profile else "default_profile"
        raise ConfigResolutionError(
            f"Unknown tools.arch.{key} '{profile_name}'. "
            f"Available: {sorted(config.profiles)}"
        )
    return profile_name, profile


def resolve_output_dir(*, output_dir: str | None, config: ArchConfig) -> Path:
    """Resolve output directory relative to project cwd."""
    target = output_dir or config.output_dir
    return resolve_cwd_path(target)


def resolve_render_target(
    *,
    config: ArchConfig,
    target: Literal["solution", "diagram"],
    profile: str | None = None,
) -> RenderTargetConfig:
    """Resolve render target command from active profile."""
    profile_name, profile = get_active_profile(config=config, profile=profile)
    return resolve_render_target_for_profile(
        target=target,
        profile_name=profile_name,
        profile=profile,
    )


def resolve_render_target_for_profile(
    *,
    target: Literal["solution", "diagram"],
    profile_name: str,
    profile: ArchProfileConfig,
) -> RenderTargetConfig:
    """Resolve render target command from an explicit profile object."""

    engine_template = (
        profile.system_engine
        if target == "solution"
        else profile.diagram_engine
    ).strip()
    target_key = "system" if target == "solution" else "diagram"
    if not engine_template:
        raise ConfigResolutionError(
            f"tools.arch.profiles.{profile_name}.{target_key}_engine must not be empty"
        )

    engine_name = engine_template.split(maxsplit=1)[0] if engine_template else ""
    if not engine_name:
        raise ConfigResolutionError(
            f"tools.arch.profiles.{profile_name}.{target_key}_engine must start with an engine command"
        )

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
    """Resolve path with config-dir then bundled fallback behavior."""
    raw = Path(configured_path).expanduser()

    if raw.is_absolute():
        resolved = raw.resolve()
        if not resolved.exists():
            raise ConfigResolutionError(f"Configured absolute path not found: {resolved}")
        return resolved

    config_candidate = _resolve_config_relative(configured_path)
    if config_candidate.exists():
        return config_candidate

    fallback = (get_global_templates_dir() / fallback_relative).resolve()
    if fallback.exists():
        return fallback

    raise ConfigResolutionError(
        f"Configured relative path not found in config dir and fallback missing: {configured_path}"
    )


def _resolve_required_file(*, configured_path: str, fallback_relative: str, label: str) -> Path:
    """Resolve a required template file path."""
    path = resolve_path_with_fallback(
        configured_path=configured_path,
        fallback_relative=fallback_relative,
    )
    if not path.is_file():
        raise ConfigResolutionError(f"{label} must be a file: {path}")
    return path


def resolve_report_template_paths(*, config: ArchConfig, profile: str | None = None) -> ReportTemplateConfig:
    """Resolve active profile report template files."""
    _, selected_profile = get_active_profile(config=config, profile=profile)
    return resolve_report_template_paths_for_profile(profile=selected_profile)


def resolve_report_template_paths_for_profile(*, profile: ArchProfileConfig) -> ReportTemplateConfig:
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
    return ReportTemplateConfig(
        solution_report_path=solution_report,
        system_report_path=system_report,
    )


def resolve_system_diagram_template_path(*, config: ArchConfig, profile: str | None = None) -> Path:
    """Resolve active profile system diagram template path."""
    _, selected_profile = get_active_profile(config=config, profile=profile)
    return resolve_system_diagram_template_path_for_profile(profile=selected_profile)


def resolve_system_diagram_template_path_for_profile(*, profile: ArchProfileConfig) -> Path:
    """Resolve system diagram template path for an explicit profile object."""
    template_path = resolve_path_with_fallback(
        configured_path=profile.system_diagram,
        fallback_relative="arch-templates/d2/system.d2.j2",
    )
    if not template_path.is_file():
        raise ConfigResolutionError(f"system_diagram must be a file: {template_path}")

    style_path = template_path.parent / "styles.d2"
    if not style_path.exists():
        raise ConfigResolutionError(
            f"system_diagram missing required file: {style_path}"
        )
    return template_path


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
    "resolve_render_target",
    "resolve_render_target_for_profile",
    "resolve_report_template_paths",
    "resolve_report_template_paths_for_profile",
    "resolve_system_diagram_template_path",
    "resolve_system_diagram_template_path_for_profile",
]
