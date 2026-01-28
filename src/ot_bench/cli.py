"""Bench CLI entry point for OneTool benchmark harness."""

from __future__ import annotations

import typer

import ot
from ot._cli import create_cli, version_callback

app = create_cli(
    "ot-bench",
    "OneTool benchmark harness for benchmarking agent + MCP configurations.",
    no_args_is_help=True,
)


@app.callback()
def main(
    _version: bool | None = typer.Option(
        None,
        "--version",
        "-v",
        callback=version_callback("ot-bench", ot.__version__),
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """OneTool benchmark harness for benchmarking agent + MCP configurations.

    Commands:
        run     - Run tasks (direct MCP calls or agent benchmarks)

    Task types:
        type: direct  - Direct MCP tool invocation (no LLM)
        type: harness - LLM benchmark with MCP servers (default)

    External client testing:
        Use `just client` to test with OpenCode or Claude Code.
    """
    import sys

    # Allow --help without requiring global config
    if any(arg in sys.argv for arg in ("--help", "-h")):
        return

    # Require global config directory (created by ot-serve)
    from ot.paths import get_global_dir

    global_dir = get_global_dir()
    if not global_dir.exists():
        print(
            f"Error: {global_dir} not found.\n"
            "Run 'ot-serve init' to initialize OneTool configuration.",
            file=sys.stderr,
        )
        raise typer.Exit(1)


# Import subcommands to register them
from ot_bench import run  # noqa: E402, F401


def cli() -> None:
    """Run the CLI application."""
    app()


if __name__ == "__main__":
    cli()
