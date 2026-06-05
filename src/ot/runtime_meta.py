"""Mutable runtime metadata for the current OneTool MCP process."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from threading import Lock
from typing import TYPE_CHECKING, Any

from ot.paths import get_effective_cwd

if TYPE_CHECKING:
    from pathlib import Path

STARTED_AT = datetime.now(UTC)


@dataclass
class RuntimeMetaState:
    """Mutable process metadata shown by the Admin App."""

    name: str = ""
    description: str = ""
    updated_at: datetime | None = None
    direct_base_url: str | None = None
    direct_port: int | None = None


_LOCK = Lock()
_STATE = RuntimeMetaState()


def set_runtime_meta(*, name: str | None = None, description: str | None = None) -> dict[str, Any]:
    """Update mutable runtime metadata and return the full metadata payload."""
    with _LOCK:
        if name is not None:
            _STATE.name = name
        if description is not None:
            _STATE.description = description
        _STATE.updated_at = datetime.now(UTC)
    return get_runtime_meta()


def set_direct_api(*, base_url: str, port: int) -> None:
    """Record the bound Direct API URL for Admin registration and diagnostics."""
    with _LOCK:
        _STATE.direct_base_url = base_url
        _STATE.direct_port = port


def get_runtime_meta() -> dict[str, Any]:
    """Return immutable and mutable metadata for the current runtime."""
    from ot.config.loader import get_loaded_config_path
    from ot.display.state import STATE

    status = STATE.status()
    config_path = get_loaded_config_path()
    config_dir = _config_dir(config_path)
    with _LOCK:
        name = _STATE.name
        description = _STATE.description
        updated_at = _STATE.updated_at
        direct_base_url = _STATE.direct_base_url
        direct_port = _STATE.direct_port
    return {
        "identity": status.mcp_instance_id,
        "short_identity": status.mcp_instance_id.removeprefix("mcp-")[:16],
        "name": name,
        "description": description,
        "cwd": str(get_effective_cwd()),
        "config_path": str(config_path) if config_path else None,
        "config_dir": str(config_dir) if config_dir else None,
        "direct_base_url": direct_base_url,
        "direct_port": direct_port,
        "started_at": STARTED_AT.isoformat(),
        "updated_at": updated_at.isoformat() if updated_at else None,
    }


def _config_dir(config_path: Path | None) -> Path | None:
    if config_path is not None:
        return config_path.parent
    try:
        from ot.config import get_config

        return get_config()._config_dir
    except Exception:
        return None
