"""Browser capture mixin - screenshot and comprehensive capture.

Provides methods for capturing screenshots, page data, and comprehensive snapshots.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

from ot_browse.config import get_config

if TYPE_CHECKING:
    from ot_browse.state import AppState


class _BrowserCoreProtocol(Protocol):
    """Protocol defining methods expected from BrowserServiceCore."""

    state: AppState

    def _set_error(self, context: str, error: Exception) -> None: ...

    async def _ensure_inspector_injected(self) -> bool: ...


class BrowserCaptureMixin(_BrowserCoreProtocol):
    """Mixin providing screenshot and capture methods."""

    async def capture_screenshot(self, full_page: bool = False) -> bytes | None:
        """Capture a screenshot.

        Args:
            full_page: Whether to capture the full scrollable page.

        Returns:
            Screenshot bytes in WebP format, or None on failure.
        """
        page = self.state.browser.page
        if not page:
            return None

        try:
            # Capture as PNG first (Playwright doesn't support WebP directly)
            try:
                screenshot = await page.screenshot(full_page=full_page, type="png")
            except Exception as e:
                if full_page:
                    # Fallback to viewport-only if full page fails (e.g., very large pages)
                    import sys

                    print(
                        f"[Screenshot] Full page failed ({e}), trying viewport only",
                        file=sys.stderr,
                    )
                    screenshot = await page.screenshot(full_page=False, type="png")
                else:
                    raise

            # Convert to WebP using Pillow
            from io import BytesIO

            from PIL import Image

            img = Image.open(BytesIO(screenshot))
            output = BytesIO()
            img.save(output, format="WebP", quality=85)
            return output.getvalue()
        except Exception as e:
            import sys

            print(f"[Screenshot error] {e}", file=sys.stderr)
            return None

    async def capture_annotations_region(
        self, annotations: list[dict[str, Any]], padding: int = 50
    ) -> bytes | None:
        """Capture a screenshot of the region containing all annotations.

        Args:
            annotations: List of annotation dicts with 'selector' keys.
            padding: Pixels of padding around the bounding box.

        Returns:
            Screenshot bytes in WebP format, or None on failure.
        """
        page = self.state.browser.page
        if not page or not annotations:
            return None

        try:
            # Collect bounding boxes for all annotations
            min_x, min_y = float("inf"), float("inf")
            max_x, max_y = 0.0, 0.0

            for ann in annotations:
                selector = ann.get("selector", "")
                if not selector:
                    continue

                element = await page.query_selector(selector)
                if not element:
                    continue

                box = await element.bounding_box()
                if not box:
                    continue

                min_x = min(min_x, box["x"])
                min_y = min(min_y, box["y"])
                max_x = max(max_x, box["x"] + box["width"])
                max_y = max(max_y, box["y"] + box["height"])

            # If no valid boxes found, return None
            if min_x == float("inf"):
                return None

            # Get page dimensions for full-page screenshot
            page_height = await page.evaluate("document.documentElement.scrollHeight")
            page_width = await page.evaluate("document.documentElement.scrollWidth")

            # Calculate clip region with padding
            x = max(0, min_x - padding)
            y = max(0, min_y - padding)
            width = min(max_x - min_x + padding * 2, page_width - x)
            height = min(max_y - min_y + padding * 2, page_height - y)

            clip = {"x": x, "y": y, "width": width, "height": height}

            # Capture full-page screenshot with clip
            screenshot = await page.screenshot(type="png", full_page=True, clip=clip)

            # Convert to WebP
            from io import BytesIO

            from PIL import Image

            img = Image.open(BytesIO(screenshot))
            output = BytesIO()
            img.save(output, format="WebP", quality=85)
            return output.getvalue()
        except Exception as e:
            self._set_error("Capture annotations region", e)
            return None

    async def capture_element_screenshot(
        self, selector: str, padding: int = 50
    ) -> bytes | None:
        """Capture a screenshot of a specific element with padding.

        Args:
            selector: CSS selector for the element.
            padding: Pixels of padding around the element.

        Returns:
            Screenshot bytes in WebP format, or None on failure.
        """
        page = self.state.browser.page
        if not page:
            return None

        try:
            # Find the element
            element = await page.query_selector(selector)
            if not element:
                return None

            # Scroll element into view first
            await element.scroll_into_view_if_needed()

            # Get bounding box after scrolling
            box = await element.bounding_box()
            if not box:
                return None

            # Get viewport size for clipping bounds
            viewport = page.viewport_size or {"width": 1280, "height": 720}

            # Calculate clip region with padding, ensuring we stay within viewport
            x = max(0, box["x"] - padding)
            y = max(0, box["y"] - padding)
            # Width/height: element size + padding, but clipped to not exceed viewport bounds
            width = min(box["width"] + padding * 2, viewport["width"] - x)
            height = min(box["height"] + padding * 2, viewport["height"] - y)

            clip = {"x": x, "y": y, "width": width, "height": height}

            # Ensure valid dimensions
            if width <= 0 or height <= 0:
                return None

            # Capture screenshot of the region
            screenshot = await page.screenshot(type="png", clip=clip)

            # Convert to WebP
            from io import BytesIO

            from PIL import Image

            img = Image.open(BytesIO(screenshot))
            output = BytesIO()
            img.save(output, format="WebP", quality=85)
            return output.getvalue()
        except Exception as e:
            import sys

            print(
                f"[Element screenshot error] selector={selector}: {e}", file=sys.stderr
            )
            return None

    async def capture_annotation_screenshots(
        self, annotations: list[dict[str, Any]], padding: int = 50
    ) -> dict[str, bytes]:
        """Capture screenshots of all annotated elements.

        Args:
            annotations: List of annotation dicts with 'id' and 'selector' keys.
            padding: Pixels of padding around each element.

        Returns:
            Dict mapping annotation ID to screenshot bytes.
        """
        import sys

        screenshots: dict[str, bytes] = {}
        for ann in annotations:
            ann_id = ann.get("id", "")
            selector = ann.get("selector", "")
            if ann_id and selector:
                screenshot = await self.capture_element_screenshot(selector, padding)
                if screenshot:
                    screenshots[ann_id] = screenshot
                else:
                    print(
                        f"[Annotation screenshot] Failed for {ann_id}", file=sys.stderr
                    )
            else:
                print(
                    f"[Annotation screenshot] Skipping ann with id={ann_id!r} selector={selector[:30] if selector else ''}...",
                    file=sys.stderr,
                )
        return screenshots

    # ─── Page Data Methods ─────────────────────────────────────────────────────

    async def get_page_info(self) -> dict[str, Any] | None:
        """Get page info (URL, title, viewport, meta)."""
        page = self.state.browser.page
        if not page:
            return None
        try:
            await self._ensure_inspector_injected()
            return await page.evaluate("window.__inspector?.getPageInfo()")
        except Exception as e:
            self._set_error("Get page info", e)
            return None

    async def get_page_html(self) -> str | None:
        """Get full page HTML."""
        page = self.state.browser.page
        if not page:
            return None
        try:
            return await page.evaluate("window.__inspector?.getPageHTML()")
        except Exception as e:
            self._set_error("Get page HTML", e)
            return None

    async def get_annotation_details(self) -> list[dict[str, Any]]:
        """Get all annotations with full element details including enhanced data.

        Returns annotations with:
        - id, label, selector, tagName, outerHTML, elementId
        - bounding_box: {x, y, width, height}
        - computed_styles: key visual properties
        """
        page = self.state.browser.page
        if not page:
            return []
        try:
            await self._ensure_inspector_injected()
            result = await page.evaluate("window.__inspector?.getAnnotationDetails()")
            if not result:
                return []

            # Enhance each annotation with bounding_box and computed_styles
            enhanced = []
            for ann in result:
                selector = ann.get("selector", "")
                if selector:
                    # Get bounding box
                    element = await page.query_selector(selector)
                    if element:
                        box = await element.bounding_box()
                        if box:
                            ann["bounding_box"] = {
                                "x": round(box["x"]),
                                "y": round(box["y"]),
                                "width": round(box["width"]),
                                "height": round(box["height"]),
                            }

                        # Get computed styles
                        styles = await self._get_computed_styles(selector)
                        if styles:
                            ann["computed_styles"] = styles
                enhanced.append(ann)

            return enhanced
        except Exception as e:
            self._set_error("Get annotation details", e)
            return []

    async def _get_computed_styles(self, selector: str) -> dict[str, str] | None:
        """Get computed styles for an element.

        Args:
            selector: CSS selector for the element.

        Returns:
            Dict of key visual properties, or None on failure.
        """
        page = self.state.browser.page
        if not page:
            return None

        try:
            styles = await page.evaluate(f"""
                (() => {{
                    const el = document.querySelector({selector!r});
                    if (!el) return null;
                    const cs = window.getComputedStyle(el);
                    return {{
                        display: cs.display,
                        position: cs.position,
                        visibility: cs.visibility,
                        color: cs.color,
                        backgroundColor: cs.backgroundColor,
                        fontSize: cs.fontSize,
                        fontWeight: cs.fontWeight,
                        width: cs.width,
                        height: cs.height,
                    }};
                }})()
            """)
            return styles
        except Exception:
            return None

    async def get_images(self) -> list[dict[str, Any]]:
        """Get all images on page."""
        page = self.state.browser.page
        if not page:
            return []
        try:
            await self._ensure_inspector_injected()
            result = await page.evaluate("window.__inspector?.getImages()")
            return result or []
        except Exception as e:
            self._set_error("Get images", e)
            return []

    async def get_console_logs(self) -> list[dict[str, Any]]:
        """Get console messages via CDP."""
        cdp = self.state.browser.cdp
        if not cdp:
            return []
        # Note: Console messages need to be collected over time
        # This returns empty for now - would need event listener setup
        return []

    async def get_performance_metrics(self) -> dict[str, Any] | None:
        """Get performance metrics via CDP."""
        cdp = self.state.browser.cdp
        page = self.state.browser.page
        if not cdp or not page:
            return None
        try:
            # Get performance timing
            timing = await page.evaluate("""
                () => {
                    const perf = window.performance;
                    const timing = perf.timing;
                    const nav = perf.getEntriesByType('navigation')[0];
                    return {
                        timing: {
                            domContentLoaded: timing.domContentLoadedEventEnd - timing.navigationStart,
                            domComplete: timing.domComplete - timing.navigationStart,
                            loadComplete: timing.loadEventEnd - timing.navigationStart,
                        },
                        navigation: nav ? {
                            type: nav.type,
                            redirectCount: nav.redirectCount,
                            domInteractive: nav.domInteractive,
                            domContentLoadedEventEnd: nav.domContentLoadedEventEnd,
                            loadEventEnd: nav.loadEventEnd,
                            transferSize: nav.transferSize,
                            encodedBodySize: nav.encodedBodySize,
                            decodedBodySize: nav.decodedBodySize,
                        } : null,
                        memory: perf.memory ? {
                            usedJSHeapSize: perf.memory.usedJSHeapSize,
                            totalJSHeapSize: perf.memory.totalJSHeapSize,
                        } : null,
                    };
                }
            """)

            # Get CDP metrics
            cdp_metrics = await cdp.send("Performance.getMetrics")
            metrics_dict = {
                m["name"]: m["value"] for m in cdp_metrics.get("metrics", [])
            }

            return {
                "browser": timing,
                "cdp": metrics_dict,
            }
        except Exception as e:
            self._set_error("Get performance metrics", e)
            return None

    async def get_resource_timing(self) -> list[dict[str, Any]]:
        """Get resource timing entries from Performance API."""
        page = self.state.browser.page
        if not page:
            return []
        try:
            resources = await page.evaluate("""
                () => {
                    return window.performance.getEntriesByType('resource').slice(0, 100).map(r => ({
                        name: r.name,
                        type: r.initiatorType,
                        duration: r.duration,
                        transferSize: r.transferSize,
                        encodedBodySize: r.encodedBodySize,
                        decodedBodySize: r.decodedBodySize,
                        startTime: r.startTime,
                    }));
                }
            """)
            return resources or []
        except Exception as e:
            self._set_error("Get resource timing", e)
            return []

    async def get_cookies(self) -> list[dict[str, Any]]:
        """Get all cookies for current page."""
        page = self.state.browser.page
        if not page:
            return []
        try:
            cookies = await page.context.cookies()
            return [
                {
                    "name": c["name"],
                    "value": c["value"],
                    "domain": c["domain"],
                    "path": c["path"],
                    "secure": c["secure"],
                    "httpOnly": c["httpOnly"],
                }
                for c in cookies
            ]
        except Exception as e:
            self._set_error("Get cookies", e)
            return []

    async def get_accessibility_snapshot(self) -> dict[str, Any] | None:
        """Get accessibility tree snapshot using ARIA snapshot."""
        page = self.state.browser.page
        if not page:
            return None
        try:
            # Use the modern Playwright API: locator.aria_snapshot()
            # Returns a YAML-formatted string of the accessibility tree
            snapshot = await page.locator("body").aria_snapshot()
            return {"aria_tree": snapshot}
        except Exception as e:
            self._set_error("Get accessibility snapshot", e)
            return None

    async def get_browser_info(self) -> dict[str, Any]:
        """Get browser/viewport info."""
        page = self.state.browser.page
        context = self.state.browser.context
        browser = self.state.browser.browser
        if not page:
            return {}
        try:
            viewport = page.viewport_size
            return {
                "browser_type": browser.browser_type.name if browser else "unknown",
                "browser_version": browser.version if browser else "unknown",
                "user_agent": await page.evaluate("navigator.userAgent"),
                "viewport": viewport,
                "device_scale_factor": await page.evaluate("window.devicePixelRatio"),
                "is_mobile": context.is_mobile
                if context and hasattr(context, "is_mobile")
                else False,
                "locale": await page.evaluate("navigator.language"),
                "timezone": await page.evaluate(
                    "Intl.DateTimeFormat().resolvedOptions().timeZone"
                ),
            }
        except Exception as e:
            self._set_error("Get browser info", e)
            return {}

    def get_collected_console_messages(self) -> list[dict[str, Any]]:
        """Get console messages collected during session."""
        from dataclasses import asdict

        return [asdict(m) for m in self.state.browser.console_messages[-100:]]

    def get_collected_network_requests(self) -> list[dict[str, Any]]:
        """Get network requests collected during session."""
        from dataclasses import asdict

        return [asdict(r) for r in self.state.browser.network_requests[-100:]]

    async def capture_comprehensive(self) -> dict[str, Any]:
        """Capture everything useful from the page.

        Returns a dict with all captured data.
        If annotations exist, captures bounding box around all annotations.
        If no annotations, captures viewport only.
        """
        page = self.state.browser.page
        if not page:
            return {"error": "Not connected"}

        # Get annotations first to determine screenshot behavior
        annotations = await self.get_annotation_details()

        # Capture screenshot: annotations region or viewport
        if annotations:
            screenshot = await self.capture_annotations_region(annotations, padding=50)
            # Fallback to viewport if region capture fails
            if screenshot is None:
                screenshot = await self.capture_screenshot(full_page=False)
        else:
            screenshot = await self.capture_screenshot(full_page=False)

        # Gather all data
        page_info = await self.get_page_info()
        images = await self.get_images()
        performance = await self.get_performance_metrics()
        cookies = await self.get_cookies()
        html = await self.get_page_html()

        accessibility = await self.get_accessibility_snapshot()
        browser_info = await self.get_browser_info()

        # Capture individual annotation screenshots (skip if too many)
        config = get_config()
        max_ann_screenshots = config.max_annotation_screenshots
        ann_count = len(annotations or [])
        if max_ann_screenshots > 0 and ann_count > max_ann_screenshots:
            annotation_screenshots = {}  # Skip screenshots
        else:
            annotation_screenshots = await self.capture_annotation_screenshots(
                annotations or [], padding=config.annotation_padding
            )

        # Collected events
        console_messages = self.get_collected_console_messages()
        network_requests = self.get_collected_network_requests()

        return {
            "page_info": page_info,
            "browser_info": browser_info,
            "annotations": annotations,
            "annotation_screenshots": annotation_screenshots,
            "accessibility": accessibility,
            "images": images,
            "performance": performance,
            "network": network_requests,
            "console": console_messages,
            "cookies": cookies,
            "html": html,
            "screenshot": screenshot,
        }
