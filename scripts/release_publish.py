#!/usr/bin/env python3
"""Publish a release to PyPI, GitHub, MCP Registry, and docs.

Usage:
    uv run scripts/release_publish.py VERSION          # Dry-run (default, safe)
    uv run scripts/release_publish.py VERSION --force  # Actually publish (interactive)
"""

import argparse
import importlib.util
import re
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent

# Global flag: dry-run is default (safe), --force to actually execute
DRY_RUN = True


def extract_release_notes(version: str) -> str | None:
    """Extract release notes for a specific version from CHANGELOG.md."""
    changelog = PROJECT_ROOT / "CHANGELOG.md"
    if not changelog.exists():
        return None

    content = changelog.read_text()

    # Match section: ## [VERSION] - DATE ... until next ## [ or end
    pattern = rf"## \[{re.escape(version)}\][^\n]*\n(.*?)(?=\n## \[|\Z)"
    match = re.search(pattern, content, re.DOTALL)

    if match:
        return match.group(1).strip()
    return None


def run(cmd: str, check: bool = True) -> subprocess.CompletedProcess | None:
    """Run a shell command."""
    if DRY_RUN:
        print(f"  $ {cmd}")
        return None
    print(f"  $ {cmd}")
    return subprocess.run(cmd, shell=True, cwd=PROJECT_ROOT, check=check)


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


def build_vscode_extension() -> Path:
    """Build the VS Code companion extension and copy the VSIX into dist."""
    script_path = PROJECT_ROOT / "scripts" / "build_ide_vscode.py"
    spec = importlib.util.spec_from_file_location("build_ide_vscode", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load scripts/build_ide_vscode.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.build_extension()


def main():
    global DRY_RUN

    parser = argparse.ArgumentParser(description="Publish a release")
    parser.add_argument("version", help="Version to release (e.g., 1.0.0rc1)")
    parser.add_argument(
        "--force", "-f", action="store_true", help="Actually publish (default is dry-run)"
    )
    args = parser.parse_args()

    version = args.version
    DRY_RUN = not args.force

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
        sys.exit(0)

    # Step 1: Build
    print("─" * 40)
    print("Step 1: Build package")
    print("─" * 40)
    removed = clean_build_dirs()
    if removed:
        print(f"  Removing: {', '.join(removed)}")
    run("uv build")
    print()
    print("─" * 40)
    print("Step 1b: Build VS Code extension")
    print("─" * 40)
    if DRY_RUN:
        run("uv run python scripts/build_ide_vscode.py")
        print("  Would copy generated .vsix to dist/")
    else:
        vsix_path = build_vscode_extension()
        print(f"  Built VSIX: {vsix_path.relative_to(PROJECT_ROOT)}")
    print()

    # Step 2: Git
    if confirm(f"Commit, tag v{version}, and push to GitHub?"):
        print("─" * 40)
        print("Step 2: Git commit, tag, push")
        print("─" * 40)
        run("git add -A")
        run(f'git commit -m "Release {version}"', check=False)
        run(f'git tag -a "v{version}" -m "Release {version}"')
        run("git push origin main")
        run(f'git push origin "v{version}"')
        print()

    # Step 3: GitHub Release
    if confirm("Create GitHub release?"):
        print("─" * 40)
        print("Step 3: Create GitHub release")
        print("─" * 40)
        notes = extract_release_notes(version)
        if notes:
            print("  Release notes from CHANGELOG.md:")
            print()
            for line in notes.split("\n"):
                print(f"    {line}")
            print()
            if not DRY_RUN:
                notes_file = PROJECT_ROOT / "tmp" / "release-notes.md"
                notes_file.parent.mkdir(exist_ok=True)
                notes_file.write_text(notes)
            run(
                f'gh release create "v{version}" dist/* --title "v{version}" --notes-file tmp/release-notes.md'
            )
        else:
            print(f"  Warning: Version {version} not found in CHANGELOG.md")
            run(
                f'gh release create "v{version}" dist/* --title "v{version}" --generate-notes'
            )
        print()

    # Step 4: PyPI (before MCP Registry — registry validates package exists on PyPI)
    if confirm("Publish to PyPI?"):
        print("─" * 40)
        print("Step 4: Publish to PyPI")
        print("─" * 40)
        run("uv publish")
        print()

    # Step 5: MCP Registry (requires PyPI package to exist)
    if confirm("Publish to MCP Registry?"):
        print("─" * 40)
        print("Step 5: Publish to MCP Registry")
        print("─" * 40)
        run("mcp-publisher login github")
        run("mcp-publisher publish")
        print()

    # Step 6: Docs
    if confirm("Deploy docs to GitHub Pages?"):
        print("─" * 40)
        print("Step 6: Deploy docs")
        print("─" * 40)
        run("uv run mkdocs gh-deploy --force")
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
        print("  - https://github.com/beycom/onetool/releases")
        print("  - https://onetool.beycom.online")
    print("=" * 60)


if __name__ == "__main__":
    main()
