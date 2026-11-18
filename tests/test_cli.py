"""V14 and config-only stdout hygiene through the installed entry point."""

import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "args,expected",
    [
        (["--version"], 0),
        (["--help"], 0),
        ([], 2),
        (["serve"], 2),
        (["check-config"], 2),
        (["old-command"], 2),
    ],
)
def test_cli_without_config(args: list[str], expected: int, tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "onetool", *args], cwd=tmp_path, capture_output=True, text=True
    )
    assert result.returncode == expected
    if args == ["--version"]:
        assert result.stdout.strip() == "4.0.0rc1"


def test_check_config_no_server_start(tmp_path: Path) -> None:
    marker = tmp_path / "started"
    upstream = tmp_path / "upstream.py"
    upstream.write_text(f"from pathlib import Path; Path({str(marker)!r}).touch()")
    config = tmp_path / "onetool.yaml"
    config.write_text(
        f"version: 4\nservers:\n  fixture:\n    transport: stdio\n"
        f"    command: {sys.executable}\n    args: [{str(upstream)!r}]\n"
    )
    result = subprocess.run(
        [sys.executable, "-m", "onetool", "check-config", "--config", str(config)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0 and result.stdout == "" and "Config valid" in result.stderr
    assert not marker.exists()
    config.write_text("version: 3\nservers: {}\n")
    result = subprocess.run(
        [sys.executable, "-m", "onetool", "check-config", "--config", str(config)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2 and result.stdout == ""
