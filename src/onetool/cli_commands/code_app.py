"""CLIProxyAPI selection, diagnostics, and official harness launch commands."""

from __future__ import annotations

import shlex
import sys
from typing import TYPE_CHECKING, Annotated, cast

import questionary
import typer
from rich.console import Console
from typer.core import TyperCommand

from onetool.code.adapters import (
    BASE_URL_ENV,
    INFERENCE_KEY_ENV,
    build_invocation,
    connection_from_environment,
    replace_process,
)
from onetool.code.diagnostics import collect_code_status, open_management_url
from onetool.code.domain import Harness
from onetool.code.proxy import DiscoveredModel, ModelDiscovery
from onetool.code.selection import parse_context, resolve_model_query

if TYPE_CHECKING:
    from typer._click.core import Context as TyperContext

console = Console(stderr=True, highlight=False)
_PASSTHROUGH_META_KEY = "onetool_harness_passthrough"


class HarnessPassthroughCommand(TyperCommand):
    """Consume launcher options and MODEL, preserving every later token."""

    def parse_args(self, ctx: TyperContext, args: list[str]) -> list[str]:
        """Hide the opaque tail from Click while retaining its exact tokens."""
        model_index = self._model_index(args)
        ctx.meta[_PASSTHROUGH_META_KEY] = (
            tuple(args[model_index + 1 :]) if model_index is not None else ()
        )
        if model_index is not None:
            args = args[: model_index + 1]
        return super().parse_args(ctx, args)

    @staticmethod
    def _model_index(args: list[str]) -> int | None:
        index = 0
        while index < len(args):
            token = args[index]
            if token in {"--help", "-h"}:
                return None
            if token == "--":
                return index + 1 if index + 1 < len(args) else None
            if token == "--context":
                index += 2
                continue
            if token.startswith("--context="):
                index += 1
                continue
            if token.startswith("-"):
                return None
            return index
        return None


code_app = typer.Typer(
    name="code",
    help="Launch official coding harnesses through CLIProxyAPI.",
    no_args_is_help=False,
    invoke_without_command=True,
)


def _launch(
    *,
    harness: Harness,
    model: str,
    context_window: int | None,
    arguments: tuple[str, ...],
    connection: tuple[str, str] | None = None,
    inventory: tuple[str, ...] | None = None,
) -> None:
    """Build and replace the current process with one official harness."""
    proxy_origin, credential = connection or connection_from_environment()
    available = inventory
    if available is None:
        available = tuple(
            model.id
            for model in ModelDiscovery(
                proxy_origin=proxy_origin,
                credential=credential,
            ).models()
        )
    resolved_model = resolve_model_query(query=model, models=available)
    invocation = build_invocation(
        harness=harness,
        model=resolved_model,
        proxy_origin=proxy_origin,
        credential=credential,
        context_window=context_window,
        arguments=arguments,
    )
    if harness == "codex":
        console.print(f"Resolved proxy model: {resolved_model}", markup=False)
        console.print(
            "Codex /model shows Codex's native catalog. Change proxy models through "
            "'onetool code'.",
            markup=False,
        )
        console.print(
            "Session scope: this proxy model/provider applies to new, resumed, and "
            "forked sessions in this Codex process. Use plain 'codex' to preserve a "
            "saved session's native model.",
            markup=False,
        )
        console.print(
            "MCP startup: if Codex reports interrupted servers, wait for refresh and "
            "use '/mcp' to verify the final state.",
            markup=False,
        )
    replace_process(invocation=invocation)


def _run_harness(
    *,
    ctx: typer.Context,
    harness: Harness,
    model: str,
    context: str,
) -> None:
    """Forward the captured tail or report a safe launcher error."""
    arguments = tuple(ctx.meta.get(_PASSTHROUGH_META_KEY, ()))
    try:
        _launch(
            harness=harness,
            model=model,
            context_window=parse_context(context),
            arguments=arguments,
        )
    except Exception as exc:
        console.print(f"Error: {exc}", markup=False)
        raise typer.Exit(2) from exc


def _stdin_is_tty() -> bool:
    """Return whether interactive selection can safely read stdin."""
    return sys.stdin.isatty()


def _ask_context(*, harness: Harness) -> str | None:
    choices = [
        questionary.Choice("Auto", value="auto"),
        questionary.Choice("200k", value="200k"),
        questionary.Choice("1m", value="1m"),
    ]
    if harness == "codex":
        choices.append(questionary.Choice("Custom", value="custom"))
    selected = questionary.select("Context", choices=choices).ask()
    if selected is None:
        return None
    if selected != "custom":
        return cast("str", selected)
    return cast(
        "str | None",
        questionary.text("Context tokens", validate=lambda value: bool(value)).ask(),
    )


def _reusable_command(*, harness: Harness, model: str, context: str) -> str:
    """Return the shell-safe public command for an interactive selection."""
    return shlex.join(("onetool", "code", harness, "--context", context, "--", model))


def _format_model_inventory(models: tuple[DiscoveredModel, ...]) -> tuple[str, ...]:
    """Return a stable plain-text model and provider table."""
    model_width = max((len(model.id) for model in models), default=0)
    model_width = max(model_width, len("MODEL"))
    rows = [f"{'MODEL':<{model_width}}  PROVIDER"]
    rows.extend(
        f"{model.id:<{model_width}}  {model.provider or '-'}" for model in models
    )
    return tuple(rows)


def _print_model_inventory(models: tuple[DiscoveredModel, ...]) -> None:
    """Print model inventory without Rich markup interpretation."""
    for row in _format_model_inventory(models):
        console.print(row, markup=False)


