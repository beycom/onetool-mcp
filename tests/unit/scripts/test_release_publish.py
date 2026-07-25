"""Tests for the release publisher's immutable preflight and command boundary."""

from __future__ import annotations

import subprocess
import sys
from importlib import import_module
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

SCRIPTS_DIR = Path(__file__).parent.parent.parent.parent / "scripts"
VERSION = "3.0.0"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _write_release_files(
    repo: Path, version: str, notes: str = "### Fixed\n\n- Safe."
) -> None:
    (repo / "packages/onetool-pack").mkdir(parents=True, exist_ok=True)
    (repo / "pyproject.toml").write_text(
        f'[project]\nname = "onetool-mcp"\nversion = "{version}"\n'
    )
    (repo / "packages/onetool-pack/pyproject.toml").write_text(
        f'[project]\nname = "onetool-pack"\nversion = "{version}"\n'
    )
    (repo / "server.json").write_text(f'{{"version": "{version}"}}\n')
    (repo / "uv.lock").write_text(
        f'[[package]]\nname = "onetool-mcp"\nversion = "{version}"\n\n'
        f'[[package]]\nname = "onetool-pack"\nversion = "{version}"\n'
    )
    (repo / "CHANGELOG.md").write_text(
        f"# Changelog\n\n## [{version}] - 2026-07-25\n\n{notes}\n"
    )


@pytest.fixture
def release_publish(monkeypatch: pytest.MonkeyPatch):
    """Import the script and reset its process-wide state."""
    project_root = str(SCRIPTS_DIR.parent)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    module = import_module("scripts.release_publish")
    module.DRY_RUN = True
    monkeypatch.setattr(module, "PROJECT_ROOT", SCRIPTS_DIR.parent)
    return module


@pytest.fixture
def release_repo(
    tmp_path: Path, release_publish, monkeypatch: pytest.MonkeyPatch
) -> Path:
    """Create a real main-branch repository with a prepared release."""
    repo = tmp_path / "release-repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.name", "Release Test")
    _git(repo, "config", "user.email", "release-test@onetool.invalid")
    _write_release_files(repo, "2.9.0")
    (repo / "tracked.txt").write_text("baseline\n")
    _git(repo, "add", "--", ".")
    _git(repo, "commit", "-m", "test: establish release fixture")
    _write_release_files(repo, VERSION)
    monkeypatch.setattr(release_publish, "PROJECT_ROOT", repo)
    return repo


def _set_failure(repo: Path, kind: str) -> str:
    requested = VERSION
    if kind == "malformed requested version":
        return "v3"
    if kind == "malformed root manifest":
        (repo / "pyproject.toml").write_text("[project\n")
    elif kind == "missing root version":
        (repo / "pyproject.toml").write_text('[project]\nname = "onetool-mcp"\n')
    elif kind == "root manifest mismatch":
        path = repo / "pyproject.toml"
        path.write_text(path.read_text().replace(VERSION, "3.0.1"))
    elif kind == "malformed package manifest":
        (repo / "packages/onetool-pack/pyproject.toml").write_text("[project\n")
    elif kind == "missing package version":
        (repo / "packages/onetool-pack/pyproject.toml").write_text(
            '[project]\nname = "onetool-pack"\n'
        )
    elif kind == "package manifest mismatch":
        path = repo / "packages/onetool-pack/pyproject.toml"
        path.write_text(path.read_text().replace(VERSION, "3.0.1"))
    elif kind == "malformed server manifest":
        (repo / "server.json").write_text("{")
    elif kind == "missing server version":
        (repo / "server.json").write_text("{}\n")
    elif kind == "server manifest mismatch":
        (repo / "server.json").write_text('{"version": "3.0.1"}\n')
    elif kind == "malformed lockfile":
        (repo / "uv.lock").write_text("[[package]\n")
    elif kind == "application lock mismatch":
        path = repo / "uv.lock"
        path.write_text(
            path.read_text().replace(f'version = "{VERSION}"', 'version = "3.0.1"', 1)
        )
    elif kind == "package lock mismatch":
        path = repo / "uv.lock"
        content = path.read_text()
        marker = f'name = "onetool-pack"\nversion = "{VERSION}"'
        path.write_text(
            content.replace(marker, 'name = "onetool-pack"\nversion = "3.0.1"')
        )
    elif kind == "missing lock entry":
        path = repo / "uv.lock"
        path.write_text(path.read_text().split("\n\n", 1)[0] + "\n")
    elif kind == "duplicate lock entry":
        path = repo / "uv.lock"
        path.write_text(path.read_text() + path.read_text().split("\n\n", 1)[0] + "\n")
    elif kind == "missing release notes":
        (repo / "CHANGELOG.md").write_text("# Changelog\n")
    elif kind == "empty release notes":
        (repo / "CHANGELOG.md").write_text(
            f"# Changelog\n\n## [{VERSION}] - 2026-07-25\n\n   \n"
        )
    elif kind == "unrelated tracked change":
        (repo / "tracked.txt").write_text("changed\n")
    elif kind == "unrelated untracked change":
        (repo / "untracked.txt").write_text("not releasable\n")
    elif kind == "wrong branch":
        _git(repo, "switch", "-c", "release-test")
    elif kind == "existing tag":
        _git(repo, "tag", f"v{VERSION}")
    else:
        raise AssertionError(f"unknown failure kind: {kind}")
    return requested


