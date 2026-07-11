"""Autosave watcher runtime for localhist."""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from contextlib import suppress
from pathlib import Path
from typing import Any

from filelock import FileLock

from otdev.tools._localhist.config import (
    Config,
    Paths,
    project_context,
    resolve_project,
)
from otdev.tools._localhist.core import (
    repository_dirty_signature,
    save_snapshot_for_project,
)

STATE_FILE = "autosave-state.json"
LOCK_FILE = "autosave.lock"


def _now() -> float:
    return time.time()


def _pid_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _state_path(paths: Paths) -> Path:
    return paths.state_dir / STATE_FILE


def _lock_path(paths: Paths) -> Path:
    paths.state_dir.mkdir(parents=True, exist_ok=True)
    return paths.state_dir / LOCK_FILE


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text())
    except FileNotFoundError:
        return {}
    except (OSError, json.JSONDecodeError) as exc:
        # A corrupt or unreadable state file must not kill the watcher.
        # Report the failure through recent_errors and let callers rebuild.
        return {"recent_errors": [f"state file reset ({type(exc).__name__}): {exc}"]}
    return data if isinstance(data, dict) else {}


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def _state(paths: Paths) -> dict[str, Any]:
    data = _read_json(_state_path(paths))
    pid = data.get("pid")
    heartbeat = data.get("heartbeat_at")
    timeout = float(data.get("heartbeat_timeout_seconds", 120.0))
    alive = _pid_alive(pid if isinstance(pid, int) else None)
    stale = bool(data) and (
        data.get("status") == "stopped"
        or not alive
        or (isinstance(heartbeat, int | float) and _now() - float(heartbeat) > timeout)
    )
    data["active"] = bool(data) and not stale and data.get("status") in {"starting", "running"}
    data["stale"] = stale
    return data


def _new_state(config: Config, paths: Paths, *, status: str) -> dict[str, Any]:
    now = _now()
    return {
        "status": status,
        "pid": None,
        "project_root": str(paths.project_root),
        "heartbeat_at": now,
        "last_event_at": None,
        "last_save": None,
        "recent_errors": [],
        "stop_requested": False,
        "poll_interval_seconds": config.autosave.poll_interval_seconds,
        "quiet_period_seconds": config.autosave.quiet_period_seconds,
        "min_save_interval_seconds": config.autosave.min_save_interval_seconds,
        "heartbeat_timeout_seconds": config.autosave.heartbeat_timeout_seconds,
        "message_prefix": config.autosave.message_prefix,
    }


def _config_payload(config: Config) -> dict[str, Any]:
    return config.model_dump()


def autosave_start_project(*, path: str | None = None) -> dict[str, object]:
    """Start or reuse the shared autosave watcher."""

    config, paths = resolve_project(path)
    if path is not None:
        _, current_paths = resolve_project(None)
        if current_paths.project_root != paths.project_root:
            with FileLock(str(_lock_path(current_paths))):
                current_state = _state(current_paths)
                if current_state.get("pid") and (
                    current_state.get("active") or current_state.get("stale")
                ):
                    _request_stop(current_paths, current_state)
    with FileLock(str(_lock_path(paths))):
        current = _state(paths)
        if current.get("active") and current.get("project_root") == str(paths.project_root):
            return {
                "ok": True,
                "started": False,
                "reused": True,
                "config": _config_payload(config),
                "state": current,
            }
        if current.get("pid") and (current.get("active") or current.get("stale")):
            _request_stop(paths, current)
        state = _new_state(config, paths, status="starting")
        _write_json(_state_path(paths), state)
        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "otdev.tools._localhist.autosave",
                "--project-root",
                str(paths.project_root),
            ],
            cwd=str(paths.project_root),
            env={**os.environ, "OT_CWD": str(paths.project_root)},
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        state["pid"] = proc.pid
        state["status"] = "running"
        state["heartbeat_at"] = _now()
        _write_json(_state_path(paths), state)
        return {
            "ok": True,
            "started": True,
            "reused": False,
            "config": _config_payload(config),
            "state": _state(paths),
        }


def autosave_list_project() -> dict[str, object]:
    """Return shared watcher status for the effective project."""

    config, paths = resolve_project(None)
    state = _state(paths)
    return {
        "ok": True,
        "state_file": str(_state_path(paths)),
        "config": _config_payload(config),
        "active_project": state.get("project_root"),
        "active": state.get("active", False),
        "stale": state.get("stale", False),
        "state": state or None,
        "last_save": state.get("last_save"),
    }


