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
        command.add_argument("--secrets", type=Path)
    init = commands.add_parser("init", help="create a starter config explicitly")
    init.add_argument("--config", type=Path, required=True)
    init.add_argument("--force", action="store_true")
    secrets_command = commands.add_parser("secrets", help="manage an explicit secrets file")
    secret_actions = secrets_command.add_subparsers(dest="secret_action", required=True)
    for action in ("init", "set", "encrypt", "status", "rotate", "audit"):
        child = secret_actions.add_parser(action)
        child.add_argument("--secrets", type=Path, required=True)
        if action == "set":
            child.add_argument("name")
    args, extra = parser.parse_known_args()
    if extra:
        parser.error("unexpected arguments; secret values must be entered at the prompt")
    if args.command == "secrets":
        import getpass
        import json

        from onetool.secrets import SecretManager

        try:
            value = getpass.getpass("Secret value: ") if args.secret_action == "set" else None
            report = SecretManager(args.secrets).run(
                args.secret_action, getattr(args, "name", None), value
            )
            print(json.dumps(report), file=sys.stderr)
            return 0
        except ConfigError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        except OSError:
            print("Secrets operation failed; check the file and secure keyring", file=sys.stderr)
            return 2
    if args.command == "init":
        from onetool.initialize import InitializationError, initialize

        try:
            for message in initialize(args.config, force=args.force):
                print(message, file=sys.stderr)
            return 0
        except OSError as exc:
            detail = str(exc) if isinstance(exc, InitializationError) else type(exc).__name__
            print(f"cannot initialize config: {detail}", file=sys.stderr)
            return 2
    try:
        config = load_config(
            args.config, secrets_path=args.secrets, defer_errors=args.command == "serve"
        )
    except ConfigError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if args.command == "check-config":
        print("Config valid", file=sys.stderr)
        for source in config.sources:
            print(f"Source: {source}", file=sys.stderr)
        for name, source in config.server_sources.items():
            print(f"Server {name}: {source}", file=sys.stderr)
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
