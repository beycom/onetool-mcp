"""Top-level `onetool admin` subcommand group."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

admin_app = typer.Typer(
    name="admin",
    help="Serve the shared local OneTool Admin App.",
    no_args_is_help=True,
)

console = Console(highlight=False)
err_console = Console(stderr=True, highlight=False)


def _resolve_admin_ot_dir(value: Path) -> Path:
    """Resolve and validate the Admin App auth directory."""
    from ot.paths import expand_path

    if not str(value).startswith("~") and not value.is_absolute():
        err_console.print("[red]Error: --ot-dir must be an absolute path after ~ expansion.[/red]")
        raise typer.Exit(2)
    return expand_path(str(value))


@admin_app.command("serve")
def admin_serve(
    ot_dir: Annotated[
        Path,
        typer.Option(
            "--ot-dir",
            help="Absolute OneTool directory containing auth/mcp-direct.key.",
        ),
    ],
    port: Annotated[
        int,
        typer.Option("--port", help="Admin App browser server port.", min=1, max=65535),
    ] = 8760,
    direct_start_port: Annotated[
        int,
        typer.Option(
            "--direct-start-port",
            help="First MCP Direct API candidate port scanned by the Admin App.",
            min=1,
            max=65535,
        ),
    ] = 8765,
    scan_max: Annotated[
        int,
        typer.Option("--scan-max", help="Maximum Direct API candidate ports per scan.", min=1),
    ] = 10,
) -> None:
    """Serve the shared local Admin App."""
    resolved_ot_dir = _resolve_admin_ot_dir(ot_dir)
    console.print(f"OneTool Admin App: http://127.0.0.1:{port}")

    from onetool.admin.server import serve_admin_app

    serve_admin_app(
        ot_dir=resolved_ot_dir,
        port=port,
        direct_start_port=direct_start_port,
        scan_max=scan_max,
    )


__all__ = ["admin_app"]
