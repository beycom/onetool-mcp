"""Tools for managing the onetool direct execution host.

Provides programmatic start/stop/status/restart/logs control over the
local HTTP execution host (the same host managed by `onetool direct start`).

Example:
    ot_direct.status()
    ot_direct.logs(lines=20)
    ot_direct.restart()
    ot_direct.stop()
"""

from __future__ import annotations

import contextlib
import json
import os
import signal
import socket
import sys
import time
from pathlib import Path
from typing import Any

from otpack import LogSpan

pack = "ot_direct"

__all__ = ["logs", "restart", "status", "stop"]

_DEFAULT_PORT = 8765
_AUTO_DIRECT_BOUND_PORT_ENV = "ONETOOL_DIRECT_BOUND_PORT"


# ---------------------------------------------------------------------------
# Internal helpers (shared with cli_commands/direct_app.py patterns)
# ---------------------------------------------------------------------------


def _pid_file(port: int) -> Path:
    return Path.home() / ".onetool" / f"direct-server-{port}.pid"


def _log_file(port: int) -> Path:
    return Path.home() / ".onetool" / f"direct-server-{port}.log"


def _read_pid_file(port: int) -> dict[str, Any] | None:
    try:
        return json.loads(_pid_file(port).read_text())
    except Exception:
        return None


def _write_pid_file(pid: int, port: int, config_path: str | None, secrets_path: str | None) -> None:
    path = _pid_file(port)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({
            "pid": pid,
            "port": port,
            "config": config_path,
            "secrets": secrets_path,
            "started": time.time(),
            "log": str(_log_file(port)),
        })
    )


def _remove_pid_file(port: int) -> None:
    with contextlib.suppress(FileNotFoundError):
        _pid_file(port).unlink()


def _is_process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False


def _kill_pid(pid: int) -> None:
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.kernel32.TerminateProcess(  # type: ignore[attr-defined]
            ctypes.windll.kernel32.OpenProcess(1, False, pid), 0  # type: ignore[attr-defined]
        )
    else:
        os.kill(pid, signal.SIGTERM)


def _tcp_probe_wait(host: str, port: int, timeout_secs: float = 5.0, interval: float = 0.1) -> bool:
    deadline = time.monotonic() + timeout_secs
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        try:
            with socket.create_connection((host, port), timeout=min(interval, remaining)):
                return True
        except (OSError, ConnectionRefusedError, TimeoutError):
            if time.monotonic() < deadline:
                time.sleep(interval)
    return False


def _resolve_port(port: int | None) -> int:
    """Resolve effective port; prefer MCP-bound auto host when available."""
    if port is not None:
        return port

    bound = os.getenv(_AUTO_DIRECT_BOUND_PORT_ENV)
    if bound:
        try:
            resolved = int(bound)
        except ValueError:
            resolved = _DEFAULT_PORT
        return resolved if 1 <= resolved <= 65535 else _DEFAULT_PORT

    return _DEFAULT_PORT


def _launch_host(config: str | None, secrets: str | None, port: int) -> int:
    """Spawn the execution host daemon. Returns the PID."""
    import subprocess

    log_path = _log_file(port)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [sys.executable, "-m", "onetool.cli_commands._direct_host_worker"]
    if config:
        cmd += ["--config", config]
    if secrets:
        cmd += ["--secrets", secrets]
    cmd += ["--port", str(port), "--host", "127.0.0.1"]

    with log_path.open("a") as log_fh:
        if sys.platform == "win32":
            proc = subprocess.Popen(
                cmd,
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
                stdout=log_fh,
                stderr=log_fh,
            )
        else:
            proc = subprocess.Popen(
                cmd,
                start_new_session=True,
                stdout=log_fh,
                stderr=log_fh,
            )

    _write_pid_file(proc.pid, port, config, secrets)
    return proc.pid


# ---------------------------------------------------------------------------
# Internal: launch + wait helper (used by restart)
# ---------------------------------------------------------------------------


