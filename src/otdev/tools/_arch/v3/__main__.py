"""Direct development CLI for architecture schema v3."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console

from .yamlio import ArchitectureLoadError, dump_architecture, load_architecture

if TYPE_CHECKING:
    from collections.abc import Sequence


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m otdev.tools._arch.v3")
    subparsers = parser.add_subparsers(dest="command", required=True)
    check = subparsers.add_parser("check", help="check a schema-v3 YAML file")
    check.add_argument("file", type=Path)
    check.add_argument(
        "--write-back",
        action="store_true",
        help="rewrite valid input in deterministic form",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the schema-v3 development CLI."""
    args = _parser().parse_args(argv)
    console = Console(highlight=False)
    error_console = Console(highlight=False, stderr=True)
    try:
        architecture = load_architecture(args.file)
        if args.write_back:
            dump_architecture(architecture, args.file)
    except (ArchitectureLoadError, OSError) as exc:
        error_console.print(str(exc), style="red")
        return 1
    console.print(f"OK: {args.file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