def _request_stop(paths: Paths, state: dict[str, Any]) -> None:
    state["stop_requested"] = True
    state["status"] = "stopping"
    _write_json(_state_path(paths), state)
    pid = state.get("pid")
    if isinstance(pid, int) and _pid_alive(pid):
        with suppress(ProcessLookupError, PermissionError):
            os.kill(pid, signal.SIGTERM)


def autosave_stop_project(*, path: str | None = None) -> dict[str, object]:
    """Stop the shared watcher, optionally scoped to a project path."""

    _, paths = resolve_project(path)
    if path is not None and not _state_path(paths).exists():
        _, current_paths = resolve_project(None)
        current_state = _state(current_paths)
        if current_state.get("active"):
            return {
                "ok": True,
                "stopped": False,
                "reason": "active_project_mismatch",
                "active_project": current_state.get("project_root"),
            }
    with FileLock(str(_lock_path(paths))):
        state = _state(paths)
        if not state:
            return {"ok": True, "stopped": False, "reason": "not_running", "state": None}
        if path is not None and state.get("project_root") != str(paths.project_root):
            return {
                "ok": True,
                "stopped": False,
                "reason": "active_project_mismatch",
                "active_project": state.get("project_root"),
            }
        _request_stop(paths, state)
        state["active"] = False
        state["stale"] = False
        return {"ok": True, "stopped": True, "state": state}


def run_once(*, project_root: Path) -> dict[str, object]:
    """Run one autosave scheduling iteration for tests and the watcher loop."""

    config, paths = resolve_project(str(project_root))
    # Hold the same lock as start/stop for the whole read-modify-write so a
    # concurrent stop_requested=True cannot be clobbered by this iteration.
    with FileLock(str(_lock_path(paths))):
        state = _state(paths) or _new_state(config, paths, status="running")
        with project_context(paths.project_root):
            dirty_signature = repository_dirty_signature()
        dirty = dirty_signature is not None
        now = _now()
        state["heartbeat_at"] = now
        state["status"] = "running"
        if dirty and state.get("last_dirty_signature") != dirty_signature:
            state["last_event_at"] = now
            state["last_dirty_signature"] = dirty_signature
        last_event = state.get("last_event_at")
        last_save = state.get("last_save") or {}
        last_save_at = last_save.get("timestamp") if isinstance(last_save, dict) else None
        quiet = not last_event or now - float(last_event) >= config.autosave.quiet_period_seconds
        interval_ok = not last_save_at or now - float(last_save_at) >= config.autosave.min_save_interval_seconds
        if dirty and quiet and interval_ok:
            result = save_snapshot_for_project(
                project_root=paths.project_root,
                message=f"{config.autosave.message_prefix}: {time.strftime('%Y-%m-%d %H:%M:%S')}",
                kind="auto",
            )
            state["last_save"] = {"timestamp": now, "result": result}
            state["last_event_at"] = None
        elif not dirty:
            state["last_save"] = {"timestamp": now, "result": {"ok": True, "created": False, "reason": "no_changes"}}
            state["last_event_at"] = None
            state["last_dirty_signature"] = None
        _write_json(_state_path(paths), state)
    return state


def run_loop(*, project_root: Path) -> None:
    """Run the watcher loop until stopped."""

    while True:
        _, paths = resolve_project(str(project_root))
        with FileLock(str(_lock_path(paths))):
            state = _read_json(_state_path(paths))
            if state.get("stop_requested"):
                state["status"] = "stopped"
                state["heartbeat_at"] = _now()
                _write_json(_state_path(paths), state)
                return
        try:
            state = dict(run_once(project_root=project_root))
        except Exception as exc:  # pragma: no cover - defensive process loop
            with FileLock(str(_lock_path(paths))):
                state = _read_json(_state_path(paths))
                errors = [str(exc), *state.get("recent_errors", [])][:5]
                state["recent_errors"] = errors
                state["heartbeat_at"] = _now()
                _write_json(_state_path(paths), state)
        time.sleep(float(state.get("poll_interval_seconds", 30.0)))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", required=True)
    args = parser.parse_args()
    run_loop(project_root=Path(args.project_root).resolve())


if __name__ == "__main__":
    main()
