"""File-backed whiteboard session state.

Board state is persisted at {CWD}/.onetool/state/whiteboard/{key}.json.
The key is derived from the resolved CWD (SHA-256 prefix) unless a named board is given.

Schema:
    {
        "shapes": {id: {"label": ..., "classes": [...]}},
        "edges":  [{"id":..., "src":..., "dst":..., "label":..., ...}],
        "groups": {gid: {"label":..., "members":[...]}},
        "edge_keys": [[src, dst, label, startArrow, endArrow], ...],
        "canvas_max_y": float
    }
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import re
from typing import TYPE_CHECKING, Any

from otpack import get_effective_cwd, get_project_state_dir

if TYPE_CHECKING:
    from pathlib import Path

_BOARD_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def _whiteboard_dir() -> Path:
    """Return the project-local whiteboard state directory, creating it if needed."""
    d = get_project_state_dir("whiteboard")
    d.mkdir(parents=True, exist_ok=True)
    return d


def cwd_key() -> str:
    """Derive session key from the resolved CWD: first 12 hex chars of SHA-256."""
    cwd = str(get_effective_cwd())
    return hashlib.sha256(cwd.encode()).hexdigest()[:12]


def session_path(board: str | None) -> Path:
    """Return the Path for the session file.

    Named boards use {CWD}/.onetool/state/whiteboard/{board}.json.
    Default (CWD-keyed) boards use {CWD}/.onetool/state/whiteboard/{cwd_key}.json.
    """
    d = _whiteboard_dir()
    if board:
        if not _BOARD_NAME_RE.match(board):
            raise ValueError(f"Invalid board name {board!r}: only A-Z, a-z, 0-9, _ and - are allowed")
        return d / f"{board}.json"
    return d / f"{cwd_key()}.json"


def load(board: str | None = None) -> dict[str, Any]:
    """Load session state from file.

    Returns a fresh empty state if no file exists or the file is corrupted.
    The ``edge_keys`` field is returned as a ``set[tuple]``.
    """
    path = session_path(board)
    if path.exists():
        try:
            data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
            # Convert edge_keys from list-of-lists back to set-of-tuples
            raw_keys = data.get("edge_keys", [])
            data["edge_keys"] = {tuple(k) for k in raw_keys}
            # Ensure all expected keys exist (forward-compat)
            data.setdefault("shapes", {})
            data.setdefault("edges", [])
            data.setdefault("groups", {})
            data.setdefault("canvas_max_y", 60.0)
            return data
        except Exception:
            pass
    return {
        "shapes": {},
        "edges": [],
        "groups": {},
        "edge_keys": set(),
        "canvas_max_y": 60.0,
    }


def save(state: dict[str, Any], board: str | None = None) -> None:
    """Persist session state to file.

    ``edge_keys`` (a ``set[tuple]``) is serialised as a list-of-lists for JSON.
    """
    path = session_path(board)
    serializable = {
        "shapes": state["shapes"],
        "edges": state["edges"],
        "groups": state["groups"],
        "edge_keys": [list(k) for k in state.get("edge_keys", set())],
        "canvas_max_y": state.get("canvas_max_y", 60.0),
    }
    path.write_text(json.dumps(serializable, indent=2, ensure_ascii=False), encoding="utf-8")


def list_boards() -> list[dict[str, Any]]:
    """Return a list of active boards with name, mtime, and shape count.

    Only files in {CWD}/.onetool/state/whiteboard/*.json are listed.
    """
    d = _whiteboard_dir()
    boards = []
    for p in sorted(d.glob("*.json")):
        name = p.stem
        mtime = p.stat().st_mtime
        shape_count = 0
        with contextlib.suppress(Exception):
            shape_count = len(json.loads(p.read_text(encoding="utf-8")).get("shapes", {}))
        boards.append({"name": name, "mtime": mtime, "shape_count": shape_count})

    return boards


def clear_board(board: str | None = None) -> str:
    """Delete the session file for the given board.

    Returns a message confirming deletion or reporting that no board was found.
    """
    path = session_path(board)
    display = board if board else f"<cwd:{cwd_key()}>"
    if path.exists():
        path.unlink()
        return f"cleared board '{display}'"
    return f"no board '{display}' found"
