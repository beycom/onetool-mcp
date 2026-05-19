"""Serve CLI entry point for OneTool MCP server."""

from __future__ import annotations

import atexit
import os
import signal
import warnings
from datetime import UTC, datetime

warnings.filterwarnings("ignore", message="builtin type.*has no __module__ attribute")
from pathlib import Path

import typer
from fastmcp import Context, FastMCP
from fastmcp.tools import ToolResult

from onetool.cli_commands.direct_app import direct_app
from onetool.kb import kb_app


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


def _stdin_is_tty() -> bool:
    """Return True if stdin is a TTY. Extracted for testability."""
    import sys

    return sys.stdin.isatty()


def _setup_signal_handlers() -> None:
    """Set up signal handlers for clean exit."""

    def handle_signal(signum: int, _frame: object) -> None:
        """Handle termination signals gracefully."""
        sig_name = signal.Signals(signum).name
        console.print(f"\nReceived {sig_name}, shutting down...")
        raise KeyboardInterrupt

    # Handle SIGINT (Ctrl+C) and SIGTERM
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)


def _write_startup_config_error(config: Path, error: Exception) -> None:
    """Write pre-handshake config failures to the serve log location."""
    log_dir = config.parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "serve.log"
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    with log_file.open("a", encoding="utf-8") as f:
        f.write(
            f"{timestamp} | ERROR  | cli | mcp.startup.config_error | "
            f"config={config} | error={error}\n"
        )


app.add_typer(direct_app, name="direct", rich_help_panel="Direct")
app.add_typer(kb_app, name="kb", rich_help_panel="Knowledge Base")

# Init subcommand group - manage OneTool configuration directory
init_app = typer.Typer(
    name="init",
    help="Initialize and manage the OneTool configuration directory.",
    invoke_without_command=True,
)
app.add_typer(init_app, rich_help_panel="Configuration")


@app.command("child", rich_help_panel="Runtime")
def child(
    url: str = typer.Option(
        ...,
        "--url",
        help="Parent OneTool direct API base URL.",
    ),
) -> None:
    """Run a restricted child MCP server that forwards run calls to a parent."""
    from ot.handoff.child_proxy import forward_run
    from ot.utils import sanitize_output

    child_mcp = FastMCP(
        name="ot-child",
        instructions="Restricted OneTool child runtime. Use only the run tool.",
    )

    @child_mcp.tool(
        description="Run OneTool code through the parent OneTool runtime.",
        annotations={
            "title": "OneTool child run",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": True,
        },
    )
    async def run(command: str, ctx: Context) -> ToolResult:  # noqa: ARG001
        payload = await forward_run(command=command, direct_url=url)
        result = str(payload.get("result", ""))
        text = sanitize_output(result, enabled=False, fmt="json_h")
        return ToolResult(content=text)

    child_mcp.run(show_banner=False)


def _next_bak(path: Path) -> Path:
    """Return the next available .bak path for *path* (avoids collisions)."""
    bak = Path(str(path) + ".bak")
    if not bak.exists():
        return bak
    n = 1
    while True:
        bak = Path(str(path) + f".bak{n}")
        if not bak.exists():
            return bak
        n += 1


def _safe_copy(src: Path, dest: Path) -> None:
    """Copy *src* to *dest*; if *dest* exists rename it to .bak first."""
    import shutil

    if dest.exists():
        bak = _next_bak(dest)
        dest.rename(bak)
        console.print(
            f"  [yellow]![/yellow] {dest.name} exists → backed up as {bak.name}"
        )
    shutil.copy(src, dest)


def _safe_write(dest: Path, content: str) -> None:
    """Write *content* to *dest*; if *dest* exists rename it to .bak first."""
    if dest.exists():
        bak = _next_bak(dest)
        dest.rename(bak)
        console.print(
            f"  [yellow]![/yellow] {dest.name} exists → backed up as {bak.name}"
        )
    dest.write_text(content)


def _write_onetool_yaml(config_path: Path, includes: list[str]) -> None:
    """Write onetool.yaml from the package template with the given includes."""
    import re

    from ot.paths import get_global_templates_dir

    template_path = get_global_templates_dir() / "onetool.yaml"
    template_text = template_path.read_text()

    # Build the replacement include block (omit entirely when no includes)
    if includes:
        new_include = "include:\n" + "".join(f"  - {inc}\n" for inc in includes)
    else:
        new_include = ""

    # Replace the existing include: block (all lines starting with "  -" after "include:")
    updated = re.sub(r"include:\n(?:  - [^\n]+\n)*", new_include, template_text)
    _safe_write(config_path, updated)


