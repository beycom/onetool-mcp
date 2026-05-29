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

        assert len(trials) == 4
        assert {trial.variant_id for trial in trials} == {
            "codex-base",
            "codex-onetool-mcp",
            "codex-skills-smoke",
            "codex-skills-smoke-onetool-mcp",
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

    def test_onetool_variant_has_http_mcp(self) -> None:
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
        assert agent["mcp_servers"][0] == {
            "name": "onetool",
            "transport": "http",
            "url": "http://host.docker.internal:8768/mcp",
        }
        assert "mounts" not in trial.config["environment"]

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

    def test_skills_variant_can_include_onetool_http_mcp(self) -> None:
        experiment = load_experiment(
            Path("packages/ot-harness/experiments/terminal-bench-codex/experiment.yaml")
        )

        trial = next(
            item
            for item in build_trials(experiment)
            if item.variant_id == "codex-skills-smoke-onetool-mcp"
        )

        agent = trial.config["agents"][0]
        assert agent["skills"][0].endswith("skills/smoke")
        assert agent["mcp_servers"][0]["transport"] == "http"
        assert agent["mcp_servers"][0]["url"] == "http://host.docker.internal:8768/mcp"
        assert trial.metadata["mcp"]["transport"] == "http"
        assert trial.metadata["mcp"]["url"] == "http://host.docker.internal:8768/mcp"

    def test_workspace_mount_adds_harbor_mount_and_metadata(self) -> None:
        experiment = load_experiment(
            Path(
                "packages/ot-harness/experiments/terminal-bench-owned-mcp/experiment.yaml"
            )
        )

        trial = next(
            item
            for item in build_trials(experiment)
            if item.variant_id == "codex-skills-pypi-owned-onetool-mcp"
        )

        mount = trial.config["environment"]["mounts"][0]
        assert mount["type"] == "bind"
        assert mount["target"] == "/app"
        assert mount["source"].endswith(
            "workspaces/terminal-bench-owned-mcp-pypi/pypi-server/"
            "codex-skills-pypi-owned-onetool-mcp/rep-001"
        )
        assert trial.workspace_dir is not None
        assert trial.workspace_target == "/app"
        assert trial.metadata["workspace_mount"] == {
            "source": str(trial.workspace_dir),
            "target": "/app",
        }
