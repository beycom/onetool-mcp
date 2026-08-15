"""Contract tests for the explicit use-worker skill."""

from pathlib import Path

import pytest
import yaml

pytestmark = [pytest.mark.unit, pytest.mark.tools]


def test_use_worker_skill_is_standard_explicit_and_coordinator_only() -> None:
    root = Path(__file__).resolve().parents[4]
    skill_dir = root / "skills" / "use-worker"
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
        "name": "use-worker",
        "description": metadata["description"],
    }
    assert "explicitly invokes $use-worker" in metadata["description"]
    assert "Act only as the coordinator" in body
    assert "set the selected Context name to `default`" in body
    assert "one-episode override" in body
    assert "same effective Context name" in body
    assert "Do not construct or pass an execution-policy object" in body
    assert "Never read, request, reproduce, or summarize a Context body" in body
    assert "Treat the result as exactly `context`, `status`, and `message`" in body

    sidecar = yaml.safe_load(
        (skill_dir / "agents" / "openai.yaml").read_text(encoding="utf-8")
    )
    assert sidecar["policy"] == {"allow_implicit_invocation": False}
    assert "$use-worker" in sidecar["interface"]["default_prompt"]

    worker_source = (root / "src" / "ottools" / "worker.py").read_text(encoding="utf-8")
    assert "use-worker" not in worker_source
    assert "install_skill" not in worker_source
    assert "serve_skill" not in worker_source
