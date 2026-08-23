"""Direct development CLI for architecture schema v3."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from rich.console import Console

from .api import advance_file, diff_file, init_file, resolve_file, validate_file
from .resolver import ResolverError, StateSelector
from .yamlio import ArchitectureLoadError, dump_architecture, load_architecture

if TYPE_CHECKING:
    from collections.abc import Sequence


def _command(subparsers: Any, name: str, help_text: str) -> argparse.ArgumentParser:
    command = cast("argparse.ArgumentParser", subparsers.add_parser(name, help=help_text))
    command.add_argument("--json", action="store_true", help="emit JSON")
    return command


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m otdev.tools._arch.v3")
    commands = parser.add_subparsers(dest="command", required=True)
    check = _command(commands, "check", "check a schema-v3 YAML file")
    check.add_argument("file", type=Path)
    check.add_argument("--write-back", action="store_true")
    init = _command(commands, "init", "create a minimal architecture")
    init.add_argument("file", type=Path)
    validation = _command(commands, "validate", "validate an architecture")
    validation.add_argument("file", type=Path)
    resolved = _command(commands, "resolve", "resolve one architecture state")
    resolved.add_argument("file", type=Path)
    resolved.add_argument("--timeline")
    resolved.add_argument("--at", default="current")
    difference = _command(commands, "diff", "diff two architecture states")
    difference.add_argument("file", type=Path)
    difference.add_argument("--timeline-a")
    difference.add_argument("--at-a", default="current")
    difference.add_argument("--timeline-b")
    difference.add_argument("--at-b", default="end")
    baseline = _command(commands, "advance", "advance the architecture baseline")
    baseline.add_argument("file", type=Path)
    baseline.add_argument("--through", required=True)
    return parser


def _human(payload: dict[str, Any]) -> str:
    if "issues" in payload:
        lines = [
            f"{item['severity'].upper()} {item['code']} {item['path']}: {item['message']}"
            for severity in ("errors", "warnings")
            for item in payload["issues"][severity]
        ]
        summary = payload["summary"]
        lines.append(f"{summary['errors']} error(s), {summary['warnings']} warning(s)")
        return "\n".join(lines)
    if "entities" in payload:
        counts = ", ".join(
            f"{kind}={len(rows)}" for kind, rows in payload["entities"].items()
        )
        return f"Resolved {payload['at']}: {counts}; clips={len(payload['clips'])}"
    if "added" in payload:
        return ", ".join(
            f"{kind}={len(payload[kind])}" for kind in ("added", "removed", "changed")
        )
    return f"OK: {payload.get('path', '')}".rstrip()


def main(argv: Sequence[str] | None = None) -> int:
    """Run the schema-v3 development CLI."""
    args = _parser().parse_args(argv)
    console = Console(highlight=False)
    try:
        if args.command == "check":
            architecture = load_architecture(args.file)
            if args.write_back:
                dump_architecture(architecture, args.file)
            payload = {"ok": True, "path": str(args.file)}
        elif args.command == "init":
            payload = init_file(args.file)
        elif args.command == "validate":
            payload = validate_file(args.file)
        elif args.command == "resolve":
            payload = resolve_file(args.file, StateSelector(args.at, args.timeline))
        elif args.command == "diff":
            payload = diff_file(
                args.file,
                StateSelector(args.at_a, args.timeline_a),
                StateSelector(args.at_b, args.timeline_b),
            )
        else:
            payload = advance_file(args.file, args.through)
    except (ArchitectureLoadError, ResolverError, OSError, ValueError) as exc:
        payload = {"ok": False, "error": str(exc)}
    if args.json:
        sys.stdout.write(json.dumps(payload, indent=2) + "\n")
    else:
        console.print(_human(payload))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
