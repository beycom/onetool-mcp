"""Project-local state helpers for OneTool packs."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import yaml

from otpack.paths import resolve_cwd_path

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["get_state", "set_state"]

STATE_VERSION = 1


def _state_path(state_path: Path | None = None) -> Path:
    """Return the project-local OneTool state file path."""
    if state_path is not None:
        return state_path
    return resolve_cwd_path(".onetool/state.yaml")


def _load_state(path: Path) -> dict[str, Any]:
    """Load and validate the full state document."""
    if not path.exists():
        return {"version": STATE_VERSION, "packs": {}}

    try:
        raw = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"Malformed OneTool state file: {path}") from exc

    if not isinstance(raw, dict):
        raise ValueError(f"Malformed OneTool state file: {path}")

    version = raw.get("version")
    if version != STATE_VERSION:
        raise ValueError(f"Unsupported OneTool state version: {version!r}")

    packs = raw.get("packs", {})
    if not isinstance(packs, dict):
        raise ValueError(f"Malformed OneTool state file: {path}")

    return {"version": STATE_VERSION, "packs": packs}


def get_state(pack: str, key: str, default: Any = None, *, state_path: Path | None = None) -> Any:
    """Return a pack-scoped project state value.

    Args:
        pack: Pack namespace under ``packs``.
        key: State key within the pack namespace.
        default: Value returned when the key is absent.
        state_path: Optional state file path. Defaults to project-local
            ``.onetool/state.yaml``.

    Returns:
        Stored value, or ``default`` when no value exists.
    """
    data = _load_state(_state_path(state_path))
    pack_state = data["packs"].get(pack, {})
    if not isinstance(pack_state, dict):
        raise ValueError(f"Malformed OneTool state for pack: {pack}")
    return pack_state.get(key, default)


def set_state(pack: str, key: str, value: Any, *, state_path: Path | None = None) -> None:
    """Store a pack-scoped project state value.

    Args:
        pack: Pack namespace under ``packs``.
        key: State key within the pack namespace.
        value: YAML-serializable state value.
        state_path: Optional state file path. Defaults to project-local
            ``.onetool/state.yaml``.
    """
    path = _state_path(state_path)
    data = _load_state(path)
    packs = data["packs"]
    pack_state = packs.setdefault(pack, {})
    if not isinstance(pack_state, dict):
        raise ValueError(f"Malformed OneTool state for pack: {pack}")
    pack_state[key] = value

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False))
