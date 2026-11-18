"""Explicit, local-first command line interface."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from onetool import __version__
from onetool.config import ConfigError, load_config


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="onetool", description="MCP gateway with Python orchestration"
    )
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name, help_text in [
        ("serve", "serve MCP over stdio"),
        ("check-config", "validate config locally"),
    ]:
        command = commands.add_parser(name, help=help_text)
        command.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    try:
        config = load_config(args.config)
    except ConfigError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if args.command == "check-config":
        print("Config valid", file=sys.stderr)
        return 0
    try:
        # These imports can create runtime objects; validation never imports them.
        from onetool.gateway import serve

        serve(config)
    except KeyboardInterrupt:
        return 0
    except Exception as exc:
        print(f"gateway failed: {type(exc).__name__}", file=sys.stderr)
        return 1
    return 0
