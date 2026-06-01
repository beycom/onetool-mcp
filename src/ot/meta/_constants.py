"""Constants, types, and shared path utilities for ot.meta."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

# Info level type for discovery functions
InfoLevel = Literal["list", "min", "default", "full"]
ServerInfoLevel = Literal["min", "default", "full", "resources", "prompts"]

# Pack name for dot notation: ot.tools(), ot.packs(), etc.
PACK_NAME = "ot"

DOC_BASE_URL = "https://onetool.beycom.online/reference/tools/"


def safe_server_name(server_name: str) -> str:
    """Return the Python-safe identifier for an MCP server name.

    my-server → my_server.
    """
    return server_name.replace("-", "_")


def resolve_ot_path(path: str) -> Path:
    """Resolve a path relative to the OT_DIR (config_path.parent).

    Resolution priority:
    1. If absolute or ~ path: use as-is
    2. Resolve relative to config._config_dir

    Args:
        path: Path string (relative, absolute, or with ~)

    Returns:
        Resolved absolute Path
    """
    p = Path(path).expanduser()
    if p.is_absolute():
        return p.resolve()

    from ot.paths import get_config_dir

    return (get_config_dir() / p).resolve()
