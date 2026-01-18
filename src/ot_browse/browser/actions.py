"""Browser actions mixin - annotation and element operations.

Provides methods for element selection, annotation management, and element queries.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from ot_browse.state import AppState


class _BrowserCoreProtocol(Protocol):
    """Protocol defining methods expected from BrowserServiceCore."""

    state: AppState

    def _set_error(self, context: str, error: Exception) -> None: ...

    async def _ensure_inspector_injected(self) -> bool: ...


class BrowserActionsMixin(_BrowserCoreProtocol):
    """Mixin providing annotation and element operation methods."""

    async def enable_annotation_mode(self) -> bool:
        """Enable element selection mode in browser."""
        page = self.state.browser.page
        if not page:
            return False

        try:
            await self._ensure_inspector_injected()
            await page.evaluate("window.__inspector?.enableSelectionMode()")
            self.state.annotation_mode = True
            return True
        except Exception as e:
            self._set_error("Enable annotation mode", e)
            return False

    async def disable_annotation_mode(self) -> bool:
        """Disable element selection mode in browser."""
        page = self.state.browser.page
        if not page:
            return False

        try:
            await page.evaluate("window.__inspector?.disableSelectionMode()")
            self.state.annotation_mode = False
            return True
        except Exception as e:
            self._set_error("Disable annotation mode", e)
            return False

    async def get_selection(self) -> dict[str, Any] | None:
        """Get the currently selected element info."""
        page = self.state.browser.page
        if not page:
            return None

        try:
            await self._ensure_inspector_injected()
            result = await page.evaluate("window.__inspector?.getSelection()")
            return result
        except Exception as e:
            self._set_error("Get selection", e)
            return None

    async def add_annotation(self, selector: str, ann_id: str, label: str) -> bool:
        """Add an x-inspect annotation to an element."""
        page = self.state.browser.page
        if not page:
            return False

        try:
            await self._ensure_inspector_injected()
            result = await page.evaluate(
                f"window.__inspector?.addAnnotation({selector!r}, {ann_id!r}, {label!r})"
            )
            # Check if the JS function returned success
            if result and isinstance(result, dict):
                return result.get("success", False)
            return False
        except Exception as e:
            self._set_error("Add annotation", e)
            return False

    async def remove_annotation(self, selector: str) -> bool:
        """Remove x-inspect annotation from an element."""
        page = self.state.browser.page
        if not page:
            return False

        try:
            await page.evaluate(f"window.__inspector?.removeAnnotation({selector!r})")
            return True
        except Exception as e:
            self._set_error("Remove annotation", e)
            return False

    async def clear_annotations(self) -> bool:
        """Clear all x-inspect annotations."""
        page = self.state.browser.page
        if not page:
            return False

        try:
            await page.evaluate("window.__inspector?.clearAnnotations()")
            return True
        except Exception as e:
            self._set_error("Clear annotations", e)
            return False

    async def get_element_by_selector(self, selector: str) -> dict[str, Any] | None:
        """Get element info by CSS selector."""
        page = self.state.browser.page
        if not page:
            return None

        try:
            await self._ensure_inspector_injected()
            result = await page.evaluate(
                f"window.__inspector?.getElementBySelector({selector!r})"
            )
            return result
        except Exception as e:
            self._set_error("Get element by selector", e)
            return None

    async def get_console_messages(self) -> list[dict[str, Any]]:
        """Get captured console messages."""
        page = self.state.browser.page
        if not page:
            return []

        try:
            result = await page.evaluate("window.__inspector?.getConsoleMessages?.()")
            return result or []
        except Exception:
            return []

    async def get_network_requests(self) -> list[dict[str, Any]]:
        """Get captured network requests."""
        page = self.state.browser.page
        if not page:
            return []

        try:
            result = await page.evaluate("window.__inspector?.getNetworkRequests?.()")
            return result or []
        except Exception:
            return []
