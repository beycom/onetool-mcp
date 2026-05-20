"""Command-line interface for ot-harness."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Annotated

import typer

from ot._cli import console, create_cli, version_callback
from ot_harness import __version__
from ot_harness.config import ConfigError, load_experiment
from ot_harness.harbor import build_trials, write_trial_config
from ot_harness.results import (
    aggregate_by_variant,
    discover_results,
    render_markdown_report,
)

app = create_cli(
    "ot-harness", "Harbor-backed Codex benchmark harness.", no_args_is_help=True
)


@app.callback()
def main(
    version: bool | None = typer.Option(
        None,
        "--version",
        "-v",
        callback=version_callback("ot-harness", __version__),
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """Harbor-backed Codex benchmark harness."""


@app.command()
def validate(
    experiment: Annotated[Path, typer.Argument(help="Path to experiment YAML.")],
) -> None:
    """Validate an experiment config and all referenced files."""
    try:
        config = load_experiment(experiment)
    except ConfigError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc
    console.print(
        f"[green]Validated[/green] {config.name}: "
        f"{len(config.tasks)} tasks, {len(config.variants)} variants, "
        f"{config.repetitions} repetition(s)"
    )


@app.command()
def run(
    experiment: Annotated[Path, typer.Argument(help="Path to experiment YAML.")],
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run", help="Generate Harbor configs without starting runs."
        ),
    ] = False,
) -> None:
    """Generate and execute Harbor runs for an experiment matrix."""
    try:
        config = load_experiment(experiment)
        trials = build_trials(config)
    except ConfigError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc

    for trial in trials:
        write_trial_config(trial)
        console.print(
            f"[green]Generated[/green] {trial.variant_id} {trial.task_id} "
            f"rep {trial.repetition}: {trial.config_path}"
        )
        if not dry_run:
            completed = subprocess.run(
                trial.command,
                cwd=trial.run_dir,
                check=False,
                text=True,
            )
            if completed.returncode != 0:
                raise typer.Exit(completed.returncode)

    console.print(
        f"[green]Complete[/green] {len(trials)} Harbor trial config(s) under {config.output_root}"
    )


@app.command()
def report(
    run_output_dir: Annotated[Path, typer.Argument(help="Run output directory.")],
    output_json: Annotated[
        bool,
        typer.Option("--json", help="Emit aggregate data as JSON."),
    ] = False,
) -> None:
    """Parse Harbor outputs and emit a concise per-variant report."""
    results = discover_results(run_output_dir)
    if output_json:
        console.print(json.dumps(aggregate_by_variant(results), indent=2))
    else:
        console.print(render_markdown_report(results))


def cli() -> None:
    """Run the ot-harness CLI."""
    app()
