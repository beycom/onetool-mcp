"""Session-scoped disk storage for Console message bodies."""

from __future__ import annotations

import atexit
import json
import os
import shutil
from contextlib import suppress
from secrets import token_hex
from typing import TYPE_CHECKING

from ot.console.models import ConsoleMessage
from ot.paths import get_project_state_dir
from ot.runtime_meta import get_or_create_instance_id

if TYPE_CHECKING:
    from pathlib import Path


def console_instances_dir() -> Path:
    """Return the root containing session-scoped Console instance state."""
    return get_project_state_dir("console") / "instances"


def console_instance_dir(*, instance_id: str | None = None) -> Path:
    """Return one Console runtime instance's state directory."""
    return console_instances_dir() / (instance_id or get_or_create_instance_id())


def console_messages_dir(*, instance_id: str | None = None) -> Path:
    """Return one Console runtime instance's message-body directory."""
    return console_instance_dir(instance_id=instance_id) / "messages"


def message_body_path(*, message_id: str, instance_id: str | None = None) -> Path:
    """Return the JSON body path for one Console message."""
    return console_messages_dir(instance_id=instance_id) / f"{message_id}.json"


def write_message_body(*, message: ConsoleMessage, instance_id: str) -> None:
    """Atomically write one Console message body to its session directory."""
    messages_dir = console_messages_dir(instance_id=instance_id)
    messages_dir.mkdir(parents=True, exist_ok=True)
    target = message_body_path(message_id=message.metadata.id, instance_id=instance_id)
    temporary = messages_dir / f".{message.metadata.id}.{token_hex(6)}.tmp"
    try:
        temporary.write_text(
            json.dumps(message.model_dump(mode="json"), ensure_ascii=False),
            encoding="utf-8",
        )
        temporary.replace(target)
    except Exception:
        with suppress(OSError):
            temporary.unlink()
        raise


def read_message_body(
    *, message_id: str, instance_id: str | None = None
) -> ConsoleMessage:
    """Load one Console message body from its session JSON file."""
    path = message_body_path(message_id=message_id, instance_id=instance_id)
    return ConsoleMessage.model_validate_json(path.read_text(encoding="utf-8"))


def unlink_message_body(*, message_id: str, instance_id: str) -> None:
    """Remove one retained Console message body if it still exists."""
    with suppress(FileNotFoundError):
        message_body_path(message_id=message_id, instance_id=instance_id).unlink()


def clear_console_messages(*, instance_id: str) -> None:
    """Remove the current instance's complete message-body directory."""
    with suppress(FileNotFoundError):
        shutil.rmtree(console_messages_dir(instance_id=instance_id))


def cleanup_console_instance(*, instance_id: str | None = None) -> None:
    """Remove one Console runtime instance directory."""
    with suppress(FileNotFoundError):
        shutil.rmtree(console_instance_dir(instance_id=instance_id))


PID_FILENAME = "pid"


def _write_pid_file(instance_dir: Path) -> None:
    (instance_dir / PID_FILENAME).write_text(str(os.getpid()), encoding="utf-8")


def _sibling_owner_alive(sibling: Path) -> bool:
    """Return True when a sibling instance dir belongs to a live process.

    Guards the startup sweep against deleting the bodies of another MCP
    server running concurrently on the same project. A missing or unreadable
    pid file means the owner cannot be verified — treat as dead (pre-pid-file
    dirs are exactly the stale state the sweep exists to remove).
    """
    try:
        pid = int((sibling / PID_FILENAME).read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return False
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # exists, owned by another user
    except OSError:
        return False
    return True


def initialize_console_storage(*, instance_id: str | None = None) -> None:
    """Create the instance root and sweep state from dead sessions.

    Sibling instance directories are removed only when their owning process
    is no longer alive, so concurrent MCP servers on the same project do not
    delete each other's message bodies.
    """
    current_id = instance_id or get_or_create_instance_id()
    instances_dir = console_instances_dir()
    instances_dir.mkdir(parents=True, exist_ok=True)
    for sibling in instances_dir.iterdir():
        if sibling.name == current_id or not sibling.is_dir():
            continue
        if _sibling_owner_alive(sibling):
            continue
        shutil.rmtree(sibling)
    instance_dir = console_instance_dir(instance_id=current_id)
    instance_dir.mkdir(parents=True, exist_ok=True)
    _write_pid_file(instance_dir)


def _cleanup_current_console_instance() -> None:
    """Best-effort backstop for shutdown paths that bypass MCP lifespan."""
    with suppress(Exception):
        cleanup_console_instance(instance_id=get_or_create_instance_id())


atexit.register(_cleanup_current_console_instance)


__all__ = [
    "cleanup_console_instance",
    "clear_console_messages",
    "console_instance_dir",
    "console_instances_dir",
    "console_messages_dir",
    "initialize_console_storage",
    "message_body_path",
    "read_message_body",
    "unlink_message_body",
    "write_message_body",
]