def _copy_servers_yaml(ot_dir: Path, server_names: list[str]) -> None:
    """Copy servers.yaml with only the requested server blocks."""
    import yaml

    from ot.paths import get_global_templates_dir

    templates_dir = get_global_templates_dir()
    src = templates_dir / "servers.yaml"
    if not src.exists():
        console.print(
            "[yellow]Warning: servers.yaml not found in package templates[/yellow]"
        )
        return

    raw = yaml.safe_load(src.read_text())
    if not isinstance(raw, dict):
        console.print(
            "[yellow]Warning: servers.yaml is not a YAML mapping, skipping[/yellow]"
        )
        return
    all_servers = raw.get("servers", {})

    selected: dict[str, object] = {}
    unknown: list[str] = []
    for name in server_names:
        if name in all_servers:
            selected[name] = all_servers[name]
        else:
            unknown.append(name)

    if unknown:
        console.print(
            f"[yellow]Unknown servers (will be skipped): {', '.join(unknown)}[/yellow]"
        )
        console.print(f"  Available: {', '.join(sorted(all_servers.keys()))}")

    dest = ot_dir / "servers.yaml"
    _safe_write(
        dest,
        yaml.dump({"servers": selected}, default_flow_style=False, sort_keys=False),
    )
    console.print(
        f"  [green]✓[/green] servers.yaml (servers: {', '.join(selected.keys())})"
    )


def _copy_file(ot_dir: Path, filename: str) -> bool:
    """Copy a single file from global_templates. Returns True if success."""
    from ot.paths import get_global_templates_dir

    templates_dir = get_global_templates_dir()
    # Support -template suffix stripping (e.g., secrets-template.yaml -> secrets.yaml)
    src_name = filename.replace(".yaml", "-template.yaml")
    src = templates_dir / src_name
    if not src.exists():
        src = templates_dir / filename
    if not src.exists():
        console.print(f"  [red]✗[/red] {filename} not found in package templates")
        return False

    dest = ot_dir / filename
    _safe_copy(src, dest)
    console.print(f"  [green]✓[/green] {filename}")
    return True


def _copy_diagram(ot_dir: Path) -> bool:
    """Copy diagram.yaml and diagram-templates/ directory. Returns True if success."""
    import shutil

    from ot.paths import get_global_templates_dir

    templates_dir = get_global_templates_dir()
    src_yaml = templates_dir / "diagram.yaml"
    if not src_yaml.exists():
        console.print("  [red]✗[/red] diagram.yaml not found in package templates")
        return False

    dest_yaml = ot_dir / "diagram.yaml"
    _safe_copy(src_yaml, dest_yaml)
    console.print("  [green]✓[/green] diagram.yaml")

    src_templates = templates_dir / "diagram-templates"
    if src_templates.exists():
        dest_templates = ot_dir / "diagram-templates"
        if dest_templates.exists():
            bak = _next_bak(dest_templates)
            dest_templates.rename(bak)
            console.print(
                f"  [yellow]![/yellow] diagram-templates/ exists → backed up as {bak.name}"
            )
        shutil.copytree(src_templates, dest_templates)
        console.print("  [green]✓[/green] diagram-templates/")

    return True


