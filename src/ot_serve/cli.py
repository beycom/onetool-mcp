"""Serve CLI entry point for OneTool MCP server."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

import ot
from ot._cli import create_cli, version_callback

app = create_cli(
    "ot-serve",
    "OneTool MCP server - exposes a single 'run' tool for LLM code generation.",
)

# Init subcommand group - manage global configuration
init_app = typer.Typer(
    name="init",
    help="Initialize and manage global configuration in ~/.onetool/",
    invoke_without_command=True,
)
app.add_typer(init_app)


@init_app.callback()
def init_callback(ctx: typer.Context) -> None:
    """Initialize and manage global configuration in ~/.onetool/.

    Run without subcommand to initialize global config directory.
    """
    if ctx.invoked_subcommand is None:
        # No subcommand = run init
        init_create()


@init_app.command("create", hidden=True)
def init_create() -> None:
    """Initialize global config directory (~/.onetool/).

    Creates the global config directory and copies template files if they
    don't already exist. Existing files are preserved.

    This is the default action when running 'ot-serve init' without a subcommand.
    """
    from ot.paths import ensure_global_dir, get_global_dir

    global_dir = get_global_dir()
    if global_dir.exists():
        console = Console(stderr=True)
        console.print(f"[dim]Global config already exists at {global_dir}/[/dim]")
        console.print("[dim]Use 'ot-serve init reset' to reinstall templates.[/dim]")
        return

    ensure_global_dir(quiet=False, force=False)


@init_app.command("reset")
def init_reset(
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Reset without confirmation prompt.",
    ),
) -> None:
    """Reset global config to default templates.

    Overwrites existing config files in ~/.onetool/ with fresh templates.
    Use with caution - any customizations will be lost.
    """
    from ot.paths import ensure_global_dir, get_global_dir

    global_dir = get_global_dir()
    console = Console(stderr=True)

    if not force:
        console.print(f"[yellow]This will overwrite files in {global_dir}/[/yellow]")
        confirm = typer.confirm("Continue?", default=False)
        if not confirm:
            raise typer.Abort()

    ensure_global_dir(quiet=False, force=True)
    console.print("[green]Global config reset to defaults.[/green]")


@init_app.command("validate")
def init_validate() -> None:
    """Validate all configuration files.

    Checks global and project config files for syntax and schema errors.
    """
    from loguru import logger

    from ot.config.loader import load_config
    from ot.paths import get_global_dir, get_project_dir

    # Suppress DEBUG logs from config loader
    logger.remove()

    console = Console(stderr=True)
    errors: list[str] = []
    validated: list[str] = []

    # Check global config
    global_dir = get_global_dir()
    global_config = global_dir / "ot-serve.yaml"
    if global_config.exists():
        try:
            load_config(global_config)
            validated.append(str(global_config))
        except Exception as e:
            errors.append(f"{global_config}: {e}")

    # Check project config
    project_dir = get_project_dir()
    if project_dir:
        project_config = project_dir / "ot-serve.yaml"
        if project_config.exists():
            try:
                load_config(project_config)
                validated.append(str(project_config))
            except Exception as e:
                errors.append(f"{project_config}: {e}")

    # Report results
    if validated:
        console.print("[green]Valid configurations:[/green]")
        for path in validated:
            console.print(f"  ✓ {path}")

    if errors:
        console.print("\n[red]Validation errors:[/red]")
        for error in errors:
            console.print(f"  ✗ {error}")
        raise typer.Exit(1)

    if not validated and not errors:
        console.print("No configuration files found.")
        console.print(f"[dim]Checked: {global_config}, .onetool/ot-serve.yaml[/dim]")


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
    # Bootstrap global config directory on first run
    from ot.paths import ensure_global_dir

    ensure_global_dir(quiet=True)

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
