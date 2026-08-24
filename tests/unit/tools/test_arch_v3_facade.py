"""Schema-v3 architecture facade smoke test."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from otdev.tools import arch
from otdev.tools._arch.v3.model import Milestone, System
from otdev.tools._arch.v3.yamlio import dump_architecture, load_architecture

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit, pytest.mark.tools]


def test_facade_workflow(tmp_path: Path) -> None:
    path = tmp_path / "architecture.yaml"

    assert arch.init(output_path=str(path))["ok"]
    assert arch.validate(input_path=str(path))["valid"]

    architecture = load_architecture(path)
    architecture.milestones = [Milestone(id="m", name="Milestone")]
    architecture.systems = [System(id="system", name="System", start_in="m")]
    dump_architecture(architecture, path)

    resolved = arch.resolve(input_path=str(path), at="base")
    difference = arch.diff(input_path=str(path), at_a="base", at_b="end")
    advanced = arch.advance(input_path=str(path), through="m")

    assert resolved["entities"]["systems"] == []
    assert [item["id"] for item in difference["added"]] == ["system"]
    assert advanced["ok"]
    assert load_architecture(path).systems[0].start_in is None
