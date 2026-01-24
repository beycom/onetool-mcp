"""Run command for running LLM benchmarks with MCP servers."""

from __future__ import annotations

import glob
import os
from pathlib import Path

import questionary
import typer
import yaml
from pydantic import BaseModel, Field
from rich.console import Console

from ot._tui import ask_select
from ot.logging import LogSpan, configure_logging
from ot.paths import get_effective_cwd, get_global_dir
from ot.support import get_support_banner, get_version
from ot_bench.cli import app
from ot_bench.harness.config import load_config
from ot_bench.harness.csv_writer import write_results_csv
from ot_bench.harness.runner import AgenticRunner
from ot_bench.reporter import ConsoleReporter
from ot_bench.utils import run_async

# Exit codes
EXIT_SUCCESS = 0
EXIT_RUNTIME_ERROR = 1
EXIT_CONFIG_ERROR = 2
EXIT_FILE_NOT_FOUND = 3


def _print_startup_banner(console: Console) -> None:
    """Print startup message."""
    version = get_version()
    console.print(f"[bold cyan]OneTool Benchmark[/bold cyan] [dim]v{version}[/dim]")
    console.print(get_support_banner())
    console.print()


class BenchFavorite(BaseModel):
    """A favorite benchmark entry."""

    name: str = Field(description="Display name in picker")
    path: str = Field(description="File path or directory")


class BenchConfig(BaseModel):
    """Configuration for ot-bench CLI."""

    favorites: list[BenchFavorite] = Field(
        default_factory=list, description="Favorite benchmarks"
    )


def load_bench_config(config_path: Path | str | None = None) -> BenchConfig:
    """Load ot-bench configuration from YAML file.

    Resolution order (when config_path is None):
    1. OT_BENCH_CONFIG env var
    2. cwd/.onetool/ot-bench.yaml
    3. ~/.onetool/ot-bench.yaml
    4. Built-in defaults
    """
    if config_path is None:
        # Check OT_BENCH_CONFIG env var first
        env_config = os.getenv("OT_BENCH_CONFIG")
        if env_config:
            config_path = Path(env_config)
        else:
            # Try project config: cwd/.onetool/ot-bench.yaml
            cwd = get_effective_cwd()
            project_config = cwd / ".onetool" / "ot-bench.yaml"
            if project_config.exists():
                config_path = project_config
            else:
                # Try global config: ~/.onetool/ot-bench.yaml
                global_config = get_global_dir() / "ot-bench.yaml"
                if global_config.exists():
                    config_path = global_config
                else:
                    # No config found, use defaults
                    return BenchConfig()
    else:
        config_path = Path(config_path)

    if not config_path.exists():
        return BenchConfig()

    with config_path.open() as f:
        raw_data = yaml.safe_load(f) or {}

    return BenchConfig.model_validate(raw_data)


def get_yaml_description(file_path: Path) -> str | None:
    """Extract description field from a YAML benchmark file."""
    try:
        with file_path.open() as f:
            data = yaml.safe_load(f)
        if isinstance(data, dict):
            return data.get("description")
    except Exception:
        pass
    return None


def scan_yaml_files(directory: Path) -> list[Path]:
    """Recursively scan directory for YAML files, excluding hidden directories."""
    files = []
    for path in directory.rglob("*"):
        # Skip hidden directories
        if any(part.startswith(".") for part in path.parts):
            continue
        if path.is_file() and path.suffix in (".yaml", ".yml"):
            files.append(path)
    return sorted(files)


