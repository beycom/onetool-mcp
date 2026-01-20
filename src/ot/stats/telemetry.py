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

Performance notes:
- All capture calls are non-blocking (run in background thread)
- Shutdown has a configurable timeout to prevent hanging
- Events are batched by PostHog client automatically
"""

from __future__ import annotations

import atexit
import hashlib
import os
import platform
import queue
import threading
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

# Shutdown timeout in seconds
SHUTDOWN_TIMEOUT = 2.0

# Background event queue and worker
_event_queue: queue.Queue[tuple[str, dict[str, Any]] | None] = queue.Queue()
_worker_thread: threading.Thread | None = None
_worker_running = False
_worker_lock = threading.Lock()


def _worker_loop() -> None:
    """Background worker that processes telemetry events."""
    global _worker_running
    while _worker_running:
        try:
            # Wait for event with timeout to allow clean shutdown
            item = _event_queue.get(timeout=0.5)
            if item is None:
                # Shutdown signal
                break
            event, properties = item
            _send_event_sync(event, properties)
        except queue.Empty:
            continue
        except Exception as e:
            logger.debug(f"Telemetry worker error: {e}")


def _send_event_sync(event: str, properties: dict[str, Any]) -> None:
    """Send event synchronously (called from worker thread)."""
    if posthog is None:
        return
    try:
        posthog.capture(
            distinct_id=_get_anonymous_id(),
            event=event,
            properties=properties,
        )
    except Exception as e:
        logger.debug(f"Telemetry capture error: {e}")


def _start_worker() -> None:
    """Start the background worker thread."""
    global _worker_thread, _worker_running
    with _worker_lock:
        if _worker_thread is not None and _worker_thread.is_alive():
            return
        _worker_running = True
        _worker_thread = threading.Thread(target=_worker_loop, daemon=True)
        _worker_thread.start()
        atexit.register(_atexit_shutdown)


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

    # Start background worker for non-blocking event capture
    _start_worker()

    logger.debug("Telemetry initialized")


def _atexit_shutdown() -> None:
    """Cleanup handler for atexit - non-blocking."""
    shutdown_telemetry(timeout=SHUTDOWN_TIMEOUT)


def shutdown_telemetry(timeout: float = SHUTDOWN_TIMEOUT) -> None:
    """Shutdown telemetry worker and flush pending events.

    Args:
        timeout: Maximum time to wait for shutdown in seconds.
    """
    global _worker_running, _worker_thread

    # Stop the worker
    with _worker_lock:
        if not _worker_running:
            return
        _worker_running = False

    # Send shutdown signal
    try:
        _event_queue.put_nowait(None)
    except queue.Full:
        pass

    # Wait for worker to finish (with timeout)
    if _worker_thread is not None:
        _worker_thread.join(timeout=timeout)
        if _worker_thread.is_alive():
            logger.debug("Telemetry worker did not stop in time")

    # Flush PostHog with timeout (run in separate thread to enforce timeout)
    if POSTHOG_AVAILABLE and posthog is not None:

        def _flush() -> None:
            try:
                posthog.shutdown()
            except Exception as e:
                logger.debug(f"Telemetry flush error: {e}")

        flush_thread = threading.Thread(target=_flush, daemon=True)
        flush_thread.start()
        flush_thread.join(timeout=timeout)
        if flush_thread.is_alive():
            logger.debug("Telemetry flush timed out")
        else:
            logger.debug("Telemetry shutdown")


def capture_event(
    event: str,
    properties: dict[str, Any] | None = None,
) -> None:
    """Capture a telemetry event (non-blocking).

    Events are queued and sent in a background thread.
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

    # Check if worker is running
    if not _worker_running:
        return

    # Queue the event (non-blocking)
    try:
        _event_queue.put_nowait((event, properties or {}))
    except queue.Full:
        # Drop event if queue is full - never block main thread
        logger.debug("Telemetry queue full, dropping event")


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
