#!/usr/bin/env python3
"""Publish a release to PyPI, GitHub, MCP Registry, and docs.

Usage:
    uv run scripts/release_publish.py VERSION          # Dry-run (default, safe)
    uv run scripts/release_publish.py VERSION --force  # Actually publish (interactive)
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent

# Global flag: dry-run is default (safe), --force to actually execute
DRY_RUN = True

RELEASE_FILES = (
    "pyproject.toml",
    "packages/onetool-pack/pyproject.toml",
    "server.json",
    "CHANGELOG.md",
    "uv.lock",
)
_VERSION_RE = re.compile(
    r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)"
    r"(?:(?:a|b|rc)(?:0|[1-9]\d*))?"
    r"(?:\.post(?:0|[1-9]\d*))?"
    r"(?:\.dev(?:0|[1-9]\d*))?"
)


class ReleasePreflightError(RuntimeError):
    """Raised when immutable release identity or Git state is unsafe."""


@dataclass(frozen=True)
class ReleasePreflight:
    """Validated release identity and prepared file set."""

    version: str
    tag: str
    notes: str
    dirty_files: tuple[str, ...]


def extract_release_notes(
    version: str, *, project_root: Path | None = None
) -> str | None:
    """Extract release notes for a specific version from CHANGELOG.md."""
    root = project_root or PROJECT_ROOT
    changelog = root / "CHANGELOG.md"
    if not changelog.exists():
        return None

    content = changelog.read_text()

    # Match section: ## [VERSION] - DATE ... until next ## [ or end
    pattern = rf"## \[{re.escape(version)}\][^\n]*\n(.*?)(?=\n## \[|\Z)"
    match = re.search(pattern, content, re.DOTALL)

    if match:
        return match.group(1).strip()
    return None


def _manifest_version(path: Path) -> str:
    with path.open("rb") as handle:
        data = tomllib.load(handle)
    project = data.get("project")
    if not isinstance(project, dict):
        raise ReleasePreflightError(f"missing [project] table in {path}")
    version = project.get("version")
    if not isinstance(version, str) or not version:
        raise ReleasePreflightError(f"missing project.version in {path}")
    return version


def _lock_versions(path: Path) -> dict[str, str]:
    with path.open("rb") as handle:
        data = tomllib.load(handle)
    packages = data.get("package")
    if not isinstance(packages, list):
        raise ReleasePreflightError("uv.lock must contain package tables")
    versions: dict[str, str] = {}
    for package in packages:
        if not isinstance(package, dict):
            raise ReleasePreflightError("uv.lock contains a malformed package table")
        name = package.get("name")
        if name not in {"onetool-mcp", "onetool-pack"}:
            continue
        version = package.get("version")
        if not isinstance(version, str) or name in versions:
            raise ReleasePreflightError(
                f"uv.lock must contain one versioned {name} workspace package"
            )
        versions[name] = version
    missing = {"onetool-mcp", "onetool-pack"} - versions.keys()
    if missing:
        raise ReleasePreflightError(
            f"uv.lock missing workspace package(s): {', '.join(sorted(missing))}"
        )
    return versions


def _git_read(project_root: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=project_root,
        check=check,
        capture_output=True,
        text=True,
    )
    return result.stdout


def _dirty_paths(status: str) -> set[str]:
    """Parse `git status --porcelain=v1 -z` paths without shell quoting."""
    records = status.split("\0")
    paths: set[str] = set()
    index = 0
    while index < len(records):
        record = records[index]
        index += 1
        if not record:
            continue
        if len(record) < 4 or record[2] != " ":
            raise ReleasePreflightError("unexpected git status porcelain record")
        code = record[:2]
        if code in {"DD", "AU", "UD", "UA", "DU", "AA", "UU"}:
            raise ReleasePreflightError(
                f"unresolved Git conflict in release worktree: {record[3:]}"
            )
        paths.add(record[3:])
        if "R" in code or "C" in code:
            if index >= len(records) or not records[index]:
                raise ReleasePreflightError("incomplete renamed git status record")
            paths.add(records[index])
            index += 1
    return paths


def preflight_release(
    version: str, *, project_root: Path | None = None
) -> ReleasePreflight:
    """Validate release identity and Git state without changing either."""
    root = (project_root or PROJECT_ROOT).resolve()
    if not _VERSION_RE.fullmatch(version):
        raise ReleasePreflightError(
            f"invalid release version '{version}'; expected an exact PEP 440 release"
        )

    versions = {
        "pyproject.toml": _manifest_version(root / "pyproject.toml"),
        "packages/onetool-pack/pyproject.toml": _manifest_version(
            root / "packages/onetool-pack/pyproject.toml"
        ),
    }
    server_data = json.loads((root / "server.json").read_text())
    if not isinstance(server_data, dict):
        raise ReleasePreflightError("server.json must contain an object")
    server_version = server_data.get("version")
    if not isinstance(server_version, str) or not server_version:
        raise ReleasePreflightError("missing version in server.json")
    versions["server.json"] = server_version
    for name, lock_version in _lock_versions(root / "uv.lock").items():
        versions[f"uv.lock:{name}"] = lock_version

    mismatches = [
        f"{source}={manifest_version}"
        for source, manifest_version in versions.items()
        if manifest_version != version
    ]
    if mismatches:
        raise ReleasePreflightError(
            f"release version mismatch: requested={version}; " + "; ".join(mismatches)
        )

    notes = extract_release_notes(version, project_root=root)
    if not notes:
        raise ReleasePreflightError(
            f"CHANGELOG.md requires a non-empty [{version}] release section"
        )

    branch = _git_read(root, "branch", "--show-current").strip()
    if branch != "main":
        raise ReleasePreflightError(
            f"release branch must be main, found {branch or 'detached HEAD'}"
        )

    tag = f"v{version}"
    tag_result = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", f"refs/tags/{tag}"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    if tag_result.returncode == 0:
        raise ReleasePreflightError(f"release tag already exists: {tag}")
    if tag_result.returncode != 1:
        raise ReleasePreflightError(
            f"unable to validate release tag {tag}: {tag_result.stderr.strip()}"
        )

    status = _git_read(
        root,
        "status",
        "--porcelain=v1",
        "-z",
        "--untracked-files=all",
    )
    dirty_files = _dirty_paths(status)
    unrelated = dirty_files - set(RELEASE_FILES)
    if unrelated:
        raise ReleasePreflightError(
            "unrelated release worktree changes: " + ", ".join(sorted(unrelated))
        )
    if not dirty_files:
        raise ReleasePreflightError(
            "no prepared release files are changed; run release::prep first"
        )

    return ReleasePreflight(
        version=version,
        tag=tag,
        notes=notes,
        dirty_files=tuple(sorted(dirty_files)),
    )


def run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess | None:
    """Run a command from an argv list (never a shell string)."""
    display = " ".join(cmd)
    if DRY_RUN:
        print(f"  $ {display}")
        return None
    print(f"  $ {display}")
    return subprocess.run(cmd, cwd=PROJECT_ROOT, check=check)


def confirm(prompt: str) -> bool:
    """Prompt user for y/N confirmation."""
    if DRY_RUN:
        return True
    response = input(f"{prompt} [y/N] ").strip().lower()
    return response == "y"


def clean_build_dirs() -> list[str]:
    """Clean build directories. Returns list of dirs that were/would be removed."""
    removed = []
    for d in ["dist", "build"]:
        path = PROJECT_ROOT / d
        if path.exists():
            removed.append(d)
            if not DRY_RUN:
                shutil.rmtree(path)
    for egg in PROJECT_ROOT.glob("*.egg-info"):
        removed.append(egg.name)
        if not DRY_RUN:
            shutil.rmtree(egg)
    return removed


def main(argv: list[str] | None = None) -> int:
    global DRY_RUN

    parser = argparse.ArgumentParser(description="Publish a release")
    parser.add_argument("version", help="Version to release (e.g., 1.0.0rc1)")
    parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Actually publish (default is dry-run)",
    )
    args = parser.parse_args(argv)

    version = args.version
    DRY_RUN = not args.force

    try:
        preflight = preflight_release(version)
    except (
        OSError,
        ValueError,
        subprocess.CalledProcessError,
        ReleasePreflightError,
    ) as exc:
        print(f"Release preflight failed: {exc}", file=sys.stderr)
        return 2

    if DRY_RUN:
        print("=" * 60)
        print("DRY RUN - showing commands that would be executed")
        print("Use --force to actually publish")
        print("=" * 60)
        print()

    print(f"Release {version}")
    print()

    if not confirm("Continue?"):
        print("Aborted.")
        return 0

    # Step 1: Build
    print("─" * 40)
    print("Step 1: Build package")
    print("─" * 40)
    removed = clean_build_dirs()
    if removed:
        print(f"  Removing: {', '.join(removed)}")
    run(["uv", "build"])
    print()

    # Step 2: Git
    if confirm(f"Commit, tag v{version}, and push to GitHub?"):
        print("─" * 40)
        print("Step 2: Git commit, tag, push")
        print("─" * 40)
        run(["git", "add", "--", *RELEASE_FILES])
        run(["git", "commit", "-m", f"Release {version}"])
        run(["git", "tag", "-a", preflight.tag, "-m", f"Release {version}"])
        run(["git", "push", "origin", "main"])
        run(["git", "push", "origin", preflight.tag])
        print()

    # Step 3: GitHub Release
    if confirm("Create GitHub release?"):
        print("─" * 40)
        print("Step 3: Create GitHub release")
        print("─" * 40)
        print("  Release notes from CHANGELOG.md:")
        print()
        for line in preflight.notes.split("\n"):
            print(f"    {line}")
        print()
        if not DRY_RUN:
            notes_file = PROJECT_ROOT / "tmp" / "release-notes.md"
            notes_file.parent.mkdir(exist_ok=True)
            notes_file.write_text(preflight.notes)
        dist_files = [
            str(p)
            for pattern in ("*.whl", "*.tar.gz")
            for p in sorted((PROJECT_ROOT / "dist").glob(pattern))
        ]
        run(
            [
                "gh",
                "release",
                "create",
                preflight.tag,
                *dist_files,
                "--title",
                preflight.tag,
                "--notes-file",
                "tmp/release-notes.md",
            ]
        )
        print()

    # Step 4: PyPI (before MCP Registry — registry validates package exists on PyPI)
    if confirm("Publish to PyPI?"):
        print("─" * 40)
        print("Step 4: Publish to PyPI")
        print("─" * 40)
        run(["uv", "publish"])
        print()

    # Step 5: MCP Registry (requires PyPI package to exist)
    if confirm("Publish to MCP Registry?"):
        print("─" * 40)
        print("Step 5: Publish to MCP Registry")
        print("─" * 40)
        run(["mcp-publisher", "login", "github"])
        run(["mcp-publisher", "publish"])
        print()

    # Step 6: Docs
    if confirm("Deploy docs to GitHub Pages?"):
        print("─" * 40)
        print("Step 6: Deploy docs")
        print("─" * 40)
        run(["uv", "run", "mkdocs", "gh-deploy", "--force"])
        print()

    print("=" * 60)
    if DRY_RUN:
        print("DRY RUN COMPLETE - no changes were made")
        print("Run with --force to actually publish")
    else:
        print(f"Release {version} complete!")
        print()
        print("Verify at:")
        print("  - https://pypi.org/project/onetool-mcp/")
        print("  - https://registry.modelcontextprotocol.io")
        print("  - https://github.com/beycom/onetool-mcp/releases")
        print("  - https://onetool.beycom.online")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