def _interactive_launch() -> None:
    """Select one harness, live model, and explicit context before launching."""
    connection = connection_from_environment()
    discovered_models = ModelDiscovery(
        proxy_origin=connection[0],
        credential=connection[1],
    ).models()
    inventory = tuple(model.id for model in discovered_models)
    harness_value = questionary.select(
        "Harness",
        choices=[
            questionary.Choice("Claude", value="claude"),
            questionary.Choice("Codex", value="codex"),
        ],
    ).ask()
    if harness_value is None:
        return
    harness = cast("Harness", harness_value)
    model_choices: list[str] = sorted(inventory, key=str.casefold)
    model_value = questionary.select(
        "Model",
        choices=model_choices,
    ).ask()
    if model_value is None:
        return
    context = _ask_context(harness=harness)
    if context is None:
        return
    model = cast("str", model_value)
    context = context.strip()
    context_window = parse_context(context)
    console.print(
        f"Next time: {_reusable_command(harness=harness, model=model, context=context)}",
        markup=False,
    )
    _launch(
        harness=harness,
        model=model,
        context_window=context_window,
        arguments=(),
        connection=connection,
        inventory=inventory,
    )


@code_app.callback()
def code_callback(ctx: typer.Context) -> None:
    """Select a coding harness interactively when no subcommand is supplied."""
    if ctx.invoked_subcommand is not None:
        return
    if not _stdin_is_tty():
        console.print(
            "Error: bare 'onetool code' requires an interactive terminal",
            markup=False,
        )
        raise typer.Exit(2)
    try:
        _interactive_launch()
    except Exception as exc:
        console.print(f"Error: {exc}", markup=False)
        raise typer.Exit(2) from exc


@code_app.command("claude", cls=HarnessPassthroughCommand)
def claude_command(
    ctx: typer.Context,
    model: Annotated[
        str,
        typer.Argument(
            help=(
                "CLIProxyAPI model ID or unique partial query. Every later token is forwarded "
                "verbatim. Connection: CLIPROXY_BASE_URL; credential: "
                "CLIPROXY_INFERENCE_KEY."
            )
        ),
    ],
    context: Annotated[
        str,
        typer.Option(
            "--context",
            help="Explicit context: auto, 200k, or 1m. Must precede MODEL.",
        ),
    ] = "auto",
) -> None:
    """Launch Claude Code with a live model match and verbatim harness arguments."""
    _run_harness(ctx=ctx, harness="claude", model=model, context=context)


@code_app.command("codex", cls=HarnessPassthroughCommand)
def codex_command(
    ctx: typer.Context,
    model: Annotated[
        str,
        typer.Argument(
            help=(
                "CLIProxyAPI model ID or unique partial query. Every later token is forwarded "
                "verbatim. Connection: CLIPROXY_BASE_URL; credential: "
                "CLIPROXY_INFERENCE_KEY."
            )
        ),
    ],
    context: Annotated[
        str,
        typer.Option(
            "--context",
            help="Explicit context: auto, 200k, 1m, or positive tokens. Must precede MODEL.",
        ),
    ] = "auto",
) -> None:
    """Launch Codex with a live model match and verbatim harness arguments."""
    _run_harness(ctx=ctx, harness="codex", model=model, context=context)


@code_app.command("models")
def models_command() -> None:
    """List direct model IDs and providers from one bounded inventory request."""
    try:
        proxy_origin, credential = connection_from_environment()
        models = ModelDiscovery(
            proxy_origin=proxy_origin,
            credential=credential,
        ).models()
    except Exception as exc:
        console.print(f"Error: {exc}", markup=False)
        raise typer.Exit(2) from exc
    _print_model_inventory(models)


@code_app.command("status")
def status_command(
    open_page: Annotated[
        bool,
        typer.Option(
            "--open",
            help="Open the derived CLIProxyAPI management page after diagnostics.",
        ),
    ] = False,
) -> None:
    """Show redacted launcher readiness, models, and management access."""
    status = collect_code_status()
    console.print("OneTool code status", style="bold")
    if status.proxy_origin is None:
        console.print(f"Proxy origin: ERROR ({status.origin_error})", markup=False)
    else:
        console.print(
            f"Proxy origin: {status.proxy_origin} ({status.origin_source})",
            markup=False,
        )
    console.print(
        "Inference credential: set"
        if status.credential_present
        else "Inference credential: missing",
        markup=False,
    )
    if status.inventory_error is None:
        console.print("Inference endpoint: reachable (authenticated)", markup=False)
        console.print(f"Models: {len(status.models)} available", markup=False)
        _print_model_inventory(status.models)
    else:
        console.print(
            f"Inference endpoint: ERROR ({status.inventory_error})",
            markup=False,
        )
        console.print("Models: unavailable", markup=False)
    if status.management_url is not None:
        page_state = (
            "reachable"
            if status.management_reachable
            else f"warning: {status.management_error}"
        )
        console.print(
            f"Management: {status.management_url} ({page_state})",
            markup=False,
        )
    else:
        console.print("Management: unavailable", markup=False)
    for executable in status.executables:
        if executable.error is not None:
            console.print(
                f"{executable.name}: warning ({executable.error})",
                markup=False,
            )
        else:
            console.print(
                f"{executable.name}: {executable.path} ({executable.version})",
                markup=False,
            )
    if open_page and (
        status.management_url is None or not open_management_url(status.management_url)
    ):
        console.print("Management browser: warning (open failed)", markup=False)
    if not status.ready:
        raise typer.Exit(2)


__all__ = [
    "BASE_URL_ENV",
    "INFERENCE_KEY_ENV",
    "HarnessPassthroughCommand",
    "claude_command",
    "code_app",
    "code_callback",
    "codex_command",
    "models_command",
    "status_command",
]
