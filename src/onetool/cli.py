"""Serve CLI entry point for OneTool MCP server."""

from __future__ import annotations

import atexit
import os
import signal
from pathlib import Path

import typer


def _suppress_shutdown_warnings() -> None:
    """Suppress pymupdf SWIG warnings at exit.

    pymupdf emits a DeprecationWarning about swigvarlink during Python's
    interpreter shutdown. This warning is emitted at the C level during
    garbage collection. Redirecting stderr at the fd level suppresses it.
    """
    try:
        # Redirect stderr at the OS level to suppress C-level warnings
        devnull_fd = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull_fd, 2)
        os.close(devnull_fd)
    except Exception:
        pass


atexit.register(_suppress_shutdown_warnings)
from rich.console import Console

import ot
from ot._cli import create_cli, version_callback
from ot.support import get_support_banner, get_version

# Console for CLI output - no auto-highlighting, output to stderr
console = Console(stderr=True, highlight=False)

app = create_cli(
    "onetool",
    "OneTool MCP server - exposes a single 'run' tool for LLM code generation.",
)


def _print_startup_banner() -> None:
    """Print startup message to stderr."""
    version = get_version()
    console.print(f"[bold cyan]OneTool MCP Server[/bold cyan] [dim]v{version}[/dim]")
    console.print(get_support_banner())


def _setup_signal_handlers() -> None:
    """Set up signal handlers for clean exit."""

    def handle_signal(signum: int, _frame: object) -> None:
        """Handle termination signals gracefully."""
        sig_name = signal.Signals(signum).name
        console.print(f"\nReceived {sig_name}, shutting down...")
        # Use os._exit() for immediate termination - sys.exit() doesn't work
        # well with asyncio event loops and can require multiple Ctrl+C presses
        os._exit(0)

    # Handle SIGINT (Ctrl+C) and SIGTERM
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

# Init subcommand group - manage global configuration
init_app = typer.Typer(
    name="init",
    help="Initialize and manage global configuration in ~/.onetool/config/",
    invoke_without_command=True,
)
app.add_typer(init_app)


@init_app.callback()
def init_callback(ctx: typer.Context) -> None:
    """Initialize and manage global configuration in ~/.onetool/config/.

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

    This is the default action when running 'onetool init' without a subcommand.
    """
    from ot.paths import ensure_global_dir, get_global_dir

    global_dir = get_global_dir()
    if global_dir.exists():
        console.print(f"Global config already exists at {global_dir}/")
        console.print("Use 'onetool init reset' to reinstall templates.")
        return

    ensure_global_dir(quiet=False, force=False)


@init_app.command("reset")
def init_reset() -> None:
    """Reset global config to default templates.

    Prompts for each file before overwriting. For existing files, offers to
    create a backup first. Backups are named file.bak, file.bak.1, etc.
    """
    import shutil

    from ot.paths import (
        CONFIG_SUBDIR,
        create_backup,
        get_global_dir,
        get_template_files,
    )

    global_dir = get_global_dir()
    config_dir = global_dir / CONFIG_SUBDIR

    # Ensure directories exist
    global_dir.mkdir(parents=True, exist_ok=True)
    config_dir.mkdir(exist_ok=True)

    template_files = get_template_files()
    if not template_files:
        console.print("No template files found.")
        return

    copied_files: list[str] = []
    backed_up_files: list[tuple[str, Path]] = []
    skipped_files: list[str] = []

    for source_path, dest_name in template_files:
        dest_path = config_dir / dest_name
        exists = dest_path.exists()

        if exists:
            # Prompt for overwrite
            console.print(f"\nconfig/{dest_name} already exists.")
            do_overwrite = typer.confirm("Overwrite?", default=True)

            if not do_overwrite:
                skipped_files.append(dest_name)
                continue

            # Prompt for backup
            do_backup = typer.confirm(f"Create backup of config/{dest_name}?", default=True)

            if do_backup:
                backup_path = create_backup(dest_path)
                backed_up_files.append((dest_name, backup_path))

        shutil.copy(source_path, dest_path)
        copied_files.append(dest_name)

    # Summary
    console.print()
    if copied_files:
        console.print(f"Reset files in {config_dir}/:")
        for name in copied_files:
            console.print(f"  + {name}")

    if backed_up_files:
        console.print("\nBackups created:")
        for name, backup_path in backed_up_files:
            console.print(f"  config/{name} -> {backup_path.name}")

    if skipped_files:
        console.print("\nSkipped:")
        for name in skipped_files:
            console.print(f"  - config/{name}")


