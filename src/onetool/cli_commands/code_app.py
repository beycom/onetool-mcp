"""Claude Code and Codex proxy-launcher CLI commands."""

from __future__ import annotations

import json
import os
from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, cast

import questionary
import typer
from questionary import Choice
from rich.console import Console
from rich.panel import Panel
from typer.core import TyperCommand

from onetool.code.adapters import (
    build_invocation,
    check_client_capabilities,
    replace_process,
    resolve_client_executable,
)
from onetool.code.domain import LaunchInvocation, ResolvedTarget
from onetool.code.proxy import ModelDiscovery
from onetool.code.resolver import (
    compatible_models,
    compatible_routes,
    configured_harnesses,
    resolve_target,
)
from ot.config.loader import load_config
from ot.config.routing import Harness, ModelSource, PermissionMode
from ot.config.secrets import get_secret
from ot.paths import expand_path

if TYPE_CHECKING:
    from typer._click.core import Context as TyperContext

    from ot.config.models import OneToolConfig

console = Console(stderr=True, highlight=False)
_PASSTHROUGH_META_KEY = "onetool_harness_passthrough"
_HARNESSES: tuple[Harness, ...] = ("claude", "codex")


class HarnessPassthroughCommand(TyperCommand):
    """Preserve the exact argument tail after the first `--` delimiter."""

    def parse_args(self, ctx: TyperContext, args: list[str]) -> list[str]:
        """Remove the opaque tail before Click parses the optional model."""
        if "--" in args:
            boundary = args.index("--")
            ctx.meta[_PASSTHROUGH_META_KEY] = tuple(args[boundary + 1 :])
            args = args[:boundary]
        else:
            ctx.meta[_PASSTHROUGH_META_KEY] = ()
        return super().parse_args(ctx, args)


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
        "Run `onetool init` to install the code-routing template."
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


def _print_warning(target: ResolvedTarget) -> None:
    """Print target notices that quiet mode must not suppress."""
    if target.warning is not None:
        console.print(f"[bold yellow]Warning:[/bold yellow] {target.warning}")


def _start_summary(invocation: LaunchInvocation, *, quiet: bool) -> None:
    """Render a polished or concise pre-launch summary."""
    _print_warning(invocation.target)
    if quiet:
        return
    target = invocation.target
    model = (
        f"{target.model.label} ({target.model.id})"
        if target.model.label is not None
        else target.model.id
    )
    lines = [
        f"Harness: {target.harness}",
        f"Model: {model}",
        f"{target.kind.title()}: {target.name}",
        f"Permission: {target.permission}",
    ]
    if console.is_terminal:
        console.print(
            Panel(
                "\n".join(lines),
                title=f"Starting {target.harness.title()}",
                border_style="cyan",
            )
        )
    else:
        console.print(
            "Starting "
            + target.harness
            + ": "
            + ", ".join(line.lower() for line in lines[1:])
        )


def _choose_model(
    *,
    config: OneToolConfig,
    harness: Harness,
    route: ModelSource | None,
    profile: str | None,
) -> tuple[str, ModelSource | None, str | None] | None:
    """Interactively select one exact configured target and model."""
    candidates = compatible_models(
        config=config,
        harness=harness,
        route=route,
        profile=profile,
    )
    selected_index = questionary.select(
        "Model",
        choices=[
            Choice(
                f"{model.label or model.id} [{kind}: {target}]",
                value=index,
            )
            for index, (kind, target, model) in enumerate(candidates)
        ],
    ).ask()
    if selected_index is None:
        return None
    kind, target, selected_model = candidates[selected_index]
    if kind == "route":
        return selected_model.id, cast("ModelSource", target), None
    return selected_model.id, None, target