@pytest.mark.unit
@pytest.mark.core
class TestReleasePreflight:
    @pytest.mark.parametrize(
        "failure",
        [
            "malformed requested version",
            "malformed root manifest",
            "missing root version",
            "root manifest mismatch",
            "malformed package manifest",
            "missing package version",
            "package manifest mismatch",
            "malformed server manifest",
            "missing server version",
            "server manifest mismatch",
            "malformed lockfile",
            "application lock mismatch",
            "package lock mismatch",
            "missing lock entry",
            "duplicate lock entry",
            "missing release notes",
            "empty release notes",
            "unrelated tracked change",
            "unrelated untracked change",
            "wrong branch",
            "existing tag",
        ],
    )
    @pytest.mark.parametrize("force", [False, True])
    def test_failure_is_read_only_before_any_release_action(
        self,
        release_publish,
        release_repo: Path,
        failure: str,
        force: bool,
    ) -> None:
        requested = _set_failure(release_repo, failure)
        status_before = _git(release_repo, "status", "--porcelain=v1", "-z")
        refs_before = _git(release_repo, "show-ref")

        with (
            patch.object(release_publish, "clean_build_dirs") as clean,
            patch.object(release_publish, "run") as run,
            patch.object(release_publish, "confirm") as confirm,
        ):
            argv = [requested, *(["--force"] if force else [])]
            assert release_publish.main(argv) == 2

        clean.assert_not_called()
        run.assert_not_called()
        confirm.assert_not_called()
        assert _git(release_repo, "status", "--porcelain=v1", "-z") == status_before
        assert _git(release_repo, "show-ref") == refs_before

    def test_success_returns_exact_validated_identity(
        self, release_publish, release_repo: Path
    ) -> None:
        assert release_repo == release_publish.PROJECT_ROOT
        result = release_publish.preflight_release(VERSION)

        assert result.version == VERSION
        assert result.tag == f"v{VERSION}"
        assert result.notes == "### Fixed\n\n- Safe."
        assert result.dirty_files == tuple(sorted(release_publish.RELEASE_FILES))

    def test_dry_run_executes_no_write_and_preserves_repository(
        self,
        release_publish,
        release_repo: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        status_before = _git(release_repo, "status", "--porcelain=v1", "-z")
        refs_before = _git(release_repo, "show-ref")

        assert release_publish.main([VERSION]) == 0

        assert _git(release_repo, "status", "--porcelain=v1", "-z") == status_before
        assert _git(release_repo, "show-ref") == refs_before
        output = capsys.readouterr().out
        stage = "git add -- " + " ".join(release_publish.RELEASE_FILES)
        assert stage in output
        assert output.index("git commit") < output.index("git tag")

    def test_force_uses_exact_stage_set_and_commits_before_tagging(
        self, release_publish, release_repo: Path
    ) -> None:
        assert release_repo == release_publish.PROJECT_ROOT
        commands: list[tuple[list[str], bool]] = []

        def record(cmd: list[str], check: bool = True):
            commands.append((cmd, check))
            return None

        with (
            patch.object(release_publish, "run", side_effect=record),
            patch.object(release_publish, "confirm", return_value=True),
        ):
            assert release_publish.main([VERSION, "--force"]) == 0

        argv = [cmd for cmd, _check in commands]
        expected_stage = ["git", "add", "--", *release_publish.RELEASE_FILES]
        assert expected_stage in argv
        commit_index = argv.index(["git", "commit", "-m", f"Release {VERSION}"])
        tag_index = argv.index(
            ["git", "tag", "-a", f"v{VERSION}", "-m", f"Release {VERSION}"]
        )
        assert commit_index < tag_index
        assert commands[commit_index][1] is True

    def test_commit_failure_stops_tag_and_publish(
        self, release_publish, release_repo: Path
    ) -> None:
        assert release_repo == release_publish.PROJECT_ROOT
        commands: list[list[str]] = []

        def fail_commit(cmd: list[str], _check: bool = True):
            commands.append(cmd)
            if cmd[:2] == ["git", "commit"]:
                raise subprocess.CalledProcessError(1, cmd)
            return None

        with (
            patch.object(release_publish, "run", side_effect=fail_commit),
            patch.object(release_publish, "confirm", return_value=True),
            pytest.raises(subprocess.CalledProcessError),
        ):
            release_publish.main([VERSION, "--force"])

        assert any(cmd[:2] == ["git", "commit"] for cmd in commands)
        assert not any(cmd[:2] == ["git", "tag"] for cmd in commands)
        assert not any(cmd[0] in {"gh", "mcp-publisher"} for cmd in commands)
        assert ["uv", "publish"] not in commands


@pytest.mark.unit
@pytest.mark.core
class TestRunHelperArgvOnly:
    def test_run_passes_argv_without_shell(self, release_publish) -> None:
        release_publish.DRY_RUN = False
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            release_publish.run(["uv", "build"])

        assert mock_run.call_args.args[0] == ["uv", "build"]
        assert "shell" not in mock_run.call_args.kwargs

    def test_dry_run_never_calls_subprocess(self, release_publish) -> None:
        with patch("subprocess.run") as mock_run:
            assert release_publish.run(["uv", "publish"]) is None

        mock_run.assert_not_called()