@init_app.command("validate")
def init_validate() -> None:
    """Validate configuration and show status.

    Checks config files for errors, then displays packs, secrets (names only),
    snippets, aliases, and MCP servers.
    """
    from loguru import logger

    from ot.config.loader import get_config, load_config
    from ot.config.secrets import load_secrets
    from ot.executor.tool_loader import load_tool_registry
    from ot.paths import CONFIG_SUBDIR, get_global_dir, get_project_dir

    # Suppress DEBUG logs from config loader
    logger.remove()

    errors: list[str] = []
    validated: list[str] = []

    # Check global config
    global_dir = get_global_dir()
    global_config = global_dir / CONFIG_SUBDIR / "onetool.yaml"
    if global_config.exists():
        try:
            load_config(global_config)
            validated.append(str(global_config))
        except Exception as e:
            errors.append(f"{global_config}: {e}")

    # Check project config
    project_dir = get_project_dir()
    if project_dir:
        project_config = project_dir / CONFIG_SUBDIR / "onetool.yaml"
        if project_config.exists():
            try:
                load_config(project_config)
                validated.append(str(project_config))
            except Exception as e:
                errors.append(f"{project_config}: {e}")

    # Report validation results
    console.print("Configuration\n")

    console.print("Directories:")
    global_exists = global_dir.exists()
    if global_exists:
        console.print(f"  Global:  {global_dir}/ - [green]OK[/green]")
    else:
        console.print(f"  Global:  {global_dir}/ - [red]missing[/red]")
    if project_dir:
        console.print(f"  Project: {project_dir}/ - [green]OK[/green]")
    else:
        console.print("  Project: (none)")

    if validated:
        console.print("\nConfig files:")
        for path in validated:
            console.print(f"  + {path}")

    if errors:
        console.print("\n[red]Validation errors:[/red]")
        for error in errors:
            console.print(f"  ! {error}")
        raise typer.Exit(1)

    if not validated and not errors:
        console.print("\nNo configuration files found.")
        console.print(f"Checked: {global_config}, .onetool/config/onetool.yaml")
        return

    # Load merged config for status display
    try:
        config = get_config()
    except Exception as e:
        console.print(f"\n[red]Config error:[/red] {e}")
        return

    # Packs and tools
    try:
        registry = load_tool_registry()
        if registry.packs:
            total_tools = 0
            pack_list = []
            for pack_name, pack_funcs in sorted(registry.packs.items()):
                from ot.executor.worker_proxy import WorkerPackProxy

                if isinstance(pack_funcs, WorkerPackProxy):
                    func_count = len(pack_funcs.functions)
                else:
                    func_count = len(pack_funcs)
                total_tools += func_count
                pack_list.append((pack_name, func_count))

            console.print(f"\nPacks ({len(pack_list)}, {total_tools} tools):")
            for pack_name, func_count in pack_list:
                console.print(f"  {pack_name} ({func_count})")
        else:
            console.print("\nPacks:")
            console.print("  (none)")
    except Exception as e:
        console.print("\nPacks:")
        console.print(f"  [red]Error loading tools:[/red] {e}")

    # Secrets (names only) - use config's secrets_file path
    try:
        secrets_path = config.get_secrets_file_path() if config else None
        secrets = load_secrets(secrets_path)
        if secrets:
            sorted_keys = sorted(secrets.keys())
            console.print(f"\nSecrets ({len(sorted_keys)}):")
            for key in sorted_keys:
                console.print(f"  {key} - [green]set[/green]")
        else:
            console.print("\nSecrets:")
            console.print("  (none configured)")
    except Exception as e:
        console.print("\nSecrets:")
        console.print(f"  [red]Error:[/red] {e}")

    # Snippets
    if config and config.snippets:
        sorted_snippets = sorted(config.snippets.keys())
        console.print(f"\nSnippets ({len(sorted_snippets)}):")
        console.print(f"  {', '.join(sorted_snippets)}")
    else:
        console.print("\nSnippets:")
        console.print("  (none)")

    # Aliases
    if config and config.alias:
        sorted_aliases = sorted(config.alias.items())
        console.print(f"\nAliases ({len(sorted_aliases)}):")
        alias_items = [f"{name} -> {target}" for name, target in sorted_aliases]
        console.print(f"  {', '.join(alias_items)}")
    else:
        console.print("\nAliases:")
        console.print("  (none)")

    # Servers
    if config and config.servers:
        sorted_servers = sorted(config.servers.keys())
        console.print(f"\nMCP Servers ({len(sorted_servers)}):")
        console.print(f"  {', '.join(sorted_servers)}")
    else:
        console.print("\nMCP Servers:")
        console.print("  (none)")

    # Dependencies
    try:
        from ot_sdk.deps import check_deps

        dep_results = check_deps()
        if dep_results:
            missing_count = sum(1 for r in dep_results if not r.ok)
            total_count = len(dep_results)
            if missing_count > 0:
                console.print(
                    f"\nDependencies ({total_count} tools, [yellow]{missing_count} missing[/yellow]):"
                )
            else:
                console.print(f"\nDependencies ({total_count} tools):")

            # Format with libs/clis breakdown per tool
            sorted_results = sorted(dep_results, key=lambda r: r.tool)
            for result in sorted_results:
                status = "[green]OK[/green]" if result.ok else "[yellow]missing[/yellow]"
                console.print(f"  {result.tool} - {status}")

                # Group by type
                libs = [d for d in result.dependencies if d.kind == "lib"]
                clis = [d for d in result.dependencies if d.kind == "cli"]
                secrets = [d for d in result.dependencies if d.kind == "secret"]

                if libs:
                    lib_items = []
                    for d in libs:
                        if d.available:
                            lib_items.append(d.name)
                        else:
                            lib_items.append(f"[yellow]{d.name}[/yellow]")
                    console.print(f"    libs: {', '.join(lib_items)}")
                if clis:
                    cli_items = []
                    for d in clis:
                        if d.available:
                            cli_items.append(d.name)
                        else:
                            cli_items.append(f"[yellow]{d.name}[/yellow]")
                    console.print(f"    clis: {', '.join(cli_items)}")
                if secrets:
                    secret_items = []
                    for d in secrets:
                        if d.available:
                            secret_items.append(d.name)
                        else:
                            secret_items.append(f"[yellow]{d.name}[/yellow]")
                    console.print(f"    secrets: {', '.join(secret_items)}")
        else:
            console.print("\nDependencies:")
            console.print("  (no tools declare dependencies)")
    except Exception as e:
        console.print("\nDependencies:")
        console.print(f"  [red]Error checking:[/red] {e}")


@app.callback(invoke_without_command=True)
def serve(
    ctx: typer.Context,
    _version: bool | None = typer.Option(
        None,
        "--version",
        "-v",
        callback=version_callback("onetool", ot.__version__),
        is_eager=True,
        help="Show version and exit.",
    ),
    config: Path | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to onetool.yaml configuration file.",
        exists=True,
        readable=True,
    ),
) -> None:
    """Run the OneTool MCP server over stdio transport.

    This starts the MCP server that exposes the 'run' tool for LLM integrations.
    The server communicates via stdio and is typically invoked by MCP clients.

    Examples:
        onetool
        onetool --config config/onetool.yaml
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

    # Set up signal handlers for clean exit (before starting server)
    _setup_signal_handlers()

    # Print startup banner to stderr (stdout is for MCP JSON-RPC)
    _print_startup_banner()

    # Import here to avoid circular imports and only load when needed
    from ot.server import main as server_main

    server_main()


def cli() -> None:
    """Run the CLI application."""
    app()


if __name__ == "__main__":
    cli()