def _launch(
    *,
    harness: Harness,
    model: str | None,
    route_name: ModelSource | None,
    profile_name: str | None,
    permission: PermissionMode | None,
    config_path: Path | None,
    secrets_path: Path | None,
    quiet: bool,
    verbose: bool,
    dry_run: bool,
    passthrough: tuple[str, ...],
) -> None:
    """Resolve, present, and optionally replace with one harness."""
    try:
        config, _ = _load_launcher_config(config_path, secrets_path)
        if (
            model is None
            and config.code is not None
            and config.code.default is None
            and os.isatty(0)
        ):
            selected = _choose_model(
                config=config,
                harness=harness,
                route=route_name,
                profile=profile_name,
            )
            if selected is None:
                return
            model, route_name, profile_name = selected
        resolved = resolve_target(
            config=config,
            harness=harness,
            model=model,
            route=route_name,
            profile=profile_name,
            permission=permission,
        )
        invocation = build_invocation(
            config=config,
            target=resolved,
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

    replace_process(invocation=invocation)


def _harness_command(
    *,
    ctx: typer.Context,
    harness: Harness,
    model: str | None,
    route: ModelSource | None,
    profile: str | None,
    permission: PermissionMode | None,
    config: Path | None,
    secrets: Path | None,
    quiet: bool,
    verbose: bool,
    dry_run: bool,
) -> None:
    """Shared implementation for top-level harness commands."""
    passthrough = tuple(ctx.meta.get(_PASSTHROUGH_META_KEY, ()))
    _launch(
        harness=harness,
        model=model,
        route_name=route,
        profile_name=profile,
        permission=permission,
        config_path=config,
        secrets_path=secrets,
        quiet=quiet,
        verbose=verbose,
        dry_run=dry_run,
        passthrough=passthrough,
    )


def claude_command(
    ctx: typer.Context,
    model: Annotated[
        str | None,
        typer.Argument(help="Exact configured model id or shortcut."),
    ] = None,
    route: Annotated[
        ModelSource | None,
        typer.Option("--route", help="Exact canonical route."),
    ] = None,
    permission: Annotated[
        PermissionMode | None,
        typer.Option("--permission", help="Permission mode: normal or bypass."),
    ] = None,
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
    """Launch Claude Code; arguments after -- pass through unchanged."""
    _harness_command(
        ctx=ctx,
        harness="claude",
        model=model,
        route=route,
        profile=None,
        permission=permission,
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
        typer.Argument(help="Exact configured model id or shortcut."),
    ] = None,
    route: Annotated[
        ModelSource | None,
        typer.Option("--route", help="Exact canonical route."),
    ] = None,
    profile: Annotated[
        str | None,
        typer.Option("--profile", "-p", help="Exact direct Codex profile."),
    ] = None,
    permission: Annotated[
        PermissionMode | None,
        typer.Option("--permission", help="Permission mode: normal or bypass."),
    ] = None,
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
    """Launch Codex; arguments after -- pass through unchanged."""
    _harness_command(
        ctx=ctx,
        harness="codex",
        model=model,
        route=route,
        profile=profile,
        permission=permission,
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
    """Run the interactive picker through the shared resolver."""
    if not os.isatty(0):
        raise ValueError(
            "Interactive selection requires a terminal. Use "
            "`onetool claude [MODEL]` or `onetool codex [MODEL]`."
        )
    config, _ = _load_launcher_config(config_path, secrets_path)
    harness = questionary.select(
        "Harness",
        choices=list(configured_harnesses(config)),
    ).ask()
    if harness is None:
        return
    selected = _choose_model(
        config=config,
        harness=harness,
        route=None,
        profile=None,
    )
    if selected is None:
        return
    model, route, profile = selected
    default_permission = config.code.permission if config.code is not None else "normal"
    permission = questionary.select(
        "Permission",
        choices=["normal", "bypass"],
        default=default_permission,
    ).ask()
    if permission is None:
        return
    _launch(
        harness=harness,
        model=model,
        route_name=route,
        profile_name=profile,
        permission=permission,
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


@code_app.command("models")
def models_command(config: ConfigOption = None) -> None:
    """List configured launcher model identities and compatibility."""
    try:
        loaded, _ = _load_launcher_config(config, None)
        if loaded.code is None:
            raise ValueError("Code routing is not configured")
    except Exception as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(2) from exc
    console.print("Configured code models")
    if loaded.code.proxy is not None:
        for route, models in loaded.code.proxy.routes.items():
            harnesses = [
                harness
                for harness in _HARNESSES
                if route in compatible_routes(harness)
            ]
            for model in models:
                policy = model.claude.model_dump(mode="json") if model.claude else None
                console.print(
                    "\n".join(
                        (
                            model.id,
                            f"  route: {route}",
                            f"  harnesses: {', '.join(harnesses)}",
                            f"  shortcut: {model.shortcut or '—'}",
                            f"  label: {model.label or '—'}",
                            f"  claude: {json.dumps(policy) if policy else '—'}",
                        )
                    ),
                    markup=False,
                )
    if loaded.code.direct is not None:
        for profile, models in loaded.code.direct.codex.profiles.items():
            for model in models:
                console.print(
                    "\n".join(
                        (
                            model.id,
                            f"  profile: {profile}",
                            "  harnesses: codex",
                            f"  shortcut: {model.shortcut or '—'}",
                            f"  label: {model.label or '—'}",
                        )
                    ),
                    markup=False,
                )


@code_app.command("config")
def config_command(config: ConfigOption = None) -> None:
    """Show effective launcher configuration without generation models."""
    try:
        loaded, resolved = _load_launcher_config(config, None)
    except Exception as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(2) from exc
    payload = {
        "path": str(resolved),
        "code": loaded.code.model_dump(mode="json") if loaded.code else None,
    }
    console.print(json.dumps(payload, indent=2))


@code_app.command("status")
def status_command(
    config: ConfigOption = None,
    secrets: SecretsOption = None,
) -> None:
    """Report local launcher prerequisites without network requests."""
    try:
        loaded, resolved = _load_launcher_config(config, secrets)
        if loaded.code is None:
            raise ValueError("Code routing is not configured")
    except Exception as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(2) from exc
    console.print(f"Config: {resolved}")
    for name in configured_harnesses(loaded):
        client = getattr(loaded.code.clients, name)
        try:
            resolve_client_executable(client.executable)
        except ValueError:
            available = False
        else:
            available = True
        console.print(f"{name}: {'available' if available else 'missing'}")
    proxy = loaded.code.proxy
    if proxy is not None:
        console.print(f"CLIProxyAPI inference endpoint: configured ({proxy.base_url})")
        console.print(
            f"{proxy.secret_name}: "
            f"{'configured' if get_secret(proxy.secret_name) else 'missing'}"
        )
        for route, models in proxy.routes.items():
            console.print(f"route {route}: {len(models)} model(s)")
    if loaded.code.direct is not None:
        for profile, models in loaded.code.direct.codex.profiles.items():
            console.print(f"profile {profile}: {len(models)} model(s)")


@code_app.command("doctor")
def doctor_command(
    config: ConfigOption = None,
    secrets: SecretsOption = None,
) -> None:
    """Check harness capabilities and one live proxy model inventory."""
    try:
        loaded, _ = _load_launcher_config(config, secrets)
        if loaded.code is None:
            raise ValueError("Code routing is not configured")
        failures = 0
        configured = configured_harnesses(loaded)
        proxy_routes = (
            loaded.code.proxy.routes if loaded.code.proxy is not None else {}
        )
        for harness in configured:
            client = getattr(loaded.code.clients, harness)
            try:
                executable = resolve_client_executable(client.executable)
                require_proxy = any(
                    route in compatible_routes(harness) for route in proxy_routes
                )
                require_profile = (
                    harness == "codex" and loaded.code.direct is not None
                )
                capabilities = check_client_capabilities(
                    executable=executable,
                    harness=harness,
                    permission=loaded.code.permission,
                    require_proxy=require_proxy,
                    require_profile=require_profile,
                )
                console.print(
                    f"[green]✓[/green] {harness}; capabilities: "
                    f"{', '.join(capabilities)}"
                )
            except Exception as exc:
                failures += 1
                console.print(f"[red]✗[/red] {harness}: {exc}")

        proxy = loaded.code.proxy
        if proxy is not None:
            secret = get_secret(proxy.secret_name)
            if not secret:
                failures += 1
                console.print(
                    f"[red]✗[/red] Named inference secret "
                    f"{proxy.secret_name!r} is not configured"
                )
            else:
                try:
                    advertised = ModelDiscovery(
                        config=proxy,
                        secret=secret,
                    ).models()
                    counts = Counter(advertised)
                    for route, models in proxy.routes.items():
                        for model in models:
                            if counts[model.id] == 1:
                                console.print(
                                    f"[green]✓[/green] {route}: {model.id}"
                                )
                            else:
                                failures += 1
                                state = (
                                    "not advertised"
                                    if counts[model.id] == 0
                                    else "duplicate"
                                )
                                console.print(
                                    f"[red]✗[/red] {route}: {model.id} ({state})"
                                )
                except Exception as exc:
                    failures += 1
                    console.print(f"[red]✗[/red] CLIProxyAPI: {exc}")
        if failures:
            raise typer.Exit(1)
    except typer.Exit:
        raise
    except Exception as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(2) from exc


__all__ = [
    "HarnessPassthroughCommand",
    "claude_command",
    "code_app",
    "codex_command",
    "resolve_code_config_path",
]
