"""Contract tests for the explicit episodic orchestrator skill."""

from pathlib import Path

import pytest
import yaml

pytestmark = [pytest.mark.unit, pytest.mark.tools]


def test_orchestrator_skill_is_standard_explicit_and_coordinator_only() -> None:
    root = Path(__file__).resolve().parents[4]
    skill_dir = root / "skills" / "episodic-orchestrator"
    assert sorted(
        path.relative_to(skill_dir).as_posix()
        for path in skill_dir.rglob("*")
        if path.is_file()
    ) == ["SKILL.md", "agents/openai.yaml"]

    skill_text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    _, frontmatter, body = skill_text.split("---", 2)
    metadata = yaml.safe_load(frontmatter)
    assert metadata == {
        "name": "episodic-orchestrator",
        "description": metadata["description"],
    }
    assert "explicitly invokes $episodic-orchestrator" in metadata["description"]
    assert "Act only as the coordinator" in body
    assert "Never read, search, write, format, validate, repair" in body

    sidecar = yaml.safe_load(
        (skill_dir / "agents" / "openai.yaml").read_text(encoding="utf-8")
    )
    assert sidecar["policy"] == {"allow_implicit_invocation": False}
    assert "$episodic-orchestrator" in sidecar["interface"]["default_prompt"]

    worker_source = (root / "src" / "ottools" / "worker.py").read_text(
        encoding="utf-8"
    )
    assert "episodic-orchestrator" not in worker_source
    assert "install_skill" not in worker_source
    assert "serve_skill" not in worker_source
