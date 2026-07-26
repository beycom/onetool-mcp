"""Claude Code and Codex launcher CLI commands."""

from __future__ import annotations

import json
import os
import subprocess
from importlib.resources import files
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import questionary
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from onetool.code.adapters import (
    build_invocation,
    check_client_version,
    required_route_capabilities,
    resolve_client_executable,
    run_capability_command,
    run_foreground,
)
from onetool.code.domain import LaunchInvocation, ResolvedRoute
from onetool.code.resolver import resolve_route
from ot.config.loader import load_config
from ot.config.secrets import get_secret
from ot.paths import expand_path

if TYPE_CHECKING:
    from ot.config.models import OneToolConfig
    from ot.config.routing import Harness, PermissionMode

console = Console(stderr=True, highlight=False)

code_app = typer.Typer(
    name="code",
    help="Select, inspect, and diagnose configured code-harness routes.",
    invoke_without_command=True,
    no_args_is_help=False,
)

ConfigOption = Annotated[
    Path | None,
    typer.Option("--config", "-c", help="Explicit onetool.yaml path."),
]
SecretsOption = Annotated[
    Path | None,
    typer.Option("--secrets", "-s", help="Explicit secrets.yaml path."),
]


def _candidate_config_paths() -> tuple[Path, Path]:
    """Return project then standard user launcher configuration paths."""
    return (
        Path.cwd() / ".onetool" / "onetool.yaml",
        expand_path("~/.onetool/onetool.yaml"),
    )


def resolve_code_config_path(explicit: Path | None) -> Path:
    """Resolve launcher configuration without changing serve semantics."""
    if explicit is not None:
        path = explicit.resolve()
        if not path.is_file():
            raise ValueError(f"Explicit launcher config is not a file: {path}")
        return path
    candidates = _candidate_config_paths()
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    checked = ", ".join(str(path) for path in candidates)
    raise ValueError(
        f"No launcher configuration found. Checked: {checked}. "
        "Run `onetool code setup --config <onetool.yaml>`."
    )


def _load_launcher_config(
    config_path: Path | None,
    secrets_path: Path | None,
) -> tuple[OneToolConfig, Path]:
    """Load the resolved launcher config and adjacent secrets when present."""
    resolved = resolve_code_config_path(config_path)
    resolved_secrets = secrets_path
    if resolved_secrets is None:
        adjacent = resolved.parent / "secrets.yaml"
        resolved_secrets = adjacent if adjacent.is_file() else None
    return load_config(resolved, secrets_path=resolved_secrets), resolved


def _permission(*, safe: bool, bypass: bool) -> PermissionMode | None:
    """Resolve non-contradictory permission options."""
    if safe and bypass:
        raise ValueError("--safe and --bypass cannot be used together")
    if safe:
        return "safe"
    if bypass:
        return "bypass"
    return None


def _print_warning(route: ResolvedRoute) -> None:
    """Print route notices that quiet mode must not suppress."""
    if route.warning is not None:
        console.print(f"[bold yellow]Warning:[/bold yellow] {route.warning}")


def _start_summary(invocation: LaunchInvocation, *, quiet: bool) -> None:
    """Render a polished or concise pre-launch summary."""
    _print_warning(invocation.route)
    if quiet:
        return
    route = invocation.route
    lines = [
        f"Harness: {route.harness}",
        f"Model: {route.model.label} ({route.model.id})",
        f"Source: {route.source}",
        f"Transport: {route.transport}",
        f"Permission: {route.permission}",
    ]
    if console.is_terminal:
        console.print(
            Panel(
                "\n".join(lines),
                title=f"Starting {route.harness.title()}",
                border_style="cyan",
            )
        )
    else:
        console.print(
            "Starting "
            + route.harness
            + ": "
            + ", ".join(line.lower() for line in lines[1:])
        )


def _end_summary(
    *,
    route: ResolvedRoute,
    return_code: int,
    elapsed: float,
    quiet: bool,
) -> None:
    """Render the matching bounded child outcome."""
    if quiet:
        return
    if return_code < 0:
        outcome = f"signal {-return_code}"
    elif return_code == 0:
        outcome = "success"
    else:
        outcome = f"exit {return_code}"
    console.print(
        f"Ended {route.harness}: model={route.model.shortcut}, "
        f"route={route.name}, elapsed={elapsed:.1f}s, outcome={outcome}"
    )