@init_app.callback()
def init_callback(
    ctx: typer.Context,
    config: Path | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Config directory or onetool.yaml path (auto-detected by suffix).",
    ),
) -> None:
    """Initialize OneTool configuration directory.

    Runs an interactive TUI to select which extensions to configure.
    Existing files are backed up to .bak before overwriting.

    Examples:
      onetool init                     (uses current directory)
      onetool init -c .onetool         (directory: writes .onetool/onetool.yaml)
      onetool init -c .onetool/ot.yaml (explicit file path)
    """
    if ctx.invoked_subcommand is not None:
        return

    # Resolve config dir and file: .yaml/.yml suffix → treat as file, else → directory
    if config is not None:
        if config.suffix in (".yaml", ".yml"):
            ot_dir = config.parent
            config_path = config
        else:
            ot_dir = config
            config_path = config / "onetool.yaml"
    else:
        ot_dir = Path()
        config_path = ot_dir / "onetool.yaml"

    includes: list[str] = []

    if _stdin_is_tty():
        import questionary

        from ot._tui import ask_checkbox, ask_text_sync

        confirmed = ask_text_sync("Config file", default=str(config_path))
        if confirmed is None:
            console.print("[dim]Cancelled.[/dim]")
            raise typer.Exit(0)
        config_path = Path(confirmed)
        ot_dir = config_path.parent

        if config_path.exists():
            overwrite = questionary.confirm(
                "onetool.yaml already exists. Overwrite?", default=False
            ).ask()
            if not overwrite:
                console.print("[dim]Cancelled.[/dim]")
                raise typer.Exit(0)

        console.print(f"\nSetting up OneTool config at [bold]{ot_dir}/[/bold]\n")
        _exts = [
            ("prompts.yaml", "prompt templates"),
            ("servers.yaml", "MCP proxy server configs"),
            ("security.yaml", "custom security rules"),
            ("diagram.yaml", "diagram tool config"),
            ("snippets.yaml", "code snippets"),
        ]
        choices = [
            questionary.Choice("None           (no extensions)", value=None),
            *[questionary.Choice(f"{v:<14}  {desc}", value=v) for v, desc in _exts],
        ]
        selected_ext = ask_checkbox("Which extensions to configure?", choices)

        if selected_ext is None:
            console.print("[dim]Cancelled.[/dim]")
            raise typer.Exit(0)

        # Filter out the explicit "None" choice
        selected_ext = [x for x in selected_ext if x is not None]

        ot_dir.mkdir(parents=True, exist_ok=True)

        if selected_ext:
            console.print(f"\nCopying files into {ot_dir}/")
            for ext in selected_ext:
                if ext == "diagram.yaml":
                    if _copy_diagram(ot_dir):
                        includes.append(ext)
                elif _copy_file(ot_dir, ext):
                    includes.append(ext)

        _write_onetool_yaml(config_path, includes)
        console.print(f"\n[green]✓[/green] {config_path.name} written")
        if includes:
            console.print(f"  Includes: {', '.join(includes)}")
        return

    # Non-interactive: write minimal onetool.yaml
    ot_dir.mkdir(parents=True, exist_ok=True)
    _write_onetool_yaml(config_path, includes)
    console.print(f"\n[green]✓[/green] {config_path} written")


