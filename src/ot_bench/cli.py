"""Bench CLI entry point for OneTool benchmark harness."""

from __future__ import annotations

import typer

import ot
from ot._cli import create_cli, version_callback

app = create_cli(
    "ot-bench",
    "OneTool benchmark harness for benchmarking LLM + MCP configurations.",
    no_args_is_help=True,
)


@app.callback()
def main(
    version: bool | None = typer.Option(
        None,
        "--version",
        "-v",
        callback=version_callback("ot-bench", ot.__version__),
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """OneTool benchmark harness for benchmarking LLM + MCP configurations.

    Commands:
        run     - Run tasks (direct MCP calls or LLM benchmarks)

    Task types:
        type: direct  - Direct MCP tool invocation (no LLM)
        type: harness - LLM benchmark with MCP servers (default)

    External client testing:
        Use `just client` to test with OpenCode or Claude Code.
    """


# Import subcommands to register them
from ot_bench import run  # noqa: E402, F401


def cli() -> None:
    """Run the CLI application."""
    app()


if __name__ == "__main__":
    cli()
