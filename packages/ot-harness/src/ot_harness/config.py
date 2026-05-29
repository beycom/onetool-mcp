"""Strict experiment and variant config loading for ot-harness."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ConfigError(ValueError):
    """Raised when an ot-harness config is invalid."""


class VariantKind(StrEnum):
    """Supported Codex benchmark variant kinds."""

    CODEX_BASE = "codex-base"
    CODEX_ONETOOL_MCP = "codex-onetool-mcp"
    CODEX_SKILLS = "codex-skills"


class HarborSettings(BaseModel):
    """Harbor execution settings shared by all trials."""

    model_config = ConfigDict(extra="forbid")

    dataset: str = Field(min_length=1)
    agent: str = Field(default="codex", min_length=1)
    model: str = Field(min_length=1)
    reasoning_effort: str | None = Field(default=None, min_length=1)
    harbor_bin: str = Field(default="harbor", min_length=1)
    run_args: list[str] = Field(default_factory=list)


class MetricExpectations(BaseModel):
    """Metric fields expected from Harbor result output."""

    model_config = ConfigDict(extra="forbid")

    verifier_required: bool = True
    tokens_required: bool = False
    cost_required: bool = False


class WorkspaceMountConfig(BaseModel):
    """Optional host workspace mounted into each Harbor task container."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    target: str = Field(default="/app", min_length=1)
    root: Path | None = None

    @field_validator("target")
    @classmethod
    def target_must_be_absolute_container_path(cls, value: str) -> str:
        """Require a simple absolute container path for the workspace mount."""
        if not value.startswith("/"):
            raise ValueError("workspace_mount.target must be an absolute path")
        if "?" in value or "#" in value or any(ch.isspace() for ch in value):
            raise ValueError(
                "workspace_mount.target must not contain whitespace, query, or fragment"
            )
        return value


class VariantRef(BaseModel):
    """Reference to a variant config file from an experiment."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    path: Path


class ExperimentConfigRaw(BaseModel):
    """Raw experiment config before path resolution."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    harbor: HarborSettings
    task_file: Path
    variants: list[VariantRef] = Field(min_length=1)
    repetitions: int = Field(default=1, ge=1)
    timeout_seconds: int = Field(default=3600, ge=1)
    extra_instruction_paths: list[Path] = Field(default_factory=list)
    output_root: Path | None = None
    metrics: MetricExpectations = Field(default_factory=MetricExpectations)
    workspace_mount: WorkspaceMountConfig = Field(
        default_factory=WorkspaceMountConfig
    )

    @field_validator("task_file")
    @classmethod
    def task_file_must_not_be_empty(cls, value: Path) -> Path:
        """Reject empty path values."""
        if str(value).strip() == "":
            raise ValueError("task_file must not be empty")
        return value


class OneToolMcpConfig(BaseModel):
    """HTTP MCP server config for OneTool harness variants."""

    model_config = ConfigDict(extra="forbid")

    config_path: Path
    server_name: str = Field(default="onetool", min_length=1)
    url: str = Field(min_length=1)

    @field_validator("url")
    @classmethod
    def url_must_be_http_mcp_endpoint(cls, value: str) -> str:
        """Require an explicit HTTP URL for the host-running OneTool MCP server."""
        if not value.startswith(("http://", "https://")):
            raise ValueError("mcp.url must start with http:// or https://")
        if "?" in value or "#" in value or any(ch.isspace() for ch in value):
            raise ValueError("mcp.url must not contain whitespace, query, or fragment")
        return value


