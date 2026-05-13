#!/usr/bin/env python3
"""Build the OneTool IDE Bridge VS Code extension."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).parent.parent
EXTENSION_DIR = PROJECT_ROOT / "packages" / "onetool-ide-vscode"
PACKAGE_JSON = EXTENSION_DIR / "package.json"
PACKAGE_LOCK = EXTENSION_DIR / "package-lock.json"
DIST_DIR = PROJECT_ROOT / "dist"
SOURCE_ICON = PROJECT_ROOT / "docs" / "assets" / "logo.png"
EXTENSION_ICON = EXTENSION_DIR / "assets" / "logo.png"
BASE_EXTENSION_VERSION = "1.0.0"


def load_json(path: Path) -> dict[str, Any]:
    """Load a JSON object from disk."""
    return json.loads(path.read_text())


def write_json(path: Path, data: dict[str, Any]) -> None:
    """Write stable JSON formatting used by npm package metadata."""
    path.write_text(json.dumps(data, indent=2) + "\n")


def generate_build_version(*, now: datetime | None = None, current_version: str | None = None) -> str:
    """Return a monotonically increasing local extension build version."""
    timestamp = int((now or datetime.now(UTC)).strftime("%Y%m%d%H%M%S"))
    current_prefix = f"{BASE_EXTENSION_VERSION}-dev."
    if current_version and current_version.startswith(current_prefix):
        current_build = current_version.removeprefix(current_prefix)
        if current_build.isdigit() and int(current_build) >= timestamp:
            timestamp = int(current_build) + 1
    return f"{BASE_EXTENSION_VERSION}-dev.{timestamp}"


def set_extension_version(version: str) -> None:
    """Set the extension version in package.json and package-lock.json."""
    package = load_json(PACKAGE_JSON)
    package["version"] = version
    write_json(PACKAGE_JSON, package)

    lock = load_json(PACKAGE_LOCK)
    lock["version"] = version
    root_package = lock.get("packages", {}).get("")
    if isinstance(root_package, dict):
        root_package["version"] = version
    write_json(PACKAGE_LOCK, lock)


def current_extension_version() -> str:
    """Return the extension version currently recorded in package.json."""
    version = load_json(PACKAGE_JSON).get("version")
    if not isinstance(version, str):
        raise RuntimeError("packages/onetool-ide-vscode/package.json must contain a string version")
    return version


def build_extension(*, version: str | None = None) -> Path:
    """Build the VSIX and copy it into dist."""
    build_version = version or generate_build_version(current_version=current_extension_version())
    set_extension_version(build_version)
    EXTENSION_ICON.parent.mkdir(exist_ok=True)
    shutil.copy2(SOURCE_ICON, EXTENSION_ICON)

    for path in [*DIST_DIR.glob("onetool-ide-vscode-*.vsix"), *EXTENSION_DIR.glob("onetool-ide-vscode-*.vsix")]:
        path.unlink()

    subprocess.run(["npm", "install"], cwd=EXTENSION_DIR, check=True)
    subprocess.run(["npm", "run", "package"], cwd=EXTENSION_DIR, check=True)

    vsix_files = sorted(EXTENSION_DIR.glob("onetool-ide-vscode-*.vsix"))
    if not vsix_files:
        raise RuntimeError("VS Code extension packaging did not produce a .vsix")

    DIST_DIR.mkdir(exist_ok=True)
    target = DIST_DIR / vsix_files[-1].name
    shutil.move(str(vsix_files[-1]), target)
    return target


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--version",
        help="Explicit extension version to package. Defaults to a generated local dev build version.",
    )
    args = parser.parse_args()

    target = build_extension(version=args.version)
    print(target.relative_to(PROJECT_ROOT))


if __name__ == "__main__":
    main()