def run_tui_picker(console: Console) -> list[Path] | None:
    """Run interactive TUI for selecting benchmark file(s).

    Returns:
        List of paths when a glob pattern matches multiple files.
        Single-item list for directory browsing or single file favorites.
        None if user cancels.
    """
    import asyncio

    bench_config = load_bench_config()

    if not bench_config.favorites:
        console.print("[dim]No favorites configured[/dim]")
        console.print("[dim]Add favorites to config/ot-bench.yaml[/dim]")
        return None

    async def pick_favorite() -> list[Path] | None:
        favorites = bench_config.favorites

        while True:
            # Build choices using indices to avoid questionary value issues
            choices = [
                questionary.Choice(fav.name, value=str(i))
                for i, fav in enumerate(favorites)
            ]
            choices.append(
                questionary.Choice("Exit", value="__exit__", shortcut_key="e")
            )

            selected = await ask_select("Select benchmark:", choices)
            if not selected or selected == "__exit__" or not selected.isdigit():
                return None

            fav = favorites[int(selected)]
            fav_path_str = fav.path

            # Check if path contains glob characters
            has_glob = any(c in fav_path_str for c in "*?[")

            if has_glob:
                # Expand glob pattern - return ALL matching files
                yaml_files = expand_glob_patterns([fav_path_str])
                if not yaml_files:
                    console.print(f"[dim]No files matched: {fav_path_str}[/dim]")
                    continue  # Go back to favorites picker

                # Return all matching files (don't prompt to pick one)
                return yaml_files

            fav_path = Path(fav_path_str)

            # If it's a file, return it directly (as a list)
            if fav_path.is_file():
                return [fav_path]

            # If it's a directory, scan for YAML files
            if fav_path.is_dir():
                yaml_files = scan_yaml_files(fav_path)
                if not yaml_files:
                    console.print(f"[dim]No YAML files found in {fav_path}[/dim]")
                    continue  # Go back to favorites picker

                # Build choices using indices
                file_choices = []
                for i, f in enumerate(yaml_files):
                    rel_path = f.relative_to(fav_path)
                    desc = get_yaml_description(f)
                    label = f"{rel_path}" + (f" - {desc}" if desc else "")
                    file_choices.append(questionary.Choice(label, value=str(i)))
                file_choices.append(
                    questionary.Choice("Back", value="__back__", shortcut_key="b")
                )

                file_selected = await ask_select("Select file:", file_choices)
                if (
                    not file_selected
                    or file_selected == "__back__"
                    or not file_selected.isdigit()
                ):
                    continue  # Go back to favorites picker
                return [yaml_files[int(file_selected)]]

            console.print(f"[red]Path not found: {fav_path}[/red]")
            continue  # Go back to favorites picker

    return asyncio.run(pick_favorite())


def expand_glob_patterns(patterns: list[str]) -> list[Path]:
    """Expand glob patterns to list of files, preserving order."""
    files: list[Path] = []
    seen: set[Path] = set()
    for pattern in patterns:
        # Try glob expansion first
        expanded = glob.glob(pattern)  # noqa: PTH207 - glob.glob handles string patterns directly
        if expanded:
            for f in sorted(expanded):
                path = Path(f)
                if path.is_file() and path not in seen:
                    files.append(path)
                    seen.add(path)
        else:
            # No glob match, treat as literal path
            path = Path(pattern)
            if path not in seen:
                files.append(path)
                seen.add(path)
    return files


def run_single_benchmark(
    config_file: Path,
    console: Console,
    scenario: str | None,
    task: str | None,
    tag: list[str] | None,
    dry_run: bool,
    verbose: bool,
    trace: bool,
    no_color: bool,
) -> tuple[list, bool]:
    """Run a single benchmark file.

    Returns:
        Tuple of (results, success) where:
        - results: List of ScenarioResult objects
        - success: True if completed without runtime errors or interrupts.
                   Test evaluation failures (PASS/FAIL) don't affect this.
    """
    with LogSpan(span="bench.config.load", path=str(config_file)) as span:
        try:
            config = load_config(config_file)
            span.add(scenarios=len(config.scenarios), servers=len(config.servers))
        except FileNotFoundError as e:
            span.add(error="file_not_found")
            console.print(f"[red]Error:[/red] {e}")
            return [], False
        except Exception as e:
            span.add(error=str(e))
            console.print(f"[red]Configuration error:[/red] {e}")
            return [], False

    console.print(f"Loaded config: {config_file}")
    console.print(f"  Scenarios: {len(config.scenarios)}")
    console.print(f"  Servers: {list(config.servers.keys())}")

    reporter = ConsoleReporter(
        console=console,
        config=config,
        verbose=verbose,
        trace=trace,
        no_color=no_color,
    )

    runner = AgenticRunner(
        config,
        dry_run=dry_run,
        verbose=verbose,
        on_progress=reporter.on_event,
    )

    interrupted = False
    try:
        results = run_async(
            runner.run_scenario(scenario_name=scenario, task_name=task, tags=tag)
        )
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
        results = runner.partial_results
        if results:
            task_count = sum(len(s.tasks) for s in results)
            console.print(f"[dim]Showing {task_count} completed task(s)[/dim]")
        interrupted = True
    except Exception as e:
        console.print(f"[red]Runtime error:[/red] {e}")
        return [], False

    # Output results for this file (even if interrupted)
    if results:
        reporter.print_results_header()
        for scenario_result in results:
            reporter.print_results_table(scenario_result)
        reporter.print_validation_errors()

    return results or [], not interrupted


