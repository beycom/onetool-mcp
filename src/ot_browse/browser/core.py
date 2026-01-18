"""Core browser service - connection, navigation, and event handling.

Provides the base browser connection and state management via Playwright CDP.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from playwright.async_api import (
    CDPSession,
    Page,
    async_playwright,
)

from ot_browse.config import get_config
from ot_browse.state import (
    Annotation,
    AppState,
    BrowserState,
    ConnectionState,
    ConsoleMessage,
    NetworkRequest,
)

# Path to the injected inspector script
_INJECT_SCRIPT_PATH = Path(__file__).parent.parent / "inject.js"


def _get_inject_script() -> str:
    """Load the inspector injection script."""
    if _INJECT_SCRIPT_PATH.exists():
        return _INJECT_SCRIPT_PATH.read_text(encoding="utf-8")
    raise FileNotFoundError(f"Inspector script not found: {_INJECT_SCRIPT_PATH}")


class BrowserServiceCore:
    """Core browser service - connection, navigation, and event handling."""

    def __init__(self, state: AppState) -> None:
        self.state = state
        self._playwright: Any = None
        self._on_close_callback: Any = None

    def _set_error(self, context: str, error: Exception) -> None:
        """Set error state and log to stderr."""
        import sys

        msg = f"{context}: {error}"
        self.state.browser.error = msg
        print(f"[BrowserService] {msg}", file=sys.stderr)

    def set_on_close_callback(self, callback: Any) -> None:
        """Set a callback to be called when browser is closed."""
        self._on_close_callback = callback

    async def connect(
        self,
        url: str | None = None,
        cdp_port: int = 9222,
        connect_existing: bool = True,
        devtools: bool = False,
        headless: bool = False,
    ) -> bool:
        """Connect to browser via CDP.

        Args:
            url: Optional URL to navigate to after connecting.
            cdp_port: CDP port for existing browser (default: 9222).
            connect_existing: If True, connect to existing browser; else launch new.
            devtools: If True, open DevTools on browser launch.
            headless: If True, run browser in headless mode.

        Returns:
            True if connection successful, False otherwise.
        """
        browser_state = self.state.browser
        browser_state.connection = ConnectionState.CONNECTING
        browser_state.error = None

        try:
            self._playwright = await async_playwright().start()

            if connect_existing:
                # Connect to existing browser via CDP
                browser_state.browser = (
                    await self._playwright.chromium.connect_over_cdp(
                        f"http://localhost:{cdp_port}"
                    )
                )
                contexts = browser_state.browser.contexts
                if contexts:
                    browser_state.context = contexts[0]
                    pages = browser_state.context.pages
                    browser_state.page = (
                        pages[0] if pages else await browser_state.context.new_page()
                    )
                else:
                    browser_state.context = await browser_state.browser.new_context()
                    browser_state.page = await browser_state.context.new_page()
            else:
                # Launch new browser
                config = get_config()
                args = list(config.browser_args)  # Copy to avoid mutating config
                if devtools:
                    args.append("--auto-open-devtools-for-tabs")

                browser_state.browser = await self._playwright.chromium.launch(
                    headless=headless,
                    devtools=devtools,
                    args=args,
                )
                # no_viewport=True allows browser window to resize normally
                browser_state.context = await browser_state.browser.new_context(
                    no_viewport=config.no_viewport
                )
                browser_state.page = await browser_state.context.new_page()

            page: Page = browser_state.page

            # Set up CDP session
            browser_state.cdp = await page.context.new_cdp_session(page)
            cdp: CDPSession = browser_state.cdp
            await cdp.send("DOM.enable")
            await cdp.send("CSS.enable")
            await cdp.send("Network.enable")

            # Inject inspector script (persists across navigation)
            inject_script = _get_inject_script()
            await page.add_init_script(inject_script)

            # Also inject into current page if already loaded
            await page.evaluate(inject_script)

            # Navigate if URL provided
            if url:
                await page.goto(url, wait_until="networkidle")
                await self._ensure_inspector_injected()

            # Update state
            browser_state.url = page.url
            browser_state.title = await page.title()
            browser_state.connection = ConnectionState.CONNECTED

            # Apply predefined annotations from config
            await self._apply_predefined_annotations()

            # Set up navigation listener to update state
            page.on("framenavigated", self._on_navigation)

            # Set up event listeners for capture
            page.on("console", self._on_console)
            page.on("request", self._on_request)
            page.on("response", self._on_response)

            # Set up close listener
            page.on("close", self._on_page_close)
            browser_state.browser.on("disconnected", self._on_browser_disconnected)

            return True

        except Exception as e:
            browser_state.connection = ConnectionState.ERROR
            browser_state.error = str(e)
            return False

    async def _on_navigation(self, frame: Any) -> None:
        """Handle page navigation events."""
        if frame.parent_frame is None:  # Main frame only
            page = self.state.browser.page
            if page:
                self.state.browser.url = page.url
                self.state.browser.title = await page.title()
                # Clear old annotations (DOM has changed)
                self.state.annotations.clear()
                # Clear collected events for new page
                self.state.browser.console_messages.clear()
                self.state.browser.network_requests.clear()
                # Re-inject inspector and apply predefined annotations
                await self._ensure_inspector_injected()
                await self._apply_predefined_annotations()

    async def _apply_predefined_annotations(self) -> None:
        """Apply predefined annotations from config and sync to state."""
        config = get_config()
        page = self.state.browser.page
        if not page or not config.annotations:
            return

        for ann in config.annotations:
            selector = ann.get("selector", "")
            label = ann.get("label", "")
            if not selector:
                continue

            # Get tag name for auto-ID
            tag = await page.evaluate(
                f"document.querySelector({selector!r})?.tagName?.toLowerCase() || 'el'"
            )
            result = await page.evaluate(
                f"window.__inspector?.addAnnotation({selector!r}, {tag!r}, {label!r})"
            )

            # Sync to local state
            if result and result.get("success"):
                for element_id in result.get("ids", []):
                    self.state.annotations.append(
                        Annotation(
                            id=element_id,
                            selector=selector,
                            label=label,
                        )
                    )

    def _on_console(self, msg: Any) -> None:
        """Handle console message events."""
        try:
            location = None
            if msg.location:
                loc = msg.location
                location = f"{loc.get('url', '')}:{loc.get('lineNumber', '')}:{loc.get('columnNumber', '')}"

            self.state.browser.console_messages.append(
                ConsoleMessage(
                    type=msg.type,
                    text=msg.text,
                    timestamp=time.time(),
                    location=location,
                )
            )
        except Exception:
            pass  # Event handler - suppress malformed events

    def _on_request(self, request: Any) -> None:
        """Handle network request events."""
        try:
            # Store request, will be updated with response later
            self.state.browser.network_requests.append(
                NetworkRequest(
                    url=request.url,
                    method=request.method,
                    resource_type=request.resource_type,
                    headers=dict(request.headers) if request.headers else None,
                    post_data=request.post_data if request.post_data else None,
                    timestamp=time.time(),
                )
            )
        except Exception:
            pass  # Event handler - suppress malformed events

    async def _on_response(self, response: Any) -> None:
        """Handle network response events."""
        try:
            # Find matching request and update it
            url = response.url
            for req in reversed(self.state.browser.network_requests):
                if req.url == url and req.status is None:
                    req.status = response.status
                    req.status_text = response.status_text
                    req.response_headers = (
                        dict(response.headers) if response.headers else None
                    )

                    # Try to get body for JSON/text responses
                    content_type = response.headers.get("content-type", "")
                    if "json" in content_type or "text" in content_type:
                        try:
                            body = await response.text()
                            req.response_body = body if body else None
                        except Exception:
                            pass
                    break
        except Exception:
            pass

    def _on_page_close(self, _page: Any) -> None:
        """Handle page close event."""
        self.state.browser.connection = ConnectionState.DISCONNECTED
        if self._on_close_callback:
            self._on_close_callback()

    def _on_browser_disconnected(self, _browser: Any) -> None:
        """Handle browser disconnection event."""
        self.state.browser.connection = ConnectionState.DISCONNECTED
        if self._on_close_callback:
            self._on_close_callback()

    async def _ensure_inspector_injected(self) -> bool:
        """Verify inspector is loaded and re-inject if needed."""
        page = self.state.browser.page
        if not page:
            return False

        try:
            is_ready = await page.evaluate(
                "typeof window.__inspector !== 'undefined' && window.__inspector?.isReady()"
            )
            if is_ready:
                return True

            # Re-inject the script
            inject_script = _get_inject_script()
            await page.evaluate(inject_script)

            is_ready = await page.evaluate(
                "typeof window.__inspector !== 'undefined' && window.__inspector?.isReady()"
            )
            return is_ready
        except Exception:
            return False

    async def disconnect(self) -> None:
        """Disconnect from browser."""
        browser_state = self.state.browser

        try:
            if browser_state.cdp:
                await browser_state.cdp.detach()
        except Exception:
            pass

        try:
            if browser_state.page:
                await browser_state.page.close()
        except Exception:
            pass

        try:
            if browser_state.context:
                await browser_state.context.close()
        except Exception:
            pass

        try:
            if browser_state.browser:
                await browser_state.browser.close()
        except Exception:
            pass

        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

        # Reset state
        self.state.browser = BrowserState()

    async def run_codegen(self, url: str | None = None) -> None:
        """Run Playwright Codegen for recording user actions.

        This launches a separate browser with codegen enabled.
        The generated code is printed to stdout.
        """
        import subprocess
        import sys

        cmd = [sys.executable, "-m", "playwright", "codegen"]
        if url:
            cmd.append(url)

        # Run codegen in subprocess (it's a blocking CLI tool)
        subprocess.run(cmd, check=False)

    async def navigate(self, url: str) -> bool:
        """Navigate to a URL."""
        page = self.state.browser.page
        if not page:
            return False

        try:
            await page.goto(url, wait_until="networkidle")
            await self._ensure_inspector_injected()
            self.state.browser.url = page.url
            self.state.browser.title = await page.title()
            return True
        except Exception as e:
            self.state.browser.error = str(e)
            return False

    async def refresh_state(self) -> None:
        """Refresh current page state."""
        page = self.state.browser.page
        if page:
            self.state.browser.url = page.url
            self.state.browser.title = await page.title()
