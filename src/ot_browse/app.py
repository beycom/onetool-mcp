"""Browser Inspector CLI - Enhanced interactive command-line interface."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

import questionary
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ot._cli import console
from ot._tui import APP_STYLE, ask_select, ask_text, safe_ask
from ot.logging import LogSpan, configure_logging
from ot.support import KOFI_URL, get_version

from .browser import BrowserService
from .config import BrowseConfig, get_config
from .state import Annotation, AppState, ConnectionState
from .storage import create_session, save_comprehensive_capture

APP_NAME = "Browser Inspector"


def _print_startup_banner() -> None:
    """Print a startup banner."""
    version = get_version()

    lines = Text()
    lines.append("OneTool Browser Inspector", style="bold cyan")
    lines.append(f" v{version}\n\n", style="dim")
    lines.append("Buy me a coffee: ", style="dim")
    lines.append(KOFI_URL, style="link " + KOFI_URL)

    panel = Panel(
        lines,
        border_style="blue",
        padding=(0, 1),
    )
    console.print(panel)
    console.print()


# ─── UI Primitives ────────────────────────────────────────────────────────────


def print_header(subtitle: str = "") -> None:
    """Clear screen and print app header."""
    console.clear()
    console.print(f"[bold #5c9aff]{APP_NAME}[/bold #5c9aff]")
    if subtitle:
        console.print(f"[#6b7280]{subtitle}[/#6b7280]")
    console.print()


def print_status(state: AppState) -> None:
    """Print connection status."""
    conn = state.browser.connection
    if conn == ConnectionState.CONNECTED:
        title = state.browser.title or "Untitled"
        url = state.browser.url or ""
        console.print(f"[green]●[/green] {title}")
        if url:
            console.print(f"  [dim]{url[:60]}{'...' if len(url) > 60 else ''}[/dim]")
    else:
        console.print("[#6b7280]○ Not connected[/#6b7280]")

    if state.annotations:
        console.print(f"  [cyan]{len(state.annotations)} annotations[/cyan]")

    # Show last error if any
    if state.browser.error:
        console.print(f"  [red]Error: {state.browser.error}[/red]")

    console.print()


async def ask_url(prompt: str = "URL:", default: str = "") -> str | None:
    """Prompt for URL. Ctrl+C or empty to cancel."""
    result = await safe_ask(questionary.text(prompt, default=default, style=APP_STYLE))
    if not result or not result.strip():
        return None
    url = result.strip()
    # Auto-add https:// if missing
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


async def ask_text_required(prompt: str) -> str | None:
    """Prompt for required text input. Ctrl+C to cancel."""
    result = await safe_ask(questionary.text(prompt, style=APP_STYLE))
    # Empty input = cancel (no validation error, just return None)
    return result.strip() if result and result.strip() else None


async def pause() -> None:
    """Wait for keypress."""
    console.print("[dim]Press any key...[/dim]")
    await safe_ask(questionary.press_any_key_to_continue(message=""))


# ─── Menu Definitions ─────────────────────────────────────────────────────────


def get_disconnected_menu() -> list[questionary.Choice]:
    """Menu when not connected."""
    return [
        questionary.Choice("Open URL", value="open_url", shortcut_key="o"),
        questionary.Choice("Open favorite", value="open_fav", shortcut_key="f"),
        questionary.Choice("Launch browser", value="connect", shortcut_key="l"),
        questionary.Choice("Attach to existing", value="attach", shortcut_key="a"),
        questionary.Choice("Help", value="help", shortcut_key="h"),
        questionary.Choice("Quit", value="quit", shortcut_key="q"),
    ]


def get_connected_menu() -> list[questionary.Choice]:
    """Menu when connected."""
    return [
        questionary.Choice("Add annotation", value="add", shortcut_key="a"),
        questionary.Choice("List annotations", value="list", shortcut_key="l"),
        questionary.Choice("Remove annotation", value="remove", shortcut_key="r"),
        questionary.Choice("Capture page", value="capture", shortcut_key="c"),
        questionary.Choice("Session info", value="info", shortcut_key="i"),
        questionary.Choice("Disconnect", value="disconnect", shortcut_key="d"),
        questionary.Choice("Quit", value="quit", shortcut_key="q"),
    ]


# ─── Actions ──────────────────────────────────────────────────────────────────


class BrowserInspectorCLI:
    """CLI controller."""

    def __init__(self, config: BrowseConfig) -> None:
        self.config = config
        self.state = AppState()
        self.browser = BrowserService(self.state)
        self.session_path: Path | None = None
        self.capture_count = 0

    async def run(self, initial_url: str | None = None) -> None:
        """Main loop."""
        try:
            if initial_url:
                await self._connect(initial_url)

            while True:
                connected = self.state.browser.connection == ConnectionState.CONNECTED
                subtitle = "Ctrl+I in browser to annotate" if connected else ""

                print_header(subtitle)
                print_status(self.state)

                choices = get_connected_menu() if connected else get_disconnected_menu()
                action = await ask_select("Action:", choices)

                if action is None or action == "quit":
                    break

                await self._handle_action(action)
        except KeyboardInterrupt:
            pass  # Clean exit on Ctrl+C
        finally:
            # Cleanup
            if self.state.browser.connection == ConnectionState.CONNECTED:
                await self.browser.disconnect()
            console.print("[dim]Goodbye[/dim]")

    async def _handle_action(self, action: str) -> None:
        """Dispatch action."""
        # Clear previous error before starting new action
        self.state.browser.error = None

        handlers = {
            "open_url": self._action_open_url,
            "open_fav": self._action_open_fav,
            "connect": self._action_connect,
            "attach": self._action_attach,
            "help": self._action_help,
            "add": self._action_add,
            "list": self._action_list,
            "remove": self._action_remove,
            "capture": self._action_capture,
            "info": self._action_info,
            "disconnect": self._action_disconnect,
        }
        handler = handlers.get(action)
        if handler:
            await handler()

    async def _sync_annotations(self) -> list[dict] | None:
        """Sync annotations from browser."""
        page = self.state.browser.page
        if not page:
            return None

        result = await page.evaluate("window.__inspector?.scanAnnotations()")
        if not result:
            return []

        self.state.annotations.clear()
        for ann in result:
            self.state.annotations.append(
                Annotation(
                    id=ann["id"],
                    selector=ann["selector"],
                    label=ann.get("label", ""),
                    comment=ann.get("content", "")[:50],
                )
            )
        return result

    async def _connect(
        self, url: str | None = None, connect_existing: bool = False
    ) -> bool:
        """Connect to browser and start new session."""
        with LogSpan(
            span="browse.session.start", url=url, connect_existing=connect_existing
        ) as s:
            # Reset session for fresh start
            self.session_path = None
            self.capture_count = 0

            # If codegen mode is enabled, use Playwright codegen instead
            if self.config.codegen and not connect_existing:
                console.print("[dim]Launching Playwright Codegen...[/dim]")
                await self.browser.run_codegen(url)
                s.add("codegen", True)
                return False  # Codegen runs separately, no connection to manage

            if connect_existing:
                console.print(
                    f"[dim]Attaching to browser on port {self.config.cdp_port}...[/dim]"
                )
            else:
                console.print("[dim]Launching browser...[/dim]")

            success = await self.browser.connect(
                url=url,
                cdp_port=self.config.cdp_port,
                connect_existing=connect_existing,
                devtools=self.config.devtools,
                headless=self.config.headless,
            )
            s.add("success", success)
            if not success:
                console.print(f"[red]Failed:[/red] {self.state.browser.error}")
                s.add("error", self.state.browser.error)
                await pause()
            else:
                # Create session on successful connection
                _, self.session_path = create_session()
                s.add("session", self.session_path.name)
                console.print(f"[dim]Session: {self.session_path.name}[/dim]")
                console.print(
                    "[green]Ready![/green] Use Ctrl+I in browser to annotate elements"
                )
            return success

    async def _action_open_url(self) -> None:
        """Open URL action."""
        print_header("Enter URL to open")
        url = await ask_url()
        if url:
            if self.state.browser.connection == ConnectionState.CONNECTED:
                await self.browser.disconnect()
            await self._connect(url)

    async def _action_open_fav(self) -> None:
        """Open favorite URL action."""
        print_header("Open favorite")

        if not self.config.favorites:
            console.print("[dim]No favorites configured[/dim]")
            console.print("[dim]Add favorites to config/ot-browse.yaml[/dim]")
            await pause()
            return

        # Build choices using indices to avoid questionary value issues
        favorites = self.config.favorites
        choices = [
            questionary.Choice(url, value=str(i)) for i, url in enumerate(favorites)
        ]
        choices.append(
            questionary.Choice("Cancel", value="__cancel__", shortcut_key="c")
        )

        selected = await ask_select("Select URL:", choices)
        if selected and selected != "__cancel__" and selected.isdigit():
            url = favorites[int(selected)]
            if self.state.browser.connection == ConnectionState.CONNECTED:
                await self.browser.disconnect()
            await self._connect(url)

    async def _action_connect(self) -> None:
        """Launch browser action."""
        await self._connect()

    async def _action_attach(self) -> None:
        """Attach to existing browser via CDP."""
        await self._connect(connect_existing=True)

    async def _action_help(self) -> None:
        """Show help."""
        print_header("Help")
        console.print("[bold]Browser:[/bold]")
        console.print("  Ctrl+I  Toggle selection mode")
        console.print("  Click   Select element → enter ID/label")
        console.print()
        console.print("[bold]Menu:[/bold]")
        console.print("  Press shortcut key or use ↑↓ + Enter")
        console.print()
        console.print("[bold]Attach to existing browser:[/bold]")
        console.print(
            f"  Start Chrome with: --remote-debugging-port={self.config.cdp_port}"
        )
        console.print("  Then use 'Attach to existing' menu option")
        await pause()

    async def _action_add(self) -> None:
        """Add annotation by selector."""
        print_header("Add annotation")
        console.print("[dim]Single: #id, .class, p:first-child, [data-attr][/dim]")
        console.print("[dim]Multi:  p (all), .card, article > p, h1,h2,h3[/dim]")
        console.print("[dim]Tip: Use Ctrl+I in browser to click-select[/dim]")
        console.print()

        selector = await ask_text_required("CSS selector:")
        if not selector:
            return

        page = self.state.browser.page
        if not page:
            console.print("[red]Not connected[/red]")
            await pause()
            return

        # Check how many elements match
        count_result = await page.evaluate(
            f"document.querySelectorAll({selector!r}).length"
        )
        count = count_result or 0

        if count == 0:
            console.print("[red]No elements found[/red]")
            await pause()
            return

        # Auto-generate ID for multi-select, ask for single
        if count > 1:
            # Get tag name from first element for auto-ID
            tag = await page.evaluate(
                f"document.querySelector({selector!r})?.tagName?.toLowerCase() || 'el'"
            )
            ann_id = tag
            console.print(f"[dim]Found {count} elements, using prefix: {ann_id}[/dim]")
        else:
            ann_id = await ask_text_required("ID:")
            if not ann_id:
                return

        label = await ask_text("Label (optional):")

        result = await page.evaluate(
            f"window.__inspector?.addAnnotation({selector!r}, {ann_id!r}, {label or ''!r})"
        )

        if result and result.get("success"):
            added_count = result.get("count", 1)
            ids = result.get("ids", [ann_id])
            # Add all annotated elements to local state
            for element_id in ids:
                self.state.annotations.append(
                    Annotation(
                        id=element_id,
                        selector=selector,
                        label=label or "",
                    )
                )
            if added_count > 1:
                console.print(
                    f"[green]Added {added_count} elements:[/green] {ids[0]} ... {ids[-1]}"
                )
            else:
                console.print(f"[green]Added:[/green] {ann_id}")
        else:
            error = (
                result.get("error", "Element not found")
                if result
                else "Element not found"
            )
            console.print(f"[red]{error}[/red]")
        await pause()

    async def _action_list(self) -> None:
        """List annotations (auto-syncs from browser)."""
        await self._sync_annotations()

        print_header("Annotations")

        if not self.state.annotations:
            console.print("[dim]No annotations[/dim]")
            await pause()
            return

        table = Table(show_header=True, header_style="bold", box=None)
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Label")
        table.add_column("Selector", style="dim")

        for ann in self.state.annotations:
            sel = ann.selector[:30] + "..." if len(ann.selector) > 30 else ann.selector
            table.add_row(ann.id, ann.label, sel)

        console.print(table)
        await pause()

    async def _action_remove(self) -> None:
        """Remove annotation (auto-syncs from browser)."""
        await self._sync_annotations()

        if not self.state.annotations:
            print_header("Remove")
            console.print("[dim]No annotations[/dim]")
            await pause()
            return

        print_header("Remove annotation")

        choices = [
            questionary.Choice(f"{ann.id} {ann.label}".strip(), value=ann.id)
            for ann in self.state.annotations
        ]
        choices.append(questionary.Choice("Cancel", value=None, shortcut_key="c"))

        ann_id = await ask_select("Select:", choices)
        if not ann_id:
            return

        page = self.state.browser.page
        if page:
            await page.evaluate(f"window.__inspector?.removeById({ann_id!r})")

        self.state.annotations = [a for a in self.state.annotations if a.id != ann_id]
        console.print(f"[yellow]Removed:[/yellow] {ann_id}")
        await pause()

    async def _action_capture(self) -> None:
        """Comprehensive capture - screenshot, HTML, annotations, DOM, CSS, network, etc."""
        if self.state.browser.connection != ConnectionState.CONNECTED:
            return

        if not self.session_path:
            console.print("[red]No active session[/red]")
            return

        print_header("Capture")

        with (
            LogSpan(span="browse.capture", session=self.session_path.name) as s,
            console.status("[bold white]Capturing page data...", spinner="dots"),
        ):
            # Get comprehensive capture data
            capture_data = await self.browser.capture_comprehensive()
            self.capture_count += 1
            s.add("captureNum", self.capture_count)

            # Sync local annotation state
            annotations = capture_data.get("annotations", [])
            self.state.annotations.clear()
            for ann in annotations:
                self.state.annotations.append(
                    Annotation(
                        id=ann.get("id", ""),
                        selector=ann.get("selector", ""),
                        label=ann.get("label", ""),
                        comment=ann.get("textContent", "")[:50]
                        if ann.get("textContent")
                        else "",
                    )
                )
            s.add("annotationCount", len(annotations))

            # Save to disk
            capture_dir = save_comprehensive_capture(
                session_path=self.session_path,
                capture_num=self.capture_count,
                capture_data=capture_data,
            )
            s.add("captureDir", str(capture_dir))

        # Show relative path from .browser-sessions
        sessions_dir = self.config.get_sessions_path()
        relative_path = capture_dir.relative_to(sessions_dir)
        console.print(f"[green]Saved:[/green] {relative_path}")
        await pause()

    async def _action_info(self) -> None:
        """Show session and page info."""
        # Sync annotations from browser first
        await self._sync_annotations()

        print_header("Info")

        # Page info
        if self.state.browser.url:
            console.print(f"[bold]URL:[/bold] {self.state.browser.url}")
            console.print(f"[bold]Title:[/bold] {self.state.browser.title}")
        else:
            console.print("[dim]Not connected[/dim]")

        console.print()

        # Annotations
        if self.state.annotations:
            console.print(f"[bold]Annotations ({len(self.state.annotations)}):[/bold]")
            for ann in self.state.annotations:
                label_part = f" - {ann.label}" if ann.label else ""
                console.print(f"  [cyan]{ann.id}[/cyan]{label_part}")
        else:
            console.print("[dim]No annotations[/dim]")

        console.print()

        # Session info
        if self.session_path:
            console.print(f"[bold]Session:[/bold] {self.session_path.name}")
            console.print(f"[bold]Captures:[/bold] {self.capture_count}")
        else:
            console.print(f"[dim]Sessions dir: {self.config.get_sessions_path()}[/dim]")
            console.print("[dim]No active session (capture to create one)[/dim]")

        console.print()
        console.print(
            f"[dim]DevTools: {'enabled' if self.config.devtools else 'disabled'}[/dim]"
        )
        await pause()

    async def _action_disconnect(self) -> None:
        """Disconnect from browser and reset session."""
        await self.browser.disconnect()
        # Reset session so next connect starts fresh
        self.session_path = None
        self.capture_count = 0


def clear_sessions() -> int:
    """Clear all browser sessions."""
    import shutil

    from .storage import _get_sessions_dir

    sessions_dir = _get_sessions_dir()
    if not sessions_dir.exists():
        console.print("[dim]No sessions to clear[/dim]")
        return 0

    count = 0
    for session in sessions_dir.iterdir():
        if session.is_dir():
            shutil.rmtree(session)
            count += 1

    console.print(f"[green]Cleared {count} session(s)[/green]")
    return count


def main() -> None:
    """CLI entry point."""
    import sys

    # Allow --help without requiring global config
    if not any(arg in sys.argv for arg in ("--help", "-h")):
        # Require global config directory (created by ot-serve)
        from ot.paths import get_global_dir

        global_dir = get_global_dir()
        if not global_dir.exists():
            print(
                f"Error: {global_dir} not found.\n"
                "Run 'ot-serve init' to initialize OneTool configuration.",
                file=sys.stderr,
            )
            sys.exit(1)

    # Initialize logging first
    configure_logging(log_name="browse")

    parser = argparse.ArgumentParser(description="Browser Inspector CLI")
    parser.add_argument("url", nargs="?", help="URL to open")
    parser.add_argument("--config", "-c", help="Path to ot-browse.yaml config file")
    parser.add_argument(
        "--clear-sessions",
        action="store_true",
        help="Clear all saved sessions before starting",
    )
    args = parser.parse_args()

    # Load config
    config = get_config(args.config)

    if args.clear_sessions:
        clear_sessions()

    # Print startup banner
    _print_startup_banner()

    try:
        cli = BrowserInspectorCLI(config)
        asyncio.run(cli.run(initial_url=args.url))
    except KeyboardInterrupt:
        console.print("[dim]Interrupted[/dim]")


if __name__ == "__main__":
    main()
