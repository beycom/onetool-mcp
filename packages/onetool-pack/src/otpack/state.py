"""Project-local state helpers for OneTool packs."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import yaml

from otpack.paths import get_project_state_dir

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["get_state", "set_state"]

def _state_path(pack: str, state_path: Path | None = None) -> Path:
    """Return the project-local pack-owned state file path."""
    if state_path is not None:
        return state_path
    return get_project_state_dir(pack) / "state.yaml"


def _load_state(path: Path) -> dict[str, Any]:
    """Load and validate a pack-owned state document."""
    if not path.exists():
        return {}

    try:
        raw = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"Malformed OneTool state file: {path}") from exc

    if not isinstance(raw, dict):
        raise ValueError(f"Malformed OneTool state file: {path}")

    return raw


def get_state(pack: str, key: str, default: Any = None, *, state_path: Path | None = None) -> Any:
    """Return a pack-scoped project state value.

    Args:
        pack: Pack namespace under the project ``state/`` directory.
        key: State key within the pack-owned file.
        default: Value returned when the key is absent.
        state_path: Optional state file path. Defaults to project-local
            ``.onetool/state/{pack}/state.yaml``.

    Returns:
        Stored value, or ``default`` when no value exists.
    """
    data = _load_state(_state_path(pack, state_path))
    return data.get(key, default)


def set_state(pack: str, key: str, value: Any, *, state_path: Path | None = None) -> None:
    """Store a pack-scoped project state value.

    Args:
        pack: Pack namespace under the project ``state/`` directory.
        key: State key within the pack-owned file.
        value: YAML-serializable state value.
        state_path: Optional state file path. Defaults to project-local
            ``.onetool/state/{pack}/state.yaml``.
    """
    path = _state_path(pack, state_path)
    data = _load_state(path)
    data[key] = value

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False))