def _launch(
    *,
    harness: Harness,
    model: str | None,
    route_name: str | None,
    safe: bool,
    bypass: bool,
    config_path: Path | None,
    secrets_path: Path | None,
    quiet: bool,
    verbose: bool,
    dry_run: bool,
    passthrough: tuple[str, ...],
) -> None:
    """Resolve, present, and optionally execute one harness route."""
    try:
        config, _ = _load_launcher_config(config_path, secrets_path)
        resolved = resolve_route(
            config=config,
            harness=harness,
            model=model,
            route=route_name,
            permission=_permission(safe=safe, bypass=bypass),
        )
        invocation = build_invocation(
            config=config,
            route=resolved,
            passthrough=passthrough,
            secret_resolver=get_secret,
        )
    except Exception as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(2) from exc

    effective_quiet = quiet or bool(config.code and config.code.presentation.quiet)
    _start_summary(invocation, quiet=effective_quiet)
    if dry_run or verbose or bool(config.code and config.code.presentation.verbose):
        console.print(json.dumps(invocation.redacted(), indent=2))
    if dry_run:
        return

    return_code, elapsed = run_foreground(invocation=invocation)
    _end_summary(
        route=resolved,
        return_code=return_code,
        elapsed=elapsed,
        quiet=effective_quiet,
    )
    if return_code != 0:
        raise typer.Exit(128 - return_code if return_code < 0 else return_code)


def _harness_command(
    *,
    ctx: typer.Context,
    harness: Harness,
    model: str | None,
    route: str | None,
    safe: bool,
    bypass: bool,
    config: Path | None,
    secrets: Path | None,
    quiet: bool,
    verbose: bool,
    dry_run: bool,
) -> None:
    """Shared implementation for top-level harness commands."""
    passthrough = list(ctx.args)
    if model is not None and model.startswith("-"):
        # Click assigns the first token after ``--`` to the optional MODEL
        # positional when MODEL was omitted. Restore that token to passthrough.
        passthrough.insert(0, model)
        model = None
    _launch(
        harness=harness,
        model=model,
        route_name=route,
        safe=safe,
        bypass=bypass,
        config_path=config,
        secrets_path=secrets,
        quiet=quiet,
        verbose=verbose,
        dry_run=dry_run,
        passthrough=tuple(passthrough),
    )


def claude_command(
    ctx: typer.Context,
    model: Annotated[
        str | None,
        typer.Argument(help="Configured model shortcut or full id."),
    ] = None,
    route: Annotated[
        str | None,
        typer.Option("--route", help="Explicit compatible route name."),
    ] = None,
    safe: Annotated[
        bool, typer.Option("--safe", help="Use normal permissions.")
    ] = False,
    bypass: Annotated[
        bool,
        typer.Option("--bypass", help="Bypass Claude permission checks."),
    ] = False,
    config: ConfigOption = None,
    secrets: SecretsOption = None,
    quiet: Annotated[
        bool,
        typer.Option("--quiet", help="Suppress decorative lifecycle summaries."),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", help="Show the redacted resolved invocation."),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Validate and display without launching."),
    ] = False,
) -> None:
    """Launch Claude Code; arguments after -- are passed through in order.

    Setup: https://onetool.beycom.online/learn/code-routing/
    """
    _harness_command(
        ctx=ctx,
        harness="claude",
        model=model,
        route=route,
        safe=safe,
        bypass=bypass,
        config=config,
        secrets=secrets,
        quiet=quiet,
        verbose=verbose,
        dry_run=dry_run,
    )


def codex_command(
    ctx: typer.Context,
    model: Annotated[
        str | None,
        typer.Argument(help="Configured model shortcut or full id."),
    ] = None,
    route: Annotated[
        str | None,
        typer.Option("--route", help="Explicit compatible route name."),
    ] = None,
    safe: Annotated[
        bool, typer.Option("--safe", help="Use normal permissions.")
    ] = False,
    bypass: Annotated[
        bool,
        typer.Option("--bypass", help="Bypass Codex approvals and sandbox."),
    ] = False,
    config: ConfigOption = None,
    secrets: SecretsOption = None,
    quiet: Annotated[
        bool,
        typer.Option("--quiet", help="Suppress decorative lifecycle summaries."),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", help="Show the redacted resolved invocation."),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Validate and display without launching."),
    ] = False,
) -> None:
    """Launch Codex; arguments after -- are passed through in order.

    Setup: https://onetool.beycom.online/learn/code-routing/
    """
    _harness_command(
        ctx=ctx,
        harness="codex",
        model=model,
        route=route,
        safe=safe,
        bypass=bypass,
        config=config,
        secrets=secrets,
        quiet=quiet,
        verbose=verbose,
        dry_run=dry_run,
    )


