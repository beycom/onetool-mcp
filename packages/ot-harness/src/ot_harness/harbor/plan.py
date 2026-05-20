"""Generate Harbor trial commands and config files."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from ot_harness.config import ExperimentConfig, VariantConfig, VariantKind


@dataclass(frozen=True)
class HarborTrial:
    """Generated Harbor command/config for one task, variant, and repetition."""

    task_id: str
    variant_id: str
    repetition: int
    run_dir: Path
    config_path: Path
    command: list[str]
    config: dict[str, Any]
    metadata: dict[str, Any]


def build_trials(experiment: ExperimentConfig) -> list[HarborTrial]:
    """Build the full Harbor trial matrix for an experiment."""
    trials: list[HarborTrial] = []
    for task_id in experiment.tasks:
        for variant in experiment.variants:
            for repetition in range(1, experiment.repetitions + 1):
                run_dir = _trial_dir(experiment, task_id, variant.id, repetition)
                config_path = run_dir / "harbor-run.yaml"
                config = _trial_config(experiment, variant, task_id, run_dir)
                command = [
                    experiment.harbor.harbor_bin,
                    "run",
                    "--config",
                    str(config_path),
                    *experiment.harbor.run_args,
                ]
                metadata = _variant_metadata(variant)
                trials.append(
                    HarborTrial(
                        task_id=task_id,
                        variant_id=variant.id,
                        repetition=repetition,
                        run_dir=run_dir,
                        config_path=config_path,
                        command=command,
                        config=config,
                        metadata=metadata,
                    )
                )
    return trials


def write_trial_config(trial: HarborTrial) -> None:
    """Write one generated Harbor config and metadata file."""
    trial.run_dir.mkdir(parents=True, exist_ok=True)
    with trial.config_path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(trial.config, handle, sort_keys=False)
    metadata_path = trial.run_dir / "ot-harness-trial.json"
    metadata = {
        "task_id": trial.task_id,
        "variant_id": trial.variant_id,
        "repetition": trial.repetition,
        "command": trial.command,
        "config_path": str(trial.config_path),
        "run_dir": str(trial.run_dir),
        "variant_metadata": trial.metadata,
    }
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")


def _trial_config(
    experiment: ExperimentConfig,
    variant: VariantConfig,
    task_id: str,
    run_dir: Path,
) -> dict[str, Any]:
    agent: dict[str, Any] = {
        "name": experiment.harbor.agent,
        "model_name": experiment.harbor.model,
        "override_timeout_sec": experiment.timeout_seconds,
    }
    codex_auth_json = Path.home() / ".codex" / "auth.json"
    if experiment.harbor.agent == "codex" and codex_auth_json.is_file():
        agent["env"] = {"CODEX_AUTH_JSON_PATH": str(codex_auth_json)}
    if experiment.harbor.reasoning_effort is not None:
        agent["kwargs"] = {"reasoning_effort": experiment.harbor.reasoning_effort}
    if variant.kind == VariantKind.CODEX_ONETOOL_MCP and variant.mcp is not None:
        agent["mcp_servers"] = [
            {
                "name": variant.mcp.server_name,
                "transport": "stdio",
                "command": variant.mcp.command,
                "args": variant.mcp.args,
            }
        ]
    skill_paths = [str(path) for path in variant.skill_paths]
    if variant.kind == VariantKind.CODEX_SKILLS and variant.skills_dir is not None:
        skill_paths.append(str(variant.skills_dir))
    if skill_paths:
        agent["skills"] = skill_paths

    environment: dict[str, Any] = {"type": "docker", "delete": True}
    if variant.kind == VariantKind.CODEX_ONETOOL_MCP:
        environment["mounts"] = [
            {
                "type": "bind",
                "source": str(_repo_root()),
                "target": "/opt/onetool-mcp",
            }
        ]

    config = {
        "job_name": f"{experiment.name}-{_slug(task_id)}-{variant.id}-{run_dir.name}",
        "jobs_dir": str(run_dir),
        "n_attempts": 1,
        "n_concurrent_trials": 1,
        "quiet": False,
        "environment": environment,
        "agents": [agent],
        "datasets": [
            {
                "name": experiment.harbor.dataset,
                "task_names": [task_id],
            }
        ],
    }
    if experiment.extra_instruction_paths:
        config["extra_instruction_paths"] = [
            str(path) for path in experiment.extra_instruction_paths
        ]
    return config


def _variant_metadata(variant: VariantConfig) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "variant_id": variant.id,
        "variant_kind": variant.kind.value,
    }
    if variant.skills_dir is not None:
        metadata["skills_dir"] = str(variant.skills_dir)
        metadata["skills_hash"] = _hash_skill_text(variant.skills_dir)
        metadata["skills"] = _skill_metadata(variant.skills_dir)
    if variant.skill_paths:
        metadata["skill_paths"] = [str(path) for path in variant.skill_paths]
        metadata["skill_path_hashes"] = {
            str(path): _hash_skill_text(path) for path in variant.skill_paths
        }
        metadata["skill_path_metadata"] = [
            item for path in variant.skill_paths for item in _skill_metadata(path)
        ]
    if variant.mcp is not None:
        metadata["mcp"] = {
            "server_name": variant.mcp.server_name,
            "command": variant.mcp.command,
            "args": variant.mcp.args,
            "config_path": str(variant.mcp.config_path),
        }
    return metadata


def _hash_skill_text(skills_dir: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(skills_dir.rglob("*")):
        if path.is_file() and path.suffix.lower() in {".md", ".txt"}:
            digest.update(str(path.relative_to(skills_dir)).encode())
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
    return digest.hexdigest()


def _skill_metadata(skills_dir: Path) -> list[dict[str, str]]:
    skills: list[dict[str, str]] = []
    for path in sorted(skills_dir.rglob("SKILL.md")):
        name = path.parent.name
        skills.append({"name": name, "path": str(path)})
    return skills


def _trial_dir(
    experiment: ExperimentConfig, task_id: str, variant_id: str, repetition: int
) -> Path:
    return (
        experiment.output_root
        / experiment.name
        / _slug(task_id)
        / variant_id
        / f"rep-{repetition:03d}"
    )


def _slug(value: str) -> str:
    chars = [char.lower() if char.isalnum() else "-" for char in value]
    slug = "".join(chars).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug or "task"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[5]
