"""Explicit starter config creation; no discovery, transport or keyring access."""

from __future__ import annotations

import shlex
from pathlib import Path

STARTER = """# OneTool V4. Add only the servers you choose to run.
version: 4
servers: {}

# --- stdio example ---
# version: 4
# servers:
#   local:
#     transport: stdio
#     command: /absolute/path/to/server
#     args: []

# --- HTTP example ---
# version: 4
# servers:
#   remote:
#     transport: http
#     url: http://127.0.0.1:8765/mcp

# --- V3 bridge example ---
# version: 4
# servers:
#   v3:
#     transport: stdio
#     command: uvx
#     args:
#       - --from
#       - "onetool-mcp==<pinned-v3-version>"
#       - onetool
#       - --config
#       - /absolute/path/to/v3.yaml
"""


class InitializationError(OSError):
    """A safe message naming the preserved backup when restoration fails."""


def initialize(path: Path, *, force: bool = False) -> list[str]:
    """Create exclusively; force preserves a regular destination in the first free backup."""
    messages = []
    backup: Path | None = None
    if path.exists() or path.is_symlink():
        if not force:
            return [f"Config exists: {path}. Use --force to back it up and replace it."]
        if path.is_symlink() or not path.is_file():
            raise OSError("force requires a regular file, not a symlink or directory")
        backup = Path(str(path) + ".bak")
        number = 0
        while backup.exists() or backup.is_symlink():
            number += 1
            backup = Path(str(path) + f".bak{number}")
        path.rename(backup)
        messages.append(f"Backed up {path} to {backup}")
    created = False
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8") as stream:
            created = True
            path.chmod(0o600)
            stream.write(STARTER)
    except OSError:
        try:
            if created:
                path.unlink(missing_ok=True)
            if backup is not None:
                if path.exists() or path.is_symlink():
                    raise OSError("destination appeared during initialization")
                backup.rename(path)
        except OSError:
            if backup is not None:
                raise InitializationError(
                    f"Config write failed; original preserved at {backup}"
                ) from None
            raise
        raise
    messages.extend(
        [f"Created {path}", shlex.join(["onetool", "check-config", "--config", str(path)])]
    )
    return messages
