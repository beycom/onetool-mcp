"""Integration tests proving Docker images are built from the current checkout."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tomllib
import uuid
from dataclasses import dataclass
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.docker,
    pytest.mark.slow,
    pytest.mark.core,
]

PROJECT_ROOT = Path(__file__).parent.parent.parent
SENTINEL_VERSION = "3.0.0.dev20260725"


@dataclass(frozen=True)
class BuiltImage:
    name: str
    build_output: str
    version: str


def _replace_version(path: Path, old: str, new: str) -> None:
    content = path.read_text()
    updated = content.replace(old, new)
    assert updated != content, f"version marker missing from {path}"
    path.write_text(updated)


def _replace_workspace_lock_version(path: Path, package: str, version: str) -> None:
    content = path.read_text()
    pattern = (
        rf'(?m)(^\[\[package\]\]\nname = "{re.escape(package)}"\nversion = ")[^"]+(")'
    )
    updated, count = re.subn(pattern, rf"\g<1>{version}\g<2>", content)
    assert count == 1, f"expected one {package} workspace entry in {path}"
    path.write_text(updated)


@pytest.fixture(scope="class")
def built_image(tmp_path_factory: pytest.TempPathFactory):
    """Build a unique image from a sentinel-versioned copy of this checkout."""
    context = tmp_path_factory.mktemp("docker-context")
    for name in (
        "Dockerfile",
        ".dockerignore",
        "README.md",
        "pyproject.toml",
        "server.json",
        "uv.lock",
    ):
        shutil.copy2(PROJECT_ROOT / name, context / name)
    shutil.copytree(PROJECT_ROOT / "src", context / "src")
    package_root = context / "packages/onetool-pack"
    package_root.mkdir(parents=True)
    shutil.copy2(
        PROJECT_ROOT / "packages/onetool-pack/pyproject.toml",
        package_root / "pyproject.toml",
    )
    shutil.copytree(PROJECT_ROOT / "packages/onetool-pack/src", package_root / "src")

    _replace_version(
        context / "pyproject.toml",
        'version = "3.0.0"',
        f'version = "{SENTINEL_VERSION}"',
    )
    _replace_version(
        package_root / "pyproject.toml",
        'version = "3.0.0"',
        f'version = "{SENTINEL_VERSION}"',
    )
    _replace_version(
        context / "server.json",
        '"version": "3.0.0"',
        f'"version": "{SENTINEL_VERSION}"',
    )
    _replace_workspace_lock_version(
        context / "uv.lock", "onetool-mcp", SENTINEL_VERSION
    )
    _replace_workspace_lock_version(
        context / "uv.lock", "onetool-pack", SENTINEL_VERSION
    )

    with (context / "pyproject.toml").open("rb") as handle:
        assert tomllib.load(handle)["project"]["version"] == SENTINEL_VERSION
    with (package_root / "pyproject.toml").open("rb") as handle:
        assert tomllib.load(handle)["project"]["version"] == SENTINEL_VERSION
    assert (
        json.loads((context / "server.json").read_text())["version"] == SENTINEL_VERSION
    )
    with (context / "uv.lock").open("rb") as handle:
        workspace_versions = {
            package["name"]: package["version"]
            for package in tomllib.load(handle)["package"]
            if package["name"] in {"onetool-mcp", "onetool-pack"}
        }
    assert workspace_versions == {
        "onetool-mcp": SENTINEL_VERSION,
        "onetool-pack": SENTINEL_VERSION,
    }

    image = f"onetool-mcp-source-test-{uuid.uuid4().hex}"
    result = subprocess.run(
        ["docker", "build", "--no-cache", "--progress=plain", "-t", image, "."],
        cwd=context,
        capture_output=True,
        text=True,
    )
    output = result.stdout + result.stderr
    try:
        assert result.returncode == 0, f"docker build failed:\n{output}"
        assert SENTINEL_VERSION in output
        yield BuiltImage(image, output, SENTINEL_VERSION)
    finally:
        subprocess.run(
            ["docker", "rmi", image, "--force"], check=False, capture_output=True
        )


class TestDockerImage:
    def test_dockerfile_builds_and_installs_local_application_wheel(self) -> None:
        dockerfile = (PROJECT_ROOT / "Dockerfile").read_text()

        assert "COPY src/ ./src/" in dockerfile
        assert "COPY packages/onetool-pack/src/" in dockerfile
        assert "python -m build --wheel" in dockerfile
        assert '"${wheel}[all]"' in dockerfile
        assert 'pip install "onetool-mcp' not in dockerfile

    def test_version_is_the_temporary_checkout_sentinel(
        self, built_image: BuiltImage
    ) -> None:
        result = subprocess.run(
            ["docker", "run", "--rm", built_image.name, "--version"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == f"onetool version {built_image.version}"

    def test_build_log_names_the_sentinel_application_wheel(
        self, built_image: BuiltImage
    ) -> None:
        assert (
            f"onetool_mcp-{built_image.version}-py3-none-any.whl"
            in built_image.build_output
        )

    def test_config_valid(self, built_image: BuiltImage) -> None:
        result = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                built_image.name,
                "init",
                "validate",
                "--config",
                "/onetool/onetool.yaml",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr

    def test_config_override(self, built_image: BuiltImage, tmp_path: Path) -> None:
        config = tmp_path / "onetool.yaml"
        config.write_text("version: 2\ntools_dir: []\n")
        result = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "-v",
                f"{config}:/onetool/onetool.yaml:ro",
                built_image.name,
                "--version",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr

    def test_secrets_flag(self, built_image: BuiltImage, tmp_path: Path) -> None:
        secrets = tmp_path / "secrets.yaml"
        secrets.write_text("# dummy\n")
        result = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "-v",
                f"{secrets}:/run/secrets/secrets.yaml:ro",
                built_image.name,
                "--secrets",
                "/run/secrets/secrets.yaml",
                "--version",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
