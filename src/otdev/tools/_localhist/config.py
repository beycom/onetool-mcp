"""Configuration and path resolution for localhist."""

from __future__ import annotations

import os
import re
from contextlib import contextmanager
from hashlib import sha256
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from otpack import get_project_state_dir, get_tool_config, resolve_cwd_path

if TYPE_CHECKING:
    from collections.abc import Iterator

SnapshotKind = str


class AutosaveConfig(BaseModel):
    """Autosave watcher scheduling configuration."""

    model_config = ConfigDict(extra="forbid")

    poll_interval_seconds: float = Field(default=30.0, gt=0)
    quiet_period_seconds: float = Field(default=30.0, ge=0)
    min_save_interval_seconds: float = Field(default=120.0, ge=0)
    heartbeat_timeout_seconds: float = Field(default=120.0, gt=0)
    message_prefix: str = Field(default="autosave")


class Config(BaseModel):
    """Pack configuration discovered by the registry."""

    model_config = ConfigDict(extra="forbid")

    git_dir: str = Field(default=".localhist")
    work_tree: str = Field(default=".")
    autosave: AutosaveConfig = Field(default_factory=AutosaveConfig)


class Paths(BaseModel):
    """Resolved localhist paths."""

    project_root: Path
    git_dir: Path
    work_tree: Path
    state_dir: Path
    force_include_file: Path

    model_config = {"arbitrary_types_allowed": True}


def load_config() -> Config:
    """Load localhist config from tools.localhist."""

    return get_tool_config("localhist", Config)


@contextmanager
def project_context(project_root: Path) -> Iterator[None]:
    """Temporarily resolve project paths against a specific project root."""

    previous = os.environ.get("OT_CWD")
    os.environ["OT_CWD"] = str(project_root)
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("OT_CWD", None)
        else:
            os.environ["OT_CWD"] = previous


def _inside(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def _project_id(project_root: Path) -> str:
    """Return a stable filesystem-safe id for the project root."""

    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", project_root.name).strip("-._") or "project"
    digest = sha256(str(project_root).encode()).hexdigest()[:12]
    return f"{slug}-{digest}"


def _resolve_git_dir(raw_git_dir: str, project_root: Path) -> Path:
    value = raw_git_dir.replace("{project_id}", _project_id(project_root))
    raw_path = Path(value)
    if raw_path.is_absolute():
        if "{project_id}" not in raw_git_dir:
            raise ValueError("absolute git_dir requires {project_id}")
        return raw_path.resolve()
    return resolve_cwd_path(value).resolve()


def resolve_paths(config: Config | None = None) -> Paths:
    """Resolve configured paths against the effective project cwd."""

    cfg = config or load_config()
    project_root = resolve_cwd_path(".").resolve()
    work_tree = resolve_cwd_path(cfg.work_tree).resolve()
    git_dir = _resolve_git_dir(cfg.git_dir, project_root)
    if not _inside(work_tree, project_root):
        raise ValueError(f"work_tree must be inside project cwd: {work_tree}")
    if "{project_id}" not in cfg.git_dir and not _inside(git_dir, project_root):
        raise ValueError(f"git_dir must be inside project cwd: {git_dir}")
    if git_dir == project_root / ".git":
        raise ValueError("git_dir must not be the primary .git directory")
    # Localhist state is intentionally project-root scoped so explicit autosave
    # paths can manage independent watchers without relying on the caller cwd.
    state_dir = get_project_state_dir("localhist")
    return Paths(
        project_root=project_root,
        git_dir=git_dir,
        work_tree=work_tree,
        state_dir=state_dir,
        force_include_file=state_dir / "force-include",
    )


def resolve_project(project_path: str | None = None) -> tuple[Config, Paths]:
    """Resolve localhist config and paths for the current or explicit project."""

    if project_path is None:
        config = load_config()
        return config, resolve_paths(config)
    project_root = resolve_cwd_path(project_path).resolve()
    if not project_root.exists() or not project_root.is_dir():
        raise ValueError(f"project path must be an existing directory: {project_path}")
    with project_context(project_root):
        config = load_config()
        return config, resolve_paths(config)


def validate_project_path(path: str, paths: Paths) -> Path:
    """Resolve and validate a path inside the configured work tree."""

    candidate = Path(os.path.normpath(paths.work_tree / path))
    if not _inside(candidate, paths.work_tree):
        raise ValueError(f"path escapes work_tree: {path}")
    return candidate


def relpath(path: Path, paths: Paths) -> str:
    """Return a POSIX project-relative path."""

    return path.relative_to(paths.work_tree).as_posix()
