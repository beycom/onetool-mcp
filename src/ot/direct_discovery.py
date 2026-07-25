"""On-disk discovery file for the MCP-owned Direct API.

External consumers (for example onetool-console) need to find the actual
port a running MCP instance bound, since the Direct API auto-increments past
`direct.host.port` when the preferred port is taken. This module writes one
JSON file per live instance under `<ot-dir>/runtime/direct-api/<instance_id>.json`
when the Direct API successfully binds, removes it on clean shutdown, and
sweeps sibling files left behind by processes that are no longer alive.
"""

from __future__ import annotations

import json
import os
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from loguru import logger

from ot.logging import LogEntry

if TYPE_CHECKING:
    from pathlib import Path

DISCOVERY_SUBDIR = "direct-api"


def _discovery_dir() -> Path:
    from ot.paths import get_ot_runtime_dir

    return get_ot_runtime_dir(DISCOVERY_SUBDIR)


def _discovery_path(instance_id: str, *, base_dir: Path | None = None) -> Path:
    directory = base_dir if base_dir is not None else _discovery_dir()
    return directory / f"{instance_id}.json"


def pid_alive(pid: int) -> bool:
    """Return whether `pid` refers to a live process (`os.kill(pid, 0)` semantics)."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # A process we cannot signal still exists.
        return True
    return True


def write_discovery_file(
    *, instance_id: str, port: int, pid: int | None = None, base_dir: Path | None = None
) -> Path:
    """Atomically write the discovery file for the currently bound Direct API.

    Writes a temp file in the same directory and `os.replace`s it into place so
    readers never observe a partially written file, then chmods it `0600`.
    """
    directory = base_dir if base_dir is not None else _discovery_dir()
    directory.mkdir(parents=True, exist_ok=True)

    resolved_pid = os.getpid() if pid is None else pid
    payload: dict[str, Any] = {
        "instance_id": instance_id,
        "port": port,
        "pid": resolved_pid,
        "started_at": datetime.now(UTC).isoformat(),
    }

    final_path = _discovery_path(instance_id, base_dir=directory)
    tmp_path = directory / f".{instance_id}.{os.getpid()}.{time.monotonic_ns()}.tmp"
    encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8")

    fd = os.open(tmp_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(encoded)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise

    try:
        tmp_path.chmod(0o600)
        tmp_path.replace(final_path)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise

    logger.info(
        LogEntry(
            event="direct.api.discovery.written",
            path=str(final_path),
            port=port,
            pid=resolved_pid,
        ).success()
    )
    return final_path


def remove_discovery_file(*, instance_id: str, base_dir: Path | None = None) -> None:
    """Remove the discovery file for `instance_id`, if present."""
    path = _discovery_path(instance_id, base_dir=base_dir)
    try:
        path.unlink(missing_ok=True)
    except OSError as e:
        logger.warning(
            LogEntry(
                event="direct.api.discovery.remove_failed", path=str(path)
            ).failure(e)
        )
        return
    logger.info(
        LogEntry(event="direct.api.discovery.removed", path=str(path)).success()
    )


def sweep_stale_discovery_files(*, base_dir: Path | None = None) -> list[Path]:
    """Remove sibling discovery files whose recorded `pid` is not alive.

    Returns the paths removed. Malformed sibling files (missing/invalid `pid`)
    are treated as stale and removed as well, since they cannot be trusted by
    consumers either.
    """
    directory = base_dir if base_dir is not None else _discovery_dir()
    if not directory.is_dir():
        return []

    removed: list[Path] = []
    for path in sorted(directory.glob("*.json")):
        stale = True
        try:
            data = json.loads(path.read_text())
            pid = data.get("pid")
            if isinstance(pid, int) and pid_alive(pid):
                stale = False
        except (OSError, ValueError):
            stale = True

        if stale:
            try:
                path.unlink(missing_ok=True)
            except OSError as e:
                logger.warning(
                    LogEntry(
                        event="direct.api.discovery.sweep_failed", path=str(path)
                    ).failure(e)
                )
                continue
            logger.debug(LogEntry(event="direct.api.discovery.swept", path=str(path)))
            removed.append(path)

    return removed


__all__ = [
    "pid_alive",
    "remove_discovery_file",
    "sweep_stale_discovery_files",
    "write_discovery_file",
]