def _picker(
    *,
    config_path: Path | None,
    secrets_path: Path | None,
) -> None:
    """Run the interactive picker through the same resolver and launcher."""
    if not os.isatty(0):
        raise ValueError(
            "Interactive selection requires a terminal. Use "
            "`onetool claude [MODEL] --route ROUTE` or "
            "`onetool codex [MODEL] --route ROUTE`."
        )
    config, _ = _load_launcher_config(config_path, secrets_path)
    code = config.code
    if code is None:
        raise ValueError("Code routing is not configured")
    harness = questionary.select("Harness", choices=["claude", "codex"]).ask()
    if harness is None:
        return
    routes = [
        name
        for name, route in code.routes.items()
        if route.harness == harness and route.enabled
    ]
    route_name = questionary.select("Route", choices=routes).ask()
    if route_name is None:
        return
    route_config = code.routes[route_name]
    models = [
        shortcut
        for shortcut, model in config.models.items()
        if model.source == route_config.source and harness in model.harnesses
    ]
    model = questionary.select("Model", choices=models).ask()
    if model is None:
        return
    permission = questionary.select(
        "Permission",
        choices=["safe", "bypass"],
        default=code.defaults.permission,
    ).ask()
    if permission is None:
        return
    _launch(
        harness=harness,
        model=model,
        route_name=route_name,
        safe=permission == "safe",
        bypass=permission == "bypass",
        config_path=config_path,
        secrets_path=secrets_path,
        quiet=False,
        verbose=False,
        dry_run=False,
        passthrough=(),
    )


@code_app.callback()
def code_callback(
    ctx: typer.Context,
    config: ConfigOption = None,
    secrets: SecretsOption = None,
) -> None:
    """Select a code harness route or run a diagnostic subcommand."""
    if ctx.invoked_subcommand is not None:
        return
    try:
        _picker(config_path=config, secrets_path=secrets)
    except Exception as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(2) from exc


