from __future__ import annotations

from pathlib import Path

import pytest

from ot_harness.config import load_experiment
from ot_harness.harbor import build_trials


@pytest.mark.unit
@pytest.mark.bench
class TestHarborPlan:
    def test_generates_trial_matrix(self) -> None:
        experiment = load_experiment(
            Path("packages/ot-harness/experiments/terminal-bench-codex/experiment.yaml")
        )

        trials = build_trials(experiment)

        assert len(trials) == 3
        assert {trial.variant_id for trial in trials} == {
            "codex-base",
            "codex-onetool-mcp",
            "codex-skills-smoke",
        }
        assert all(
            trial.command[:3] == ["harbor", "run", "--config"] for trial in trials
        )

    def test_base_variant_has_no_mcp_or_non_neutral_skills(self) -> None:
        experiment = load_experiment(
            Path("packages/ot-harness/experiments/terminal-bench-codex/experiment.yaml")
        )

        trial = next(
            item for item in build_trials(experiment) if item.variant_id == "codex-base"
        )

        agent = trial.config["agents"][0]
        assert "mcp_servers" not in agent
        assert "skills" not in agent

    def test_onetool_variant_has_stdio_mcp(self) -> None:
        experiment = load_experiment(
            Path("packages/ot-harness/experiments/terminal-bench-codex/experiment.yaml")
        )

        trial = next(
            item
            for item in build_trials(experiment)
            if item.variant_id == "codex-onetool-mcp"
        )

        agent = trial.config["agents"][0]
        assert {Path(path).name for path in agent["skills"]} == {"ot-cm", "ot-ref"}
        assert agent["mcp_servers"][0]["transport"] == "stdio"
        assert agent["mcp_servers"][0]["command"] == "bash"
        assert agent["mcp_servers"][0]["args"][:1] == ["-lc"]
        assert "/opt/onetool-mcp" in agent["mcp_servers"][0]["args"][1]
        assert trial.config["environment"]["mounts"][0]["target"] == "/opt/onetool-mcp"

    def test_skills_variant_has_hash_and_metadata(self) -> None:
        experiment = load_experiment(
            Path("packages/ot-harness/experiments/terminal-bench-codex/experiment.yaml")
        )

        trial = next(
            item
            for item in build_trials(experiment)
            if item.variant_id == "codex-skills-smoke"
        )

        assert trial.config["agents"][0]["skills"][0].endswith("skills/smoke")
        assert len(trial.metadata["skills_hash"]) == 64
        assert trial.metadata["skills"][0]["name"] == "terminal-smoke"