class VariantConfigRaw(BaseModel):
    """Raw variant config before path resolution."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    kind: VariantKind
    description: str = ""
    skills_dir: Path | None = None
    skill_paths: list[Path] = Field(default_factory=list)
    mcp: OneToolMcpConfig | None = None
    neutral_skills_dir: Path | None = None

    @model_validator(mode="after")
    def validate_kind_fields(self) -> VariantConfigRaw:
        """Validate required and forbidden fields by variant kind."""
        if self.kind == VariantKind.CODEX_BASE:
            if self.mcp is not None:
                raise ValueError("codex-base variant must not configure mcp")
            if self.skills_dir is not None:
                raise ValueError("codex-base variant must not configure skills_dir")
        if self.kind == VariantKind.CODEX_ONETOOL_MCP:
            if self.mcp is None:
                raise ValueError("codex-onetool-mcp variant requires mcp")
            if self.skills_dir is not None:
                raise ValueError(
                    "codex-onetool-mcp variant must not configure skills_dir"
                )
        if self.kind == VariantKind.CODEX_SKILLS:
            if self.skills_dir is None:
                raise ValueError("codex-skills variant requires skills_dir")
            if not self.id.startswith("codex-skills-"):
                raise ValueError(
                    "codex-skills variant id must start with codex-skills-"
                )
        return self


class VariantConfig(BaseModel):
    """Resolved variant config."""

    model_config = ConfigDict(frozen=True)

    id: str
    kind: VariantKind
    description: str
    path: Path
    skills_dir: Path | None = None
    skill_paths: list[Path]
    mcp: OneToolMcpConfig | None = None
    neutral_skills_dir: Path | None = None


class ExperimentConfig(BaseModel):
    """Resolved experiment config with referenced tasks and variants."""

    model_config = ConfigDict(frozen=True)

    name: str
    path: Path
    harbor: HarborSettings
    task_file: Path
    tasks: list[str]
    variants: list[VariantConfig]
    repetitions: int
    timeout_seconds: int
    extra_instruction_paths: list[Path]
    output_root: Path
    metrics: MetricExpectations
    workspace_mount: WorkspaceMountConfig


LEGACY_FIELDS = frozenset(
    {
        "scenarios",
        "providers",
        "models",
        "servers",
        "prompts",
        "evaluators",
        "judge",
        "secrets",
        "bench",
    }
)


def load_experiment(path: Path) -> ExperimentConfig:
    """Load, validate, and resolve an experiment config.

    Args:
        path: Experiment YAML file.

    Returns:
        Resolved experiment config.

    Raises:
        ConfigError: If the experiment, task file, variant refs, or output root
            are invalid.
    """
    config_path = path.resolve()
    raw_data = _load_yaml_mapping(config_path)
    _reject_legacy_fields(raw_data, config_path)
    raw = _parse_model(ExperimentConfigRaw, raw_data, config_path)

    task_file = _resolve_existing_file(config_path.parent, raw.task_file, "task_file")
    tasks = _load_tasks(task_file)
    extra_instruction_paths = [
        _resolve_existing_file(
            config_path.parent, instruction_path, "extra_instruction_path"
        )
        for instruction_path in raw.extra_instruction_paths
    ]

    variants = [
        _load_variant(config_path.parent, ref.path, expected_id=ref.id)
        for ref in raw.variants
    ]
    _reject_duplicate_variant_ids(variants)

    output_root = (
        (config_path.parent / raw.output_root).resolve()
        if raw.output_root
        else _default_output_root()
    )
    package_root = _package_root()
    if output_root == package_root or package_root in output_root.parents:
        raise ConfigError(
            f"output_root must not resolve inside packages/ot-harness: {output_root}"
        )
    workspace_root = (
        (config_path.parent / raw.workspace_mount.root).resolve()
        if raw.workspace_mount.root is not None
        else output_root / "workspaces" / raw.name
    )
    workspace_mount = raw.workspace_mount.model_copy(update={"root": workspace_root})

    return ExperimentConfig(
        name=raw.name,
        path=config_path,
        harbor=raw.harbor,
        task_file=task_file,
        tasks=tasks,
        variants=variants,
        repetitions=raw.repetitions,
        timeout_seconds=raw.timeout_seconds,
        extra_instruction_paths=extra_instruction_paths,
        output_root=output_root,
        metrics=raw.metrics,
        workspace_mount=workspace_mount,
    )


def _load_variant(base_dir: Path, path: Path, *, expected_id: str) -> VariantConfig:
    variant_path = _resolve_existing_file(base_dir, path, "variant path")
    raw_data = _load_yaml_mapping(variant_path)
    _reject_legacy_fields(raw_data, variant_path)
    raw = _parse_model(VariantConfigRaw, raw_data, variant_path)
    if raw.id != expected_id:
        raise ConfigError(
            f"{variant_path}: variant id {raw.id!r} does not match experiment ref {expected_id!r}"
        )

    skills_dir = (
        _resolve_existing_dir(variant_path.parent, raw.skills_dir, "skills_dir")
        if raw.skills_dir is not None
        else None
    )
    neutral_skills_dir = (
        _resolve_existing_dir(
            variant_path.parent, raw.neutral_skills_dir, "neutral_skills_dir"
        )
        if raw.neutral_skills_dir is not None
        else None
    )
    skill_paths = [
        _resolve_existing_dir(variant_path.parent, skill_path, "skill_paths")
        for skill_path in raw.skill_paths
    ]
    mcp = raw.mcp
    if mcp is not None:
        config_path = _resolve_existing_file(
            variant_path.parent, mcp.config_path, "mcp.config_path"
        )
        mcp = mcp.model_copy(update={"config_path": config_path})

    return VariantConfig(
        id=raw.id,
        kind=raw.kind,
        description=raw.description,
        path=variant_path,
        skills_dir=skills_dir,
        skill_paths=skill_paths,
        neutral_skills_dir=neutral_skills_dir,
        mcp=mcp,
    )


def _load_yaml_mapping(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ConfigError(f"Config file does not exist: {path}")
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ConfigError(f"{path}: expected YAML mapping")
    return data


def _parse_model[T: BaseModel](
    model_type: type[T], data: dict[str, Any], path: Path
) -> T:
    try:
        return model_type.model_validate(data)
    except ValueError as exc:
        raise ConfigError(f"{path}: {exc}") from exc


def _reject_legacy_fields(data: dict[str, Any], path: Path) -> None:
    legacy = sorted(set(data) & LEGACY_FIELDS)
    if legacy:
        joined = ", ".join(legacy)
        raise ConfigError(
            f"{path}: legacy bench config fields are not supported: {joined}"
        )


def _resolve_existing_file(base_dir: Path, path: Path, label: str) -> Path:
    resolved = (base_dir / path).resolve()
    if not resolved.is_file():
        raise ConfigError(f"{label} does not exist: {resolved}")
    return resolved


def _resolve_existing_dir(base_dir: Path, path: Path, label: str) -> Path:
    resolved = (base_dir / path).resolve()
    if not resolved.is_dir():
        raise ConfigError(f"{label} does not exist: {resolved}")
    return resolved


def _load_tasks(path: Path) -> list[str]:
    data = _load_yaml_mapping(path)
    _reject_legacy_fields(data, path)
    tasks = data.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        raise ConfigError(f"{path}: tasks must be a non-empty list")
    result: list[str] = []
    for index, item in enumerate(tasks):
        if not isinstance(item, str) or not item.strip():
            raise ConfigError(f"{path}: tasks[{index}] must be a non-empty string")
        result.append(item)
    allowed: set[str] = {"tasks"}
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise ConfigError(f"{path}: unknown fields: {', '.join(unknown)}")
    return result


def _reject_duplicate_variant_ids(variants: list[VariantConfig]) -> None:
    seen: set[str] = set()
    for variant in variants:
        if variant.id in seen:
            raise ConfigError(f"Duplicate variant id: {variant.id}")
        seen.add(variant.id)


def _default_output_root() -> Path:
    return (_repo_root() / "tmp" / "harness" / "harbor").resolve()


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _package_root() -> Path:
    return Path(__file__).resolve().parents[2]
