"""Playwright annotation utilities for the inject.js system.

Provides high-level functions to interact with the inject.js v2.0 annotation
system via the Playwright MCP server (``playwright.evaluate``).

For Chrome DevTools, use the ``chrome_util`` pack instead.
"""

from __future__ import annotations

pack = "play_util"
pack_aliases = ("play",)

__all__ = [
    "clear_annotations",
    "enable_auto_inject",
    "guide_user",
    "highlight_element",
    "inject_annotations",
    "scan_annotations",
]

from typing import Any

from otdev._inject_base import (
    clear_annotations as _clear,
)
from otdev._inject_base import (
    enable_auto_inject as _enable_auto_inject,
)
from otdev._inject_base import (
    guide_user as _guide,
)
from otdev._inject_base import (
    highlight_element as _highlight,
)
from otdev._inject_base import (
    inject_annotations as _inject,
)
from otdev._inject_base import (
    scan_annotations as _scan,
)

_SERVER = "playwright"
_TOOL = "browser_evaluate"
_PACK = "play_util"


def inject_annotations() -> dict[str, Any]:
    """Inject the annotation script into the current browser page.

    Loads inject.js v2.0 via Playwright, enabling element annotation,
    highlighting, and the Ctrl+I (Cmd+I) selection mode. When the user
    presses Ctrl+I/Cmd+I and clicks an element, a prompt dialog appears
    allowing them to enter a custom annotation name. Idempotent: re-calling
    after injection returns success without re-injecting.

    Returns:
        Dict with ``success``, ``ready``, and ``version`` fields.

    Example:
        play_util.inject_annotations()
    """
    return _inject(_SERVER, _TOOL, _PACK)


def enable_auto_inject() -> dict[str, Any]:
    """Register inject.js as a Playwright init script for automatic injection.

    Uses ``page.addInitScript()`` to register inject.js once. After this call,
    ``window.__inspector`` is available on every page for the rest of the
    browser session — including pages loaded after navigation — without any
    per-page re-injection.

    This is more efficient than ``inject_annotations()`` when navigating
    across multiple pages. The two approaches can coexist: calling
    ``enable_auto_inject()`` does not affect the ``_ensure_injected()``
    fallback used by other annotation tools.

    Returns:
        Dict with ``success`` and ``auto_inject`` fields.

    Example:
        play_util.enable_auto_inject()
    """
    return _enable_auto_inject(_SERVER, _PACK)


def highlight_element(
    *,
    selector: str,
    label: str,
    color: str = "orange",
    element_id: str | None = None,
) -> dict[str, Any]:
    """Highlight elements matching a CSS selector with an annotation overlay.

    Requires inject.js to be loaded on the page (call ``inject_annotations()``
    first). Adds ``x-inspect`` attributes and renders visual overlays.

    Args:
        selector: CSS selector for the target element(s).
        label: Text label displayed on the highlight overlay.
        color: Colour scheme - ``orange``, ``red``, ``blue``, or ``green``.
        element_id: Optional custom annotation ID. Auto-generated if omitted.

    Returns:
        Dict with ``success``, ``count``, and ``ids`` fields.

    Example:
        play_util.highlight_element(selector="button.submit", label="Click here")
    """
    return _highlight(
        _SERVER, _TOOL, _PACK,
        selector=selector, label=label, color=color, element_id=element_id,
    )


def scan_annotations() -> list[dict[str, Any]]:
    """Read all current annotations from the page.

    Returns a list of annotation descriptors for every element that has
    an ``x-inspect`` attribute, including those added by the user via
    Ctrl+I (Cmd+I) selection mode with custom labels.

    Returns:
        List of dicts with ``id``, ``label``, ``selector``, ``content``,
        ``tagName``, and ``color`` fields. Empty list if none exist.

    Example:
        play_util.scan_annotations()
    """
    return _scan(_SERVER, _TOOL, _PACK)


def clear_annotations() -> dict[str, Any]:
    """Remove all annotations and visual highlights from the page.

    Clears all ``x-inspect`` and ``x-inspect-color`` attributes and
    removes overlay elements.

    Returns:
        Dict with ``success`` and ``cleared`` count.

    Example:
        play_util.clear_annotations()
    """
    return _clear(_SERVER, _TOOL, _PACK)


def guide_user(
    *,
    task: str,
    steps: list[dict[str, str]],
) -> dict[str, Any]:
    """Highlight a sequence of elements to guide the user through a task.

    Each step specifies a CSS selector and label. All steps are highlighted
    at once so the user can see the full workflow. An optional ``color`` key
    per step overrides the default orange scheme.

    Args:
        task: Short description of the guided task.
        steps: List of step dicts, each with ``selector``, ``label``,
               and optional ``color`` (default ``"orange"``).

    Returns:
        Dict with ``task``, ``total`` step count, ``highlighted`` count,
        and per-step ``results``.

    Example:
        play_util.guide_user(
            task="Fill form",
            steps=[
                {"selector": "input[name='name']", "label": "Enter name"},
                {"selector": "button[type='submit']", "label": "Submit"},
            ],
        )
    """
    return _guide(_SERVER, _TOOL, _PACK, task=task, steps=steps)
