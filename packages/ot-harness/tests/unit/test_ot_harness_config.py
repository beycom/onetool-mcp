from __future__ import annotations

from pathlib import Path

import pytest

from ot_harness.config import ConfigError, VariantKind, load_experiment


@pytest.mark.unit
@pytest.mark.bench
class TestExperimentConfig:
    def test_loads_valid_example_config(self) -> None:
        config = load_experiment(
            Path("packages/ot-harness/experiments/terminal-bench-codex/experiment.yaml")
        )

        assert config.name == "terminal-bench-codex-smoke"
        assert config.harbor.dataset == "terminal-bench"
        assert config.tasks == ["terminal-bench-smoke-task"]
        assert [variant.id for variant in config.variants] == [
            "codex-base",
            "codex-onetool-mcp",
            "codex-skills-smoke",
        ]
        assert config.variants[2].kind == VariantKind.CODEX_SKILLS
        assert config.output_root.name == "harbor"

    def test_resolves_paths_relative_to_experiment_and_variant_files(self) -> None:
        config = load_experiment(
            Path("packages/ot-harness/experiments/terminal-bench-codex/experiment.yaml")
        )

        assert config.task_file.is_absolute()
        assert config.variants[0].neutral_skills_dir is not None
        assert config.variants[0].neutral_skills_dir.name == "neutral"
        assert config.variants[1].mcp is not None
        assert config.variants[1].mcp.config_path.name == "onetool-local.toml"

    def test_rejects_unknown_experiment_fields(self, tmp_path: Path) -> None:
        experiment = _write_valid_tree(tmp_path)
        experiment.write_text(
            experiment.read_text(encoding="utf-8") + "unexpected: true\n",
            encoding="utf-8",
        )

        with pytest.raises(ConfigError, match="extra_forbidden"):
            load_experiment(experiment)

    def test_rejects_legacy_fields(self, tmp_path: Path) -> None:
        experiment = _write_valid_tree(tmp_path)
        experiment.write_text(
            experiment.read_text(encoding="utf-8") + "scenarios: []\n",
            encoding="utf-8",
        )

        with pytest.raises(ConfigError, match="legacy bench config fields"):
            load_experiment(experiment)

    def test_rejects_missing_task_file(self, tmp_path: Path) -> None:
        experiment = _write_valid_tree(tmp_path)
        experiment.write_text(
            experiment.read_text(encoding="utf-8").replace(
                "tasks.yaml", "missing.yaml"
            ),
            encoding="utf-8",
        )

        with pytest.raises(ConfigError, match="task_file does not exist"):
            load_experiment(experiment)

    def test_rejects_missing_variant_file(self, tmp_path: Path) -> None:
        experiment = _write_valid_tree(tmp_path)
        experiment.write_text(
            experiment.read_text(encoding="utf-8").replace("base.yaml", "missing.yaml"),
            encoding="utf-8",
        )

        with pytest.raises(ConfigError, match="variant path does not exist"):
            load_experiment(experiment)

    def test_rejects_package_internal_output_root(self) -> None:
        experiment = Path(
            "packages/ot-harness/experiments/terminal-bench-codex/experiment.yaml"
        )
        original = experiment.read_text(encoding="utf-8")
        try:
            experiment.write_text(
                original + "output_root: ../../reports/generated\n",
                encoding="utf-8",
            )
            with pytest.raises(
                ConfigError, match="output_root must not resolve inside"
            ):
                load_experiment(experiment)
        finally:
            experiment.write_text(original, encoding="utf-8")


def _write_valid_tree(tmp_path: Path) -> Path:
    (tmp_path / "variants").mkdir()
    (tmp_path / "skills").mkdir()
    (tmp_path / "skills" / "neutral").mkdir()
    (tmp_path / "tasks.yaml").write_text("tasks:\n  - task-one\n", encoding="utf-8")
    (tmp_path / "variants" / "base.yaml").write_text(
        "id: codex-base\nkind: codex-base\nneutral_skills_dir: ../skills/neutral\n",
        encoding="utf-8",
    )
    experiment = tmp_path / "experiment.yaml"
    experiment.write_text(
        "\n".join(
            [
                "name: local",
                "harbor:",
                "  dataset: terminal-bench",
                "  model: gpt-5.2",
                "task_file: tasks.yaml",
                "variants:",
                "  - id: codex-base",
                "    path: variants/base.yaml",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return experiment
