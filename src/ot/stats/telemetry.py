"""Optional anonymous telemetry via PostHog.

Telemetry is disabled by default and must be explicitly enabled.
Respects DO_NOT_TRACK and ONETOOL_TELEMETRY_DISABLED environment variables.

Data collected (when enabled):
- Anonymous machine identifier
- Event counts and success rates
- Execution durations
- OneTool version
- Tool names
- Client name

Data NOT collected:
- Code or queries
- File contents or paths
- API keys or credentials
- Personal information
"""

from __future__ import annotations

import hashlib
import os
import platform
from typing import TYPE_CHECKING, Any

from loguru import logger

if TYPE_CHECKING:
    from ot.config.loader import StatsConfig

# PostHog project API key (public, safe to share in open source)
# This key can only send events, not read data - it's designed to be client-side.
# Telemetry is disabled by default and must be explicitly enabled.
POSTHOG_API_KEY = "phc_Abm7GbXLKOv1ti9x5Su7mdQRUdUthSuJeYqV5DNAlFl"
POSTHOG_HOST = "https://app.posthog.com"

# Try to import posthog (optional dependency)
try:
    import posthog  # type: ignore[import-not-found]

    POSTHOG_AVAILABLE = True
except ImportError:
    posthog = None
    POSTHOG_AVAILABLE = False


def _get_anonymous_id() -> str:
    """Generate an anonymous machine identifier.

    Uses a hash of machine-specific info to create a stable but anonymous ID.
    Does not include any personal information.
    """
    # Combine platform info into a stable identifier
    machine_info = f"{platform.node()}-{platform.machine()}-{platform.system()}"

    # Hash to anonymize while keeping stability
    return hashlib.sha256(machine_info.encode()).hexdigest()[:16]


def is_telemetry_enabled(config: StatsConfig) -> bool:
    """Check if telemetry should be enabled.

    Telemetry is disabled if:
    - DO_NOT_TRACK=1 environment variable is set (industry standard)
    - ONETOOL_TELEMETRY_DISABLED=1 environment variable is set
    - stats.telemetry.enabled is False in config (default)
    - PostHog package is not installed

    Args:
        config: Stats configuration

    Returns:
        True if telemetry should be enabled
    """
    # Check environment variables first
    if os.getenv("DO_NOT_TRACK") == "1":
        return False
    if os.getenv("ONETOOL_TELEMETRY_DISABLED") == "1":
        return False

    # Check config setting
    if not config.telemetry.enabled:
        return False

    # Check if posthog is available
    if not POSTHOG_AVAILABLE:
        logger.debug("Telemetry enabled but posthog not installed")
        return False

    return True


def initialize_telemetry(config: StatsConfig) -> None:
    """Initialize PostHog telemetry if enabled.

    Args:
        config: Stats configuration
    """
    if not is_telemetry_enabled(config):
        return

    if posthog is None:
        return

    posthog.project_api_key = POSTHOG_API_KEY
    posthog.host = POSTHOG_HOST

    # Disable debug mode in production
    posthog.debug = False

    logger.debug("Telemetry initialized")


def shutdown_telemetry() -> None:
    """Shutdown PostHog and flush pending events."""
    if not POSTHOG_AVAILABLE or posthog is None:
        return

    try:
        posthog.shutdown()
        logger.debug("Telemetry shutdown")
    except Exception as e:
        logger.debug(f"Telemetry shutdown error: {e}")


def capture_event(
    event: str,
    properties: dict[str, Any] | None = None,
) -> None:
    """Capture a telemetry event.

    No-op if telemetry is disabled or posthog not available.

    Args:
        event: Event name (e.g., "server_started", "run_completed")
        properties: Event properties
    """
    if not POSTHOG_AVAILABLE or posthog is None:
        return

    # Quick check without config if possible
    if os.getenv("DO_NOT_TRACK") == "1":
        return
    if os.getenv("ONETOOL_TELEMETRY_DISABLED") == "1":
        return

    try:
        posthog.capture(
            distinct_id=_get_anonymous_id(),
            event=event,
            properties=properties or {},
        )
    except Exception as e:
        # Never let telemetry errors affect the main application
        logger.debug(f"Telemetry capture error: {e}")


def capture_server_started(version: str, tool_count: int) -> None:
    """Capture server started event.

    Args:
        version: OneTool version
        tool_count: Number of available tools
    """
    capture_event(
        "server_started",
        {
            "version": version,
            "tool_count": tool_count,
        },
    )


def capture_run_completed(
    chars_in: int,
    chars_out: int,
    duration_ms: int,
    success: bool,
) -> None:
    """Capture run completed event.

    Args:
        chars_in: Input character count
        chars_out: Output character count
        duration_ms: Execution time in milliseconds
        success: Whether the run succeeded
    """
    capture_event(
        "run_completed",
        {
            "chars_in": chars_in,
            "chars_out": chars_out,
            "duration_ms": duration_ms,
            "success": success,
        },
    )


def capture_tool_executed(
    tool_name: str,
    duration_ms: int,
    success: bool,
) -> None:
    """Capture tool executed event.

    Args:
        tool_name: Name of the tool
        duration_ms: Execution time in milliseconds
        success: Whether the tool call succeeded
    """
    capture_event(
        "tool_executed",
        {
            "tool_name": tool_name,
            "duration_ms": duration_ms,
            "success": success,
        },
    )
