"""Serve CLI entry point for OneTool MCP server."""

from __future__ import annotations

from pathlib import Path

import typer

import ot
from ot._cli import create_cli, version_callback

app = create_cli(
    "ot-serve",
    "OneTool MCP server - exposes a single 'run' tool for LLM code generation.",
)


@app.callback(invoke_without_command=True)
def serve(
    ctx: typer.Context,
    _version: bool | None = typer.Option(
        None,
        "--version",
        "-v",
        callback=version_callback("ot-serve", ot.__version__),
        is_eager=True,
        help="Show version and exit.",
    ),
    config: Path | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to ot-serve.yaml configuration file.",
        exists=True,
        readable=True,
    ),
) -> None:
    """Run the OneTool MCP server over stdio transport.

    This starts the MCP server that exposes the 'run' tool for LLM integrations.
    The server communicates via stdio and is typically invoked by MCP clients.

    Examples:
        ot-serve
        ot-serve --config config/ot-serve.yaml
    """
    # Only run if no subcommand was invoked (handles --help automatically)
    if ctx.invoked_subcommand is not None:
        return

    # Load config if specified
    if config:
        from ot.config.loader import get_config

        get_config(config)

    # Note: MCP uses stdio for JSON-RPC, so we must not print to stdout
    # Use stderr for any startup messages if needed

    # Import here to avoid circular imports and only load when needed
    from ot.server import main as server_main

    server_main()


def cli() -> None:
    """Run the CLI application."""
    app()


if __name__ == "__main__":
    cli()