@init_app.command("validate")
def init_validate(
    config: Path = typer.Option(
        ...,
        "--config",
        "-c",
        exists=True,
        readable=True,
        help="Path to onetool.yaml to validate.",
    ),
    secrets: Path | None = typer.Option(
        None,
        "--secrets",
        "-s",
        help="Path to secrets file.",
    ),
) -> None:
    """Validate configuration and show status.

    Checks config files for errors, then displays packs, secrets (names only),
    snippets, aliases, and MCP servers.
    """
    from loguru import logger

    from ot import __version__
    from ot.config.loader import get_config
    from ot.config.secrets import load_secrets
    from ot.executor.tool_loader import load_tool_registry

    # Suppress DEBUG logs from config loader
    logger.remove()

    errors: list[str] = []
    validated: list[str] = []

    try:
        get_config(config, reload=True, secrets_path=secrets)
        validated.append(str(config))
    except Exception as e:
        errors.append(f"{config}: {e}")

    # Report validation results
    console.print("Configuration\n")
    console.print(f"Version: [cyan]{__version__}[/cyan]\n")

    console.print("Config directory:")
    ot_dir = config.parent
    if ot_dir.exists():
        console.print(f"  {ot_dir}/ - [green]OK[/green]")
    else:
        console.print(f"  {ot_dir}/ - [red]missing[/red]")

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
        return

    # Include source reporting
    try:
        import yaml

        from ot.config.loader import _resolve_include_path
        from ot.paths import get_global_templates_dir

        raw_config = yaml.safe_load(config.read_text()) or {}
        include_list: list[str] = raw_config.get("include", [])
        ot_dir = config.parent.resolve()
        templates_dir = get_global_templates_dir()

        # Known includeable template files (filter on dest name after transformation)
        _excluded = {"onetool.yaml", "secrets.yaml"}
        known_templates = sorted(
            dest
            for tmpl in templates_dir.glob("*.yaml")
            if not tmpl.name.startswith("_")
            for dest in [tmpl.name.replace("-template.yaml", ".yaml")]
            if dest not in _excluded
        )

        listed_set = set(include_list)
        console.print(f"\nIncludes ({len(include_list)} listed):")

        # Show source for each listed include
        for inc in include_list:
            resolved = _resolve_include_path(inc, ot_dir)
            if resolved is None:
                console.print(f"  [red]\\[missing][/red] {inc}")
            elif resolved.is_relative_to(ot_dir):
                console.print(f"  [cyan]\\[user][/cyan]    {inc}")
            elif resolved.is_relative_to(templates_dir):
                console.print(f"  [yellow]\\[default][/yellow] {inc}")
                console.print(
                    f"             [dim]Hint: Copy to your config dir to customise: {resolved.name}[/dim]"
                )
            else:
                console.print(f"  [green]\\[absolute][/green] {inc} -> {resolved}")

        # Show known templates that are not listed
        not_listed = [t for t in known_templates if t not in listed_set]
        if not_listed:
            for name in not_listed:
                console.print(f"  [dim]\\[not listed][/dim] {name}")
    except Exception as e:
        console.print(f"\n[dim]Include source check skipped: {e}[/dim]")

    # Load merged config for status display
    try:
        cfg = get_config()
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

    # Secrets (names only) - use explicit --secrets path only
    try:
        secrets_data = load_secrets(secrets)
        if secrets_data:
            sorted_keys = sorted(secrets_data.keys())
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
    if cfg and cfg.snippets:
        sorted_snippets = sorted(cfg.snippets.keys())
        console.print(f"\nSnippets ({len(sorted_snippets)}):")
        console.print(f"  {', '.join(sorted_snippets)}")
    else:
        console.print("\nSnippets:")
        console.print("  (none)")

    # Aliases
    if cfg and cfg.alias:
        sorted_aliases = sorted(cfg.alias.items())
        console.print(f"\nAliases ({len(sorted_aliases)}):")
        alias_items = [f"{name} -> {target}" for name, target in sorted_aliases]
        console.print(f"  {', '.join(alias_items)}")
    else:
        console.print("\nAliases:")
        console.print("  (none)")

    # Servers
    if cfg and cfg.servers:
        sorted_servers = sorted(cfg.servers.keys())
        console.print(f"\nMCP Servers ({len(sorted_servers)}):")
        console.print(f"  {', '.join(sorted_servers)}")
    else:
        console.print("\nMCP Servers:")
        console.print("  (none)")


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
    ),
    secrets: Path | None = typer.Option(
        None,
        "--secrets",
        "-s",
        help="Path to secrets file. If omitted, no secrets are loaded.",
    ),
) -> None:
    """Run the OneTool MCP server over stdio transport.

    This starts the MCP server that exposes the 'run' tool for LLM integrations.
    The server communicates via stdio and is typically invoked by MCP clients.

    Examples:
        onetool --config /path/to/.onetool/onetool.yaml
        onetool --config /path/to/.onetool/onetool.yaml --secrets /path/to/.onetool/secrets.yaml
    """
    # Only run if no subcommand was invoked (handles --help automatically)
    if ctx.invoked_subcommand is not None:
        return

    if config is None:
        console.print("[red]Error: Missing option '--config' / '-c'.[/red]")
        console.print("Usage: onetool --config /path/to/.onetool/onetool.yaml")
        raise typer.Exit(1)
    if not config.exists():
        if _stdin_is_tty():
            console.print("[yellow]OneTool is not initialized.[/yellow]")
            console.print(f"Config file not found: {config}")
            do_init = typer.confirm("Initialize now?", default=True)
            if do_init:
                from ot.paths import ensure_ot_dir

                ensure_ot_dir(config, quiet=False, force=False)
                console.print(f"[green]✓[/green] Initialized at {config.parent}/")
            else:
                console.print(f"Run 'onetool init --config {config}' when ready.")
                raise typer.Exit(1)
        else:
            console.print(
                f"OneTool not initialized. Run: onetool init --config {config}"
            )
            raise typer.Exit(1)

    # Remove loguru's default stderr handler before any logging occurs
    import ot.logging  # noqa: F401

    # Load config (secrets threaded through load_config)
    from ot.config.loader import get_config

    try:
        get_config(config, reload=True, secrets_path=secrets)
    except Exception as e:
        _write_startup_config_error(config, e)
        console.print(f"[red]Error loading config:[/red] {e}")
        raise typer.Exit(1) from e

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