@app.command()
def run(
    config_files: list[str] = typer.Argument(
        None,
        help="Path(s) to YAML config file(s). Supports glob patterns (e.g., *.yaml).",
    ),
    scenario: str | None = typer.Option(
        None,
        "--scenario",
        "-s",
        help="Run only scenarios matching this pattern (supports wildcards).",
    ),
    task: str | None = typer.Option(
        None,
        "--task",
        "-t",
        help="Run only tasks matching this pattern (supports wildcards: direct*, *:sha256:*).",
    ),
    tag: list[str] | None = typer.Option(
        None,
        "--tag",
        help="Run only tasks with the specified tag(s). Can be specified multiple times.",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Path to write results YAML file.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Validate config without making API calls.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose output with full content.",
    ),
    trace: bool = typer.Option(
        False,
        "--trace",
        help="Show timestamped request/response cycle for debugging timing.",
    ),
    no_color: bool = typer.Option(
        False,
        "--no-color",
        help="Disable colored output (for CI/CD compatibility).",
    ),
    tui: bool = typer.Option(
        False,
        "--tui",
        help="Interactive TUI mode for selecting from favorites.",
    ),
    csv: bool = typer.Option(
        False,
        "--csv",
        help="Write results to CSV file with per-call metrics breakdown.",
    ),
) -> None:
    """Run tasks (direct MCP calls or LLM benchmarks).

    Task types:
        type: direct  - Direct MCP tool invocation (no LLM)
        type: harness - LLM benchmark with MCP servers (default)

    Examples:
        ot-bench run config.yaml
        ot-bench run examples/bench/*.yaml
        ot-bench run file1.yaml file2.yaml
        ot-bench run config.yaml --scenario "Tool Tests"
        ot-bench run config.yaml --task "direct*"
        ot-bench run config.yaml --tag focus
        ot-bench run config.yaml --verbose --trace
        ot-bench run config.yaml --dry-run
        ot-bench run config.yaml --output results.yaml
        ot-bench run --tui
    """
    # Initialize console with no_color option and no auto-highlighting
    console = Console(no_color=no_color, force_terminal=not no_color, highlight=False)

    # Initialize logging inside command to avoid module-level side effects
    configure_logging(log_name="bench")

    # Print startup banner
    _print_startup_banner(console)

    # Handle TUI mode
    if tui:
        selected_files = run_tui_picker(console)
        if not selected_files:
            raise typer.Exit(EXIT_SUCCESS)
        files_to_run = selected_files
    elif not config_files:
        console.print(
            "[red]Error:[/red] Missing config file. Use --tui or provide a path."
        )
        raise typer.Exit(EXIT_CONFIG_ERROR)
    else:
        # Expand glob patterns
        files_to_run = expand_glob_patterns(config_files)
        if not files_to_run:
            console.print("[red]Error:[/red] No files matched the provided pattern(s).")
            raise typer.Exit(EXIT_FILE_NOT_FOUND)

    # Validate all files exist
    missing = [f for f in files_to_run if not f.exists()]
    if missing:
        for f in missing:
            console.print(f"[red]Error:[/red] File not found: {f}")
        raise typer.Exit(EXIT_FILE_NOT_FOUND)

    if dry_run:
        console.print("[yellow]Dry run mode - no API calls will be made[/yellow]")

    if len(files_to_run) > 1:
        console.print(f"[cyan]Running {len(files_to_run)} benchmark files[/cyan]\n")

    # Run each benchmark file
    # Note: runtime_error tracks exceptions/interrupts, NOT test evaluation failures.
    # Test failures (PASS/FAIL) don't affect exit code - only runtime errors do.
    all_results = []
    runtime_error = False

    for i, config_file in enumerate(files_to_run):
        if len(files_to_run) > 1:
            console.print(
                f"\n[bold cyan]═══ File {i + 1}/{len(files_to_run)}: {config_file} ═══[/bold cyan]\n"
            )

        results, success = run_single_benchmark(
            config_file=config_file,
            console=console,
            scenario=scenario,
            task=task,
            tag=tag,
            dry_run=dry_run,
            verbose=verbose,
            trace=trace,
            no_color=no_color,
        )
        all_results.extend(results)
        if not success:
            runtime_error = True

    if not all_results:
        console.print("[yellow]No results to report[/yellow]")
        raise typer.Exit(EXIT_SUCCESS if not runtime_error else EXIT_RUNTIME_ERROR)

    # Write aggregated results to file if specified
    if output:
        try:
            output_data = {"results": [r.to_dict() for r in all_results]}
            with output.open("w") as f:
                yaml.dump(output_data, f, default_flow_style=False, sort_keys=False)
            console.print(f"\nResults written to: {output}")
        except OSError as e:
            console.print(f"[red]Error writing results:[/red] {e}")
            raise typer.Exit(EXIT_RUNTIME_ERROR) from e

    # Write CSV with per-call metrics if requested
    if csv:
        try:
            csv_path = write_results_csv(all_results)
            console.print(f"CSV results written to: {csv_path}")
        except OSError as e:
            console.print(f"[red]Error writing CSV:[/red] {e}")
            raise typer.Exit(EXIT_RUNTIME_ERROR) from e

    # Exit 1 only for runtime errors (exceptions, config errors, interrupts)
    # Test evaluation failures (PASS/FAIL) exit 0 - they're not runtime errors
    if runtime_error:
        raise typer.Exit(EXIT_RUNTIME_ERROR)
