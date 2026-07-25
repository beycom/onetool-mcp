"""Command-level regression tests for repository quality recipes."""

from __future__ import annotations

import shlex
import subprocess
import tomllib
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).parents[3]
_PRODUCTION_ROOTS = ("src/", "packages/onetool-pack/src/")
_SHIPPED_IMPORTS = {"ot", "ottools", "onetool", "otdev", "otutil", "otpack"}


def _just_dry_run(recipe: str) -> str:
    result = subprocess.run(
        ["just", "--dry-run", recipe],
        cwd=_REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return f"{result.stdout}\n{result.stderr}"


@pytest.mark.unit
@pytest.mark.core
@pytest.mark.parametrize(
    ("recipe", "mode"),
    [
        ("lint", "ruff check "),
        ("lint-fix", "ruff check --fix "),
        ("fmt", "ruff format "),
        ("fmt-check", "ruff format --check "),
    ],
)
def test_quality_recipes_use_exact_production_roots(recipe: str, mode: str):
    expansion = _just_dry_run(recipe)
    tokens = shlex.split(expansion)

    assert mode in expansion
    for root in _PRODUCTION_ROOTS:
        assert tokens.count(root) == 1
    assert "tests/" not in expansion
    assert "scripts/" not in expansion


@pytest.mark.unit
@pytest.mark.core
def test_root_and_release_checks_use_canonical_lint():
    root_check = _just_dry_run("check")
    release_check = _just_dry_run("release::check")

    assert "ruff check src/ packages/onetool-pack/src/" in root_check
    assert "just lint" in release_check


@pytest.mark.unit
@pytest.mark.core
def test_canonical_lint_rejects_otpack_violation():
    probe = (
        _REPO_ROOT
        / "packages"
        / "onetool-pack"
        / "src"
        / "otpack"
        / "_lint_scope_probe.py"
    )
    probe.write_text("missing_name\n")
    try:
        result = subprocess.run(
            ["just", "lint"],
            cwd=_REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
    finally:
        probe.unlink(missing_ok=True)

    assert result.returncode != 0
    assert "_lint_scope_probe.py" in f"{result.stdout}\n{result.stderr}"
    assert "F821" in f"{result.stdout}\n{result.stderr}"


@pytest.mark.unit
@pytest.mark.core
def test_coverage_sources_match_shipped_wheel_imports():
    config = tomllib.loads((_REPO_ROOT / "pyproject.toml").read_text())
    wheel_paths = config["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"]
    wheel_imports = {Path(path).name for path in wheel_paths}
    coverage_imports = set(config["tool"]["coverage"]["run"]["source"])

    assert wheel_imports == _SHIPPED_IMPORTS
    assert coverage_imports == wheel_imports


@pytest.mark.unit
@pytest.mark.core
def test_coverage_recipe_uses_central_config_and_non_integration_tier():
    expansion = _just_dry_run("test-coverage")

    assert "uv run --all-extras pytest" in expansion
    assert '-m "not integration"' in expansion
    assert "--cov " in expansion
    assert "--cov=" not in expansion
    assert "--cov-report=html:tmp/htmlcov" in expansion