def _start_and_wait(
    config: str | None,
    secrets: str | None,
    port: int,
) -> dict[str, Any] | str:
    """Launch the execution host daemon and wait until it is ready."""
    with LogSpan(span="ot_direct.start", port=port) as s:
        pid = _launch_host(config, secrets, port)
        s.add(pid=pid)

        if _tcp_probe_wait("127.0.0.1", port):
            return {
                "status": "running",
                "pid": pid,
                "port": port,
                "log": str(_log_file(port)),
            }
        return f"Error: execution host did not become ready within 5 seconds (PID {pid}, port {port})"


# ---------------------------------------------------------------------------
# Public tools
# ---------------------------------------------------------------------------


def stop(*, port: int | None = None) -> str:
    """Stop the running execution host.

    Args:
        port: Port of the host to stop (default: 8765).

    Returns:
        Status message.

    Example:
        ot_direct.stop()
        ot_direct.stop(port=9000)
    """
    resolved_port = _resolve_port(port)
    with LogSpan(span="ot_direct.stop", port=resolved_port):
        info = _read_pid_file(resolved_port)
        if info is None:
            return "No execution host running"

        pid = info["pid"]
        if not _is_process_alive(pid):
            _remove_pid_file(resolved_port)
            return "Stale PID file removed (process was not running)"

        try:
            _kill_pid(pid)
        except Exception as e:
            return f"Error: failed to stop host: {e}"

        _remove_pid_file(resolved_port)
        return "Execution host stopped"


def status(*, port: int | None = None) -> dict[str, Any] | str:
    """Show execution host status.

    Args:
        port: Port to query (default: 8765).

    Returns:
        Dict with pid, port, uptime_seconds, log — or "not running" string.

    Example:
        ot_direct.status()
        ot_direct.status(port=9000)
    """
    resolved_port = _resolve_port(port)
    with LogSpan(span="ot_direct.status", port=resolved_port) as s:
        info = _read_pid_file(resolved_port)
        if info is None:
            return "No execution host running"

        pid = info["pid"]
        if not _is_process_alive(pid):
            return "No execution host running"

        started = info.get("started")
        uptime = int(time.time() - started) if started else None
        s.add(pid=pid, uptime=uptime)
        return {
            "status": "running",
            "pid": pid,
            "port": info.get("port", resolved_port),
            "uptime_seconds": uptime,
            "config": info.get("config"),
            "log": info.get("log", str(_log_file(resolved_port))),
        }


def restart(
    *,
    config: str | None = None,
    secrets: str | None = None,
    port: int | None = None,
) -> dict[str, Any] | str:
    """Stop and restart the execution host.

    Reuses the saved config and port from the previous start.
    Explicit arguments override the saved values.

    Args:
        config: Path to onetool.yaml (defaults to saved value).
        secrets: Path to secrets file (defaults to saved value).
        port: Port (default: saved port or 8765).

    Returns:
        Same as start().

    Example:
        ot_direct.restart()
        ot_direct.restart(config='new-onetool.yaml')
    """
    resolved_port = _resolve_port(port)
    with LogSpan(span="ot_direct.restart", port=resolved_port):
        info = _read_pid_file(resolved_port)
        if info:
            pid = info["pid"]
            if _is_process_alive(pid):
                with contextlib.suppress(Exception):
                    _kill_pid(pid)
                    time.sleep(0.3)
            _remove_pid_file(resolved_port)

            if config is None and info.get("config"):
                config = info["config"]
            if secrets is None and info.get("secrets"):
                secrets = info["secrets"]

        return _start_and_wait(config, secrets, resolved_port)


def logs(*, port: int | None = None, lines: int = 50) -> str:
    """Return the last N lines of the execution host log.

    Args:
        port: Port of the host (default: 8765).
        lines: Number of lines to return (default: 50).

    Returns:
        Log tail as a string, or error message if log not found.

    Example:
        ot_direct.logs()
        ot_direct.logs(port=9000, lines=100)
    """
    resolved_port = _resolve_port(port)
    with LogSpan(span="ot_direct.logs", port=resolved_port, lines=lines):
        log_path = _log_file(resolved_port)
        if not log_path.exists():
            return f"Error: no log file found at {log_path}"

        content = log_path.read_text(encoding="utf-8", errors="replace")
        tail = content.splitlines()[-lines:]
        return "\n".join(tail)
