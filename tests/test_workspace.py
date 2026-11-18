"""Planning link location/idempotence in an isolated Git repository/worktree."""

import subprocess
from pathlib import Path


def test_planning_link_uses_common_repository_from_a_worktree(tmp_path: Path) -> None:
    main = tmp_path / "onetool-mcp"
    planning = tmp_path / "onetool-mcp-planning"
    worktree = tmp_path / "worktrees/v4"
    for path in [main, planning]:
        subprocess.run(["git", "init", "-q", str(path)], check=True)
    (main / "justfile").write_text((Path(__file__).parent.parent / "justfile").read_text())
    subprocess.run(
        [
            "git",
            "-C",
            str(main),
            "-c",
            "user.name=fixture",
            "-c",
            "user.email=fixture@localhost",
            "commit",
            "--allow-empty",
            "-qm",
            "fixture",
        ],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(main), "worktree", "add", "--detach", "-q", str(worktree)], check=True
    )
    # The recipe is not tracked in this empty fixture commit.
    (worktree / "justfile").write_text((main / "justfile").read_text())
    for _ in range(2):
        subprocess.run(["just", "planning-link"], cwd=worktree, check=True, capture_output=True)
        assert (worktree / "planning").is_symlink()
        assert (worktree / "planning").resolve() == planning
        assert (worktree / ".claude").readlink() == Path(".codex")
