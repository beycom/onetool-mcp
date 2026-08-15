"""Unit tests for worker warm-runtime isolation and lifecycle primitives."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from ottools._worker.app_server import build_isolation_key

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit, pytest.mark.tools]


def _key(
    project: Path,
    identity: Path,
    *,
    environment: dict[str, str] | None = None,
    execution: dict[str, object] | None = None,
) -> str:
    return build_isolation_key(
        project_root=project,
        command=("/usr/local/bin/codex", "app-server"),
        environment=environment or {"PATH": "/usr/bin", "TOKEN": "secret-a"},
        execution_envelope=execution
        or {
            "approval": "never",
            "sandbox": "external",
            "network": "enabled",
            "writable_roots": [str(project)],
        },
        identity_files=(identity,),
    )


def test_isolation_key_is_deterministic_and_contains_no_secret(
    tmp_path: Path,
) -> None:
    identity = tmp_path / "codex-config.toml"
    identity.write_text('token = "credential-secret"\n', encoding="utf-8")

    first = _key(tmp_path, identity)
    second = _key(tmp_path, identity)

    assert first == second
    assert len(first) == 64
    assert "secret" not in first
    assert str(tmp_path) not in first


@pytest.mark.parametrize(
    "change",
    ["project", "approval", "sandbox", "network", "writable", "mcp", "credential"],
)
def test_every_isolation_boundary_change_produces_a_new_key(
    tmp_path: Path,
    change: str,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    other_project = tmp_path / "other"
    other_project.mkdir()
    identity = tmp_path / "codex-config.toml"
    identity.write_text('[mcp_servers.demo]\ncommand = "demo"\n', encoding="utf-8")
    baseline = _key(project, identity)
    environment = {"PATH": "/usr/bin", "TOKEN": "secret-a"}
    execution: dict[str, object] = {
        "approval": "never",
        "sandbox": "external",
        "network": "enabled",
        "writable_roots": [str(project)],
    }
    selected_project = project

    if change == "project":
        selected_project = other_project
    elif change == "approval":
        execution["approval"] = "on-request"
    elif change == "sandbox":
        execution["sandbox"] = "read-only"
    elif change == "network":
        execution["network"] = "disabled"
    elif change == "writable":
        execution["writable_roots"] = [str(other_project)]
    elif change == "mcp":
        identity.write_text(
            '[mcp_servers.other]\ncommand = "other"\n', encoding="utf-8"
        )
    else:
        environment["TOKEN"] = "secret-b"

    assert (
        _key(
            selected_project,
            identity,
            environment=environment,
            execution=execution,
        )
        != baseline
    )
