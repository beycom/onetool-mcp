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


def test_init_backups_and_generated_examples(tmp_path: Path) -> None:
    import re
    import shlex

    from onetool.config import load_config
    from onetool.initialize import STARTER

    path = tmp_path / "nested dir" / "config with spaces.yaml"
    command = [sys.executable, "-m", "onetool", "init", "--config", str(path)]
    first = subprocess.run(command, capture_output=True, text=True)
    assert (
        first.returncode == 0
        and shlex.join(["onetool", "check-config", "--config", str(path)]) in first.stderr
    )
    load_config(path)
    path.write_text("old configuration")
    assert (
        subprocess.run(command, capture_output=True).returncode == 0
        and path.read_text() == "old configuration"
    )
    Path(str(path) + ".bak").write_text("earlier backup")
    forced = subprocess.run([*command, "--force"], capture_output=True, text=True)
    assert forced.returncode == 0 and str(path) + ".bak1" in forced.stderr
    assert Path(str(path) + ".bak1").read_text() == "old configuration"
    for number, block in enumerate(re.split(r"# --- .* example ---\n", STARTER)[1:]):
        sample = tmp_path / f"sample{number}.yaml"
        sample.write_text(
            "\n".join(line[2:] for line in block.splitlines() if line.startswith("# "))
        )
        load_config(sample)
    symlink = tmp_path / "symlink.yaml"
    symlink.symlink_to(path)
    assert (
        subprocess.run(
            [sys.executable, "-m", "onetool", "init", "--config", str(symlink), "--force"],
            capture_output=True,
        ).returncode
        == 2
    )


def test_init_failed_write_restores_original(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from onetool.initialize import initialize

    path = tmp_path / "config.yaml"
    path.write_text("original")
    original = Path.open

    def fail_open(self, mode="r", *args, **kwargs):
        if self == path and mode == "x":
            raise PermissionError("injected write failure")
        return original(self, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", fail_open)
    with pytest.raises(PermissionError):
        initialize(path, force=True)
    assert path.read_text() == "original" and not Path(str(path) + ".bak").exists()
