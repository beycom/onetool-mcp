"""Shared CLI utilities for OneTool CLIs.

Provides common patterns used across ot-serve and ot-bench CLIs.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import typer
from rich.console import Console

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = ["console", "create_cli", "version_callback"]


def _is_debug_tracebacks() -> bool:
    """Check if verbose tracebacks are enabled.

    Reads debug_tracebacks from ~/.onetool/ot-serve.yaml.
    Returns False on any error (fail-safe for broken configs).
    """
    try:
        import yaml

        config_path = Path.home() / ".onetool" / "ot-serve.yaml"
        if not config_path.exists():
            return False
        with config_path.open() as f:
            data = yaml.safe_load(f)
        return bool(data.get("debug_tracebacks", False)) if data else False
    except Exception:
        return False

# Shared console instance for consistent output
console = Console(highlight=False)


def version_callback(name: str, version: str) -> Callable[[bool], None]:
    """Create a version callback for Typer CLI.

    Args:
        name: CLI name to display (e.g., "ot", "ot-bench")
        version: Version string to display

    Returns:
        Callback function for --version option

    Example:
        @app.callback()
        def main(
            version: bool | None = typer.Option(
                None,
                "--version", "-v",
                callback=version_callback("ot", __version__),
                is_eager=True,
                help="Show version and exit.",
            ),
        ) -> None:
            ...
    """

    def callback(value: bool) -> None:
        if value:
            console.print(f"{name} version {version}")
            raise typer.Exit()

    return callback


def create_cli(
    name: str,
    help_text: str,
    *,
    no_args_is_help: bool = False,
) -> typer.Typer:
    """Create a Typer CLI app with standard configuration.

    Args:
        name: CLI name
        help_text: Help text for the CLI
        no_args_is_help: Show help when no args provided (default: False)

    Returns:
        Configured Typer app

    Note:
        Set debug_tracebacks: true in ~/.onetool/ot-serve.yaml for Rich
        formatted tracebacks with local variables and syntax highlighting.

    Example:
        app = create_cli(
            "ot-bench",
            "OneTool benchmark harness.",
            no_args_is_help=True,
        )
    """
    debug = _is_debug_tracebacks()
    return typer.Typer(
        name=name,
        help=help_text,
        no_args_is_help=no_args_is_help,
        pretty_exceptions_enable=debug,
    )
