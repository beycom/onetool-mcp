"""End-to-end schema-v2 resolve and diff operation tests."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from otdev.tools import arch
from otdev.tools._arch.v2.load import load_workspace
from otdev.tools._arch.v2.normalize import normalize_change
from otdev.tools._arch.v2.replay import apply_operations
from tests.otdev.arch_v2_fixtures import ARCH_V2_FIXTURES

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.integration, pytest.mark.tools]

FIXTURES = ARCH_V2_FIXTURES


def _without_sources(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _without_sources(item)
            for key, item in value.items()
            if key not in {"source", "source_location"}
        }
    if isinstance(value, list):
        return [_without_sources(item) for item in value]
    return value


def test_resolve_2027_yaml_excel(tmp_path: Path) -> None:
    """resolve-2027-yaml-excel: production writers materialize equivalent states."""
    source = FIXTURES / "arch-v2-canonical.yaml"
    yaml_path = tmp_path / "resolved 2027.yaml"
    excel_path = tmp_path / "resolved 2027.xlsx"

    yaml_result = arch.resolve(
        input_path=str(source),
        output_path=str(yaml_path),
        roadmap="preferred",
        through="arch-v2-change-2027",
        output_state_id="resolved-2027",
    )
    excel_result = arch.resolve(
        input_path=str(source),
        output_path=str(excel_path),
        roadmap="preferred",
        through="arch-v2-change-2027",
        output_state_id="resolved-2027",
    )

    assert yaml_result["ok"] is excel_result["ok"] is True
    yaml_state = load_workspace(yaml_path).workspace.states[0]
    excel_state = load_workspace(excel_path).workspace.states[0]
    assert _without_sources(yaml_state.model_dump(mode="json")) == _without_sources(
        excel_state.model_dump(mode="json")
    )
    assert {system.id for system in yaml_state.systems} == {"A", "B", "C", "E", "F", "G", "H"}
    assert {application.id for application in yaml_state.applications} == {"app-a"}
    assert yaml_state.interfaces == []


def test_diff_base_target_materialization(tmp_path: Path) -> None:
    """diff-base-target-materialization: public diff writes a replayable stable change."""
    source = FIXTURES / "arch-v2-canonical.yaml"
    base_path = tmp_path / "base.yaml"
    target_path = tmp_path / "target.yaml"
    change_path = tmp_path / "derived change.yaml"
    assert arch.resolve(
        input_path=str(source),
        output_path=str(base_path),
        state="arch-v2-base",
        output_state_id="derived-base",
    )["ok"]
    assert arch.resolve(
        input_path=str(source),
        output_path=str(target_path),
        roadmap="preferred",
        order=1,
        output_state_id="derived-target",
    )["ok"]

    missing_id = arch.diff(
        base_path=str(base_path),
        target_path=str(target_path),
        output_path=str(change_path),
    )
    assert missing_id["ok"] is False
    assert missing_id["issues"]["errors"][0]["code"] == "arch.change_id_required"
    assert not change_path.exists()

    result = arch.diff(
        base_path=str(base_path),
        target_path=str(target_path),
        output_path=str(change_path),
        change_id="derived-2027",
    )

    assert result["ok"] is True
    assert result["summary"]["generated"] == 1
    derived_workspace = load_workspace(change_path).workspace
    assert derived_workspace.changes[0].id == "derived-2027"
    assert derived_workspace.changes[0].model_extra == {
        "base_state_id": "derived-base",
        "target_state_id": "derived-target",
    }
    base = load_workspace(base_path).workspace.states[0]
    target = load_workspace(target_path).workspace.states[0]
    normalized = normalize_change(state=base, change=derived_workspace.changes[0])
    assert normalized.issues.errors == []
    replayed, _ = apply_operations(
        state=base,
        operations=normalized.change.operations,
        output_state_id=target.id,
    )
    assert _without_sources(replayed.model_dump(mode="json")) == _without_sources(
        target.model_dump(mode="json")
    )
