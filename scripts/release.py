"""Local versioning and release inventory. Does not tag, commit, push or publish."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import subprocess
import sys
import tomllib
from datetime import UTC, datetime
from importlib.metadata import distributions, metadata, version
from pathlib import Path


def git(root: Path, *arguments: str) -> str | None:
    result = subprocess.run(["git", "-C", str(root), *arguments], capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else None


def set_version(root: Path, value: str) -> None:
    if not re.fullmatch(r"4\.\d+\.\d+(?:(?:a|b|rc)\d+)?", value):
        raise SystemExit("Expected a V4 version, for example 4.0.0rc1")
    path = root / "pyproject.toml"
    text = path.read_text()
    old = tomllib.loads(text)["project"]["version"]
    updated = text.replace(f'version = "{old}"', f'version = "{value}"', 1)
    if tomllib.loads(updated)["project"]["version"] != value:
        raise SystemExit("Could not set project version")
    if updated != text:
        path.write_text(updated)
    print(value)


def line_counts(root: Path) -> dict[str, int]:
    groups = {
        "runtime_python": list((root / "src/onetool").glob("*.py")),
        "shipped_helpers": list((root / "scripts").glob("*.py"))
        + list((root / "scripts").glob("*.sh"))
        + [
            root / "justfile",
            root / "pyproject.toml",
            root / ".wtp.yml",
            root / ".github/workflows/check.yml",
        ],
        "tests": list((root / "tests").rglob("*.py")),
        "user_docs": [
            root / "README.md",
            root / "CHANGELOG.md",
            *list((root / "docs").glob("*.md")),
        ],
        "developer_docs": [root / "AGENTS.md", *list((root / "dev").glob("*.md"))],
    }
    return {
        name: sum(len(path.read_text().splitlines()) for path in paths if path.is_file())
        for name, paths in groups.items()
    }


def inventory(root: Path, directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    packages = []
    for distribution in distributions():
        info = distribution.metadata
        classifiers = info.get_all("Classifier", [])
        license_text = info.get("License-Expression") or info.get("License")
        if not license_text:
            license_text = (
                "; ".join(item for item in classifiers if item.startswith("License ::"))
                or "not declared"
            )
        packages.append(
            {"name": info["Name"], "version": distribution.version, "license": license_text}
        )
    artifacts = {
        path.name: {
            "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        for path in directory.iterdir()
        if path.name.endswith((".whl", ".tar.gz", ".sh"))
    }
    payload = {
        "created": datetime.now(UTC).isoformat(),
        "version": version("onetool-mcp"),
        "source_sha": git(root, "rev-parse", "HEAD"),
        "source_tag": git(root, "describe", "--exact-match", "--tags", "HEAD"),
        "source_status": git(root, "status", "--porcelain"),
        "published": False,
        "python": sys.version,
        "platform": platform.platform(),
        "architecture": platform.machine(),
        "direct_requirements": metadata("onetool-mcp").get_all("Requires-Dist", []),
        "dependencies": sorted(packages, key=lambda item: item["name"].lower()),
        "line_counts": line_counts(root),
        "artifacts": artifacts,
    }
    (directory / "inventory.json").write_text(json.dumps(payload, indent=2) + "\n")
    entries = [
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}"
        for path in sorted(directory.iterdir())
        if path.name in {*artifacts, "inventory.json"}
    ]
    (directory / "SHA256SUMS").write_text("\n".join(entries) + "\n")
    print(
        json.dumps(
            {
                "packages": len(packages),
                "line_counts": payload["line_counts"],
                "artifacts": artifacts,
            }
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("version").add_argument("value")
    commands.add_parser("inventory").add_argument("directory", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    if args.command == "version":
        set_version(root, args.value)
    else:
        inventory(root, args.directory)


if __name__ == "__main__":
    main()
