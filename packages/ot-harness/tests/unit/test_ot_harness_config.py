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
        assert config.tasks == ["fix-git"]
        assert [variant.id for variant in config.variants] == [
            "codex-base",
            "codex-onetool-mcp",
            "codex-skills-smoke",
            "codex-skills-smoke-onetool-mcp",
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
        assert config.variants[1].mcp.config_path.name == "onetool-http.toml"
        assert config.variants[1].mcp.url == "http://host.docker.internal:8768/mcp"
        assert config.variants[3].mcp is not None
        assert config.variants[3].skills_dir is not None

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

    def test_rejects_stdio_mcp_config(self, tmp_path: Path) -> None:
        experiment = _write_valid_tree(tmp_path)
        mcp_variant = tmp_path / "variants" / "mcp.yaml"
        (tmp_path / "mcp.toml").write_text(
            "[mcp_servers.onetool]\ntransport = \"stdio\"\n",
            encoding="utf-8",
        )
        mcp_variant.write_text(
            "\n".join(
                [
                    "id: codex-onetool-mcp",
                    "kind: codex-onetool-mcp",
                    "mcp:",
                    "  config_path: ../mcp.toml",
                    "  server_name: onetool",
                    "  command: uv",
                    "  args: [run, onetool]",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        experiment.write_text(
            experiment.read_text(encoding="utf-8").replace(
                "  - id: codex-base\n    path: variants/base.yaml",
                "  - id: codex-onetool-mcp\n    path: variants/mcp.yaml",
            ),
            encoding="utf-8",
        )

        with pytest.raises(ConfigError, match="extra_forbidden"):
            load_experiment(experiment)

    def test_rejects_non_http_mcp_url(self, tmp_path: Path) -> None:
        experiment = _write_valid_tree(tmp_path)
        mcp_variant = tmp_path / "variants" / "mcp.yaml"
        (tmp_path / "mcp.toml").write_text(
            "[mcp_servers.onetool]\ntransport = \"http\"\n",
            encoding="utf-8",
        )
        mcp_variant.write_text(
            "\n".join(
                [
                    "id: codex-onetool-mcp",
                    "kind: codex-onetool-mcp",
                    "mcp:",
                    "  config_path: ../mcp.toml",
                    "  server_name: onetool",
                    "  url: host.docker.internal:8768/mcp",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        experiment.write_text(
            experiment.read_text(encoding="utf-8").replace(
                "  - id: codex-base\n    path: variants/base.yaml",
                "  - id: codex-onetool-mcp\n    path: variants/mcp.yaml",
            ),
            encoding="utf-8",
        )

        with pytest.raises(ConfigError, match=r"mcp\.url must start"):
            load_experiment(experiment)

    def test_workspace_mount_defaults_to_disabled_output_workspace(self) -> None:
        config = load_experiment(
            Path("packages/ot-harness/experiments/terminal-bench-codex/experiment.yaml")
        )

        assert config.workspace_mount.enabled is False
        assert config.workspace_mount.target == "/app"
        assert config.workspace_mount.root == (
            config.output_root / "workspaces" / config.name
        )

    def test_rejects_relative_workspace_mount_target(self, tmp_path: Path) -> None:
        experiment = _write_valid_tree(tmp_path)
        experiment.write_text(
            experiment.read_text(encoding="utf-8")
            + "workspace_mount:\n  enabled: true\n  target: app\n",
            encoding="utf-8",
        )

        with pytest.raises(
            ConfigError, match=r"workspace_mount\.target must be an absolute path"
        ):
            load_experiment(experiment)


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