@code_app.command("setup")
def setup_command(
    config: Annotated[
        Path,
        typer.Option(
            "--config",
            "-c",
            help="Existing onetool.yaml whose directory receives the template.",
        ),
    ],
    output: Annotated[
        Path | None,
        typer.Option("--output", help="Optional output path."),
    ] = None,
) -> None:
    """Materialize the packaged routing configuration template."""
    if not config.is_file():
        console.print(f"[red]Error:[/red] Config file not found: {config}")
        raise typer.Exit(2)
    target = output or config.parent / "code-routing.yaml"
    if target.exists():
        console.print(
            f"[red]Error:[/red] Refusing to overwrite existing file: {target}"
        )
        raise typer.Exit(2)
    template = (
        files("ot.config.global_templates")
        .joinpath("code-routing.yaml")
        .read_text(encoding="utf-8")
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(template, encoding="utf-8")
    console.print(f"[green]Created:[/green] {target}")
    console.print(
        f"Add `{target.name}` to the `include` list in {config}, then review every "
        "route and named secret."
    )


@code_app.command("models")
def models_command(config: ConfigOption = None) -> None:
    """List configured model identities and compatibility."""
    try:
        loaded, _ = _load_launcher_config(config, None)
    except Exception as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(2) from exc
    table = Table(title="Configured code models")
    for column in ("Shortcut", "Model", "Source", "Harnesses", "Context"):
        table.add_column(column)
    for shortcut, model in loaded.models.items():
        table.add_row(
            shortcut,
            model.id,
            model.source,
            ", ".join(sorted(model.harnesses)),
            f"{model.context_window:,}",
        )
    console.print(table)


@code_app.command("config")
def config_command(config: ConfigOption = None) -> None:
    """Show effective launcher configuration without secret values."""
    try:
        loaded, resolved = _load_launcher_config(config, None)
    except Exception as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(2) from exc
    payload = {
        "path": str(resolved),
        "models": {
            name: model.model_dump(mode="json") for name, model in loaded.models.items()
        },
        "code": loaded.code.model_dump(mode="json") if loaded.code else None,
    }
    console.print(json.dumps(payload, indent=2))


@code_app.command("status")
def status_command(
    config: ConfigOption = None,
    secrets: SecretsOption = None,
) -> None:
    """Report configured route prerequisites without credential values."""
    try:
        loaded, resolved = _load_launcher_config(config, secrets)
    except Exception as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(2) from exc
    console.print(f"Config: {resolved}")
    if loaded.code is None:
        console.print("Code routing: not configured")
        return
    for name in ("claude", "codex", "cliproxy"):
        client = getattr(loaded.code.clients, name)
        if client is None:
            console.print(f"{name}: not configured")
            continue
        try:
            resolve_client_executable(client.executable)
        except ValueError:
            available = False
        else:
            available = True
        console.print(f"{name}: {'available' if available else 'missing'}")
    if loaded.code.cliproxy is not None:
        console.print(
            f"CLIProxyAPI inference endpoint: configured "
            f"({loaded.code.cliproxy.base_url})"
        )
        secret_name = loaded.code.cliproxy.secret_name
        console.print(
            f"{secret_name}: {'configured' if get_secret(secret_name) else 'missing'}"
        )
    for name, route in loaded.code.routes.items():
        console.print(
            f"{name}: {'enabled' if route.enabled else 'disabled'} "
            f"({route.harness}/{route.source}/{route.transport})"
        )
        if route.settings_path is not None:
            settings = loaded._resolve_onetool_relative_path(route.settings_path)
            console.print(
                f"  settings: {'available' if settings.is_file() else 'missing'}"
            )
        if route.profile is not None:
            codex = loaded.code.clients.codex
            home = (
                loaded._resolve_onetool_relative_path(codex.home_path)
                if codex is not None and codex.home_path is not None
                else expand_path(os.environ.get("CODEX_HOME", "~/.codex"))
            )
            profile = home / f"{route.profile}.config.toml"
            console.print(
                f"  profile {route.profile}: "
                f"{'available' if profile.is_file() else 'missing'}"
            )
        if route.model_catalog_path is not None:
            catalog = loaded._resolve_onetool_relative_path(
                route.model_catalog_path
            )
            console.print(
                f"  model catalog: {'available' if catalog.is_file() else 'missing'}"
            )


@code_app.command("doctor")
def doctor_command(
    config: ConfigOption = None,
    secrets: SecretsOption = None,
) -> None:
    """Validate binaries, paths, capabilities, environments, and live proxy models."""
    try:
        loaded, _ = _load_launcher_config(config, secrets)
        if loaded.code is None:
            raise ValueError("Code routing is not configured")
        failures = 0
        for client_name in ("claude", "codex", "cliproxy"):
            client = getattr(loaded.code.clients, client_name)
            if client is None:
                continue
            try:
                installed = check_client_version(
                    executable=client.executable,
                    configured=client.version,
                )
                constraint = client.version or "none (capability checked)"
                console.print(
                    f"[green]✓[/green] {client_name} {installed}; "
                    f"configured constraint: {constraint}"
                )
            except Exception as exc:
                failures += 1
                console.print(f"[red]✗[/red] {client_name}: {exc}")
        for name, candidate in loaded.code.routes.items():
            if not candidate.enabled:
                continue
            try:
                route = resolve_route(
                    config=loaded,
                    harness=candidate.harness,
                    model=candidate.model,
                    route=name,
                    permission="safe",
                )
                build_invocation(
                    config=loaded,
                    route=route,
                    passthrough=(),
                    secret_resolver=get_secret,
                )
                capabilities = required_route_capabilities(
                    harness=candidate.harness,
                    route=candidate,
                    permission="safe",
                )
                console.print(
                    f"[green]✓[/green] {name}; required capabilities: "
                    f"{', '.join(capabilities)}"
                )
            except Exception as exc:
                failures += 1
                console.print(f"[red]✗[/red] {name}: {exc}")
        if failures:
            raise typer.Exit(1)
    except typer.Exit:
        raise
    except Exception as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(2) from exc


@code_app.command("login")
def login_command(
    client_name: Annotated[
        str,
        typer.Argument(help="External owner: claude, codex, or cliproxy."),
    ],
    config: ConfigOption = None,
) -> None:
    """Delegate login to a capability-verified external client."""
    try:
        loaded, _ = _load_launcher_config(config, None)
        if loaded.code is None:
            raise ValueError("Code routing is not configured")
        client = getattr(loaded.code.clients, client_name, None)
        if client_name not in {"claude", "codex", "cliproxy"} or client is None:
            raise ValueError(f"Unsupported or unconfigured login client: {client_name}")
        executable = resolve_client_executable(client.executable)
        help_output = run_capability_command((executable, "--help"))
        argv: tuple[str, ...]
        if client_name == "claude":
            if "auth" not in help_output:
                raise ValueError("Configured Claude client lacks auth login support")
            argv = (executable, "auth", "login")
        elif client_name == "codex":
            if "login" not in help_output:
                raise ValueError("Configured Codex client lacks login support")
            argv = (executable, "login")
        else:
            if "-config" not in help_output or "-codex-login" not in help_output:
                raise ValueError(
                    "Configured CLIProxyAPI client lacks delegated Codex login support"
                )
            config_path = getattr(client, "config_path", None)
            if config_path is None:
                raise ValueError(
                    "code.clients.cliproxy.config_path must name a user-owned file"
                )
            resolved_config_path = loaded._resolve_onetool_relative_path(config_path)
            if not resolved_config_path.is_file():
                raise ValueError(
                    "code.clients.cliproxy.config_path must name a user-owned file"
                )
            argv = (
                executable,
                "-config",
                str(resolved_config_path),
                "-codex-login",
            )
        result = subprocess.run(argv, check=False, shell=False)
    except Exception as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(2) from exc
    if result.returncode != 0:
        raise typer.Exit(result.returncode)


__all__ = ["claude_command", "code_app", "codex_command", "resolve_code_config_path"]
