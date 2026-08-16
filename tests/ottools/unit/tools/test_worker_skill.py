"""Contract tests for the explicit ot-use-worker skill."""

from pathlib import Path

import pytest
import yaml

pytestmark = [pytest.mark.unit, pytest.mark.tools]


def test_ot_use_worker_skill_is_standard_explicit_and_coordinator_only() -> None:
    root = Path(__file__).resolve().parents[4]
    skill_dir = root / "skills" / "ot-use-worker"
    assert not (root / "skills" / "episodic-orchestrator").exists()
    assert sorted(
        path.relative_to(skill_dir).as_posix()
        for path in skill_dir.rglob("*")
        if path.is_file()
    ) == ["SKILL.md", "agents/openai.yaml"]

    skill_text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    _, frontmatter, body = skill_text.split("---", 2)
    metadata = yaml.safe_load(frontmatter)
    assert metadata == {
        "name": "ot-use-worker",
        "description": metadata["description"],
    }
    assert "explicitly invokes $ot-use-worker" in metadata["description"]
    assert "Act only as the coordinator" in body
    assert "set the selected Context name to `default`" in body
    assert "one-episode override" in body
    assert "same effective Context name" in body
    assert "Do not construct or pass an execution-policy object" in body
    assert "Never read, request, reproduce, or summarize a Context body" in body
    assert "Treat the result as exactly `context`, `status`, and `message`" in body
    assert "bounded internal continuation turns" in body
    assert "Use artifacts explicitly" in body
    assert "worker.asset_create" in body
    for removed_name in (
        "worker.select",
        "worker.list_contexts",
        "worker.update_context",
        "worker.archive_context",
        "worker.artifact_create",
        "worker.artifact_open",
        "worker.artifact_list",
        "worker.artifact_delete",
    ):
        assert removed_name not in body
    assert "never automatic Chat, Context, Console, Status" in body
    assert "never inspect" in body
    assert "`continue` is not a public result status" in body
    assert "`turn_limit` or" in body
    assert "`episode_timeout` classification" in body

    sidecar = yaml.safe_load(
        (skill_dir / "agents" / "openai.yaml").read_text(encoding="utf-8")
    )
    assert sidecar["policy"] == {"allow_implicit_invocation": False}
    assert "$ot-use-worker" in sidecar["interface"]["default_prompt"]

    worker_source = (root / "src" / "ottools" / "worker.py").read_text(encoding="utf-8")
    assert "ot-use-worker" not in worker_source
    assert "install_skill" not in worker_source
    assert "serve_skill" not in worker_source
