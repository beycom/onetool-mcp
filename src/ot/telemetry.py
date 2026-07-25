"""Anonymous startup telemetry via PostHog.

Fires a single non-blocking event on each server start.
No user data, no tool call data, no config contents — only:
  event type, version, OS, architecture, Python version, anonymous machine UUID.

Opt-out: set DO_NOT_TRACK=1 or telemetry.enabled: false in config.
See docs/telemetry.md for full disclosure.
"""

from __future__ import annotations

import contextlib
import os
import platform
import sys
import threading
import uuid
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

from ot.config.loader import get_config
from ot.meta._constants import resolve_ot_path
from ot.support import get_version

# Same PostHog project as mkdocs.yml
_POSTHOG_API_KEY = "phc_Abm7GbXLKOv1ti9x5Su7mdQRUdUthSuJeYqV5DNAlFl"


def _is_opted_out() -> bool:
    """Return True if the user has opted out via environment variables."""
    val = os.environ.get("DO_NOT_TRACK", "")
    return bool(val and val != "0")


def _read_marker(marker: Path) -> tuple[str | None, str | None]:
    """Read marker file, returning (version, machine_uuid).

    Supports both old format (version only) and new format (version\\nuuid).
    Returns (None, None) if file does not exist.
    """
    try:
        text = marker.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return None, None

    lines = text.splitlines()
    stored_version = lines[0] if lines else None
    stored_uuid = lines[1] if len(lines) >= 2 else None
    return stored_version, stored_uuid


def _get_or_create_uuid(stored_uuid: str | None) -> str:
    """Return existing UUID from marker file, or generate a new one."""
    if stored_uuid:
        return stored_uuid
    return str(uuid.uuid4())


def _fire(event: str, properties: dict[str, Any], machine_uuid: str) -> None:
    """Send PostHog event via direct HTTP POST. All errors are silently ignored."""
    with contextlib.suppress(Exception):
        import httpx

        httpx.post(
            "https://us.i.posthog.com/capture/",
            json={
                "api_key": _POSTHOG_API_KEY,
                "event": event,
                "distinct_id": machine_uuid,
                "properties": properties,
            },
            timeout=5.0,
        )


def ping() -> None:
    """Determine telemetry event and fire it in a daemon thread.

    Events:
      server-installed  — first ever start (marker file absent)
      server-upgraded   — version in marker differs from running version
      server-started    — all other starts
    """
    if _is_opted_out():
        return

    if not get_config().telemetry.enabled:
        return

    current_version = get_version()
    marker = resolve_ot_path("telemetry")

    stored_version, stored_uuid = _read_marker(marker)
    machine_uuid = _get_or_create_uuid(stored_uuid)

    properties: dict[str, Any] = {
        "version": current_version,
        "os": {"Darwin": "macOS"}.get(platform.system(), platform.system()),
        "arch": platform.machine(),
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}",
        "$process_person_profile": False,
    }

    if stored_version is None:
        event = "server-installed"
    elif stored_version != current_version:
        event = "server-upgraded"
        properties["version_from"] = stored_version
        properties["version_to"] = current_version
    else:
        event = "server-started"

    # Update marker file (silent failure — ping still fires with stale event)
    with contextlib.suppress(Exception):
        marker.write_text(f"{current_version}\n{machine_uuid}", encoding="utf-8")

    t = threading.Thread(
        target=_fire, args=(event, properties, machine_uuid), daemon=True
    )
    t.start()
